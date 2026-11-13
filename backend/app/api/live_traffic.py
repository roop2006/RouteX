from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.services.live_traffic_service import live_traffic_service
from backend.app.services.tomtom_traffic_service import tomtom_traffic_service

router = APIRouter(
    prefix="/live-traffic",
    tags=["Live Traffic"]
)


@router.get("/")
@router.get("")
def get_live_traffic(db: Session = Depends(get_db)):
    """
    Returns live traffic telemetry.
    Checks Redis real-time stream buffer, falls back to TomTom Live Traffic API,
    then to database telemetry, or returns an informative UNAVAILABLE status to prevent infinite loading.
    """
    data = live_traffic_service.get_latest_live_traffic(db=db)
    return data


@router.get("/tomtom")
def get_tomtom_live_traffic(db: Session = Depends(get_db)):
    """
    Retrieves live TomTom traffic flow across monitored arterial intersections
    and active incidents in Chennai.
    """
    if not tomtom_traffic_service.is_configured:
        return {
            "status": "UNCONFIGURED",
            "provider": "TomTom Traffic API",
            "message": "TOMTOM_API_KEY environment variable is not configured.",
            "junctions": [],
            "incidents": [],
        }

    try:
        snapshot = tomtom_traffic_service.get_chennai_live_snapshot(db=db)
        return snapshot
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query TomTom traffic data: {str(exc)}",
        )


@router.get("/incidents")
def get_live_incidents(
    min_lng: float = Query(default=80.12, ge=-180.0, le=180.0),
    min_lat: float = Query(default=12.94, ge=-90.0, le=90.0),
    max_lng: float = Query(default=80.32, ge=-180.0, le=180.0),
    max_lat: float = Query(default=13.18, ge=-90.0, le=90.0),
    db: Session = Depends(get_db),
):
    """
    Retrieves active live traffic incidents within a bounding box from TomTom.
    Defaults to Chennai Greater Metro.
    """
    if not tomtom_traffic_service.is_configured:
        return {
            "status": "UNCONFIGURED",
            "count": 0,
            "incidents": [],
            "message": "TomTom API key not configured.",
        }

    incidents = tomtom_traffic_service.get_incident_details(
        min_lng=min_lng,
        min_lat=min_lat,
        max_lng=max_lng,
        max_lat=max_lat,
    )
    if tomtom_traffic_service.last_incident_error:
        raise HTTPException(
            status_code=502,
            detail=tomtom_traffic_service.last_incident_error,
        )
    for incident in incidents:
        try:
            from backend.app.services.alert_service import process_alert_event
            process_alert_event(db, {
                "source": "tomtom_traffic_incidents",
                "source_event_id": incident.get("id"),
                "timestamp": incident.get("start_time"),
                "latitude": incident.get("centroid_lat"),
                "longitude": incident.get("centroid_lng"),
                "delay_seconds": incident.get("delay_seconds"),
                "road_name": incident.get("from_road") or incident.get("to_road"),
                "events": [incident],
                "details": {"provider": "TomTom Traffic Incidents API"},
            })
        except Exception:
            import logging
            logging.getLogger("routex.live_traffic").exception(
                "TomTom incident returned; alert creation failed for provider event %s",
                incident.get("id"),
            )
    return {
        "status": "ACTIVE",
        "provider": "TomTom Traffic Incidents API",
        "count": len(incidents),
        "incidents": incidents,
    }


@router.get("/tile/{layer}/{zoom}/{x}/{y}.png")
def get_traffic_tile_proxy(
    layer: str,
    zoom: int,
    x: int,
    y: int,
    style: str = Query(default="relative0"),
):
    """
    Proxies TomTom traffic flow or incident raster tiles securely without
    exposing credentials to the frontend.
    """
    if layer not in ("flow", "incidents"):
        raise HTTPException(status_code=400, detail="Layer must be 'flow' or 'incidents'")

    tile_bytes = tomtom_traffic_service.get_traffic_tile(
        layer=layer,
        zoom=zoom,
        x=x,
        y=y,
        format="png",
        style=style,
    )
    if not tile_bytes:
        # Return empty 1x1 transparent PNG if tile is unavailable or error
        transparent_1x1_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
            b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        return Response(content=transparent_1x1_png, media_type="image/png")

    return Response(
        content=tile_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
def ingest_live_traffic(payload: dict[str, Any], db: Session = Depends(get_db)):
    """
    Ingests and validates a live traffic snapshot from an external provider or camera feed,
    persisting it to PostgreSQL/PostGIS and updating the live buffer.
    """
    try:
        event = live_traffic_service.ingest_traffic_snapshot(payload, db=db)
        return {
            "status": "INGESTED",
            "event_id": event.id,
            "intersection_id": event.intersection_id,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "total_vehicles": event.total_vehicles,
            "congestion_level": event.congestion_level,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest live traffic: {str(exc)}")
