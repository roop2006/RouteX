# Docker operation and verification

Run commands from the repository root. Docker Desktop must use Linux containers. Allow at least 6 GB Docker memory, 2 CPUs and 12 GB free disk for builds; 8 GB memory is preferable for simultaneous video jobs. The verified target is Linux amd64, including Windows Docker Desktop/WSL2. ARM64 is not yet verified and requires compatible CPU wheels.

## First start

1. Copy `.env.example` to `.env.docker` (PowerShell: `Copy-Item .env.example .env.docker`; POSIX: `cp .env.example .env.docker`). Preserve any native-development `.env`.
2. Set a unique URL-safe `POSTGRES_PASSWORD`. Add your own `TOMTOM_API_KEY` for live traffic. Leave it blank to verify explicit unavailable-provider behavior.
3. Run:

```sh
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps -a
```

Initial image builds need internet access to registries, package indexes and the pinned YOLO weight URL. Models are checksum-verified; training/data downloads are not required. PostgreSQL initializes PostGIS, then the one-shot application initializer creates additive schema, rules and reference geography. A one-shot Kafka volume initializer sets the broker UID ownership; topic initialization waits for a healthy broker. The API and consumer wait for initialization, and nginx waits for API readiness.

Open `http://localhost:5173`, API docs `http://localhost:8001/docs`. Browser requests use nginx `/api`, so there is no developer-specific backend hostname in the production bundle. Nested-route refreshes fall back to `index.html`. Host listeners bind only to `127.0.0.1`.

## Normal operation

```sh
docker compose --env-file .env.docker logs --tail=100 backend consumer
docker compose --env-file .env.docker restart backend consumer
docker compose --env-file .env.docker stop
docker compose --env-file .env.docker start
docker compose --env-file .env.docker down
```

`down` keeps named volumes. Do not use `down -v` on application data. The default project `routex-stack` deliberately differs from the earlier two-service `routex` project, preserving those containers and the native Windows database. Do not connect new PG17 containers directly to an existing PG18 data directory.

`postgres-data`, `kafka-data`, `redis-data` and `uploads` persist independently. In-memory video jobs are not durable across API restarts. No automatic upload deletion is enabled: uploaded and annotated videos can be sensitive and should be removed under an operator-defined retention policy after jobs finish. Never delete files while a job is running.

## Native development

Keep the existing `.env` and `.venv`. Native API command: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8001`; frontend: `npm --prefix frontend run dev`. Run `python deploy/prepare_assets.py` once if restoring artifacts in a new native checkout.

For container dependencies with native code, add `-f docker-compose.yml -f compose.dev.yml`. Optional ports are PostgreSQL 5434, Redis 6379 and Kafka 9092, all loopback-only. Stop conflicting local services or override `POSTGRES_PORT`, `REDIS_PORT`, `KAFKA_PORT`; never stop the native database without checking its users. Configure native `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:PORT/DB`, Redis and Kafka endpoints accordingly. Frontend overrides use `VITE_API_BASE_URL`; CORS uses comma-separated exact `CORS_ORIGINS`.

## Backup and restore

Avoid binary shell redirection in old Windows PowerShell. Create the archive inside the database container and copy it:

```sh
docker compose --env-file .env.docker exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/routex.dump'
docker compose --env-file .env.docker cp db:/tmp/routex.dump ./backups/routex.dump
```

Create the local `backups` directory first. Secure this dump; it may contain private observations. Back up the uploads volume separately with a trusted archive tool after stopping video jobs. For restoration, create a **new empty database**; copy the dump into its container and run `pg_restore --no-owner --no-acl -U USER -d NEW_DB /tmp/routex.dump`. Never restore over existing production tables or add `--clean` casually. Match PostgreSQL client/server versions; a PG18 native dump requires a compatible target (do not assume downgrade to PG17 works).

## Isolated automated tests

Use a separate project and alternate host ports in a separate env file copied from the template. All tests must use disposable database volumes; older tests persist fixtures.

```sh
docker compose --env-file .env.test -p routex-test -f docker-compose.yml -f compose.test.yml build backend frontend tests
docker compose --env-file .env.test -p routex-test up -d
docker compose --env-file .env.test -p routex-test -f docker-compose.yml -f compose.test.yml run --rm tests
docker compose --env-file .env.test -p routex-test -f docker-compose.yml -f compose.test.yml run --rm --no-deps tests python -m pip_audit
```

Tests use real PostGIS and explicitly mocked TomTom/OSRM transports (`ROUTEX_TEST_OFFLINE=1`). A generated black-frame clip is used only as a CI job-lifecycle fixture, never as real traffic evidence. The opt-in real-video streaming test is excluded from ordinary CI. No frontend test runner existed; lint, TypeScript checking, production builds, proxy checks and browser verification cover the current frontend.

For real provider checks in a disposable stack, configure credentials and run `docker compose ... exec backend python -m deploy.smoke --base-url http://frontend:8080/api --providers`. This also writes a labelled prediction test input to history. For a video you have permission to use, `docker compose ... cp YOUR_VIDEO.mp4 backend:/tmp/verification.mp4`, then:

```sh
docker compose --env-file .env.test -p routex-test exec backend python -m deploy.smoke --video /tmp/verification.mp4
docker compose --env-file .env.test -p routex-test exec backend python -m deploy.verify_stream /tmp/verification.mp4 --disposable-stack
```

The latter exercises the running consumer daemon, persistence, Redis and API using measured detections. It writes labelled verification observations, so use only a disposable stack. Repeat after restarting backend, consumer, Redis and DB; compare persistent table counts before/after. Missing credentials, provider timeouts, invalid uploads and route changes have focused regressions. Clean up **only the disposable test project** with `docker compose --env-file .env.test -p routex-test -f docker-compose.yml -f compose.test.yml down -v` after recording results.

## Troubleshooting

| Symptom | Check / action |
|---|---|
| Docker daemon unavailable | Start Docker Desktop; select Linux containers; check `docker info`. |
| Port already allocated | Change frontend/backend overrides; inspect existing listeners. Default DB/cache/broker have no host bindings. |
| DB authentication fails after changing password | Existing volumes retain the original password. Update credentials through PostgreSQL; changing an env file does not rotate it. |
| Kafka volume permission failure | Check `kafka-volume-init` exit status and broker logs; do not delete the data volume. |
| Kafka consumer stopped | Inspect logs, broker topic and database initialization; Compose restarts process failures. |
| Redis unavailable | Check its health; database paths degrade gracefully and cooldowns are advisory. |
| TomTom not configured / 401 / 403 / 429 | Set your key, check enabled Flow/Incidents products and quotas; wait for rate-limit backoff. |
| OSRM unavailable | Check `OSRM_BASE_URL` and external reachability. PostGIS fallback only covers matching registered roads. No OSRM dataset is required by the default setup. |
| Model missing / checksum failure | Rebuild from trusted tracked artifacts; verify upstream YOLO access. Never substitute an untrusted pickle. |
| Upload or video job fails | Supported extensions: MP4/AVI/MOV/MKV; 100 MB limit; codec must be decodable. Inspect worker logs and CPU/memory. |
| Request timeout | Check integration status, provider quotas and dependency health; do not increase retries without measuring. |
| Video result unavailable after restart | Job metadata is in memory; stored files remain but job lookup does not survive restart. |
