import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.core import get_core
from app.main import create_app
from app.providers.api_provider import ApiProvider
from app.providers.batch_provider import BatchProvider


def test_api_provider_mock():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'[{"a": 1}, {"b": 2}]'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp):
        p = ApiProvider("api", "http://example.com/data")
        obs = p.fetch()
        assert len(obs) == 2
        assert obs[0].source == "http://example.com/data"


def test_batch_provider_csv(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n3,4\n")
    p = BatchProvider("batch", f)
    obs = p.fetch()
    assert len(obs) == 2
    assert obs[0].payload["a"] == "1"


def test_batch_provider_json(tmp_path):
    f = tmp_path / "data.json"
    f.write_text(json.dumps([{"x": 1}, {"x": 2}]))
    p = BatchProvider("batch", f)
    obs = p.fetch()
    assert len(obs) == 2


def test_batch_provider_missing():
    p = BatchProvider("batch", "/tmp/nope_xyz.csv")
    try:
        p.fetch()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_route_providers():
    core = get_core()
    core.register_provider("prov", ApiProvider("prov", "http://example.com"))
    client = TestClient(create_app())
    r = client.get("/api/providers")
    assert r.status_code == 200
    assert "prov" in r.json()["providers"]
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'[{"a": 1}]'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_resp):
        r2 = client.post("/api/providers/prov/fetch")
        assert r2.status_code == 200
        assert r2.json()["count"] == 1
    # 404
    r3 = client.post("/api/providers/nope/fetch")
    assert r3.status_code == 404
    core.providers.unregister("prov")