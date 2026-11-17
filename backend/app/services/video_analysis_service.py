import base64
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2
from fastapi import HTTPException, UploadFile

from backend.app.core.database import SessionLocal
from backend.app.core.geo_config import POSTGIS_SRID
from backend.app.models.intersection import Intersection
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.schemas.user_analysis import (
    FrameSample,
    VideoAnalysisJobResponse,
    VideoAnalysisResult,
    VideoAnalysisStatusResponse,
)
from backend.app.services.prediction_history_service import record_prediction
from ml.prediction.predictor import TrafficPredictor
from vision.processing.anomaly_detector import AnomalyDetector
from vision.processing.congestion import calculate_density, classify_congestion
from vision.processing.direction_detector import DirectionDetector
from vision.processing.event_builder import build_events
from vision.processing.lane_detector import LaneDetector
from vision.processing.line_counter import LineCounter
from vision.processing.speed_estimator import SpeedEstimator
from vision.processing.traffic_intelligence import TrafficIntelligence
from vision.processing.traffic_processor import TrafficProcessor

logger = logging.getLogger("routex.video_analysis")
from vision.tracking.tracker import VehicleTracker

# Safe upload storage directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = _PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_VIDEO_ROOTS = (
    (_PROJECT_ROOT / "data" / "uploads").resolve(),
    (_PROJECT_ROOT / "data" / "videos").resolve(),
)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

# Thread pool for asynchronous video analysis
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="VideoAnalysisWorker")
_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def sanitize_filename(name: str) -> str:
    """Sanitize filename to avoid path traversal and invalid characters."""
    base = os.path.basename(name)
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    return sanitized or "video.mp4"


def _is_allowed_local_video_path(path: Path) -> bool:
    resolved = path.resolve()
    for root in _ALLOWED_VIDEO_ROOTS:
        if resolved == root or root in resolved.parents:
            return True
    return False


def _video_is_readable(file_path: Path) -> bool:
    cap = cv2.VideoCapture(str(file_path))
    try:
        if not cap.isOpened():
            return False
        ret, _frame = cap.read()
        return bool(ret)
    finally:
        cap.release()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            return dict(job)
        return None


def worker_status() -> dict[str, Any]:
    """Report the actual in-process job lifecycle without starting inference."""
    with _jobs_lock:
        jobs = list(_jobs.values())
    active = [job for job in jobs if job["status"] in {"PENDING", "PROCESSING"}]
    if active:
        return {"status": "healthy", "details": f"Video worker has {len(active)} queued/running job(s).", "error": None}
    if not (_PROJECT_ROOT / "yolo11n.pt").is_file():
        return {"status": "not_configured", "details": "YOLO model artifact is missing.", "error": None}
    latest = jobs[-1] if jobs else None
    if latest and latest["status"] == "FAILED":
        return {"status": "degraded", "details": "Last video job failed; worker awaits another input.", "error": latest.get("error")}
    return {"status": "idle", "details": "No video job is running; awaiting uploaded or sample video. Model artifact is present; inference is not probed by this check.", "error": None}


def cancel_job(job_id: str) -> bool:
    with _jobs_lock:
        if job_id in _jobs:
            if _jobs[job_id]["status"] in ("PENDING", "PROCESSING"):
                _jobs[job_id]["cancel_requested"] = True
                _jobs[job_id]["status"] = "CANCELLED"
                return True
    return False


