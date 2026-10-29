import json

from kafka import KafkaProducer

from vision.streaming.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRAFFIC_TOPIC
)


class TrafficKafkaProducer:

    def __init__(self):

        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,

            value_serializer=lambda value:
                json.dumps(value).encode("utf-8")
        )

    def send_event(self, traffic_data):

        future = self.producer.send(
            TRAFFIC_TOPIC,
            value=traffic_data
        )

        future.get(timeout=10)

    def close(self):

        self.producer.flush()
        self.producer.close()