"""
Database migration and schema verification utility for RouteX.
Ensures that all tables, including prediction_history, exist without deleting or altering existing data.
"""
from backend.app.core.database import Base, engine
from backend.app.models import (
    TrafficEvent,
    TrafficStreamEvent,
    Intersection,
    RoadSegment,
    TrafficZone,
    PredictionHistory,
    AlertRule,
    TrafficAlert,
    AlertNotification,
)
from sqlalchemy import text


def apply_integration_schema():
    """Add identities and allow genuinely missing provider metrics; preserve rows."""
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE traffic_stream_events ADD COLUMN IF NOT EXISTS source_event_id VARCHAR(220)"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_stream_source_event ON traffic_stream_events(source_event_id)"))
        for column in ("total_vehicles", "average_speed", "density"):
            connection.execute(text(f"ALTER TABLE traffic_stream_events ALTER COLUMN {column} DROP NOT NULL"))


def apply_migrations():
    print("Applying RouteX database migrations (non-destructive)...")
    Base.metadata.create_all(bind=engine)
    apply_integration_schema()
    from backend.app.core.database import SessionLocal
    from backend.app.services.alert_service import initialize_alert_rules
    with SessionLocal() as db:
        initialize_alert_rules(db)
    print("Migrations applied successfully. All tables verified.")


if __name__ == "__main__":
    apply_migrations()
