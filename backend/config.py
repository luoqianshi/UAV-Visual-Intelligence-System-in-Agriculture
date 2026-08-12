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

# ── 数据管理（架次注册）─────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
BATCHES_YAML = DATA_DIR / "batches.yaml"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_IMAGES_PER_BATCH = 2000
MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
THUMBNAIL_MAX_SIZE = 400
PREVIEW_MEDIUM_SIZE = 1920
CROP_NAME_MAP = {"sugarcane": "甘蔗", "corn": "玉米", "wheat": "小麦", "rice": "水稻"}
DEFAULT_DRONE_MODEL = "DJI Mavic 3 M"
DEFAULT_OVERLAP_FRONT = 0.8
DEFAULT_OVERLAP_SIDE = 0.7

HOST = "0.0.0.0"
PORT = 5000
DEBUG = True
MAX_WORKERS = 1       # PRD: 并发=1
LRU_CACHE_SIZE = 3    # 引擎实例缓存上限

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 数据处理（模块二）─────────────────────────────────────────────
OUTPUT_DIR = PROJECT_ROOT / "output"
PROCESSING_TASKS_YAML = DATA_DIR / "processing_tasks.yaml"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
