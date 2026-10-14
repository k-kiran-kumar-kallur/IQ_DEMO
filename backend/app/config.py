"""Paths and settings. Values come from IQ/.env and can be overridden from the Settings screen (stored in SQLite)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # the IQ repo
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"                            # local file store (stands in for Azure Blob)
# SQLite (stands in for PostgreSQL). SQLITE_PATH in .env may be absolute or relative to the IQ repo.
DB_PATH = Path(os.getenv("SQLITE_PATH") or "data/iq.db").expanduser()
DB_PATH = DB_PATH if DB_PATH.is_absolute() else ROOT / DB_PATH
CORPUS_DIR = ROOT / "test_documents"
CORPUS_EXCLUDE = {"_reference", "README.md"}          # answer key and corpus notes are never ingested

DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# key -> (environment variable, default, is_secret)
SETTINGS = {
    "neo4j_uri": ("NEO4J_URI", "", False),
    "neo4j_username": ("NEO4J_USERNAME", "neo4j", False),
    "neo4j_password": ("NEO4J_PASSWORD", "", True),
    "neo4j_database": ("NEO4J_DATABASE", "", False),
    "llm_provider": ("LLM_PROVIDER", "gemini", False),          # gemini | none
    "gemini_api_key": ("GOOGLE_API_KEY", "", True),
    "gemini_chat_model": ("GEMINI_CHAT_MODEL", "gemini-2.5-flash", False),
    "gemini_base_url": ("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/", False),
    "embed_model": ("EMBED_MODEL", "BAAI/bge-small-en-v1.5", False),
}


def env_default(key):
    env, default, _ = SETTINGS[key]
    return os.getenv(env, default)
