"""引擎单例容器：集中持有 registry / batch_registry / detector / counter / task_manager。

通过 init_engines() 一次性初始化，get_*() 在各处取用。

设计要点：registry 仅依赖 PyYAML，与 cv2/torch/ultralytics 解耦——
即便推理依赖缺失，模型管理（列表/注册/热切换）仍可正常工作，
检测/计数 API 以降级模式返回提示而非 500（见 README §环境要求）。
"""
import logging

from config import (BATCHES_YAML, DATA_DIR, LRU_CACHE_SIZE, MAX_WORKERS,
                    MODELS_DIR, MODELS_YAML)
from core.batch_registry import BatchRegistry
from core.registry import ModelRegistry
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)

registry = None
batch_registry = None
detector = None
counter = None
task_manager = None
processing_engine = None
processing_registry = None
processing_task_manager = None
dataset_registry = None
dataset_analyzer = None


def init_engines():
    """初始化全部引擎单例。

    - registry 从 models.yaml 加载配置（仅解析 YAML，不依赖 cv2/torch），
      始终优先初始化，确保模型管理/列表/注册可用；
    - batch_registry 从 batches.yaml 加载架次配置并自动扫描 data/，仅依赖
      PyYAML + Pillow，始终初始化；
    - task_manager 仅依赖标准库，同样始终初始化；
    - detector / counter 依赖 cv2/numpy/ultralytics，在独立 try/except 中
      初始化：缺失时降级（detector/counter 保持 None），仅影响检测/计数
      推理，不影响模型管理与 mock 页面。
    """
    global registry, batch_registry, detector, counter, task_manager

    # ① 模型注册中心：仅依赖 PyYAML，必须成功
    registry = ModelRegistry(str(MODELS_YAML), str(MODELS_DIR), lru_size=LRU_CACHE_SIZE)
    registry.load_from_yaml()

    # ② 架次注册中心：仅依赖 PyYAML + Pillow，必须成功
    batch_registry = BatchRegistry(DATA_DIR, BATCHES_YAML)
    batch_registry.load_from_yaml()

    # ③ 任务管理器：仅依赖标准库
    task_manager = TaskManager(max_workers=MAX_WORKERS)

    # ④ 检测/计数引擎：依赖 cv2/numpy/ultralytics，缺失时降级
    try:
        from core.counter import CountingEngine
        from core.detector import DetectionEngine
        detector = DetectionEngine(registry)
        counter = CountingEngine(detector, task_manager)
    except Exception as exc:
        logger.warning(
            "检测/计数引擎初始化失败（推理功能不可用，模型管理正常）：%s", exc
        )

    # ⑤ 处理引擎：依赖 cv2/numpy，缺失时降级
    global processing_engine, processing_registry, processing_task_manager
    try:
        from core.processing_engine import ProcessingEngine
        from core.processing_registry import ProcessingRegistry
        processing_engine = ProcessingEngine()
        processing_registry = ProcessingRegistry()
        processing_registry.load_from_yaml()
        processing_task_manager = TaskManager(max_workers=1)
    except Exception as exc:
        logger.warning("处理引擎初始化失败（数据处理功能不可用）：%s", exc)

    # ⑥ 数据集注册中心 + 分析器：仅依赖 PyYAML + Pillow + stdlib，必须成功
    global dataset_registry, dataset_analyzer
    try:
        from core.dataset_registry import DatasetRegistry
        from core.dataset_analyzer import DatasetAnalyzer
        from config import DATASETS_DIR, DATASETS_YAML
        dataset_registry = DatasetRegistry(DATASETS_DIR, DATASETS_YAML)
        dataset_analyzer = DatasetAnalyzer(registry=dataset_registry)
        dataset_registry.set_analyzer(dataset_analyzer)
        dataset_registry.load_from_yaml()
    except Exception as exc:
        logger.warning("数据集引擎初始化失败：%s", exc)


def get_registry():
    return registry


def get_batch_registry():
    return batch_registry


def get_detector():
    return detector


def get_counter():
    return counter


def get_task_manager():
    return task_manager


def get_processing_engine():
    return processing_engine


def get_processing_registry():
    return processing_registry


def get_processing_task_manager():
    return processing_task_manager


def get_dataset_registry():
    return dataset_registry


def get_dataset_analyzer():
    return dataset_analyzer
