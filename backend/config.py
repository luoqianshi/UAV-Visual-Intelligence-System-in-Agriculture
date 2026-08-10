"""全局配置：路径与常量。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_DIR = PROJECT_ROOT / "config"
RESULTS_DIR = PROJECT_ROOT / "results"
MOCK_DIR = BACKEND_DIR / "mock"
MOCK_IMAGES_DIR = PROJECT_ROOT / "mock"
STATIC_DIR = BACKEND_DIR / "static"
MODELS_YAML = CONFIG_DIR / "models.yaml"

HOST = "0.0.0.0"
PORT = 5000
DEBUG = True
MAX_WORKERS = 1       # PRD: 并发=1
LRU_CACHE_SIZE = 3    # 引擎实例缓存上限

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
