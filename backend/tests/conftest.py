import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.make_fake_artifacts import make_image_and_ecg, make_tabular  # noqa: E402


@pytest.fixture(scope="session")
def fake_artifacts_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("fake_artifacts")
    make_tabular(out / "tabular")
    make_image_and_ecg(out)
    return out


@pytest.fixture()
def empty_artifacts_dir(tmp_path) -> Path:
    out = tmp_path / "empty_artifacts"
    out.mkdir()
    return out


def _fresh_app_module(artifacts_dir: Path, data_dir: Path, monkeypatch, *, narrative_llm="0", groq_key=""):
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("NARRATIVE_LLM", narrative_llm)
    monkeypatch.setenv("GROQ_API_KEY", groq_key)
    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]
    import app.main as main_mod
    from app.store import Store

    main_mod.store = Store(data_dir / "store.json")  # redirect away from the real backend/data/store.json
    return main_mod


@pytest.fixture()
def app_module(tmp_path, fake_artifacts_dir, monkeypatch):
    return _fresh_app_module(fake_artifacts_dir, tmp_path / "data", monkeypatch)


@pytest.fixture()
def no_artifacts_app_module(tmp_path, empty_artifacts_dir, monkeypatch):
    return _fresh_app_module(empty_artifacts_dir, tmp_path / "data", monkeypatch)


@pytest.fixture()
def client(app_module):
    from fastapi.testclient import TestClient

    return TestClient(app_module.app)


@pytest.fixture()
def patient_id(client) -> str:
    resp = client.post("/patients", json={"mrn": "MRN-1", "name": "Test Patient", "age": 40, "sex": "female"})
    assert resp.status_code == 200
    return resp.json()["id"]
