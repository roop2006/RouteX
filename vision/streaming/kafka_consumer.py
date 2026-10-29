import json

from kafka import KafkaConsumer

from vision.streaming.redis_client import TrafficRedis
from vision.streaming.event_storage import save_traffic_event

from vision.streaming.kafka_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRAFFIC_TOPIC,
    KAFKA_GROUP_ID,
)


class TrafficKafkaConsumer:

    def __init__(self):

        print("Creating Kafka consumer...")

        self.consumer = KafkaConsumer(
            TRAFFIC_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda value:
                json.loads(value.decode("utf-8")),
        )

        print("Kafka consumer connected.")

        self.redis = TrafficRedis()

        print("Redis client connected.")

    def consume(self):

        print("RouteX Kafka consumer started...")
        print(f"Topic: {TRAFFIC_TOPIC}")
        print(f"Group: {KAFKA_GROUP_ID}")

        for message in self.consumer:

            traffic_event = message.value

            print("\nReceived traffic event:")
            print(
                json.dumps(
                    traffic_event,
                    indent=2
                )
            )

            # Redis
            self.redis.set_latest(
                traffic_event
            )

            # PostgreSQL
            save_traffic_event(
                traffic_event
            )


if __name__ == "__main__":

    print("Starting RouteX Kafka Consumer...")

    consumer = TrafficKafkaConsumer()

    consumer.consume()
    