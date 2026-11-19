"""Explicit offline transport fixtures for CI; production code never uses them."""
import io
import json
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def offline_provider_transport():
    if os.getenv("ROUTEX_TEST_OFFLINE") != "1":
        yield
        return
    import cv2
    import numpy as np
    import httpx
    import urllib.request
    from backend.app.services.tomtom_traffic_service import tomtom_traffic_service

    patch = pytest.MonkeyPatch()
    patch.setattr(tomtom_traffic_service, "api_key", "ci-fixture-provider-key")
    def provider_get(url, params=None, **kwargs):
        if "flowSegmentData" in url:
            lat, lng = map(float, params["point"].split(','))
            body = {"flowSegmentData": {"currentSpeed": 32, "freeFlowSpeed": 48,
                    "currentTravelTime": 90, "freeFlowTravelTime": 60, "confidence": 0.9,
                    "frc": "FRC3", "roadClosure": False,
                    "coordinates": {"coordinate": [{"latitude": lat, "longitude": lng}]}}}
            return httpx.Response(200, json=body)
        if "incidentDetails" in url:
            return httpx.Response(200, json={"incidents": []})
        raise AssertionError(f"Unexpected external request in offline test: {url.split('?')[0]}")
    patch.setattr(tomtom_traffic_service._http_client, "get", provider_get)
    def urlopen(request, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if "/route/v1/driving/" in url:
            raw = url.split('/driving/')[1].split('?')[0]
            coords = [list(map(float, p.split(','))) for p in raw.split(';')]
            return io.BytesIO(json.dumps({"code": "Ok", "routes": [{"distance": 1500,
                "duration": 180, "geometry": {"type": "LineString", "coordinates": coords},
                "legs": [{"summary": "CI route fixture"}]}]}).encode())
        if "nominatim" in url:
            return io.BytesIO(b'[]')
        raise AssertionError("Unexpected external urllib request in offline tests")
    patch.setattr(urllib.request, "urlopen", urlopen)
    # This test pattern is solely an upload/job-lifecycle fixture, never live data.
    video = Path("data/videos/traffic.mp4")
    created = not video.exists()
    if created:
        video.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 12, (320, 240))
        assert writer.isOpened()
        for _ in range(24):
            writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
        writer.release()
    try:
        yield
    finally:
        patch.undo()
        # Leave the temporary test video until background fixture jobs finish.
