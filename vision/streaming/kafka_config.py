import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TRAFFIC_TOPIC = os.getenv("KAFKA_TRAFFIC_TOPIC", "routex-traffic-events")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "routex-postgres-consumer")