async def save_and_start_video_analysis(
    upload_file: UploadFile,
    intersection_id: Optional[str] = None,
) -> VideoAnalysisJobResponse:
    """
    Validates uploaded video file, writes to isolated storage, and schedules background processing.
    """
    original_filename = sanitize_filename(upload_file.filename or "upload.mp4")
    ext = Path(original_filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    safe_stored_filename = f"{job_id}_{original_filename}"
    target_path = UPLOAD_DIR / safe_stored_filename

    # Stream chunks to disk and enforce size limit
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB
    try:
        with open(target_path, "wb") as f:
            while chunk := await upload_file.read(chunk_size):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    f.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed upload size of 100MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to store video upload: {str(exc)}")

    if total_bytes == 0:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=400, detail="Uploaded video file is empty.")

    if not _video_is_readable(target_path):
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=400,
            detail="Uploaded file could not be decoded as a supported video. The file may be corrupt or an unsupported codec.",
        )

    # Initialize job tracking state
    job_record: dict[str, Any] = {
        "job_id": job_id,
        "filename": original_filename,
        "file_path": str(target_path),
        "intersection_id": intersection_id,
        "status": "PENDING",
        "progress_percent": 0.0,
        "current_fps": 0.0,
        "frames_processed": 0,
        "total_frames": 0,
        "error": None,
        "cancel_requested": False,
        "result": None,
        "created_at": datetime.now(),
    }

    with _jobs_lock:
        _jobs[job_id] = job_record

    # Schedule background execution
    _executor.submit(_process_video_worker, job_id, str(target_path), intersection_id)

    return VideoAnalysisJobResponse(
        job_id=job_id,
        filename=original_filename,
        status="PENDING",
        message="Video uploaded successfully. Video analysis job scheduled.",
        created_at=job_record["created_at"],
    )


def start_local_video_analysis(
    video_path_str: str,
    intersection_id: Optional[str] = None,
) -> VideoAnalysisJobResponse:
    """
    Schedules analysis for a local or pre-existing server video (e.g. data/videos/traffic.mp4).
    """
    path = Path(video_path_str)
    if not path.is_absolute():
        path = (_PROJECT_ROOT / video_path_str).resolve()
    else:
        path = path.resolve()

    if not _is_allowed_local_video_path(path):
        raise HTTPException(
            status_code=400,
            detail="Local video path is outside the allowed data/videos and data/uploads directories.",
        )

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Video file not found at: {video_path_str}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format: '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_record: dict[str, Any] = {
        "job_id": job_id,
        "filename": path.name,
        "file_path": str(path),
        "intersection_id": intersection_id,
        "status": "PENDING",
        "progress_percent": 0.0,
        "current_fps": 0.0,
        "frames_processed": 0,
        "total_frames": 0,
        "error": None,
        "cancel_requested": False,
        "result": None,
        "created_at": datetime.now(),
    }

    with _jobs_lock:
        _jobs[job_id] = job_record

    _executor.submit(_process_video_worker, job_id, str(path), intersection_id)

    return VideoAnalysisJobResponse(
        job_id=job_id,
        filename=path.name,
        status="PENDING",
        message="Local sample video analysis job scheduled successfully.",
        created_at=job_record["created_at"],
    )


