import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.user_analysis import (
    CombinedAnalysisRequest,
    CombinedAnalysisResponse,
    LocalVideoAnalysisRequest,
    LocationSuggestion,
    RouteAnalysisRequest,
    RouteAnalysisResponse,
    VideoAnalysisJobResponse,
    VideoAnalysisStatusResponse,
)
from backend.app.services.route_analysis_service import (
    calculate_user_route,
    search_locations,
)
from backend.app.services.video_analysis_service import (
    cancel_job,
    get_video_job_status,
    save_and_start_video_analysis,
    start_local_video_analysis,
)

router = APIRouter(
    prefix="/analysis",
    tags=["User Traffic Analysis"],
)


@router.post("/route", response_model=RouteAnalysisResponse)
def analyze_route(
    request: RouteAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Calculate real road route geometry between origin and destination,
    correlate with PostGIS corridor infrastructure & stream events,
    and compute AI traffic predictions.
    """
    try:
        return calculate_user_route(request=request, db=db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Route analysis encountered an internal error: {str(exc)}",
        )


@router.post("/video/upload", response_model=VideoAnalysisJobResponse)
async def upload_video_for_analysis(
    file: UploadFile = File(...),
    intersection_id: Optional[str] = Form(None),
):
    """
    Upload a local traffic recording for computer vision analysis
    (YOLO detection, tracking, vehicle counting, speed estimation, and AI forecasting).
    """
    return await save_and_start_video_analysis(
        upload_file=file,
        intersection_id=intersection_id,
    )


@router.post("/video/sample", response_model=VideoAnalysisJobResponse)
def analyze_sample_video(
    request: LocalVideoAnalysisRequest,
):
    """
    Trigger analysis on an existing sample video on the server (e.g. data/videos/traffic.mp4)
    without requiring client file re-upload.
    """
    return start_local_video_analysis(
        video_path_str=request.video_path,
        intersection_id=request.intersection_id,
    )


@router.get("/video/{job_id}", response_model=VideoAnalysisStatusResponse)
def get_video_analysis_status(job_id: str):
    """
    Poll the status, progress percentage, or completed results of a video analysis job.
    """
    return get_video_job_status(job_id)


@router.post("/video/{job_id}/cancel")
def cancel_video_analysis(job_id: str):
    """
    Cancel an ongoing video analysis job.
    """
    cancelled = cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' could not be cancelled. It may already be completed or not exist.",
        )
    return {"message": f"Job '{job_id}' cancellation requested successfully."}


@router.get("/geocoding/search", response_model=list[LocationSuggestion])
def search_location_suggestions(
    q: str = Query("", description="Location query term"),
    db: Session = Depends(get_db),
):
    """
    Autocomplete / search for locations matching database intersections, roads, and known hotspots.
    """
    return search_locations(query=q, db=db)


@router.post("/combine", response_model=CombinedAnalysisResponse)
def combine_route_and_video(
    request: CombinedAnalysisRequest,
    db: Session = Depends(get_db),
):
    """
    Combines route intelligence with video analysis when the video's
    camera/intersection maps to the route corridor.
    """
    # 1. Run route analysis
    route_result = calculate_user_route(request=request.route_request, db=db)

    # 2. Retrieve video analysis result
    video_status = get_video_job_status(request.video_job_id)
    if video_status.status != "COMPLETED" or not video_status.result:
        raise HTTPException(
            status_code=400,
            detail=f"Video analysis job '{request.video_job_id}' is not yet completed (current status: {video_status.status}).",
        )

    video_result = video_status.result
    vid_intersection_id = (video_result.intersection_id or "").strip()
    missing_location_ids = {"", "STANDALONE_CAMERA"}

    # 3. Check whether the video's intersection is geographically associated with the route.
    # Never assume a missing camera location belongs to INT_001 or any other junction.
    is_associated = False
    association_reason = ""

    if vid_intersection_id in missing_location_ids:
        is_associated = False
        association_reason = (
            "Video recording has no camera coordinates or intersection metadata. "
            "RouteX will not assume that this recording belongs to the selected route. "
            "Route intelligence and video results remain available independently."
        )
    else:
        matched_int = next(
            (
                i
                for i in route_result.corridor.nearby_intersections
                if i.intersection_id == vid_intersection_id
            ),
            None,
        )

        if matched_int:
            is_associated = True
            association_reason = (
                f"Video camera at {matched_int.name} ({matched_int.intersection_id}) "
                f"is directly on the selected route corridor."
            )
        else:
            int_row = db.execute(
                text("SELECT intersection_id, name, location FROM intersections WHERE intersection_id = :id"),
                {"id": vid_intersection_id},
            ).first()

            if int_row and int_row.location is not None:
                primary_geom_json = json.dumps(route_result.selected_route.geometry)
                dist_res = db.execute(
                    text("""
                        SELECT ST_Distance(
                            location::geography,
                            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography
                        ) AS dist_meters
                        FROM intersections
                        WHERE intersection_id = :id
                    """),
                    {"geom": primary_geom_json, "id": vid_intersection_id},
                ).first()

                dist_m = float(dist_res.dist_meters) if dist_res and dist_res.dist_meters is not None else 99999.0
                if dist_m <= 500.0:
                    is_associated = True
                    association_reason = (
                        f"Video intersection '{int_row.name}' is within {round(dist_m)}m of the route corridor."
                    )
                else:
                    is_associated = False
                    association_reason = (
                        f"Video intersection '{int_row.name}' is {round(dist_m / 1000.0, 1)}km away from the route. "
                        f"Video observations cannot be substituted for unrelated route traffic."
                    )
            else:
                is_associated = False
                association_reason = (
                    "Video recording location could not be resolved against registered intersections. "
                    "Video analysis is available independently, but cannot be combined with this specific route."
                )

    # 4. Integrated summary if associated
    integrated_summary: dict[str, Any] = {}
    if is_associated:
        integrated_summary = {
            "corridor_status": "INTEGRATED_VISION_TELEMETRY",
            "video_vehicles_observed": video_result.total_vehicles_detected,
            "video_measured_speed": video_result.average_speed,
            "video_measured_density": video_result.density,
            "video_congestion_level": video_result.congestion_level,
            "combined_ai_confidence": video_result.ai_prediction.get("prediction_confidence")
            if video_result.ai_prediction
            else None,
            "traffic_note": (
                f"Real-time video feed at {vid_intersection_id} detected {video_result.total_vehicles_detected} vehicles "
                f"traveling at an average of {video_result.average_speed} km/h (density: {video_result.density:.2f}). "
                f"Corridor congestion level is confirmed as {video_result.congestion_level}."
            ),
        }
    else:
        integrated_summary = {
            "corridor_status": "DISCONNECTED",
            "reason": association_reason,
            "advice": (
                "Keep using Route Intelligence and Video Analysis independently, "
                "or associate the video with an intersection that actually lies on this corridor."
            ),
        }

    return CombinedAnalysisResponse(
        is_associated=is_associated,
        association_reason=association_reason,
        route_analysis=route_result,
        video_analysis=video_result,
        integrated_traffic_summary=integrated_summary,
    )
