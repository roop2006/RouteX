# RouteX — AI-Powered Intelligent Traffic Management & Route Analysis

RouteX is an intelligent traffic management and route analysis platform combining computer vision vehicle tracking, historical traffic analytics, real-time live traffic telemetry from TomTom APIs, PostGIS spatial route corridor evaluation, and machine learning traffic forecasting.

See the [Phase 9 integration repair report](docs/PHASE9_INTEGRATION_REPORT.md) for current verification, service startup commands, changed files, and operating limitations (2026-11-15).

---

## Key Features

1. **TomTom Live Traffic Integration**:
   - Real-time road flow speeds, free-flow speeds, travel times, and congestion factors.
   - Live traffic incidents (stationary traffic, accidents, road works) with delays and descriptions.
   - Coordinate-rounded TTL caching and request sampling to respect developer allowances.
   - Credential-secure map tile proxying without exposing API keys to the frontend.
2. **Origin-to-Destination Route Intelligence**:
   - Real road routing via OSRM with OpenStreetMap tiles.
   - Dynamic corridor analysis matching road segments and intersections within 350m in PostGIS.
   - Automated TomTom flow & incident observation ingestion for queried routes.
   - Multi-route alternative evaluation with evidence-based ranking and incident alerts.
3. **Computer Vision Traffic Analysis**:
   - YOLO object detection and ByteTrack vehicle tracking on uploaded or sample traffic videos.
   - Full annotated MP4 video recording with HUD overlays and streaming endpoint.
   - Direct persistence of video-derived observations into PostGIS when tied to an intersection.
4. **Machine Learning Congestion Forecasting**:
   - 15-feature production predictor (`TrafficPredictor`) evaluating volume, velocity, density, time components, and lag dynamics.
   - Separate 9-feature model for historical interstate benchmark evaluation.
5. **Interactive React 19 Dashboard**:
   - Built with Vite, TypeScript, TailwindCSS, Lucide icons, and React Leaflet.
   - Layer toggles for intersections, roads, zones, and live TomTom flow / incident tiles.

---

## Architecture & Technology Stack

- **Backend**: FastAPI (Python 3.12), SQLAlchemy, PostGIS (PostgreSQL 18.6 on port 5434), Redis (port 6379)
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS, React Leaflet, Recharts, TanStack Query
- **ML / Vision**: scikit-learn, joblib, OpenCV, Ultralytics YOLOv8, ByteTrack
- **External Data**: TomTom Traffic API (Flow Segment v4, Incidents v5, Orbis Tiles v1/v2), OSRM Driving Engine, OpenStreetMap

---

## Getting Started

### 1. Environment Configuration

Ensure `.env` contains:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5434/routex_db
TOMTOM_API_KEY=your_tomtom_api_key_here
```

### 2. Backend Startup
```bash
uvicorn backend.app.main:app --reload --port 8001
```

### 3. Frontend Startup
```bash
cd frontend
npm install
npm run dev
```

### 4. Running Verification Tests
```bash
.\.venv\Scripts\python -m pytest
npm --prefix frontend run lint
npm --prefix frontend run build
```

For detailed TomTom architecture and endpoint specifications, see [docs/TOMTOM_INTEGRATION.md](docs/TOMTOM_INTEGRATION.md).
