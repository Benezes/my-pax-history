from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "simulador.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
BRAZIL_CONFIG = REPO_ROOT / "pre_inicio_brasil.md"
WORLD_CONFIG = REPO_ROOT / "contexto_mundial.md"
ENV_PATH = REPO_ROOT / ".env"
