"""引擎单例容器：集中持有 registry / detector / counter / task_manager。

通过 init_engines() 一次性初始化，get_*() 在各处取用。
"""
from config import MODELS_YAML, LRU_CACHE_SIZE, MAX_WORKERS
from core.registry import ModelRegistry
from core.detector import DetectionEngine
from core.counter import CountingEngine
from core.task_manager import TaskManager

registry = None
detector = None
counter = None
task_manager = None


def init_engines():
    """初始化全部引擎单例。

    - registry 从 models.yaml 加载配置（仅解析 YAML，不实例化 YOLO）；
    - task_manager / detector / counter 依次构造。
    """
    global registry, detector, counter, task_manager
    registry = ModelRegistry(str(MODELS_YAML), lru_size=LRU_CACHE_SIZE)
    registry.load_from_yaml()
    task_manager = TaskManager(max_workers=MAX_WORKERS)
    detector = DetectionEngine(registry)
    counter = CountingEngine(detector, task_manager)


def get_registry():
    return registry


def get_detector():
    return detector


def get_counter():
    return counter


def get_task_manager():
    return task_manager
