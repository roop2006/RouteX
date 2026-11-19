import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import Base, engine, SessionLocal
from .core.config import settings
from .models.traffic_event import TrafficEvent
from .models.traffic_stream_event import TrafficStreamEvent
from .models.intersection import Intersection
from .models.road_segment import RoadSegment
from .models.traffic_zone import TrafficZone
from .models.prediction_history import PredictionHistory
from .models.alert_rule import AlertRule
from .models.traffic_alert import TrafficAlert, AlertNotification

from .api.traffic import router as traffic_router
from .api.live_traffic import router as live_traffic_router
from .api.geo import router as geo_router
from .api.intersections import router as intersections_router
from .api.roads import router as roads_router
from .api.prediction import router as prediction_router
from .api.ai_live import router as ai_live_router
from .api.user_analysis import router as user_analysis_router
from .api.alerts import router as alerts_router
from .api.health import router as integration_health_router

from .services.road_network_service import ensure_arterial_network
import logging
from .core.apply_migrations import apply_integration_schema

# Keep diagnostics available even when PostgreSQL is temporarily unavailable.
try:
    Base.metadata.create_all(bind=engine)
    apply_integration_schema()
    _init_db = SessionLocal()
    try:
        from .services.alert_service import initialize_alert_rules
        initialize_alert_rules(_init_db)
        ensure_arterial_network(_init_db)
    finally:
        _init_db.close()
except Exception as exc:
    logging.getLogger(__name__).warning("Database initialization unavailable (%s); run the migration helper after restoring connectivity", type(exc).__name__)

app = FastAPI(title="RouteX API")

# HTTP client debug messages can include provider query-string credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse


@app.exception_handler(StarletteHTTPException)
async def safe_http_error(request, exc):
    if exc.status_code == 500:
        return JSONResponse(status_code=500, content={"detail": "Internal service error. Check server diagnostics."})
    return await http_exception_handler(request, exc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traffic_router)
app.include_router(live_traffic_router)
app.include_router(geo_router)
app.include_router(intersections_router)
app.include_router(roads_router)
app.include_router(prediction_router)
app.include_router(ai_live_router)
app.include_router(user_analysis_router)
app.include_router(alerts_router)
app.include_router(integration_health_router)


@app.get("/")
def root():
    return {"message": "RouteX API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/ready")
def readiness():
    from fastapi import HTTPException
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM alert_rules LIMIT 1"))
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database schema is not ready")
