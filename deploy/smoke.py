"""Disposable-stack checks, including a prediction fixture and optional video."""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--providers", action="store_true")
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    results = {}
    with httpx.Client(base_url=args.base_url.rstrip('/'), timeout=60, follow_redirects=True) as client:
        for path in ("/health/ready", "/intersections", "/roads", "/prediction/models", "/alert-rules"):
            response = client.get(path)
            response.raise_for_status()
            results[path] = response.status_code
        response = client.post('/prediction/', json={"total_vehicles": 12, "average_speed": 30, "density": 0.4})
        response.raise_for_status()
        results['prediction_fixture'] = response.status_code
        route = client.post('/analysis/route', json={"origin": {"lat": 13.0827, "lng": 80.2707},
                            "destination": {"lat": 13.0824, "lng": 80.2755}, "include_alternatives": False})
        route.raise_for_status()
        results['route'] = route.status_code
        if args.providers:
            # The aggregate endpoint correctly prefers a fresh Kafka/Redis frame.
            # Probe TomTom directly so streaming verification cannot mask Flow.
            live = client.get('/live-traffic/tomtom')
            live.raise_for_status()
            assert live.json()['status'] == 'ACTIVE' and live.json()['junctions'], 'Expected real provider flow'
            incidents = client.get('/live-traffic/incidents')
            incidents.raise_for_status()
            results['tomtom_flow'] = live.json()['status']
            results['tomtom_incidents'] = incidents.json()['count']
            status = client.get('/health/integrations').json()
            assert status['components']['osrm']['status'] == 'available', 'OSRM real route not verified'
            results['osrm'] = 'available'
        if args.video:
            with args.video.open('rb') as video:
                upload = client.post('/analysis/video/upload', files={'file': (args.video.name, video, 'video/mp4')})
            upload.raise_for_status()
            job_id = upload.json()['job_id']
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                job = client.get(f'/analysis/video/{job_id}').json()
                if job['status'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
                    break
                time.sleep(1)
            assert job['status'] == 'COMPLETED', f"Video job ended in {job['status']}"
            results['video'] = 'COMPLETED'
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
