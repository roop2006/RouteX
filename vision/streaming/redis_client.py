import json
import hashlib
import os
import time
from datetime import datetime, timezone

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


class TrafficRedis:
    _unavailable_until = 0.0

    def __init__(
        self,
        host=None,
        port=None
    ):

        self.client = redis.Redis(
            host=host or os.getenv("REDIS_HOST", "localhost"),
            port=port or int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            retry=Retry(NoBackoff(), 0),
        )

    def _call(self, operation, *args, **kwargs):
        # redis-py defaults include retries even when retry_on_timeout=False.
        # A shared short circuit prevents one failed cache lookup per alert rule.
        if time.monotonic() < type(self)._unavailable_until:
            raise redis.ConnectionError("Redis temporarily unavailable; using persistent storage")
        try:
            return getattr(self.client, operation)(*args, **kwargs)
        except redis.RedisError:
            type(self)._unavailable_until = time.monotonic() + 15
            raise

    def set_latest(self, traffic_data, ttl_seconds=60):

        self._call("set",
            "routex:traffic:latest",
            json.dumps(traffic_data),
            ex=max(1, int(ttl_seconds)),
        )

    def get_latest(self):

        data = self._call("get",
            "routex:traffic:latest"
        )

        if data is None:
            return None

        payload = json.loads(data)
        timestamp = payload.get("timestamp") if isinstance(payload, dict) else None
        if not timestamp:
            return None
        if timestamp:
            try:
                recorded = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if recorded.tzinfo is None:
                    recorded = recorded.replace(tzinfo=timezone.utc)
                age_seconds = int((datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds())
                if age_seconds > 60 or age_seconds < -5:
                    return None
                payload["cache_age_seconds"] = age_seconds
                payload["freshness"] = "FRESH" if age_seconds <= 15 else "RECENT"
            except (TypeError, ValueError):
                return None
        return payload

    @staticmethod
    def _alert_key(namespace, value):
        token = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
        return f"routex:alerts:{namespace}:{token}"

    def get_alert_event(self, event_id):
        return self._call("get", self._alert_key("event", event_id))

    def set_alert_event(self, event_id, ttl_seconds=86400):
        self._call("set", self._alert_key("event", event_id), "1", ex=max(1, int(ttl_seconds)))

    def get_alert_cooldown(self, scope_key):
        return self._call("get", self._alert_key("cooldown", scope_key))

    def set_alert_cooldown(self, scope_key, ttl_seconds=900):
        self._call("set", self._alert_key("cooldown", scope_key), "1", ex=max(1, int(ttl_seconds)))