def _process_video_worker(job_id: str, file_path: str, intersection_id: Optional[str]) -> None:
    """
    Executes actual RouteX computer vision and intelligence pipeline on the video file.
    """
    with _jobs_lock:
        if job_id not in _jobs or _jobs[job_id]["cancel_requested"]:
            return
        _jobs[job_id]["status"] = "PROCESSING"

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        with _jobs_lock:
            _jobs[job_id]["status"] = "FAILED"
            _jobs[job_id]["error"] = f"Unable to open video file with OpenCV decoder: {Path(file_path).name}"
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    duration_seconds = total_frames / fps if total_frames > 0 else 0.0

    with _jobs_lock:
        _jobs[job_id]["total_frames"] = total_frames

    # Stride calculation: For long videos (>300 frames), step every 2 frames to optimize speed
    # while preserving YOLO tracker state continuity.
    stride = 2 if total_frames > 300 else 1

    try:
        # Initialize existing RouteX vision pipeline components
        tracker = VehicleTracker()
        processor = TrafficProcessor()
        line_counter = LineCounter(line_y=int(height * 0.55))
        anomaly_detector = AnomalyDetector()
        traffic_intelligence = TrafficIntelligence()
        speed_estimator = SpeedEstimator(pixels_per_meter=8.0)

        # Dynamic lane boundaries based on actual resolution
        w_third = width // 3
        lane_detector = LaneDetector(
            lane_boundaries=[
                (0, w_third),
                (w_third, 2 * w_third),
                (2 * w_third, width),
            ]
        )
        direction_detector = DirectionDetector()

        # Initialize VideoWriter for saving the fully processed and annotated video
        annotated_filename = f"annotated_{job_id}.mp4"
        annotated_path = UPLOAD_DIR / annotated_filename
        writer = None
        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_fps = fps if fps > 0 else 25.0
            writer = cv2.VideoWriter(str(annotated_path), fourcc, out_fps, (width, height))
        except Exception as w_err:
            writer = None

        frame_idx = 0
        processed_count = 0
        start_time = time.time()
        preview_image_b64: Optional[str] = None
        max_vehicles_seen = -1
        frame_samples: list[FrameSample] = []
        sample_interval = max(1, int(fps * 2))  # Record a sample every 2 seconds

        latest_intelligence: dict[str, Any] = {}
        latest_lane_counts: dict[str, int] = {}
        latest_directions: dict[int, str] = {}
        anomaly_events: list[dict[str, Any]] = []

        while True:
            # Check cancellation flag
            with _jobs_lock:
                if _jobs[job_id].get("cancel_requested", False):
                    cap.release()
                    if writer is not None and writer.isOpened():
                        writer.release()
                    return

            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % stride != 0 and frame_idx != 1:
                continue

            processed_count += 1

            # 1. YOLO vehicle tracking
            tracking_result = tracker.track(frame)

            # 2. Extract and count unique vehicles
            traffic_data = processor.process(tracking_result)

            # 3. Assign vehicles to lanes
            tracks, lane_counts = lane_detector.assign_lanes(traffic_data["tracks"])
            traffic_data["tracks"] = tracks
            traffic_data["lane_counts"] = lane_counts
            latest_lane_counts = lane_counts

            # 4. Vehicle direction
            tracks, directions = direction_detector.update(tracks)
            traffic_data["tracks"] = tracks
            traffic_data["directions"] = directions
            latest_directions = directions

            # 5. Speed estimation using video time, not wall-clock processing time
            video_time = frame_idx / fps if fps > 0 else processed_count
            speed_estimator.update(tracks, current_time=video_time)
            current_avg_speed = speed_estimator.get_average_speed()

            # 6. Anomalies
            anomalies = anomaly_detector.detect(tracks)
            current_events = build_events(anomalies)
            if current_events:
                anomaly_events.extend(current_events)

            # 7. Traffic intelligence analysis
            # Compute instantaneous intelligence from active vehicles currently occupying this frame
            curr_vehicle_count = len(tracks)
            instantaneous_traffic_data = {
                "tracks": tracks,
                "total_vehicles": curr_vehicle_count,
                "vehicle_types": traffic_data["vehicle_types"],
                "lane_counts": lane_counts,
            }
            latest_intelligence = traffic_intelligence.analyze(
                instantaneous_traffic_data,
                average_speed=current_avg_speed,
                anomaly_events=current_events,
            )

            # 8. Virtual line counter
            line_counter.update(tracks)

            # 9. Render annotations on frame and write to annotated video
            annotated_frame = tracking_result.plot()
            cv2.putText(
                annotated_frame,
                f"RouteX AI Vision | Active Vehicles: {curr_vehicle_count} | Velocity: {round(current_avg_speed, 1)} km/h",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 0),
                2,
            )
            if writer is not None and writer.isOpened():
                writer.write(annotated_frame)

            # Capture annotated thumbnail preview of frame with high activity
            if curr_vehicle_count > max_vehicles_seen or preview_image_b64 is None:
                max_vehicles_seen = curr_vehicle_count
                try:
                    # Resize thumbnail to save memory
                    thumb = cv2.resize(annotated_frame, (640, int(640 * height / width)))
                    _, buffer = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    preview_image_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"
                except Exception:
                    pass

            # Record periodic time-series sample
            if frame_idx % sample_interval == 0 or frame_idx == total_frames:
                sec = round(frame_idx / fps, 1)
                frame_samples.append(
                    FrameSample(
                        second=sec,
                        frame_index=frame_idx,
                        vehicles_in_frame=curr_vehicle_count,
                        density=round(latest_intelligence.get("density", 0.0), 3),
                        speed=round(current_avg_speed, 1),
                    )
                )

            # Update progress state periodically
            if processed_count % 5 == 0 or frame_idx >= total_frames:
                elapsed = time.time() - start_time
                current_fps = processed_count / elapsed if elapsed > 0 else 0.0
                pct = min(99.0, (frame_idx / total_frames) * 100.0) if total_frames > 0 else 50.0
                with _jobs_lock:
                    _jobs[job_id]["progress_percent"] = round(pct, 1)
                    _jobs[job_id]["frames_processed"] = frame_idx
                    _jobs[job_id]["current_fps"] = round(current_fps, 1)

        cap.release()
        if writer is not None and writer.isOpened():
            writer.release()

        with _jobs_lock:
            if _jobs[job_id].get("cancel_requested", False):
                return

        # Final aggregated metrics from genuine pipeline components
        total_unique_vehicles = processor.counter.get_total()
        vehicle_types = processor.counter.get_type_counts()
        line_crossing_counts = line_counter.get_type_counts()
        line_crossing_total = len(line_counter.counted_ids)
        final_speed = speed_estimator.get_average_speed()
        if frame_samples:
            final_density = round(sum(s.density for s in frame_samples) / len(frame_samples), 2)
        else:
            final_density = round(calculate_density(len(tracks) if 'tracks' in locals() else 0), 2)
        final_congestion = classify_congestion(final_density, final_speed)

        direction_counts = {
            "toward_camera": sum(1 for d in latest_directions.values() if d == "toward_camera"),
            "away_from_camera": sum(1 for d in latest_directions.values() if d == "away_from_camera"),
            "unknown": sum(1 for d in latest_directions.values() if d not in ("toward_camera", "away_from_camera")),
        }

        # Integrate existing AI / ML prediction pipeline using real observation metrics
        ai_prediction_result: Optional[dict[str, Any]] = None
        now = datetime.now()
        try:
            predictor = TrafficPredictor()
            ai_input = {
                "total_vehicles": total_unique_vehicles,
                "average_speed": round(final_speed, 1),
                "density": round(final_density, 2),
                "hour": now.hour,
                "day_of_week": now.weekday(),
                "minute": now.minute,
            }
            raw_prediction = predictor.predict(ai_input)
            ai_prediction_result = {
                "model_name": "routex_production_predictor",
                "predicted_congestion": raw_prediction.get("predicted_congestion"),
                "prediction_confidence": raw_prediction.get("prediction_confidence"),
                "predicted_vehicle_count": raw_prediction.get("predicted_vehicle_count"),
                "input_features": ai_input,
                "forecast_horizon": "next_observation_step",
            }

            # Persist observation only when the video is explicitly tied to a real intersection
            associated_intersection = (intersection_id or "").strip()
            if associated_intersection and associated_intersection not in {"STANDALONE_CAMERA"}:
                try:
                    db = SessionLocal()
                    try:
                        record_prediction(
                            db=db,
                            model_name="routex_production_predictor",
                            predicted_value=raw_prediction.get("predicted_vehicle_count", 0.0),
                            forecast_target="total_vehicles",
                            forecast_horizon="video_analysis_forecast",
                            model_version="v1.0.0",
                            predicted_congestion=raw_prediction.get("predicted_congestion"),
                            prediction_confidence=raw_prediction.get("prediction_confidence"),
                            intersection_id=associated_intersection,
                            input_features=ai_input,
                            prediction_timestamp=now,
                        )

                        # Look up intersection to extract genuine coordinates and store observation in PostGIS
                        inter = (
                            db.query(Intersection)
                            .filter(Intersection.intersection_id == associated_intersection)
                            .first()
                        )
                        if inter:
                            loc_point = WKTElement(f"POINT({inter.longitude} {inter.latitude})", srid=POSTGIS_SRID)
                            video_event = TrafficStreamEvent(
                                total_vehicles=total_unique_vehicles,
                                vehicle_types=vehicle_types,
                                lane_counts=latest_lane_counts,
                                direction_counts=direction_counts,
                                average_speed=round(final_speed, 1),
                                density=round(final_density, 3),
                                congestion_level=final_congestion,
                                events=[{
                                    "source": "video_analysis",
                                    "job_id": job_id,
                                    "filename": _jobs[job_id]["filename"],
                                    "duration_seconds": round(duration_seconds, 2),
                                    "processed_at": now.isoformat(),
                                }],
                                intersection_id=associated_intersection,
                                latitude=inter.latitude,
                                longitude=inter.longitude,
                                location=loc_point,
                                timestamp=now,
                            )
                            db.add(video_event)
                            db.commit()
                            try:
                                from backend.app.services.alert_service import process_alert_event
                                process_alert_event(db, {
                                    "source": "video_analysis",
                                    "source_event_id": f"video:{job_id}",
                                    "timestamp": now,
                                    "intersection_id": associated_intersection,
                                    "latitude": inter.latitude,
                                    "longitude": inter.longitude,
                                    "total_vehicles": total_unique_vehicles,
                                    "average_speed": round(final_speed, 1),
                                    "density": round(final_density, 3),
                                    "congestion_level": final_congestion,
                                    "anomaly_detected": bool(anomaly_events),
                                    "events": [
                                        {"source": "video_analysis", "job_id": job_id},
                                        *[item for item in anomaly_events if isinstance(item, dict)],
                                    ],
                                })
                            except Exception as alert_error:
                                logger.warning("Video observation stored; alert evaluation skipped: %s", alert_error)
                    finally:
                        db.close()
                except Exception:
                    pass
        except Exception as pred_err:
            ai_prediction_result = {
                "status": "PREDICTION_SKIPPED",
                "reason": f"AI model inference error: {str(pred_err)}",
            }

        # Check if annotated video file was generated
        annotated_url = (
            f"/analysis/video/{job_id}/stream"
            if annotated_path.exists() and annotated_path.stat().st_size > 0
            else None
        )

        with _jobs_lock:
            _jobs[job_id]["annotated_video_path"] = str(annotated_path) if annotated_url else None
            _jobs[job_id]["annotated_video_url"] = annotated_url

        # Build final completed result object
        result = VideoAnalysisResult(
            job_id=job_id,
            filename=_jobs[job_id]["filename"],
            total_frames=total_frames,
            processed_frames=processed_count,
            duration_seconds=round(duration_seconds, 2),
            fps=round(fps, 2),
            total_vehicles_detected=total_unique_vehicles,
            vehicle_types=vehicle_types,
            lane_counts=latest_lane_counts,
            direction_counts=direction_counts,
            line_crossing_counts=line_crossing_counts,
            line_crossing_total=line_crossing_total,
            average_speed=round(final_speed, 2),
            density=round(final_density, 3),
            congestion_level=final_congestion,
            anomaly_events=anomaly_events,
            frame_samples=frame_samples,
            preview_image_base64=preview_image_b64,
            annotated_video_url=annotated_url,
            intersection_id=intersection_id,
            ai_prediction=ai_prediction_result,
            processed_at=datetime.now(),
        )

        with _jobs_lock:
            if _jobs[job_id].get("cancel_requested", False):
                return
            _jobs[job_id]["status"] = "COMPLETED"
            _jobs[job_id]["progress_percent"] = 100.0
            _jobs[job_id]["frames_processed"] = total_frames
            _jobs[job_id]["result"] = result.model_dump()

    except Exception as exc:
        if cap.isOpened():
            cap.release()
        if writer is not None and writer.isOpened():
            writer.release()
        with _jobs_lock:
            _jobs[job_id]["status"] = "FAILED"
            _jobs[job_id]["error"] = f"Pipeline processing exception: {str(exc)}"


def get_annotated_video_path(job_id: str) -> Optional[str]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return job.get("annotated_video_path")


def get_video_job_status(job_id: str) -> VideoAnalysisStatusResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Analysis job with ID '{job_id}' not found.")

        result_obj = None
        if job.get("result"):
            result_obj = VideoAnalysisResult(**job["result"])

        return VideoAnalysisStatusResponse(
            job_id=job["job_id"],
            filename=job["filename"],
            status=job["status"],
            progress_percent=job.get("progress_percent", 0.0),
            current_fps=job.get("current_fps", 0.0),
            frames_processed=job.get("frames_processed", 0),
            total_frames=job.get("total_frames", 0),
            error=job.get("error"),
            result=result_obj,
        )
