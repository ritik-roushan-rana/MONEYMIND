# backend/config.py

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loads GEMINI_API_KEY (and any overrides below) from the repo-root .env,
# same convention the ml/src/scripts use.
load_dotenv(REPO_ROOT / ".env")


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


ML_SRC_PATH = _env_path("ML_SRC_PATH", REPO_ROOT / "ml" / "src")
DATA_DIR = _env_path("DATA_DIR", REPO_ROOT / "ml" / "data" / "processed" / "accounts")
JOBS_DB_PATH = _env_path("JOBS_DB_PATH", REPO_ROOT / "ml" / "data" / "processed" / "jobs.db")

# How the pre-trained M1 model participates at inference time (open question
# #1 in the spec — see backend/README.md):
#   "off"      -> never called; existing/rule/LLM categories are final
#   "fallback" -> only rows still labeled "Other" after rules + LLM get an
#                 M1 prediction
M1_INFERENCE_MODE = os.environ.get("M1_INFERENCE_MODE", "fallback").strip().lower()

ALLOWED_EXTENSIONS = {".csv", ".pdf"}


def ensure_ml_src_on_path() -> None:
    """The pipeline modules import each other as top-level packages
    (`from ingestion.schema import ...`), so ml/src itself must be on
    sys.path — not the repo root."""
    p = str(ML_SRC_PATH)
    if p not in sys.path:
        sys.path.insert(0, p)


ensure_ml_src_on_path()
