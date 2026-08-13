"""pytest 配置：确保 backend/ 目录在 sys.path 上，使 bare 导入生效。

测试运行方式：cd backend && python -m pytest tests/ -v
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 数据集管理模块测试用 bare 导入（dataset_formats / dataset_factory 等），
# 需将 core/ 与 tests/ 一并加入 sys.path
for _sub in ("core", "tests"):
    _d = BACKEND_DIR / _sub
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

# 测试期间重定向数据集目录到临时空目录，避免 import app → init_engines 扫描真实 SSDC-UAV
import tempfile as _tempfile
import config as _config
_DATASETS_TEST_DIR = Path(_tempfile.mkdtemp(prefix="datasets_test_"))
_config.DATASETS_DIR = _DATASETS_TEST_DIR
_config.DATASETS_YAML = _DATASETS_TEST_DIR / "datasets.yaml"
