"""引擎单例容器：集中持有 registry / detector / counter / task_manager。

通过 init_engines() 一次性初始化，get_*() 在各处取用。

设计要点：registry 仅依赖 PyYAML，与 cv2/torch/ultralytics 解耦——
即便推理依赖缺失，模型管理（列表/注册/热切换）仍可正常工作，
检测/计数 API 以降级模式返回提示而非 500（见 README §环境要求）。
"""
import logging

from config import MODELS_YAML, LRU_CACHE_SIZE, MAX_WORKERS
from core.registry import ModelRegistry
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)

registry = None
detector = None
counter = None
task_manager = None


def init_engines():
    """初始化全部引擎单例。

    - registry 从 models.yaml 加载配置（仅解析 YAML，不依赖 cv2/torch），
      始终优先初始化，确保模型管理/列表/注册可用；
    - task_manager 仅依赖标准库，同样始终初始化；
    - detector / counter 依赖 cv2/numpy/ultralytics，在独立 try/except 中
      初始化：缺失时降级（detector/counter 保持 None），仅影响检测/计数
      推理，不影响模型管理与 mock 页面。
    """
    global registry, detector, counter, task_manager

    # ① 注册中心：仅依赖 PyYAML，必须成功
    registry = ModelRegistry(str(MODELS_YAML), lru_size=LRU_CACHE_SIZE)
    registry.load_from_yaml()

    # ② 任务管理器：仅依赖标准库
    task_manager = TaskManager(max_workers=MAX_WORKERS)

    # ③ 检测/计数引擎：依赖 cv2/numpy/ultralytics，缺失时降级
    try:
        from core.detector import DetectionEngine
        from core.counter import CountingEngine
        detector = DetectionEngine(registry)
        counter = CountingEngine(detector, task_manager)
    except Exception as exc:
        logger.warning(
            "检测/计数引擎初始化失败（推理功能不可用，模型管理正常）：%s", exc
        )


def get_registry():
    return registry


def get_detector():
    return detector


def get_counter():
    return counter


def get_task_manager():
    return task_manager
