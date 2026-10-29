from datetime import datetime

from vision.config import CAMERA_CONFIG
from vision.streaming.kafka_producer import (
    TrafficKafkaProducer
)


producer = TrafficKafkaProducer()

event = {
    "timestamp": datetime.now().isoformat(),

    "total_vehicles": 25,

    "vehicle_types": {
        "car": 18,
        "motorcycle": 5,
        "truck": 2
    },

    "lane_counts": {
        "Lane 1": 10,
        "Lane 2": 15
    },

    "direction_counts": {
        "toward_camera": 15,
        "away_from_camera": 10
    },

    "average_speed": 24.5,

    "density": 0.83,

    "congestion_level": "HIGH",

    "events": [],

    **CAMERA_CONFIG
}

producer.send_event(event)

producer.close()

print("Traffic event sent to Kafka")
