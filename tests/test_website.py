import json
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import SecretStr

from quantum_primer.config import Settings
from quantum_primer.models import Answer
from quantum_primer.website import create_website


def setup_site(tmp_path):
    manifest = tmp_path / "index.json"
    manifest.write_text(json.dumps({"chunks": [
        {"source_id": "book", "title": "Test book", "author": "Author", "text": "private passage"}
    ]}))
    settings = Settings(_env_file=None, manifest_path=manifest,
                        model_api_key=SecretStr("private-model-key"))
    graph = Mock()
    graph.invoke.return_value = {"response": Answer(answer="Supported answer.",
                                                   status="answered", mode="demo")}
    return TestClient(create_website(settings, graph), base_url="http://localhost"), graph


def test_website_serves_only_safe_library_metadata(tmp_path):
    client, _ = setup_site(tmp_path)
    with client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Your knowledge guide" in page.text
        assert "private-model-key" not in page.text
        library = client.get("/api/library").json()
        assert library["sources"] == [{"id": "book", "title": "Test book", "author": "Author"}]
        assert client.get("/data/index.json").status_code == 404
        assert client.get("/.env").status_code == 404
        assert client.get("/assets/styles.css").status_code == 200


def test_website_chat_origin_validation_and_errors(tmp_path):
    client, graph = setup_site(tmp_path)
    with client:
        response = client.post("/api/ask", json={"question": "Explain this?"},
                               headers={"Origin": "http://localhost"})
        assert response.status_code == 200
        assert response.json()["answer"] == "Supported answer."
        assert client.post("/api/ask", json={"question": "Explain this?"},
                           headers={"Origin": "https://unrelated.example"}).status_code == 403
        assert client.post("/api/ask", json={"question": "  "}).status_code == 422
        graph.invoke.side_effect = RuntimeError("private-model-key")
        response = client.post("/api/ask", json={"question": "Explain this?"})
        assert response.status_code == 503
        assert "private-model-key" not in response.text
        assert client.get("/", headers={"Host": "unrelated.example"}).status_code == 400


def test_website_still_opens_when_manifest_missing(tmp_path):
    settings = Settings(_env_file=None, manifest_path=tmp_path / "missing.json")
    with TestClient(create_website(settings), base_url="http://localhost") as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/library").status_code == 503


def test_vercel_hosts_are_explicit_and_private_files_stay_private(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "quantum-primer-build.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "quantum-primer.vercel.app")
    client, graph = setup_site(tmp_path)
    for host in ["quantum-primer.vercel.app", "quantum-primer-build.vercel.app"]:
        with TestClient(client.app, base_url=f"https://{host}") as hosted:
            assert hosted.get("/").status_code == 200
            assert hosted.post("/api/ask", json={"question": "Explain this?"},
                               headers={"Origin": f"https://{host}"}).status_code == 200
            for path in ["/data/index.json", "/.env", "/assets/../data/index.json"]:
                assert hosted.get(path).status_code == 404
    assert client.get("/", headers={"Host": "another-project.vercel.app"}).status_code == 400
