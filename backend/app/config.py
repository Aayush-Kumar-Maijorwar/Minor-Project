"""Environment-backed settings. Never log or return GROQ_API_KEY."""
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    def __init__(self):
        self.groq_api_key: str = os.getenv("GROQ_API_KEY", "")
        self.groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.narrative_llm: bool = os.getenv("NARRATIVE_LLM", "0") == "1"
        artifacts_dir = os.getenv("ARTIFACTS_DIR", "./artifacts")
        self.artifacts_dir: Path = (BACKEND_DIR / artifacts_dir).resolve() if not os.path.isabs(artifacts_dir) else Path(artifacts_dir)
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]
        self.data_dir: Path = BACKEND_DIR / "data"

    @property
    def llm_enabled(self) -> bool:
        return self.narrative_llm and bool(self.groq_api_key)


def get_settings() -> Settings:
    # why: re-read env each call so tests can monkeypatch os.environ per-case
    return Settings()
