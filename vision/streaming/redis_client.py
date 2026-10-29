import json

import redis


class TrafficRedis:

    def __init__(
        self,
        host="localhost",
        port=6379
    ):

        self.client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            retry_on_timeout=False
        )

    def set_latest(
        self,
        traffic_data
    ):

        self.client.set(
            "routex:traffic:latest",
            json.dumps(traffic_data)
        )

    def get_latest(self):

        data = self.client.get(
            "routex:traffic:latest"
        )

        if data is None:
            return None

        return json.loads(data)