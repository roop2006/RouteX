# Verified architecture

Inventory verified against the source during Phase 10 (2026-11-17).

| Component | Technology / purpose | Dependencies | Container |
|---|---|---|---|
| Dashboard | React 19, Vite 8, TypeScript; shared selected route | Same-origin `/api`, OpenStreetMap tiles | nginx unprivileged |
| API | FastAPI, SQLAlchemy, GeoAlchemy2 | PostGIS, Redis, external providers | Python 3.12 CPU runtime |
| Database | PostgreSQL 17 / PostGIS 3.5 | Persistent volume | `db` |
| Cache | Redis 7.4; latest stream, alert advisory dedup/cooldown | TTLs; persistence is authoritative in DB | `redis` |
| Broker | Kafka 4.0 KRaft | Persistent log volume, initialized topic | `kafka` |
| Consumer | Existing `TrafficKafkaConsumer` | Kafka, PostGIS, Redis; atomic event+alert writes | `consumer`, same runtime image |
| Routing | External OSRM; TomTom/PostGIS fallbacks | `OSRM_BASE_URL`; network | No local routing engine required |
| Live providers | TomTom Flow v4 and Incidents v5 | User's API key and product quotas | Inside API, bounded in-memory provider caches |
| Vision | YOLO11n, BoT-SORT, OpenCV | Pinned downloaded weights, uploaded video | Existing two-thread pool inside API |
| ML | 15-feature urban models; separate 9-feature interstate model | Existing joblib artifacts, matching sklearn version | Inside API |
| Alerts | Existing rules, route corridor matching, notification rows | Provider observations or consumer events; PostGIS | Inside API and consumer |
| Initialization | Additive schema, default rules, geographic reference entries | Healthy DB; no traffic seeding | One-shot `initialize` |

The dependency flow is shown in the root README. Kafka is not placed between TomTom and every API response: TomTom requests and video upload jobs use their existing direct paths. The live stream uses Kafka -> consumer -> PostgreSQL/Redis. Provider caches are in-process; Redis stores the latest camera stream and advisory alert keys.

## Geography and measurements

Coordinates are WGS84, GeoJSON `[longitude, latitude]`. Existing road/intersection reference definitions in `road_network_service.py` are a small Chennai demonstration inventory with simplified geometries, not a complete street survey or guaranteed authoritative speed limits. They initialize idempotently. No historical or live observations are created at startup.

Roads use a 250 m corridor, intersections/observations 350 m, and asset summaries 100 m. Nearby parallel roads may match. Full incident geometry is matched; TMC direction is retained but not verified against OSRM references. TomTom does not supply measured vehicle counts; those stay null and do not satisfy ML count inputs.

## Process and persistence boundaries

One Uvicorn worker is intentional: video job state and provider caches are in memory. Upload and annotated files persist in `uploads`, but job lookup state is lost on restart. Finish or cancel jobs before restarting. Prediction history, alerts, notifications, roads and observations persist in PostgreSQL. Kafka retains its logs and Redis uses AOF; cache keys still expire normally.

The consumer commits offsets only after processing. Kafka message identities uniquely identify observations and alerts; Redis dedup is advisory. The consumer exits on SIGTERM and Compose restarts it after a process failure. Health diagnostics distinguish idle, unavailable and unverified states; the Kafka TCP diagnostic does not certify consumer processing. Use the disposable-stack streaming check for that evidence.

## Model provenance

Urban metadata identifies the congestion random forest and linear-regression forecast, with 15 inputs. The external model is a separate random forest for the Metro Interstate Traffic Volume dataset; it is not applied to Chennai route corridors. Phase 10 packages existing bytes (SHA-256 in `deploy/assets.json`) and does not retrain. The 45 MB external joblib is shipped as a roughly 12 MB losslessly compressed file, expanded during image build. Historical datasets are unnecessary for inference and are not included.

YOLO weights are downloaded from the pinned upstream v8.3.0 asset release and verified before use. CPU PyTorch is installed explicitly. Linux runtime dependencies include FFmpeg, OpenCV native libraries, libgomp, psycopg and python-multipart, which were not all reproducible from the prior Windows package export.
