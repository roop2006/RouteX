"""Idempotent schema/reference initialization, no traffic fabrication."""
from backend.app.core.apply_migrations import apply_migrations
from backend.app.core.database import SessionLocal
from backend.app.services.road_network_service import ensure_arterial_network

if __name__ == "__main__":
    apply_migrations()
    with SessionLocal() as db:
        ensure_arterial_network(db)
    print("RouteX schema, alert rules and geographic reference data ready.")
