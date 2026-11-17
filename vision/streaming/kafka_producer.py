import json
from datetime import datetime, timezone

from kafka import KafkaProducer

from vision.streaming.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRAFFIC_TOPIC
)


class TrafficKafkaProducer:

    def __init__(self):

        bootstrap_option = (
            "bootstrap_timeout_ms" if "bootstrap_timeout_ms" in KafkaProducer.DEFAULT_CONFIG
            else "api_version_auto_timeout_ms"
        )
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            max_block_ms=5000,
            request_timeout_ms=5000,
            **{bootstrap_option: 3000},

            value_serializer=lambda value:
                json.dumps(value).encode("utf-8")
        )

    def send_event(self, traffic_data):

        future = self.producer.send(
            TRAFFIC_TOPIC,
            value={"timestamp": datetime.now(timezone.utc).isoformat(), **traffic_data}
        )

        future.get(timeout=10)

    def close(self):

        self.producer.flush()
        self.producer.close()
