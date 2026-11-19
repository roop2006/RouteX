"""Kafka consumer with validated, retryable traffic and alert persistence."""
import json
import logging
import time
import signal
from datetime import datetime, timezone

from kafka import KafkaConsumer, TopicPartition
from pydantic import ValidationError

from backend.app.schemas.alerts import AlertEventInput
from vision.streaming.event_storage import save_traffic_event
from vision.streaming.kafka_config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_GROUP_ID, TRAFFIC_TOPIC
from vision.streaming.redis_client import TrafficRedis

logger = logging.getLogger("routex.kafka_consumer")


def kafka_message_id(topic: str, partition: int, offset: int) -> str:
    return f"{topic}:{partition}:{offset}"


def process_kafka_payload(
    payload: dict,
    message_id: str,
    *,
    redis_client: TrafficRedis | None = None,
    storage=save_traffic_event,
):
    """Validate, deduplicate, persist, alert, then publish the live cache snapshot."""
    validated = AlertEventInput.model_validate(payload)
    normalized = validated.model_dump(exclude_none=True)
    normalized.setdefault("timestamp", datetime.now(timezone.utc))
    redis_client = redis_client or TrafficRedis()

    try:
        if redis_client.get_alert_event(message_id):
            logger.info("Skipping duplicate Kafka traffic event %s", message_id)
            return None
    except Exception as exc:
        logger.info("Kafka Redis dedup unavailable; PostgreSQL alert idempotency remains active: %s", exc)

    stored = storage(normalized, source_event_id=message_id)

    latest = {
        **normalized,
        "source": normalized["source"],
        "timestamp": (validated.timestamp or stored.timestamp).isoformat(),
        "status": "ACTIVE",
    }
    try:
        redis_client.set_latest(latest)
        redis_client.set_alert_event(message_id, ttl_seconds=86400)
    except Exception as exc:
        # PostgreSQL alert/event persistence is authoritative; Redis is only a fast path.
        logger.warning("Kafka event persisted but Redis update failed: %s", exc)
    return stored


class TrafficKafkaConsumer:
    def __init__(self):
        self.consumer = KafkaConsumer(
            TRAFFIC_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=None,
            request_timeout_ms=10000,
            consumer_timeout_ms=-1,
        )
        self.redis = TrafficRedis()

    def consume(self):
        logger.info("RouteX Kafka alert consumer started: topic=%s group=%s", TRAFFIC_TOPIC, KAFKA_GROUP_ID)
        for message in self.consumer:
            message_id = kafka_message_id(message.topic, message.partition, message.offset)
            try:
                payload = json.loads(message.value.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Kafka traffic event must be a JSON object")
                process_kafka_payload(payload, message_id, redis_client=self.redis)
                self.consumer.commit()
            except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError) as exc:
                # Poison messages are logged and skipped so they cannot block the partition forever.
                logger.error("Discarding invalid Kafka traffic event %s: %s", message_id, exc)
                self.consumer.commit()
            except Exception:
                logger.exception("Kafka event failed; retrying message %s", message_id)
                partition = TopicPartition(message.topic, message.partition)
                self.consumer.seek(partition, message.offset)
                time.sleep(1.0)

    def close(self):
        self.consumer.close()
        try:
            self.redis.client.close()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # SystemExit unwinds the loop and closes the consumer on Docker SIGTERM.
    def stop_consumer(_signum, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop_consumer)
    consumer = TrafficKafkaConsumer()
    try:
        consumer.consume()
    finally:
        consumer.close()
