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
)


def apply_migrations():
    print("Applying RouteX database migrations (non-destructive)...")
    Base.metadata.create_all(bind=engine)
    print("Migrations applied successfully. All tables verified.")


if __name__ == "__main__":
    apply_migrations()
