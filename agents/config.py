import os

from agents.env import load_env

load_env()

BACKENDS = ("api", "subscription", "local")
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
DEFAULT_WORKDIR = os.environ.get("CODER_WORKDIR", "workspace")
LOCAL_BASE_URL = os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "llama3.1")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "")
LOCAL_TIMEOUT = float(os.environ.get("LOCAL_TIMEOUT", "600"))


def default_model(backend):
    return LOCAL_MODEL if backend == "local" else DEFAULT_MODEL
