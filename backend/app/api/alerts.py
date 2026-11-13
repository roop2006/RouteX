from datetime import datetime
import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.alert_rule import AlertRule
from backend.app.models.traffic_alert import AlertNotification, TrafficAlert
from backend.app.schemas.alerts import (
    AlertEventInput,
    AlertNotificationList,
    AlertNotificationRead,
    AlertRuleRead,
    AlertRuleUpdate,
    AlertStatistics,
    RouteAlertSearch,
    RouteTrafficAlertRead,
    TrafficAlertRead,
)
from backend.app.services.alert_service import (
    DEFAULT_ALERT_RULES,
    alert_statistics,
    mark_notification_read,
    process_alert_event,
    route_alert_matches,
    update_alert_status,
)

router = APIRouter(tags=["Traffic Alerts"])


@router.get("/alert-rules", response_model=list[AlertRuleRead])
def list_alert_rules(db: Session = Depends(get_db)):
    return db.query(AlertRule).order_by(AlertRule.category, AlertRule.rule_key).all()


@router.patch("/alert-rules/{rule_key}", response_model=AlertRuleRead)
def patch_alert_rule(rule_key: str, update: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_key)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    if update.thresholds is not None:
        defaults = next((item["thresholds"] for item in DEFAULT_ALERT_RULES if item["rule_key"] == rule_key), {})
        if set(update.thresholds) - set(defaults):
            raise HTTPException(status_code=422, detail="Threshold keys are not supported for this rule")
        for key, value in update.thresholds.items():
            expected = defaults[key]
            if isinstance(expected, list):
                if not isinstance(value, list) or not value or any(type(item) is not type(expected[0]) for item in value):
                    raise HTTPException(status_code=422, detail=f"Threshold '{key}' must be a non-empty list of {type(expected[0]).__name__} values")
            elif isinstance(expected, (float, int)):
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                    raise HTTPException(status_code=422, detail=f"Threshold '{key}' must be a finite non-negative number")
                if key in {"minimum_density", "maximum_speed_ratio", "minimum_speed_drop"} and value > 1:
                    raise HTTPException(status_code=422, detail=f"Threshold '{key}' must be between 0 and 1")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/alerts/evaluate", response_model=list[TrafficAlertRead])
def evaluate_alert_event(event: AlertEventInput, db: Session = Depends(get_db)):
    try:
        return process_alert_event(db, event)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Alert evaluation failed: {exc}")


def _alert_query(
    db: Session,
    *,
    status: str | None,
    severity: str | None,
    category: str | None,
    source: str | None,
    route_id: str | None,
    since: datetime | None,
    include_resolved: bool = False,
):
    query = db.query(TrafficAlert)
    if status:
        query = query.filter(TrafficAlert.status == status.upper())
    elif not include_resolved:
        query = query.filter(TrafficAlert.status.in_(["ACTIVE", "ACKNOWLEDGED"]))
    if severity:
        query = query.filter(TrafficAlert.severity == severity.upper())
    if category:
        query = query.filter(TrafficAlert.category == category.upper())
    if source:
        query = query.filter(TrafficAlert.source == source)
    if route_id:
        query = query.filter(TrafficAlert.route_id == route_id)
    if since:
        query = query.filter(TrafficAlert.created_at >= since)
    return query


@router.get("/alerts", response_model=list[TrafficAlertRead])
def list_alerts(
    status: Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"] | None = None,
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    category: str | None = None,
    source: str | None = None,
    route_id: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return _alert_query(
        db, status=status, severity=severity, category=category, source=source,
        route_id=route_id, since=since,
    ).order_by(TrafficAlert.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/alerts/history", response_model=list[TrafficAlertRead])
def alert_history(
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    category: str | None = None,
    source: str | None = None,
    route_id: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return _alert_query(
        db, status=None, severity=severity, category=category, source=source,
        route_id=route_id, since=since, include_resolved=True,
    ).filter(TrafficAlert.status == "RESOLVED").order_by(TrafficAlert.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/alerts/route", response_model=list[RouteTrafficAlertRead])
def alerts_for_route(request: RouteAlertSearch, db: Session = Depends(get_db)):
    coordinates = request.geometry.get("coordinates")
    if request.geometry.get("type") != "LineString" or not isinstance(coordinates, list) or len(coordinates) < 2:
        raise HTTPException(status_code=422, detail="Route geometry must be a GeoJSON LineString with at least two points")
    for point in coordinates:
        if not isinstance(point, list) or len(point) < 2:
            raise HTTPException(status_code=422, detail="Route coordinates must use [longitude, latitude] pairs")
        lng, lat = point[0], point[1]
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise HTTPException(status_code=422, detail="Route coordinates are outside WGS84 bounds")

    matches = route_alert_matches(db, request.route_id, request.geometry, request.corridor_meters)
    results = []
    for row in matches:
        alert = db.get(TrafficAlert, row.id)
        if alert is None:
            continue
        results.append({
            "alert": alert,
            "distance_to_route_meters": float(row.distance_to_route_meters),
            "distance_along_route_meters": float(row.distance_along_route_meters),
        })
    return results


@router.post("/alerts/{alert_id}/acknowledge", response_model=TrafficAlertRead)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(TrafficAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return update_alert_status(db, alert, "acknowledge")


@router.post("/alerts/{alert_id}/resolve", response_model=TrafficAlertRead)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(TrafficAlert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return update_alert_status(db, alert, "resolve")


@router.get("/alerts/notifications", response_model=AlertNotificationList)
def list_notifications(
    include_read: bool = False,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(AlertNotification)
    unread_count = query.filter(AlertNotification.is_read.is_(False)).count()
    if not include_read:
        query = query.filter(AlertNotification.is_read.is_(False))
    notifications = query.order_by(AlertNotification.created_at.desc()).limit(limit).all()
    return {"unread_count": unread_count, "notifications": notifications}


@router.post("/alerts/notifications/{notification_id}/read", response_model=AlertNotificationRead)
def read_notification(notification_id: int, db: Session = Depends(get_db)):
    notification = db.get(AlertNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return mark_notification_read(db, notification)


@router.get("/alerts/statistics", response_model=AlertStatistics)
def get_alert_statistics(db: Session = Depends(get_db)):
    return alert_statistics(db)
