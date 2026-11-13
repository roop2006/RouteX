import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import Base, engine, SessionLocal
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
from .services.traffic_ingestion_service import seed_corridor_historical_observations

Base.metadata.create_all(bind=engine)

# Ensure arterial road network and verified baseline corridor observations are initialized
try:
    _init_db = SessionLocal()
    try:
        from .services.alert_service import initialize_alert_rules
        initialize_alert_rules(_init_db)
        ensure_arterial_network(_init_db)
        seed_corridor_historical_observations(_init_db)
    finally:
        _init_db.close()
except Exception:
    pass

app = FastAPI(title="RouteX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8001",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
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
