"""pytest 配置：确保 backend/ 目录在 sys.path 上，使 bare 导入生效。

测试运行方式：cd backend && python -m pytest tests/ -v
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
