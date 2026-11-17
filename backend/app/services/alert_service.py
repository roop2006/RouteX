"""Validated traffic alert rules, persistence, deduplication, and lifecycle helpers."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.geo_config import POSTGIS_SRID
from backend.app.models.alert_rule import AlertRule
from backend.app.models.traffic_alert import AlertNotification, TrafficAlert
from backend.app.schemas.alerts import AlertEventInput
from vision.streaming.redis_client import TrafficRedis

logger = logging.getLogger("routex.alerts")

DEFAULT_ALERT_RULES = (
    {
        "rule_key": "congestion_high",
        "name": "High traffic congestion",
        "category": "CONGESTION",
        "severity": "HIGH",
        "cooldown_seconds": 900,
        "thresholds": {"congestion_levels": ["HIGH"]},
    },
    {
        "rule_key": "congestion_critical",
        "name": "Critical traffic congestion",
        "category": "CONGESTION",
        "severity": "CRITICAL",
        "cooldown_seconds": 900,
        "thresholds": {"minimum_density": 0.85, "maximum_speed_ratio": 0.25},
    },
    {
        "rule_key": "significant_speed_reduction",
        "name": "Significant speed reduction",
        "category": "SPEED_REDUCTION",
        "severity": "HIGH",
        "cooldown_seconds": 900,
        "thresholds": {"maximum_speed_ratio": 0.5, "minimum_speed_drop": 0.4},
    },
    {
        "rule_key": "traffic_delay",
        "name": "Significant traffic delay",
        "category": "TRAFFIC_DELAY",
        "severity": "MEDIUM",
        "cooldown_seconds": 900,
        "thresholds": {"minimum_delay_seconds": 300},
    },
    {
        "rule_key": "road_closure",
        "name": "Road closure",
        "category": "ROAD_CLOSURE",
        "severity": "CRITICAL",
        "cooldown_seconds": 1800,
        "thresholds": {"icon_categories": [8]},
    },
    {
        "rule_key": "roadworks",
        "name": "Roadworks reported",
        "category": "ROADWORKS",
        "severity": "MEDIUM",
        "cooldown_seconds": 1800,
        "thresholds": {"icon_categories": [9]},
    },
    {
        "rule_key": "stationary_traffic",
        "name": "Stationary traffic",
        "category": "STATIONARY_TRAFFIC",
        "severity": "HIGH",
        "cooldown_seconds": 900,
        "thresholds": {"icon_categories": [6]},
    },
    {
        "rule_key": "traffic_incident",
        "name": "Traffic incident",
        "category": "INCIDENT",
        "severity": "HIGH",
        "cooldown_seconds": 900,
        "thresholds": {"icon_categories": [1, 2, 3, 4, 5, 7, 10, 11, 14]},
    },
    {
        "rule_key": "ai_congestion_forecast",
        "name": "AI predicts high congestion",
        "category": "AI_FORECAST",
        "severity": "MEDIUM",
        "cooldown_seconds": 1800,
        "thresholds": {"predicted_levels": ["HIGH", "CRITICAL"]},
    },
    {
        "rule_key": "traffic_anomaly",
        "name": "Traffic anomaly detected",
        "category": "ANOMALY",
        "severity": "MEDIUM",
        "cooldown_seconds": 900,
        "thresholds": {},
    },
)


def initialize_alert_rules(db: Session) -> None:
    """Insert default rules without overwriting operator configuration."""
    for rule in DEFAULT_ALERT_RULES:
        if db.get(AlertRule, rule["rule_key"]) is None:
            db.add(AlertRule(**rule))
    db.commit()


def _metadata_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    events = data.get("events") or []
    if isinstance(events, dict):
        events = [events]
    return [item for item in events if isinstance(item, dict)]


def _icon_category(event: dict[str, Any]) -> int | None:
    value = event.get("icon_category", event.get("iconCategory"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _event_context(data: dict[str, Any]) -> dict[str, Any]:
    records = _metadata_records(data)
    nested = records[0] if records else {}
    context = {**nested, **data}
    context["records"] = records
    context["source"] = data.get("source") or nested.get("source") or "unknown"
    context["source_event_id"] = (
        data.get("source_event_id") or nested.get("id") or nested.get("source_event_id")
    )
    context["road_name"] = data.get("road_name") or nested.get("road_name") or nested.get("from_road") or nested.get("to_road")
    context["delay_seconds"] = data.get("delay_seconds", nested.get("delay_seconds", nested.get("delay")))
    context["road_closure"] = bool(
        data.get("road_closure") or nested.get("road_closure") or nested.get("roadClosed")
    )
    context["icon_category"] = _icon_category(nested)
    context["category_name"] = str(
        nested.get("category_name") or nested.get("categoryName") or nested.get("event_type") or ""
    ).lower()
    return context


def _triggered(rule: AlertRule, context: dict[str, Any]) -> tuple[bool, str, str]:
    thresholds = rule.thresholds or {}
    category = rule.category
    if rule.rule_key in ("congestion_high", "congestion_critical"):
        level = str(context.get("congestion_level") or "").upper()
        ratio = None
        current = context.get("average_speed", context.get("current_speed"))
        free_flow = context.get("free_flow_speed")
        if current is not None and free_flow is not None and float(free_flow) > 0:
            ratio = float(current) / float(free_flow)
        critical = (
            rule.rule_key == "congestion_critical"
            and context.get("density") is not None
            and float(context["density"]) >= float(thresholds.get("minimum_density", 1.1))
            and ratio is not None
            and ratio <= float(thresholds.get("maximum_speed_ratio", 0.0))
        )
        ordinary = (
            rule.rule_key == "congestion_high"
            and level in [str(item).upper() for item in thresholds.get("congestion_levels", ["HIGH"])]
        )
        if critical or ordinary:
            return True, "Congestion threshold reached", f"Traffic congestion is {level or 'critical'} at this location."
    elif category == "SPEED_REDUCTION":
        current = context.get("average_speed", context.get("current_speed"))
        free_flow = context.get("free_flow_speed")
        if current is not None and free_flow is not None and float(free_flow) > 0:
            ratio = float(current) / float(free_flow)
            drop = 1.0 - ratio
            if ratio <= float(thresholds.get("maximum_speed_ratio", 0.5)) and drop >= float(thresholds.get("minimum_speed_drop", 0.4)):
                return True, "Significant speed reduction", f"Observed speed has fallen to {ratio:.0%} of free-flow speed."
    elif category == "TRAFFIC_DELAY":
        delay = context.get("delay_seconds")
        if delay is not None and float(delay) >= float(thresholds.get("minimum_delay_seconds", 300)):
            return True, "Traffic delay threshold reached", f"Reported traffic delay is {round(float(delay) / 60, 1)} minutes."
    elif category in {"ROAD_CLOSURE", "ROADWORKS", "STATIONARY_TRAFFIC", "INCIDENT"}:
        icon = context.get("icon_category")
        allowed = [int(item) for item in thresholds.get("icon_categories", [])]
        name = context.get("category_name", "")
        matches = icon in allowed or (
            category == "ROAD_CLOSURE" and context.get("road_closure")
        ) or (
            category == "ROADWORKS" and "road work" in name
        ) or (
            category == "STATIONARY_TRAFFIC" and ("stationary" in name or "jam" in name)
        )
        if matches:
            description = str(context.get("description") or context.get("category_name") or rule.name)
            return True, rule.name, description
    elif category == "AI_FORECAST":
        predicted = str(context.get("predicted_congestion") or "").upper()
        if predicted in [str(item).upper() for item in thresholds.get("predicted_levels", ["HIGH", "CRITICAL"])] and context.get("source") in {"routex_ai", "ai_prediction", "routex_production_predictor"}:
            return True, "AI congestion forecast", f"RouteX AI forecasts {predicted.lower()} congestion from the submitted observation."
    elif category == "ANOMALY":
        has_anomaly = context.get("anomaly_detected") is True or any(
            item.get("anomaly_detected") is True
            or "anomaly" in str(item.get("type") or item.get("event_type") or "").lower()
            for item in context["records"]
        )
        if has_anomaly:
            return True, "Traffic anomaly detected", str(context.get("description") or "An existing anomaly detector flagged this observation.")
    return False, "", ""


def _scope_key(rule_key: str, context: dict[str, Any]) -> str:
    if context.get("source") == "tomtom_traffic_incidents" and context.get("source_event_id"):
        anchor = f"incident:{context['source_event_id']}"
    elif context.get("intersection_id"):
        anchor = f"intersection:{context['intersection_id']}"
    elif context.get("road_id"):
        anchor = f"road:{context['road_id']}"
    elif context.get("latitude") is not None and context.get("longitude") is not None:
        anchor = f"point:{float(context['latitude']):.3f}:{float(context['longitude']):.3f}"
    elif context.get("source_event_id"):
        anchor = f"event:{context['source_event_id']}"
    else:
        anchor = f"source:{context['source']}"
    return f"{context['source']}:{context.get('route_id') or ''}:{rule_key}:{anchor}"[:220]


def _event_dedupe_key(rule_key: str, event_id: str | None) -> str | None:
    if not event_id:
        return None
    return hashlib.sha256(f"{rule_key}:{event_id}".encode("utf-8")).hexdigest()


def process_alert_event(
    db: Session,
    event: dict[str, Any] | AlertEventInput,
    *,
    source_event_id: str | None = None,
    commit: bool = True,
) -> list[TrafficAlert]:
    """Evaluate an observation and persist only triggered, deduplicated alerts."""
    payload = event.model_dump(exclude_none=True) if isinstance(event, AlertEventInput) else dict(event)
    if source_event_id:
        payload["source_event_id"] = source_event_id
    validated = AlertEventInput.model_validate(payload)
    context = _event_context(validated.model_dump(exclude_none=True))
    if not context.get("source_event_id") and source_event_id:
        context["source_event_id"] = source_event_id

    if context.get("latitude") is not None and context.get("longitude") is not None:
        latitude, longitude = float(context["latitude"]), float(context["longitude"])
        context["location"] = WKTElement(f"POINT({longitude} {latitude})", srid=POSTGIS_SRID)
    else:
        context["location"] = None

    rules = db.query(AlertRule).filter(AlertRule.enabled.is_(True)).all()
    now = datetime.utcnow()
    generated: list[TrafficAlert] = []
    redis = TrafficRedis()
    redis_available = True
    event_key = context.get("source_event_id")
    is_incident = context["source"] == "tomtom_traffic_incidents"

    # Redis is an optimization only. PostgreSQL idempotency and cooldown checks remain authoritative.
    if event_key and not is_incident and commit:
        try:
            if redis.get_alert_event(f"{context['source']}:{event_key}"):
                prior = db.query(TrafficAlert).filter(
                    TrafficAlert.source_event_id == str(event_key), TrafficAlert.source == context["source"]
                ).all()
                if prior:
                    return prior
        except Exception as exc:
            redis_available = False
            logger.info("Alert dedup cache unavailable; using PostgreSQL: %s", exc)

    try:
        # Serialize a scope within PostgreSQL, including when Redis is down.
        scope_lock = _scope_key("evaluation", context)
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": scope_lock})
        for rule in rules:
            triggered, title, description = _triggered(rule, context)
            if not triggered:
                continue

            dedupe_key = _event_dedupe_key(rule.rule_key, f"{context['source']}:{event_key}" if event_key else None)
            if dedupe_key:
                existing_event = db.query(TrafficAlert).filter(
                    (TrafficAlert.event_dedupe_key == dedupe_key) |
                    ((TrafficAlert.source == context["source"]) & (TrafficAlert.source_event_id == str(event_key)) & (TrafficAlert.rule_key == rule.rule_key))
                ).first()
                if existing_event:
                    if is_incident:
                        _refresh_incident(existing_event, validated, context, title, description, rule, now)
                    generated.append(existing_event)
                    continue

            scope = _scope_key(rule.rule_key, context)
            try:
                # Redis avoids unnecessary scope lookups under load; PostgreSQL remains authoritative.
                cooling_hint = redis.get_alert_cooldown(scope) if redis_available and commit else None
            except Exception as exc:
                redis_available = False
                cooling_hint = None
                logger.info("Alert cooldown cache unavailable; checking PostgreSQL: %s", exc)
            existing_active = db.query(TrafficAlert).filter(
                TrafficAlert.scope_key == scope,
                TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
            ).order_by(TrafficAlert.created_at.desc()).first()
            if existing_active:
                existing_active.source_event_id = str(event_key)[:160] if event_key else None
                existing_active.event_dedupe_key = dedupe_key
                existing_active.title, existing_active.description = title[:240], description[:2000]
                existing_active.severity = rule.severity
                existing_active.last_seen_at = now
                existing_active.updated_at = now
                existing_active.source_timestamp = validated.timestamp
                existing_active.details = {
                    **(existing_active.details or {}),
                    "last_observation": validated.model_dump(mode="json", exclude_none=True),
                }
                generated.append(existing_active)
                continue

            cooldown_cutoff = now - timedelta(seconds=max(0, rule.cooldown_seconds))
            recent = db.query(TrafficAlert).filter(
                TrafficAlert.scope_key == scope,
                TrafficAlert.created_at >= cooldown_cutoff,
            ).order_by(TrafficAlert.created_at.desc()).first()
            if recent:
                continue

            if cooling_hint:
                logger.debug("Redis cooldown was set for %s but no persistent alert remains; allowing database-backed recovery.", scope)

            alert = TrafficAlert(
                event_dedupe_key=dedupe_key,
                scope_key=scope,
                rule_key=rule.rule_key,
                category=rule.category,
                severity=rule.severity,
                title=title[:240],
                description=description[:2000],
                source=str(context["source"])[:100],
                source_event_id=str(event_key)[:160] if event_key is not None else None,
                road_id=str(context["road_id"])[:80] if context.get("road_id") else None,
                road_name=str(context["road_name"])[:200] if context.get("road_name") else None,
                intersection_id=str(context["intersection_id"])[:80] if context.get("intersection_id") else None,
                latitude=context.get("latitude"),
                longitude=context.get("longitude"),
                location=context["location"],
                route_id=str(context["route_id"])[:80] if context.get("route_id") else None,
                status="ACTIVE",
                details={
                    **(validated.details or {}),
                    "observation": validated.model_dump(mode="json", exclude_none=True),
                    "trigger_reason": title,
                },
                source_timestamp=validated.timestamp,
                last_seen_at=now,
            )
            db.add(alert)
            db.flush()
            db.add(AlertNotification(
                alert_id=alert.id,
                title=alert.title,
                message=alert.description[:1000],
            ))
            generated.append(alert)

        if is_incident and event_key:
            active_ids = [item.id for item in generated]
            superseded = db.query(TrafficAlert).filter(
                TrafficAlert.source == context["source"], TrafficAlert.source_event_id == str(event_key),
                TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"]), ~TrafficAlert.id.in_(active_ids),
            ).all()
            for alert in superseded:
                alert.status, alert.resolved_at, alert.resolved_by = "RESOLVED", now, "provider_rule_update"
        if commit:
            db.commit()
        else:
            db.flush()
        if redis_available and commit and not is_incident:
            try:
                if event_key:
                    redis.set_alert_event(f"{context['source']}:{event_key}", ttl_seconds=86400)
                for alert in generated:
                    rule = next((item for item in rules if item.rule_key == alert.rule_key), None)
                    if rule:
                        redis.set_alert_cooldown(alert.scope_key, ttl_seconds=max(rule.cooldown_seconds, 1))
            except Exception as exc:
                logger.info("Alert saved; Redis alert state update skipped: %s", exc)
        return generated
    except IntegrityError:
        db.rollback()
        if not commit:
            raise
        if event_key:
            return db.query(TrafficAlert).filter(
                TrafficAlert.source_event_id == str(event_key), TrafficAlert.source == context["source"]
            ).all()
        raise

    except Exception:
        db.rollback()
        raise


def _refresh_incident(alert, validated, context, title, description, rule, now):
    alert.title, alert.description, alert.severity = title[:240], description[:2000], rule.severity
    alert.road_name = context.get("road_name")
    alert.latitude, alert.longitude, alert.location = context.get("latitude"), context.get("longitude"), context["location"]
    alert.source_timestamp = validated.timestamp
    alert.last_seen_at = alert.updated_at = now
    alert.details = {**(validated.details or {}), "observation": validated.model_dump(mode="json", exclude_none=True)}
    # A manually resolved incident stays resolved; provider expiry may reopen.
    if alert.status == "RESOLVED" and alert.resolved_by in {"provider", "provider_rule_update"}:
        alert.status, alert.resolved_at, alert.resolved_by = "ACTIVE", None, None


def incident_is_current(incident: dict) -> bool:
    now = datetime.now(timezone.utc)
    if incident.get("time_validity") == "future":
        return False
    for key, future in (("start_time", True), ("end_time", False)):
        if incident.get(key):
            try:
                value = datetime.fromisoformat(incident[key].replace("Z", "+00:00"))
                value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
                if (future and value > now) or (not future and value <= now):
                    return False
            except (ValueError, TypeError):
                return False
    return True


def sync_incident_alerts(db: Session, incidents: list[dict], bbox=None):
    """Update provider identities and reconcile only a successfully retrieved area."""
    current = [inc for inc in incidents if incident_is_current(inc)]
    for inc in current:
        process_alert_event(db, {
            "source": "tomtom_traffic_incidents", "source_event_id": inc["id"],
            "timestamp": inc.get("updated_at") or inc.get("retrieved_at") or datetime.now(timezone.utc),
            "latitude": inc.get("centroid_lat"), "longitude": inc.get("centroid_lng"),
            "road_name": inc.get("from_road") or inc.get("to_road"),
            "delay_seconds": inc.get("delay_seconds"), "events": [inc],
            "details": {"provider": "TomTom Traffic Incidents API", "geometry": inc.get("geometry"),
                        "direction": (inc.get("tmc") or {}).get("direction"),
                        "direction_match": "UNVERIFIED", "road_numbers": inc.get("road_numbers", []),
                        "time_validity": inc.get("time_validity"), "end_time": inc.get("end_time")},
        }, commit=False)
    if bbox is not None:
        # A failure must never enter this path. Restrict absence resolution to
        # geometries fully covered by the provider query, preserving other routes.
        db.execute(text("""
            UPDATE traffic_alerts SET status='RESOLVED', resolved_at=timezone('utc', now()),
                updated_at=timezone('utc', now()), resolved_by='provider'
            WHERE source='tomtom_traffic_incidents' AND status IN ('ACTIVE','ACKNOWLEDGED')
              AND NOT (source_event_id = ANY(:ids))
              AND ST_CoveredBy(
                CASE WHEN details->'geometry'->>'type' IN ('Point','LineString')
                  THEN ST_SetSRID(ST_GeomFromGeoJSON((details->'geometry')::text),4326)
                  ELSE location END,
                ST_MakeEnvelope(:min_lng,:min_lat,:max_lng,:max_lat,4326))
        """), {"ids": [inc["id"] for inc in current], **dict(zip(("min_lng","min_lat","max_lng","max_lat"), bbox))})
    db.commit()
    return current


def match_route_incidents(db: Session, geometry: dict, incidents: list[dict], corridor_meters=350):
    """Use the same PostGIS geography corridor for full provider geometries."""
    if not incidents:
        return []
    rows = db.execute(text("""
        WITH route AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:route),4326) geom),
        incidents AS (
          SELECT item, ST_SetSRID(ST_GeomFromGeoJSON((item->'geometry')::text),4326) geom
          FROM jsonb_array_elements(CAST(:incidents AS jsonb)) item
        )
        SELECT item FROM incidents, route
        WHERE ST_DWithin(incidents.geom::geography,route.geom::geography,:meters)
    """), {"route": json.dumps(geometry), "incidents": json.dumps(incidents), "meters": corridor_meters})
    return [row.item for row in rows if incident_is_current(row.item)]


def update_alert_status(
    db: Session,
    alert: TrafficAlert,
    action: str,
    actor: str | None = None,
) -> TrafficAlert:
    now = datetime.utcnow()
    if action == "acknowledge" and alert.status == "ACTIVE":
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = now
        alert.acknowledged_by = actor
    elif action == "resolve" and alert.status != "RESOLVED":
        alert.status = "RESOLVED"
        alert.resolved_at = now
        alert.resolved_by = actor
    elif action not in {"acknowledge", "resolve"}:
        raise ValueError("Unsupported alert lifecycle action")
    alert.updated_at = now
    db.commit()
    db.refresh(alert)
    return alert


def mark_notification_read(db: Session, notification: AlertNotification) -> AlertNotification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def route_alert_matches(db: Session, route_id: str, geometry: dict[str, Any], corridor_meters: int):
    geojson = json.dumps(geometry)
    return db.execute(text("""
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326) AS geom
        )
        , alerts AS (
            SELECT a.*, CASE WHEN details->'geometry'->>'type' IN ('Point','LineString')
              THEN ST_SetSRID(ST_GeomFromGeoJSON((details->'geometry')::text),4326)
              ELSE location END AS incident_geom FROM traffic_alerts a
        )
        SELECT a.id,
               ST_Distance(a.incident_geom::geography, route.geom::geography) AS distance_to_route_meters,
               ST_Y(ST_ClosestPoint(a.incident_geom, route.geom)) AS marker_latitude,
               ST_X(ST_ClosestPoint(a.incident_geom, route.geom)) AS marker_longitude,
               ST_LineLocatePoint(route.geom, ST_ClosestPoint(route.geom, a.incident_geom))
                 * ST_Length(route.geom::geography) AS distance_along_route_meters
        FROM alerts a CROSS JOIN route
        WHERE a.incident_geom IS NOT NULL
          AND a.status IN ('ACTIVE', 'ACKNOWLEDGED')
          AND (a.source = 'tomtom_traffic_incidents' OR a.last_seen_at >= timezone('utc', now()) - interval '1 hour')
          AND (a.route_id IS NULL OR a.route_id = :route_id)
          AND ST_DWithin(a.incident_geom::geography, route.geom::geography, :corridor_meters)
        ORDER BY distance_along_route_meters, a.created_at DESC
    """), {"geometry": geojson, "corridor_meters": corridor_meters, "route_id": route_id}).fetchall()


def alert_statistics(db: Session) -> dict[str, Any]:
    counts = {
        row.status.lower(): int(row.count)
        for row in db.query(TrafficAlert.status, func.count(TrafficAlert.id).label("count")).group_by(TrafficAlert.status)
    }
    severity = {
        row.severity: int(row.count)
        for row in db.query(TrafficAlert.severity, func.count(TrafficAlert.id).label("count"))
        .filter(TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
        .group_by(TrafficAlert.severity)
    }
    categories = {
        row.category: int(row.count)
        for row in db.query(TrafficAlert.category, func.count(TrafficAlert.id).label("count"))
        .filter(TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
        .group_by(TrafficAlert.category)
    }
    unread = db.query(func.count(AlertNotification.id)).filter(AlertNotification.is_read.is_(False)).scalar() or 0
    return {
        "active": counts.get("active", 0),
        "acknowledged": counts.get("acknowledged", 0),
        "resolved": counts.get("resolved", 0),
        "unread_notifications": int(unread),
        "by_severity": severity,
        "by_category": categories,
    }
