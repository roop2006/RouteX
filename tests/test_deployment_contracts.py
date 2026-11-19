from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings


def test_database_readiness():
    response = TestClient(app).get('/health/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ready'}


def test_cors_does_not_allow_arbitrary_origins():
    response = TestClient(app).options('/health', headers={
        'Origin': 'https://untrusted.invalid', 'Access-Control-Request-Method': 'GET'})
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers


def test_osrm_configured_url_used(monkeypatch):
    from backend.app.services.route_analysis_service import fetch_osrm_route
    import io
    captured = []
    def response(req, **kwargs):
        captured.append(req.full_url)
        return io.BytesIO(b'{"code":"NoRoute"}')
    monkeypatch.setattr(settings, 'osrm_base_url', 'http://routing-fixture:5000')
    monkeypatch.setattr('urllib.request.urlopen', response)
    fetch_osrm_route(80.27, 13.08, 80.28, 13.09)
    assert captured[0].startswith('http://routing-fixture:5000/route/v1/driving/')
