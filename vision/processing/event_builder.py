from datetime import datetime


def build_events(anomaly_events):

    events = []

    for anomaly in anomaly_events:

        events.append({
            "event_type": anomaly["event_type"],
            "severity": anomaly["severity"],
            "vehicle_id": anomaly["vehicle_id"],
            "vehicle_type": anomaly["vehicle_type"],
            "timestamp": datetime.now().isoformat()
        })

    return events