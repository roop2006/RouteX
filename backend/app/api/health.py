from datetime import datetime, timezone
import logging
import socket
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.alert_rule import AlertRule
from backend.app.models.traffic_alert import TrafficAlert
from backend.app.services.route_analysis_service import OSRM_CONNECTIVITY
from backend.app.services.tomtom_traffic_service import tomtom_traffic_service
from vision.streaming.kafka_config import KAFKA_BOOTSTRAP_SERVERS
from vision.streaming.redis_client import TrafficRedis

logger = logging.getLogger("routex.integration_health")
router = APIRouter(prefix="/health", tags=["Connectivity"])


def _result(status: str, details: str, start: float | None, *, checked_at: datetime | None = None, error: str | None = None):
    return {
        "status": status,
        "details": details,
        "latency_ms": round((time.perf_counter() - start) * 1000, 1) if start is not None else None,
        "checked_at": (checked_at or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat() if checked_at or start is not None else None,
        "error": error,
    }


@router.get("/integrations")
def integration_health(db: Session = Depends(get_db)):
    """Probe local dependencies without triggering paid provider requests."""
    components = {}

    started = time.perf_counter()
    try:
        postgis_version = db.execute(text("SELECT PostGIS_Version()")).scalar_one()
        components["database"] = _result("healthy", f"PostgreSQL and PostGIS reachable ({postgis_version.split()[0]}).", started)
    except Exception as exc:
        db.rollback()
        logger.warning("PostGIS health probe failed (%s)", type(exc).__name__)
        components["database"] = _result("unavailable", "PostgreSQL/PostGIS query failed.", started, error=type(exc).__name__)

    started = time.perf_counter()
    redis_service = TrafficRedis()
    try:
        redis_service.client.ping()
        components["redis"] = _result("healthy", "Redis PING succeeded.", started)
    except Exception as exc:
        logger.info("Redis health probe unavailable: %s", exc)
        components["redis"] = _result("unavailable", "Redis PING failed; persistent PostgreSQL paths remain available.", started, error=type(exc).__name__)
    finally:
        try:
            redis_service.client.close()
        except Exception:
            pass

    started = time.perf_counter()
    try:
        broker = KAFKA_BOOTSTRAP_SERVERS.split(",", 1)[0].strip()
        host, port_text = broker.rsplit(":", 1)
        with socket.create_connection((host, int(port_text)), timeout=0.6):
            pass
        components["kafka"] = _result("degraded", f"Kafka TCP {host}:{port_text} is reachable; topic consumption has not been verified by this probe.", started)
    except Exception as exc:
        logger.info("Kafka broker health probe unavailable: %s", exc)
        components["kafka"] = _result("unavailable", "Kafka broker TCP connection failed.", started, error=type(exc).__name__)

    flow_status = tomtom_traffic_service.flow_connectivity_status
    components["tomtom_flow"] = _result(
        flow_status if tomtom_traffic_service.is_configured else "not_configured",
        "TomTom Traffic Flow API configuration loaded; live requests are made by the traffic service, not by this status probe."
        if flow_status == "unverified" else "TomTom Traffic Flow API last observed result.",
        None,
        checked_at=tomtom_traffic_service.last_flow_checked_at,
        error=tomtom_traffic_service.last_flow_error,
    )
    incident_status = tomtom_traffic_service.incident_connectivity_status
    components["tomtom_incidents"] = _result(
        incident_status if tomtom_traffic_service.is_configured else "not_configured",
        "TomTom Traffic Incidents API configuration loaded; live requests are made by the traffic service, not by this status probe."
        if incident_status == "unverified" else "TomTom Traffic Incidents API last observed result.",
        None,
        checked_at=tomtom_traffic_service.last_incident_checked_at,
        error=tomtom_traffic_service.last_incident_error,
    )

    osrm_status = OSRM_CONNECTIVITY.get("status", "unverified")
    components["osrm"] = {
        "status": osrm_status,
        "details": "OSRM remains the primary router. This probe does not issue a route or external request."
        if osrm_status == "unverified" else "Status reflects the last primary OSRM route request.",
        "latency_ms": None,
        "checked_at": OSRM_CONNECTIVITY.get("checked_at").isoformat() if OSRM_CONNECTIVITY.get("checked_at") else None,
        "error": OSRM_CONNECTIVITY.get("error"),
    }

    started = time.perf_counter()
    try:
        rules_count = db.query(func.count(AlertRule.rule_key)).scalar() or 0
        active_count = db.query(func.count(TrafficAlert.id)).filter(
            TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"])
        ).scalar() or 0
        components["alert_store"] = _result(
            "healthy" if rules_count else "not_configured", f"Alert persistence query succeeded ({rules_count} rules, {active_count} active/acknowledged alerts).", started
        )
    except Exception as exc:
        db.rollback()
        logger.warning("Alert store health probe failed (%s)", type(exc).__name__)
        components["alert_store"] = _result("unavailable", "Alert database tables could not be queried; run the additive migration helper.", started, error=type(exc).__name__)

    from backend.app.services.video_analysis_service import worker_status
    components["yolo"] = {**worker_status(), "checked_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "latency_ms": None}

    for key in ("tomtom_flow", "tomtom_incidents", "osrm"):
        component = components[key]
        checked = component.get("checked_at")
        if checked and component["status"] == "available" and (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(checked)).total_seconds() > 600:
            component.update(status="unverified", details="Last successful provider observation is older than 10 minutes.")

    return {"checked_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), "components": components}
