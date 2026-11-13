import json
import hashlib
import os
from datetime import datetime, timezone

import redis


class TrafficRedis:

    def __init__(
        self,
        host=None,
        port=None
    ):

        self.client = redis.Redis(
            host=host or os.getenv("REDIS_HOST", "localhost"),
            port=port or int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            retry_on_timeout=False
        )

    def set_latest(self, traffic_data, ttl_seconds=60):

        self.client.set(
            "routex:traffic:latest",
            json.dumps(traffic_data),
            ex=max(1, int(ttl_seconds)),
        )

    def get_latest(self):

        data = self.client.get(
            "routex:traffic:latest"
        )

        if data is None:
            return None

        payload = json.loads(data)
        timestamp = payload.get("timestamp") if isinstance(payload, dict) else None
        if timestamp:
            try:
                recorded = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if recorded.tzinfo is None:
                    recorded = recorded.replace(tzinfo=timezone.utc)
                age_seconds = max(0, int((datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds()))
                if age_seconds > 60:
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
        return self.client.get(self._alert_key("event", event_id))

    def set_alert_event(self, event_id, ttl_seconds=86400):
        self.client.set(self._alert_key("event", event_id), "1", ex=max(1, int(ttl_seconds)))

    def get_alert_cooldown(self, scope_key):
        return self.client.get(self._alert_key("cooldown", scope_key))

    def set_alert_cooldown(self, scope_key, ttl_seconds=900):
        self.client.set(self._alert_key("cooldown", scope_key), "1", ex=max(1, int(ttl_seconds)))
