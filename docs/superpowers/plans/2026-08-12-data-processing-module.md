# 数据处理模块（模块二）真实实现实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PRD §3 模块二（数据处理）从 Mock 状态升级为真实功能，包含 CLAHE 增强、滑窗裁切、任务持久化、加工数据浏览（新功能）。

**Architecture:** ProcessingEngine（执行层，复用 clahe.py/tiling.py）+ ProcessingRegistry（YAML 持久化 + output/ 自扫描）+ processing_task_manager（独立异步队列，max_workers=1）+ processing_api.py（10 个端点）+ 前端 Tasks/TaskNew/TaskDetail 改造 + 新增【加工数据】双 tab。

**Tech Stack:** Flask 2.2.3、OpenCV 4.7.0.72、Pillow 9.4.0、PyYAML 6.0、Vue 3 + Composition API + Pinia + Axios + Tailwind CSS。

**Spec:** `docs/superpowers/specs/2026-08-12-data-processing-module-design.md`

---

## 文件结构总览

### 新建文件

| 路径 | 职责 |
|------|------|
| `backend/core/processing_engine.py` | 执行层：批处理 CLAHE / 裁切 |
| `backend/core/processing_registry.py` | 持久化层：YAML + output/ 自扫描 |
| `backend/tests/test_processing_engine.py` | 引擎单元测试 |
| `backend/tests/test_processing_registry.py` | 注册中心单元测试 |
| `backend/tests/test_processing_api.py` | API 单元测试 |
| `backend/tests/test_processing_integration.py` | 端到端集成测试 |
| `backend/tests/fixtures/sample_images/small_640.jpg` | 测试图（640×640） |
| `backend/tests/fixtures/sample_images/medium_1280.jpg` | 测试图（1280×960） |
| `backend/tests/fixtures/sample_images/large_2000.jpg` | 测试图（2000×1500） |
| `frontend/src/api/processing.ts` | API 客户端 |
| `frontend/src/stores/processing.ts` | Pinia store |
| `frontend/src/components/layout/DataSubTabs.vue` | 数据管理子 tab |
| `frontend/src/views/data/Processed.vue` | 加工数据列表 |
| `frontend/src/views/data/ProcessedDetail.vue` | 加工数据详情 |

### 修改文件

| 路径 | 改动 |
|------|------|
| `backend/config.py` | 新增 OUTPUT_DIR、PROCESSING_TASKS_YAML |
| `backend/core/task_manager.py` | submit() 增加 task_id 参数 |
| `backend/core/engine.py` | 新增 3 个单例 + getter |
| `backend/api/processing_api.py` | 重写：替换 Mock，10 个端点 |
| `backend/tests/test_mock_api.py` | 移除 processing 测试 |
| `backend/tests/test_task_manager.py` | 增加 task_id 参数测试 |
| `frontend/src/api/mock.ts` | 移除 ProcessingTask 类型与 fetchTasks |
| `frontend/src/stores/mock.ts` | 移除 tasks 相关逻辑 |
| `frontend/src/views/process/Tasks.vue` | 改用真实 API |
| `frontend/src/views/process/TaskNew.vue` | submit() 调用真实 API |
| `frontend/src/views/process/TaskDetail.vue` | 真实预览 + 进度轮询 |
| `frontend/src/views/data/Batches.vue` | 顶部加 DataSubTabs |
| `frontend/src/views/data/BatchNew.vue` | 顶部加 DataSubTabs |
| `frontend/src/views/data/BatchDetail.vue` | 顶部加 DataSubTabs |
| `frontend/src/router/index.ts` | 新增 2 条路由 |

### 删除文件

| 路径 |
|------|
| `backend/mock/tasks.json` |

---

## Task 1: 后端基础设施（config.py + task_manager.py 扩展）

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/core/task_manager.py`
- Test: `backend/tests/test_task_manager.py`

- [ ] **Step 1: 扩展 config.py，新增 OUTPUT_DIR 与 PROCESSING_TASKS_YAML**

修改 `backend/config.py`，在文件末尾（`DATA_DIR.mkdir(...)` 之后）追加：

```python
# ── 数据处理（模块二）─────────────────────────────────────────────
OUTPUT_DIR = PROJECT_ROOT / "output"
PROCESSING_TASKS_YAML = DATA_DIR / "processing_tasks.yaml"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: 扩展 task_manager.py，submit() 增加 task_id 参数**

修改 `backend/core/task_manager.py` 的 `submit` 方法签名与首行：

```python
def submit(self, task_type: str, func, *args, task_id: str = None, **kwargs) -> str:
    task_id = task_id or f"{task_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    self._tasks[task_id] = {"task_id": task_id, "task_type": task_type, "status": "pending",
        "progress": 0.0, "result": None, "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(), "completed_at": None}
```

其余 `_run` 内部逻辑保持不变。

- [ ] **Step 3: 为 task_manager 写 task_id 参数的测试**

在 `backend/tests/test_task_manager.py` 末尾追加测试：

```python
def test_submit_with_custom_task_id():
    """submit 支持自定义 task_id 参数。"""
    tm = TaskManager(max_workers=1)
    custom_id = "clahe_20260812_153000_456"

    def _dummy(task_id):
        return {"task_id": task_id}

    returned_id = tm.submit("processing", _dummy, task_id=custom_id)
    assert returned_id == custom_id
    # 等待任务完成
    import time
    time.sleep(0.2)
    task = tm.get(custom_id)
    assert task["task_id"] == custom_id
    assert task["status"] == "completed"
    assert task["result"] == {"task_id": custom_id}


def test_submit_without_task_id_backward_compatible():
    """不传 task_id 时仍按原逻辑生成。"""
    tm = TaskManager(max_workers=1)
    returned_id = tm.submit("test", lambda tid: None)
    assert returned_id.startswith("test_")
    assert tm.get(returned_id) is not None
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend && python -m pytest tests/test_task_manager.py -v
```

预期：所有测试通过，包含新增的 2 个测试。

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/core/task_manager.py backend/tests/test_task_manager.py
git commit -m "feat(processing): 扩展 config 与 task_manager 支持数据处理模块"
```

---

## Task 2: ProcessingEngine 执行层

**Files:**
- Create: `backend/core/processing_engine.py`
- Test: `backend/tests/test_processing_engine.py`
- Fixture: `backend/tests/fixtures/sample_images/`

- [ ] **Step 1: 生成测试 fixture 图片**

创建 `backend/tests/fixtures/sample_images/` 目录，使用 Python 生成 3 张测试图：

```bash
cd backend && python -c "
import cv2, numpy as np, os
os.makedirs('tests/fixtures/sample_images', exist_ok=True)
# 640x640 单块
img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
cv2.imwrite('tests/fixtures/sample_images/small_640.jpg', img)
# 1280x960 2x2 分块
img = np.random.randint(0, 255, (960, 1280, 3), dtype=np.uint8)
cv2.imwrite('tests/fixtures/sample_images/medium_1280.jpg', img)
# 2000x1500 4x3 分块
img = np.random.randint(0, 255, (1500, 2000, 3), dtype=np.uint8)
cv2.imwrite('tests/fixtures/sample_images/large_2000.jpg', img)
print('测试图已生成')
"
```

- [ ] **Step 2: 写 ProcessingEngine 测试（TDD）**

创建 `backend/tests/test_processing_engine.py`：

```python
"""ProcessingEngine 单元测试。"""
import json
from pathlib import Path

import pytest

from core.processing_engine import ProcessingEngine

FIXTURES = Path(__file__).parent / "fixtures" / "sample_images"


@pytest.fixture
def engine():
    return ProcessingEngine()


@pytest.fixture
def tmp_input_dir(tmp_path):
    """创建临时输入目录，复制一张测试图。"""
    import shutil
    src = FIXTURES / "small_640.jpg"
    dst_dir = tmp_path / "input_batch"
    dst_dir.mkdir()
    shutil.copy(src, dst_dir / "DJI_0001.jpg")
    shutil.copy(src, dst_dir / "DJI_0002.jpg")
    return dst_dir


def test_run_clahe_single_batch(engine, tmp_input_dir, tmp_path):
    """CLAHE 增强单架次：生成增强图与 index.json。"""
    output_dir = tmp_path / "clahe_test"
    output_dir.mkdir()
    params = {"clip_limit": 2.0, "grid_size": [8, 8]}

    result = engine.run_clahe(
        task_id="clahe_test_001",
        input_paths=[str(tmp_input_dir)],
        params=params,
        output_dir=output_dir,
    )

    assert result["total_images"] == 2
    assert result["processed_images"] == 2
    # 子目录用输入目录名
    assert len(result["sub_dirs"]) == 1
    assert result["sub_dirs"][0]["sub_dir"] == "input_batch"
    # 验证输出文件存在
    sub_dir = output_dir / "input_batch"
    assert (sub_dir / "DJI_0001.jpg").is_file()
    assert (sub_dir / "DJI_0002.jpg").is_file()


def test_run_clahe_multiple_batches(engine, tmp_path):
    """CLAHE 多架次合并处理：按架次分子目录。"""
    import shutil
    batch1 = tmp_path / "batch1"
    batch1.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", batch1 / "a.jpg")
    batch2 = tmp_path / "batch2"
    batch2.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", batch2 / "b.jpg")

    output_dir = tmp_path / "clahe_multi"
    output_dir.mkdir()
    params = {"clip_limit": 2.0, "grid_size": [8, 8]}

    result = engine.run_clahe(
        task_id="clahe_multi_001",
        input_paths=[str(batch1), str(batch2)],
        params=params,
        output_dir=output_dir,
    )

    assert result["total_images"] == 2
    assert len(result["sub_dirs"]) == 2
    assert (output_dir / "batch1" / "a.jpg").is_file()
    assert (output_dir / "batch2" / "b.jpg").is_file()


def test_run_crop_naming_convention(engine, tmp_path):
    """裁切子图命名：{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg"""
    import shutil
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "medium_1280.jpg", input_dir / "DJI_0001.JPG")

    output_dir = tmp_path / "crop_test"
    output_dir.mkdir()
    params = {"tile_size": 640, "overlap_ratio": 0.05}

    result = engine.run_crop(
        task_id="crop_test_001",
        input_paths=[str(input_dir)],
        params=params,
        output_dir=output_dir,
    )

    sub_dir = output_dir / "input"
    files = list(sub_dir.glob("*.jpg"))
    assert len(files) > 0
    # 验证命名格式
    import re
    pattern = r"^DJI_0001_tile_\d{4}_x\d+_y\d+\.jpg$"
    for f in files:
        assert re.match(pattern, f.name), f"命名不符: {f.name}"
    assert result["total_tiles"] > 0


def test_run_crop_progress_callback(engine, tmp_path):
    """裁切进度回调被正确调用。"""
    import shutil
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "a.jpg")
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "b.jpg")

    output_dir = tmp_path / "crop_progress"
    output_dir.mkdir()
    progress_calls = []

    def on_progress(processed, total):
        progress_calls.append((processed, total))

    engine.run_crop(
        task_id="crop_progress_001",
        input_paths=[str(input_dir)],
        params={"tile_size": 640, "overlap_ratio": 0.05},
        output_dir=output_dir,
        on_progress=on_progress,
    )

    assert len(progress_calls) == 2  # 2 张图
    assert progress_calls[-1] == (2, 2)


def test_write_index(engine, tmp_path):
    """write_index 生成 index.json。"""
    output_dir = tmp_path / "index_test"
    output_dir.mkdir()
    result = {
        "total_images": 2,
        "processed_images": 2,
        "output_dir": str(output_dir),
        "sub_dirs": [{"sub_dir": "batch1", "image_count": 2}],
    }
    engine.write_index(
        output_dir=output_dir,
        task_id="clahe_index_001",
        task_type="clahe",
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
        result=result,
        created_at="2026-08-12T15:30:00",
    )
    index_file = output_dir / "index.json"
    assert index_file.is_file()
    data = json.loads(index_file.read_text(encoding="utf-8"))
    assert data["task_id"] == "clahe_index_001"
    assert data["task_type"] == "clahe"
    assert data["total_images"] == 2
    assert data["sub_dirs"][0]["sub_dir"] == "batch1"


def test_collect_inputs_normalization(engine, tmp_path):
    """_collect_inputs 把路径列表归一化为 (sub_dir, [image_paths])。"""
    import shutil
    d1 = tmp_path / "batch_a"
    d1.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", d1 / "x.jpg")
    d2 = tmp_path / "batch_b"
    d2.mkdir()
    shutil.copy(FIXTURES / "small_640.jpg", d2 / "y.jpg")

    sources = engine._collect_inputs([str(d1), str(d2)])
    assert len(sources) == 2
    assert sources[0][0] == "batch_a"
    assert sources[1][0] == "batch_b"
    assert len(sources[0][1]) == 1
    assert len(sources[1][1]) == 1


def test_collect_inputs_subdir_collision(engine, tmp_path):
    """同名的输入目录会追加 _2/_3 后缀避免冲突。"""
    import shutil
    # 两个不同路径但同名目录
    p1 = tmp_path / "parent1" / "sugarcane_5m"
    p1.mkdir(parents=True)
    shutil.copy(FIXTURES / "small_640.jpg", p1 / "a.jpg")
    p2 = tmp_path / "parent2" / "sugarcane_5m"
    p2.mkdir(parents=True)
    shutil.copy(FIXTURES / "small_640.jpg", p2 / "b.jpg")

    sources = engine._collect_inputs([str(p1), str(p2)])
    assert sources[0][0] == "sugarcane_5m"
    assert sources[1][0] == "sugarcane_5m_2"


def test_error_isolation(engine, tmp_path):
    """单张图片失败不中断整体处理。"""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    # 一张正常图 + 一个非图片文件
    import shutil
    shutil.copy(FIXTURES / "small_640.jpg", input_dir / "good.jpg")
    (input_dir / "bad.txt").write_text("not an image")

    output_dir = tmp_path / "error_test"
    output_dir.mkdir()

    result = engine.run_clahe(
        task_id="err_001",
        input_paths=[str(input_dir)],
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
        output_dir=output_dir,
    )
    # .txt 不在 IMAGE_EXTENSIONS 内，会被 _collect_inputs 过滤
    assert result["total_images"] == 1
    assert result["processed_images"] == 1
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_processing_engine.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'core.processing_engine'`

- [ ] **Step 4: 实现 ProcessingEngine**

创建 `backend/core/processing_engine.py`：

```python
"""数据处理执行引擎：批处理 CLAHE / 滑窗裁切。

复用 core/clahe.py 与 core/tiling.py 的纯算法函数，叠加文件 IO 与进度上报。
不持有状态，每次调用独立；由 processing_task_manager 异步驱动。
"""
import json
import logging
from pathlib import Path

import cv2

from core import clahe, tiling
from config import IMAGE_EXTENSIONS, PROJECT_ROOT

logger = logging.getLogger(__name__)


class ProcessingEngine:
    """批处理执行器：无状态，可被 task_manager 安全驱动。"""

    def __init__(self):
        pass

    # ── 公开入口 ──────────────────────────────────────────────
    def run_clahe(self, task_id: str, input_paths: list,
                  params: dict, output_dir: Path,
                  on_progress=None) -> dict:
        """批量 CLAHE 增强。

        Args:
            task_id: 任务 ID
            input_paths: 输入源路径列表（架次文件夹路径 / 自定义目录路径）
            params: {clip_limit: float, grid_size: [int, int]}
            output_dir: output/{task_id}/ Path 对象
            on_progress: 回调 fn(processed: int, total: int)

        Returns:
            {total_images, processed_images, output_dir, sub_dirs}
        """
        clip_limit = float(params.get("clip_limit", 2.0))
        grid_size_raw = params.get("grid_size", [8, 8])
        grid_size = tuple(grid_size_raw) if isinstance(grid_size_raw, (list, tuple)) else (8, 8)

        sources = self._collect_inputs(input_paths)
        total = sum(len(imgs) for _, imgs in sources)
        processed = 0
        sub_dir_stats = []

        for sub_name, img_paths in sources:
            sub_out = output_dir / sub_name
            sub_out.mkdir(parents=True, exist_ok=True)
            sub_count = 0
            for img_path in img_paths:
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        logger.warning("跳过无法读取: %s", img_path)
                        continue
                    enhanced = clahe.enhance(img, clip_limit=clip_limit, grid_size=grid_size)
                    cv2.imwrite(str(sub_out / img_path.name), enhanced)
                    processed += 1
                    sub_count += 1
                    if on_progress:
                        on_progress(processed, total)
                except Exception as e:
                    logger.warning("处理失败 %s: %s", img_path.name, e)
            sub_dir_stats.append({"sub_dir": sub_name, "image_count": sub_count})

        return {
            "total_images": total,
            "processed_images": processed,
            "output_dir": str(output_dir),
            "sub_dirs": sub_dir_stats,
        }

    def run_crop(self, task_id: str, input_paths: list,
                 params: dict, output_dir: Path,
                 on_progress=None) -> dict:
        """批量滑窗裁切。命名：{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg
        """
        tile_size = int(params.get("tile_size", 640))
        overlap_ratio = float(params.get("overlap_ratio", 0.05))

        sources = self._collect_inputs(input_paths)
        total_images = sum(len(imgs) for _, imgs in sources)
        processed_images = 0
        total_tiles = 0
        sub_dir_stats = []

        for sub_name, img_paths in sources:
            sub_out = output_dir / sub_name
            sub_out.mkdir(parents=True, exist_ok=True)
            sub_tiles = 0
            sub_images = 0
            for img_path in img_paths:
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        logger.warning("跳过无法读取: %s", img_path)
                        continue
                    tiles = tiling.slide_window(img, tile_size, overlap_ratio)
                    seq = 0
                    for tile_img, ox, oy in tiles:
                        seq += 1
                        fname = f"{img_path.stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg"
                        cv2.imwrite(str(sub_out / fname), tile_img)
                    total_tiles += seq
                    sub_tiles += seq
                    processed_images += 1
                    sub_images += 1
                    if on_progress:
                        on_progress(processed_images, total_images)
                except Exception as e:
                    logger.warning("裁切失败 %s: %s", img_path.name, e)
            sub_dir_stats.append({
                "sub_dir": sub_name,
                "image_count": sub_images,
                "tiles_count": sub_tiles,
            })

        return {
            "total_images": total_images,
            "processed_images": processed_images,
            "total_tiles": total_tiles,
            "output_dir": str(output_dir),
            "sub_dirs": sub_dir_stats,
        }

    def write_index(self, output_dir: Path, task_id: str, task_type: str,
                    params: dict, result: dict, created_at: str) -> None:
        """写入 output/{task_id}/index.json（任务参数 + 输出统计快照）。"""
        index = {
            "task_id": task_id,
            "task_type": task_type,
            "params": params,
            "created_at": created_at,
            "total_images": result["total_images"],
            "processed_images": result["processed_images"],
            "sub_dirs": result["sub_dirs"],
        }
        if task_type == "crop":
            index["total_tiles"] = result.get("total_tiles", 0)
        (output_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── 辅助 ──────────────────────────────────────────────────
    def _collect_inputs(self, input_paths: list) -> list:
        """输入源归一化为 [(sub_dir_name, [image_paths])]。

        sub_dir_name 用源目录名；若同名则追加 _2、_3 避免冲突。
        """
        sources = []
        used_names = set()
        for p in input_paths:
            path = Path(p)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.is_dir():
                logger.warning("跳过不存在的输入路径: %s", path)
                continue
            img_paths = sorted([
                f for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            ])
            if not img_paths:
                continue
            # 处理子目录命名冲突
            base_name = path.name
            sub_name = base_name
            counter = 2
            while sub_name in used_names:
                sub_name = f"{base_name}_{counter}"
                counter += 1
            used_names.add(sub_name)
            sources.append((sub_name, img_paths))
        return sources
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_processing_engine.py -v
```

预期：所有 8 个测试通过。

- [ ] **Step 6: Commit**

```bash
git add backend/core/processing_engine.py backend/tests/test_processing_engine.py backend/tests/fixtures/
git commit -m "feat(processing): 新增 ProcessingEngine 执行层（CLAHE/crop 批处理）"
```

---

## Task 3: ProcessingRegistry 持久化层

**Files:**
- Create: `backend/core/processing_registry.py`
- Test: `backend/tests/test_processing_registry.py`

- [ ] **Step 1: 写 ProcessingRegistry 测试（TDD）**

创建 `backend/tests/test_processing_registry.py`：

```python
"""ProcessingRegistry 单元测试。"""
import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from core.processing_registry import ProcessingRegistry


@pytest.fixture
def registry(tmp_path):
    """独立 output_dir 与 yaml_path 的 registry。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()
    return reg


def test_create_task(registry, tmp_path):
    """create_task 生成 task_id 与 output_path。"""
    # 准备输入目录
    input_dir = tmp_path / "batch_input"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")  # 极简 JPEG

    cfg = registry.create_task(
        name="测试 CLAHE",
        task_type="clahe",
        input_paths=[str(input_dir)],
        params={"clip_limit": 2.0, "grid_size": [8, 8]},
    )

    assert cfg["task_id"].startswith("clahe_")
    assert cfg["name"] == "测试 CLAHE"
    assert cfg["status"] == "pending"
    assert cfg["output_path"].startswith("output/clahe_")
    assert cfg["total_images"] == 1
    assert cfg["params"]["clip_limit"] == 2.0


def test_persist_and_reload(tmp_path):
    """任务记录持久化到 YAML 并能重新加载。"""
    yaml_path = tmp_path / "processing_tasks.yaml"
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    reg1 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg1.load_from_yaml()
    input_dir = tmp_path / "batch"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = reg1.create_task("持久化测试", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    # 重新加载
    reg2 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg2.load_from_yaml()
    loaded = reg2.get_task(cfg["task_id"])
    assert loaded["name"] == "持久化测试"
    assert loaded["task_type"] == "clahe"


def test_update_task(registry, tmp_path):
    """update_task 更新字段并持久化。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("up", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    updated = registry.update_task(
        cfg["task_id"], status="processing", progress=50, processed_images=1
    )
    assert updated["status"] == "processing"
    assert updated["progress"] == 50
    assert updated["processed_images"] == 1


def test_list_tasks_filter(registry, tmp_path):
    """list_tasks 支持 type 与 status 过滤。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg1 = registry.create_task("t1", "clahe", [str(input_dir)], {"clip_limit": 2.0})
    cfg2 = registry.create_task("t2", "crop", [str(input_dir)], {"tile_size": 640})
    registry.update_task(cfg1["task_id"], status="completed")

    assert len(registry.list_tasks()) == 2
    assert len(registry.list_tasks(task_type="clahe")) == 1
    assert len(registry.list_tasks(status="completed")) == 1
    assert len(registry.list_tasks(task_type="crop", status="completed")) == 0


def test_interrupted_on_reload(tmp_path):
    """重启时 processing 状态标记为 interrupted。"""
    yaml_path = tmp_path / "tasks.yaml"
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    reg1 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg1.load_from_yaml()
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = reg1.create_task("interrupted test", "clahe", [str(input_dir)], {"clip_limit": 2.0})
    reg1.update_task(cfg["task_id"], status="processing", progress=30)

    # 重新加载
    reg2 = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg2.load_from_yaml()
    loaded = reg2.get_task(cfg["task_id"])
    assert loaded["status"] == "interrupted"
    assert "重启" in loaded["error"]


def test_auto_discover_output(tmp_path):
    """output/ 自扫描：未注册的 index.json 自动重建任务。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    # 模拟一个未注册的 output 目录
    clahe_dir = out_dir / "clahe_20260812_153000_456"
    clahe_dir.mkdir()
    (clahe_dir / "index.json").write_text(json.dumps({
        "task_id": "clahe_20260812_153000_456",
        "task_type": "clahe",
        "params": {"clip_limit": 2.0},
        "created_at": "2026-08-12T15:30:00",
        "total_images": 10,
        "processed_images": 10,
        "sub_dirs": [{"sub_dir": "batch1", "image_count": 10}],
    }), encoding="utf-8")

    yaml_path = tmp_path / "tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()

    cfg = reg.get_task("clahe_20260812_153000_456")
    assert cfg["status"] == "completed"
    assert cfg["total_images"] == 10


def test_list_processed(registry, tmp_path):
    """list_processed 返回 output/ 下所有处理产物。"""
    out_dir = tmp_path / "output"
    # 创建两个 output 子目录
    for name in ["clahe_20260812_150000_001", "crop_20260812_160000_002"]:
        d = out_dir / name
        d.mkdir(parents=True)
        (d / "index.json").write_text(json.dumps({
            "task_id": name,
            "task_type": name.split("_")[0],
            "params": {},
            "created_at": "2026-08-12T15:00:00",
            "total_images": 5,
            "processed_images": 5,
            "sub_dirs": [],
        }), encoding="utf-8")
        (d / "img.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    # 用新 registry 加载这些 output
    yaml_path = tmp_path / "tasks.yaml"
    reg = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    reg.load_from_yaml()

    items = reg.list_processed()
    assert len(items) == 2
    types = {i["task_type"] for i in items}
    assert types == {"clahe", "crop"}


def test_delete_task(registry, tmp_path):
    """delete_task 删除任务记录。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("del", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    registry.delete_task(cfg["task_id"])
    with pytest.raises(KeyError):
        registry.get_task(cfg["task_id"])


def test_delete_task_with_output(registry, tmp_path):
    """delete_task(delete_output=True) 删除 output 目录。"""
    input_dir = tmp_path / "b"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    cfg = registry.create_task("del2", "clahe", [str(input_dir)], {"clip_limit": 2.0})

    # 创建 output 目录
    out_path = tmp_path / "output" / cfg["task_id"]
    out_path.mkdir(parents=True)
    (out_path / "result.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    registry.delete_task(cfg["task_id"], delete_output=True)
    assert not out_path.exists()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_processing_registry.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'core.processing_registry'`

- [ ] **Step 3: 实现 ProcessingRegistry**

创建 `backend/core/processing_registry.py`：

```python
"""处理任务注册中心：YAML 持久化 + output/ 自扫描 + CRUD。

参考 BatchRegistry 模式：
- data/processing_tasks.yaml 持久化任务元数据
- 启动时扫描 output/ 目录，发现未注册的 index.json 自动重建任务记录
- 内存维护任务索引，支持过滤查询
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from config import IMAGE_EXTENSIONS, OUTPUT_DIR, PROCESSING_TASKS_YAML, PROJECT_ROOT

logger = logging.getLogger(__name__)

_TASK_FIELD_ORDER = [
    "task_id", "name", "task_type", "status", "progress",
    "input_paths", "output_path", "params",
    "total_images", "processed_images", "total_tiles",
    "created_at", "started_at", "completed_at", "error",
    "sub_dirs",
]


class ProcessingRegistry:
    """处理任务注册中心。"""

    def __init__(self, output_dir: Path = OUTPUT_DIR,
                 yaml_path: Path = PROCESSING_TASKS_YAML):
        self._output_dir = Path(output_dir)
        self._yaml_path = Path(yaml_path)
        self._tasks: Dict[str, dict] = {}

    # ── 加载与持久化 ──────────────────────────────────────────
    def load_from_yaml(self) -> None:
        """启动时加载：
        1. 读取 processing_tasks.yaml
        2. processing 状态的任务标记为 interrupted（重启后无法恢复进程）
        3. 扫描 output/ 目录，发现未注册的 index.json 自动补全
        """
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            tasks_list = data.get("tasks", []) or []
            for t in tasks_list:
                # 重启后处理中的任务标记为 interrupted
                if t.get("status") == "processing":
                    t["status"] = "interrupted"
                    t["error"] = "服务重启，任务被中断"
                self._tasks[t["task_id"]] = t

        # 扫描 output/ 补全未注册任务
        newly_added = self._auto_discover_output()
        if newly_added:
            self.save_to_yaml()

    def save_to_yaml(self) -> None:
        """持久化任务列表到 YAML。"""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_list = [self._ordered_config(t) for t in self._tasks.values()]
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"tasks": tasks_list}, f,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                indent=2,
                width=1000,
            )

    # ── CRUD ──────────────────────────────────────────────────
    def create_task(self, name: str, task_type: str,
                    input_paths: list, params: dict) -> dict:
        """创建任务记录。生成 task_id 与 output_path。

        task_id 格式：{task_type}_{ts}_{ms:03d}
        output_path 格式：output/{task_id}（与 task_id 完全一致）
        """
        if task_type not in ("clahe", "crop"):
            raise ValueError(f"未知任务类型: {task_type}")
        if not input_paths:
            raise ValueError("必须指定至少一个输入源")

        now = datetime.now().isoformat(timespec="seconds")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 生成唯一 task_id（同毫秒冲突时自增）
        ms = datetime.now().microsecond % 1000
        task_id = f"{task_type}_{timestamp}_{ms:03d}"
        while task_id in self._tasks:
            ms += 1
            task_id = f"{task_type}_{timestamp}_{ms:03d}"

        output_path = f"output/{task_id}"
        total_images = self._count_input_images(input_paths)

        cfg = {
            "task_id": task_id,
            "name": name,
            "task_type": task_type,
            "status": "pending",
            "progress": 0,
            "input_paths": input_paths,
            "output_path": output_path,
            "params": params,
            "total_images": total_images,
            "processed_images": 0,
            "total_tiles": 0 if task_type == "crop" else None,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "sub_dirs": [],
        }
        self._tasks[task_id] = cfg
        self.save_to_yaml()
        return cfg

    def update_task(self, task_id: str, **fields) -> dict:
        """更新任务字段。"""
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        cfg = self._tasks[task_id]
        for k, v in fields.items():
            if k in cfg:
                cfg[k] = v
        self.save_to_yaml()
        return cfg

    def get_task(self, task_id: str) -> dict:
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        return self._tasks[task_id]

    def list_tasks(self, task_type: Optional[str] = None,
                   status: Optional[str] = None) -> List[dict]:
        result = list(self._tasks.values())
        if task_type:
            result = [t for t in result if t["task_type"] == task_type]
        if status:
            result = [t for t in result if t["status"] == status]
        return sorted(result, key=lambda t: t["created_at"], reverse=True)

    def delete_task(self, task_id: str, delete_output: bool = False) -> None:
        """删除任务记录。delete_output=True 时同时删除 output 目录。"""
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        cfg = self._tasks[task_id]
        if delete_output:
            out_dir = self._resolve_path(cfg["output_path"])
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
        del self._tasks[task_id]
        self.save_to_yaml()

    # ── 加工数据列表（output 扫描）──────────────────────────────
    def list_processed(self) -> list:
        """列出 output/ 下所有处理产物。"""
        items = []
        if not self._output_dir.is_dir():
            return items
        for entry in sorted(self._output_dir.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            name = entry.name
            task_type = None
            if name.startswith("clahe_"):
                task_type = "clahe"
            elif name.startswith("crop_"):
                task_type = "crop"
            else:
                continue
            # task_id 即目录名
            task_id = name
            task_cfg = self._tasks.get(task_id, {})
            # 统计图片
            image_count = sum(
                1 for f in entry.rglob("*")
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            )
            # 读取 index.json
            index_path = entry / "index.json"
            index_data = {}
            if index_path.exists():
                try:
                    index_data = json.loads(index_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append({
                "output_path": f"output/{name}",
                "task_id": task_id,
                "task_type": task_type,
                "name": task_cfg.get("name") or index_data.get("name") or name,
                "status": task_cfg.get("status", "completed" if index_data else "unknown"),
                "params": task_cfg.get("params") or index_data.get("params", {}),
                "image_count": image_count,
                "total_tiles": index_data.get("total_tiles") or task_cfg.get("total_tiles") or 0,
                "created_at": task_cfg.get("created_at") or index_data.get("created_at", ""),
                "sub_dirs": index_data.get("sub_dirs", task_cfg.get("sub_dirs", [])),
                "has_task": task_id in self._tasks,
            })
        return items

    # ── 私有 ──────────────────────────────────────────────────
    def _auto_discover_output(self) -> bool:
        """扫描 output/ 目录，发现未注册的 index.json 自动重建任务记录。

        返回是否有新增。
        """
        if not self._output_dir.is_dir():
            return False
        newly_added = False
        for entry in sorted(self._output_dir.iterdir()):
            if not entry.is_dir():
                continue
            index_path = entry / "index.json"
            if not index_path.exists():
                continue
            name = entry.name
            if name.startswith("clahe_"):
                task_type = "clahe"
            elif name.startswith("crop_"):
                task_type = "crop"
            else:
                continue
            task_id = name  # task_id 即目录名
            if task_id in self._tasks:
                continue
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
                cfg = {
                    "task_id": task_id,
                    "name": f"{task_type} 产物 {name}",
                    "task_type": task_type,
                    "status": "completed",
                    "progress": 100,
                    "input_paths": index_data.get("input_paths", []),
                    "output_path": f"output/{name}",
                    "params": index_data.get("params", {}),
                    "total_images": index_data.get("total_images", 0),
                    "processed_images": index_data.get("processed_images", 0),
                    "total_tiles": index_data.get("total_tiles") if task_type == "crop" else None,
                    "created_at": index_data.get("created_at", ""),
                    "started_at": None,
                    "completed_at": index_data.get("created_at"),
                    "error": None,
                    "sub_dirs": index_data.get("sub_dirs", []),
                }
                self._tasks[task_id] = cfg
                newly_added = True
                logger.info("自扫描发现未注册任务: %s", task_id)
            except Exception as e:
                logger.warning("读取 %s 失败: %s", index_path, e)
        return newly_added

    def _count_input_images(self, input_paths: list) -> int:
        """统计输入源图片总数。"""
        count = 0
        for p in input_paths:
            path = self._resolve_path(p)
            if not path.is_dir():
                continue
            count += sum(
                1 for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            )
        return count

    def _resolve_path(self, path_str: str) -> Path:
        """路径解析：相对路径相对 PROJECT_ROOT。"""
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _ordered_config(self, cfg: dict) -> dict:
        """按标准字段顺序排列。"""
        ordered = {}
        for key in _TASK_FIELD_ORDER:
            if key in cfg:
                ordered[key] = cfg[key]
        for key, val in cfg.items():
            if key not in ordered:
                ordered[key] = val
        return ordered
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_processing_registry.py -v
```

预期：所有 9 个测试通过。

- [ ] **Step 5: Commit**

```bash
git add backend/core/processing_registry.py backend/tests/test_processing_registry.py
git commit -m "feat(processing): 新增 ProcessingRegistry 持久化层（YAML + output 自扫描）"
```

---

## Task 4: engine.py 集成

**Files:**
- Modify: `backend/core/engine.py`

- [ ] **Step 1: 扩展 engine.py，新增 3 个单例**

在 `backend/core/engine.py` 中：

1. 在全局变量区追加（`task_manager = None` 之后）：

```python
processing_engine = None
processing_registry = None
processing_task_manager = None
```

2. 在 `init_engines()` 函数末尾（`return` 之前如果有，或在 ④ 检测/计数引擎之后）追加：

```python
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
```

3. 在文件末尾追加 getter：

```python
def get_processing_engine():
    return processing_engine


def get_processing_registry():
    return processing_registry


def get_processing_task_manager():
    return processing_task_manager
```

- [ ] **Step 2: 验证引擎初始化**

```bash
cd backend && python -c "
from core.engine import init_engines
init_engines()
from core.engine import get_processing_engine, get_processing_registry, get_processing_task_manager
assert get_processing_engine() is not None, 'processing_engine 未初始化'
assert get_processing_registry() is not None, 'processing_registry 未初始化'
assert get_processing_task_manager() is not None, 'processing_task_manager 未初始化'
print('引擎初始化成功')
"
```

预期：输出 `引擎初始化成功`

- [ ] **Step 3: Commit**

```bash
git add backend/core/engine.py
git commit -m "feat(processing): engine.py 集成处理引擎三单例"
```

---

## Task 5: processing_api.py 重写

**Files:**
- Modify: `backend/api/processing_api.py`
- Test: `backend/tests/test_processing_api.py`

- [ ] **Step 1: 写 API 测试（TDD）**

创建 `backend/tests/test_processing_api.py`：

```python
"""processing_api 单元测试。"""
import json
import shutil
from pathlib import Path

import pytest

from backend.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """创建独立 app 实例，重定向 OUTPUT_DIR 与 PROCESSING_TASKS_YAML 到临时目录。"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"

    # monkeypatch config
    import config
    monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(config, "PROCESSING_TASKS_YAML", yaml_path)

    # 重新初始化引擎
    from core import engine
    from core.processing_engine import ProcessingEngine
    from core.processing_registry import ProcessingRegistry
    from core.task_manager import TaskManager
    engine.processing_engine = ProcessingEngine()
    engine.processing_registry = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    engine.processing_registry.load_from_yaml()
    engine.processing_task_manager = TaskManager(max_workers=1)

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def input_dir(tmp_path):
    """准备测试输入目录（含一张测试图）。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    d = tmp_path / "test_batch"
    d.mkdir()
    shutil.copy(fixtures / "small_640.jpg", d / "DJI_0001.jpg")
    return d


def test_list_tasks_empty(client):
    """空任务列表。"""
    r = client.get("/api/processing/tasks")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["total"] == 0


def test_submit_clahe(client, input_dir):
    """提交 CLAHE 任务。"""
    r = client.post("/api/processing/clahe", json={
        "name": "测试 CLAHE",
        "input_paths": [str(input_dir)],
        "params": {"clip_limit": 2.0, "grid_size": [8, 8]},
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"].startswith("clahe_")
    assert data["data"]["status"] == "pending"


def test_submit_crop(client, input_dir):
    """提交裁切任务。"""
    r = client.post("/api/processing/crop", json={
        "name": "测试裁切",
        "input_paths": [str(input_dir)],
        "params": {"tile_size": 640, "overlap_ratio": 0.05},
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["task_id"].startswith("crop_")


def test_submit_clahe_missing_input(client):
    """缺少 input_paths 时返回 400。"""
    r = client.post("/api/processing/clahe", json={
        "name": "无输入",
        "input_paths": [],
        "params": {"clip_limit": 2.0},
    })
    assert r.status_code == 400
    data = r.get_json()
    assert data["success"] is False


def test_get_task_not_found(client):
    """查询不存在的任务返回 404。"""
    r = client.get("/api/processing/tasks/nonexistent_001")
    assert r.status_code == 404
    data = r.get_json()
    assert data["success"] is False


def test_list_processed_empty(client):
    """空加工数据列表。"""
    r = client.get("/api/processing/processed")
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["data"]["total"] == 0


def test_list_tasks_with_filter(client, input_dir):
    """任务列表过滤。"""
    # 提交两个任务
    client.post("/api/processing/clahe", json={
        "name": "t1", "input_paths": [str(input_dir)], "params": {"clip_limit": 2.0}
    })
    client.post("/api/processing/crop", json={
        "name": "t2", "input_paths": [str(input_dir)], "params": {"tile_size": 640}
    })

    # 过滤 clahe
    r = client.get("/api/processing/tasks?type=clahe")
    data = r.get_json()
    assert data["data"]["total"] == 1
    assert data["data"]["tasks"][0]["task_type"] == "clahe"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_processing_api.py -v
```

预期：FAIL（现有 API 是 Mock，端点不匹配）

- [ ] **Step 3: 重写 processing_api.py**

完全替换 `backend/api/processing_api.py` 内容：

```python
"""数据处理 API：CLAHE 增强 / 滑窗裁切 任务提交 + 查询 + 预览 + 加工数据列表。

所有响应遵循统一信封：{"success": bool, "data": <data>|None, "message": str}。
"""
import io
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from config import IMAGE_EXTENSIONS, PROJECT_ROOT
from core.engine import (get_processing_engine, get_processing_registry,
                          get_processing_task_manager)

processing_bp = Blueprint("processing", __name__)


def _error(message, status_code=400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


# ── 任务提交 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/clahe", methods=["POST"])
def submit_clahe():
    """POST /api/processing/clahe → 提交 CLAHE 任务（异步）。"""
    engine = get_processing_engine()
    registry = get_processing_registry()
    tm = get_processing_task_manager()
    if engine is None or registry is None or tm is None:
        return _error("处理引擎未初始化（依赖 cv2/numpy）", 503)

    body = request.get_json(silent=True) or {}
    name = body.get("name") or "CLAHE 任务"
    input_paths = body.get("input_paths") or []
    params = body.get("params") or {}
    if not input_paths:
        return _error("必须指定 input_paths（至少一个架次或目录）")

    try:
        cfg = registry.create_task(
            name=name, task_type="clahe",
            input_paths=input_paths, params=params
        )
    except ValueError as e:
        return _error(str(e))

    _submit_async(engine, registry, tm, cfg, "clahe")
    return jsonify({"success": True, "data": cfg, "message": "任务已提交"})


@processing_bp.route("/api/processing/crop", methods=["POST"])
def submit_crop():
    """POST /api/processing/crop → 提交滑窗裁切任务（异步）。"""
    engine = get_processing_engine()
    registry = get_processing_registry()
    tm = get_processing_task_manager()
    if engine is None or registry is None or tm is None:
        return _error("处理引擎未初始化（依赖 cv2/numpy）", 503)

    body = request.get_json(silent=True) or {}
    name = body.get("name") or "裁切任务"
    input_paths = body.get("input_paths") or []
    params = body.get("params") or {}
    if not input_paths:
        return _error("必须指定 input_paths（至少一个架次或目录）")

    try:
        cfg = registry.create_task(
            name=name, task_type="crop",
            input_paths=input_paths, params=params
        )
    except ValueError as e:
        return _error(str(e))

    _submit_async(engine, registry, tm, cfg, "crop")
    return jsonify({"success": True, "data": cfg, "message": "任务已提交"})


def _submit_async(engine, registry, tm, cfg, task_type):
    """提交异步任务到 task_manager。"""
    task_id = cfg["task_id"]
    input_paths = cfg["input_paths"]
    params = cfg["params"]
    output_dir = _resolve_path(cfg["output_path"])
    output_dir.mkdir(parents=True, exist_ok=True)

    def _progress(processed, total):
        pct = int(processed / total * 100) if total else 0
        registry.update_task(
            task_id, progress=pct, processed_images=processed, status="processing"
        )

    def _run(tid):
        registry.update_task(task_id, status="processing",
                             started_at=datetime.now().isoformat(timespec="seconds"))
        try:
            if task_type == "clahe":
                result = engine.run_clahe(task_id, input_paths, params, output_dir, _progress)
            else:
                result = engine.run_crop(task_id, input_paths, params, output_dir, _progress)
            engine.write_index(
                output_dir, task_id, task_type, params, result, cfg["created_at"]
            )
            registry.update_task(
                task_id, status="completed", progress=100,
                processed_images=result["processed_images"],
                sub_dirs=result["sub_dirs"],
                total_tiles=result.get("total_tiles") if task_type == "crop" else None,
                completed_at=datetime.now().isoformat(timespec="seconds"),
            )
            return result
        except Exception as e:
            registry.update_task(task_id, status="failed", error=str(e),
                                 completed_at=datetime.now().isoformat(timespec="seconds"))
            raise

    tm.submit("processing", _run, task_id=task_id)


# ── 任务查询 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks", methods=["GET"])
def list_tasks():
    """GET /api/processing/tasks → 任务列表，支持 ?type= &status= 过滤。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    task_type = request.args.get("type")
    status = request.args.get("status")
    tasks = registry.list_tasks(task_type=task_type, status=status)
    return jsonify({
        "success": True,
        "data": {"tasks": tasks, "total": len(tasks)},
        "message": "获取任务列表成功",
    })


@processing_bp.route("/api/processing/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """GET /api/processing/tasks/<task_id> → 任务详情。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)
    return jsonify({"success": True, "data": cfg, "message": "获取任务详情成功"})


# ── 结果文件清单 ──────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks/<task_id>/files", methods=["GET"])
def list_task_files(task_id):
    """GET /api/processing/tasks/<task_id>/files?sub_dir=&page=&page_size="""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)

    sub_dir = request.args.get("sub_dir")
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(200, max(1, int(request.args.get("page_size", 50))))

    out_dir = _resolve_path(cfg["output_path"])
    target_dir = out_dir / sub_dir if sub_dir else out_dir
    if not target_dir.is_dir():
        return _error(f"目录不存在: {sub_dir or '/'}", 404)

    # 收集图片文件
    files = sorted([
        f for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ])
    total = len(files)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    paged = files[start:start + page_size]

    # 读取图片尺寸
    from PIL import Image
    result_files = []
    for f in paged:
        try:
            with Image.open(f) as im:
                width, height = im.size
            stat = f.stat()
            result_files.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "width": width,
                "height": height,
                "format": f.suffix.lstrip(".").upper(),
                "thumbnail_url": f"/api/processing/tasks/{task_id}/preview?filename={f.name}&size=thumbnail" + (f"&sub_dir={sub_dir}" if sub_dir else ""),
                "preview_url": f"/api/processing/tasks/{task_id}/preview?filename={f.name}&size=medium" + (f"&sub_dir={sub_dir}" if sub_dir else ""),
            })
        except Exception:
            continue

    return jsonify({
        "success": True,
        "data": {
            "files": result_files, "total": total,
            "page": page, "page_size": page_size, "total_pages": total_pages,
            "sub_dir": sub_dir or "",
        },
        "message": "获取文件列表成功",
    })


# ── 结果预览 ──────────────────────────────────────────────────
@processing_bp.route("/api/processing/tasks/<task_id>/preview", methods=["GET"])
def task_preview(task_id):
    """GET /api/processing/tasks/<task_id>/preview?filename=&sub_dir=&size="""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    try:
        cfg = registry.get_task(task_id)
    except KeyError as e:
        return _error(str(e), 404)

    filename = request.args.get("filename")
    if not filename:
        return _error("必须指定 filename 参数")
    sub_dir = request.args.get("sub_dir")
    size = request.args.get("size", "medium")

    out_dir = _resolve_path(cfg["output_path"])
    img_path = out_dir / sub_dir / filename if sub_dir else out_dir / filename
    if not img_path.is_file():
        return _error(f"图片不存在: {filename}", 404)

    if size == "original":
        with open(img_path, "rb") as f:
            return Response(f.read(), mimetype="image/jpeg")

    from PIL import Image
    max_size = 400 if size == "thumbnail" else 1920
    quality = 80 if size == "thumbnail" else 85
    with Image.open(img_path) as im:
        im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
        im.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return Response(buf.getvalue(), mimetype="image/jpeg")


# ── 加工数据列表 ─────────────────────────────────────────────
@processing_bp.route("/api/processing/processed", methods=["GET"])
def list_processed():
    """GET /api/processing/processed → 加工数据列表。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    items = registry.list_processed()
    return jsonify({
        "success": True,
        "data": {"items": items, "total": len(items)},
        "message": "获取加工数据列表成功",
    })


@processing_bp.route("/api/processing/processed/<processed_id>", methods=["GET"])
def get_processed(processed_id):
    """GET /api/processing/processed/<id> → 加工数据详情。"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    items = registry.list_processed()
    for item in items:
        if Path(item["output_path"]).name == processed_id:
            return jsonify({"success": True, "data": item, "message": "获取加工数据详情成功"})
    return _error(f"加工数据不存在: {processed_id}", 404)


@processing_bp.route("/api/processing/processed/<processed_id>/files", methods=["GET"])
def list_processed_files(processed_id):
    """GET /api/processing/processed/<id>/files?sub_dir=&page=&page_size="""
    # 复用 list_task_files 逻辑：processed_id 即 task_id（目录名）
    return list_task_files(processed_id)


@processing_bp.route("/api/processing/processed/<processed_id>", methods=["DELETE"])
def delete_processed(processed_id):
    """DELETE /api/processing/processed/<id>?delete_output=true"""
    registry = get_processing_registry()
    if registry is None:
        return _error("registry 未初始化", 503)
    delete_output = request.args.get("delete_output", "false").lower() == "true"
    try:
        registry.delete_task(processed_id, delete_output=delete_output)
    except KeyError as e:
        return _error(str(e), 404)
    return jsonify({"success": True, "data": None, "message": "加工数据已删除"})
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_processing_api.py -v
```

预期：所有 7 个测试通过。

- [ ] **Step 5: Commit**

```bash
git add backend/api/processing_api.py backend/tests/test_processing_api.py
git commit -m "feat(processing): 重写 processing_api（10 个端点替换 Mock）"
```

---

## Task 6: Mock 清理

**Files:**
- Delete: `backend/mock/tasks.json`
- Modify: `backend/tests/test_mock_api.py`
- Modify: `frontend/src/api/mock.ts`
- Modify: `frontend/src/stores/mock.ts`

- [ ] **Step 1: 删除 backend/mock/tasks.json**

```bash
git rm backend/mock/tasks.json
```

- [ ] **Step 2: 修改 backend/tests/test_mock_api.py**

移除所有 processing 相关测试函数（保留 datasets 部分）。删除文件中所有以 `test_processing` 或 `test_task` 开头的测试函数，以及任何导入 `processing_api` 或读取 `tasks.json` 的代码。

- [ ] **Step 3: 运行剩余 mock 测试验证**

```bash
cd backend && python -m pytest tests/test_mock_api.py -v
```

预期：仅 datasets 相关测试通过。

- [ ] **Step 4: 修改 frontend/src/api/mock.ts**

移除 `ProcessingTask` 接口、`fetchTasks`、`fetchTask` 函数。保留 `Dataset` 相关接口与函数。

- [ ] **Step 5: 修改 frontend/src/stores/mock.ts**

移除 `tasks` state、`fetchTasks` action、`taskTotal` getter 等所有 processing 相关逻辑。保留 datasets 部分。

- [ ] **Step 6: 验证前端 TypeScript 编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误（mock.ts 不再被 process 页面引用）。

- [ ] **Step 7: Commit**

```bash
git add backend/mock/ backend/tests/test_mock_api.py frontend/src/api/mock.ts frontend/src/stores/mock.ts
git commit -m "chore(processing): 清理 Mock 数据（tasks.json 与相关代码）"
```

---

## Task 7: 前端 API 客户端与 Pinia Store

**Files:**
- Create: `frontend/src/api/processing.ts`
- Create: `frontend/src/stores/processing.ts`

- [ ] **Step 1: 创建 frontend/src/api/processing.ts**

```typescript
import { apiClient } from './client'

export interface ProcessingTask {
  task_id: string
  name: string
  task_type: 'clahe' | 'crop'
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'interrupted'
  progress: number
  input_paths: string[]
  output_path: string
  params: {
    clip_limit?: number
    grid_size?: [number, number]
    tile_size?: number
    overlap_ratio?: number
  }
  total_images: number
  processed_images: number
  total_tiles: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  sub_dirs: { sub_dir: string; image_count: number; tiles_count?: number }[]
}

export interface ProcessedItem {
  output_path: string
  task_id: string
  task_type: 'clahe' | 'crop'
  name: string
  status: string
  params: Record<string, any>
  image_count: number
  total_tiles: number
  created_at: string
  sub_dirs: { sub_dir: string; image_count: number; tiles_count?: number }[]
  has_task: boolean
}

export interface TaskFile {
  filename: string
  size_bytes: number
  width: number
  height: number
  format: string
  thumbnail_url: string
  preview_url: string
}

export interface TaskFileList {
  files: TaskFile[]
  total: number
  page: number
  page_size: number
  total_pages: number
  sub_dir: string
}

function parseGrid(gridStr: string): [number, number] {
  const m = gridStr.match(/(\d+)\s*[×x]\s*(\d+)/)
  return m ? [parseInt(m[1]), parseInt(m[2])] : [8, 8]
}

export const processingApi = {
  list: (params?: { type?: string; status?: string }) =>
    apiClient.get('/api/processing/tasks', { params }),
  get: (taskId: string) =>
    apiClient.get(`/api/processing/tasks/${taskId}`),
  submitClahe: (data: { name: string; input_paths: string[]; params: { clip_limit: number; grid_size: string | [number, number] } }) => {
    const params = {
      clip_limit: data.params.clip_limit,
      grid_size: typeof data.params.grid_size === 'string'
        ? parseGrid(data.params.grid_size)
        : data.params.grid_size,
    }
    return apiClient.post('/api/processing/clahe', { name: data.name, input_paths: data.input_paths, params })
  },
  submitCrop: (data: { name: string; input_paths: string[]; params: { tile_size: number; overlap_ratio: number } }) =>
    apiClient.post('/api/processing/crop', data),
  listFiles: (taskId: string, params?: { sub_dir?: string; page?: number; page_size?: number }) =>
    apiClient.get(`/api/processing/tasks/${taskId}/files`, { params }),
  previewUrl: (taskId: string, filename: string, subDir?: string, size = 'medium') => {
    const q = new URLSearchParams({ filename, size })
    if (subDir) q.set('sub_dir', subDir)
    return `/api/processing/tasks/${taskId}/preview?${q.toString()}`
  },
  // 加工数据
  listProcessed: () =>
    apiClient.get('/api/processing/processed'),
  getProcessed: (processedId: string) =>
    apiClient.get(`/api/processing/processed/${processedId}`),
  listProcessedFiles: (processedId: string, params?: { sub_dir?: string; page?: number; page_size?: number }) =>
    apiClient.get(`/api/processing/processed/${processedId}/files`, { params }),
  deleteProcessed: (processedId: string, deleteOutput = false) =>
    apiClient.delete(`/api/processing/processed/${processedId}`, { params: { delete_output: deleteOutput } }),
}
```

- [ ] **Step 2: 创建 frontend/src/stores/processing.ts**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { processingApi, type ProcessingTask } from '@/api/processing'

export const useProcessingStore = defineStore('processing', () => {
  const tasks = ref<ProcessingTask[]>([])
  const loading = ref(false)
  const error = ref('')
  const filterType = ref('')
  const filterStatus = ref('')

  const taskTotal = tasks.value.length

  async function fetchTasks(params?: { type?: string; status?: string }) {
    loading.value = true
    error.value = ''
    try {
      const res = await processingApi.list(params)
      tasks.value = res.data.tasks
    } catch (e: any) {
      error.value = e.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function applyFilters() {
    await fetchTasks({
      type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
  }

  return {
    tasks,
    loading,
    error,
    filterType,
    filterStatus,
    taskTotal,
    fetchTasks,
    applyFilters,
  }
})
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/processing.ts frontend/src/stores/processing.ts
git commit -m "feat(processing): 新增前端 API 客户端与 Pinia store"
```

---

## Task 8: 前端 Tasks.vue 改造

**Files:**
- Modify: `frontend/src/views/process/Tasks.vue`

- [ ] **Step 1: 改造 Tasks.vue 数据源**

打开 `frontend/src/views/process/Tasks.vue`，替换 `<script setup>` 块开头部分：

将原来的：
```typescript
import { useMockStore } from '@/stores/mock'
import type { ProcessingTask } from '@/api/mock'

const store = useMockStore()
```

改为：
```typescript
import { useProcessingStore } from '@/stores/processing'
import { processingApi, type ProcessingTask } from '@/api/processing'

const store = useProcessingStore()
```

并将 `applyFilters` 函数改为：
```typescript
async function applyFilters() {
  errorMsg.value = ''
  try {
    await store.fetchTasks({
      type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  }
}
```

将 `tasksOfType` 函数改为：
```typescript
function tasksOfType(type: string): ProcessingTask[] {
  return store.tasks.filter((t) => t.task_type === type)
}
```

注意：原 mock 数据中 `t.batch_id` 字段需要替换为 `t.input_paths.join(', ')` 或显示第一个 input_path。

- [ ] **Step 2: 模板中调整字段引用**

在模板中，`t.batch_id` 改为 `t.input_paths?.[0] || '-'`，`t.id` 改为 `t.task_id`。

- [ ] **Step 3: 验证前端编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/process/Tasks.vue
git commit -m "feat(processing): Tasks.vue 改用真实 API 替换 mock"
```

---

## Task 9: 前端 TaskNew.vue 改造

**Files:**
- Modify: `frontend/src/views/process/TaskNew.vue`

- [ ] **Step 1: 改造 submit() 函数**

打开 `frontend/src/views/process/TaskNew.vue`，替换 `submit()` 函数：

```typescript
async function submit() {
  submitting.value = true
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const input_paths = inputMode.value === 'batch'
      ? selectedBatches.value.map(b => b.image_folder_path)
      : [customDir.value]
    const params = selectedType.value === 'clahe'
      ? { clip_limit: form.value.clip_limit, grid_size: form.value.grid }
      : { tile_size: form.value.tile_size, overlap_ratio: form.value.overlap_ratio }
    const api = selectedType.value === 'clahe'
      ? processingApi.submitClahe
      : processingApi.submitCrop
    const res = await api({ name: form.value.name, input_paths, params })
    // 提交成功后跳转到任务详情
    router.push(`/process/tasks/${res.data.task_id}`)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.message || e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}
```

在 `<script setup>` 顶部添加导入：

```typescript
import { processingApi } from '@/api/processing'
import { useRouter } from 'vue-router'
const router = useRouter()
```

- [ ] **Step 2: 移除"V1 演示模式"提示**

在模板中找到"V1 演示模式：提交后仅展示成功提示..."的提示块，删除整个 `<div class="mt-4 bg-brand-50/50 border border-brand-100 rounded-btn p-3 text-xs text-ink-secondary flex items-start gap-2">` 块。

- [ ] **Step 3: 验证前端编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/process/TaskNew.vue
git commit -m "feat(processing): TaskNew.vue submit 调用真实 API"
```

---

## Task 10: 前端 TaskDetail.vue 改造

**Files:**
- Modify: `frontend/src/views/process/TaskDetail.vue`

- [ ] **Step 1: 改造 TaskDetail.vue 数据源与轮询**

打开 `frontend/src/views/process/TaskDetail.vue`，替换 `<script setup>` 中的导入与 `load` 函数：

```typescript
import { processingApi, type ProcessingTask } from '@/api/processing'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const task = ref<ProcessingTask | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const previewMode = ref<'grid' | 'compare'>('grid')
const previewFiles = ref<{ filename: string; sub_dir?: string }[]>([])
let pollTimer: number | undefined

async function loadPreviewFiles() {
  if (!task.value) return
  try {
    const subDir = task.value.sub_dirs[0]?.sub_dir
    const res = await processingApi.listFiles(task.value.task_id, { sub_dir, page: 1, page_size: 12 })
    previewFiles.value = res.data.files.map(f => ({ filename: f.filename, sub_dir: subDir }))
  } catch {
    previewFiles.value = []
  }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.get(id.value)
    task.value = res.data
    await loadPreviewFiles()
    // 处理中任务：轮询
    if (task.value.status === 'processing' || task.value.status === 'pending') {
      pollTimer = window.setInterval(async () => {
        try {
          const r = await processingApi.get(id.value)
          task.value = r.data
          if (r.data.status === 'completed' || r.data.status === 'failed' || r.data.status === 'interrupted') {
            if (pollTimer) clearInterval(pollTimer)
            await loadPreviewFiles()
          }
        } catch {}
      }, 2000)
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载任务详情失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
```

- [ ] **Step 2: 模板中调整预览图 URL**

在模板中，预览图 `<img>` 的 `src` 改为：
```html
:src="processingApi.previewUrl(task.task_id, file.filename, file.sub_dir, 'thumbnail')"
```

需要确保 `processingApi` 在模板中可用（在 `<script setup>` 中已导入，模板可直接引用）。

- [ ] **Step 3: 验证前端编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/process/TaskDetail.vue
git commit -m "feat(processing): TaskDetail.vue 真实预览图与进度轮询"
```

---

## Task 11: 端到端集成测试

**Files:**
- Create: `backend/tests/test_processing_integration.py`

- [ ] **Step 1: 写集成测试**

创建 `backend/tests/test_processing_integration.py`：

```python
"""端到端集成测试：提交任务 → 轮询状态 → 校验 output 结构。"""
import json
import shutil
import time
from pathlib import Path

import pytest

from backend.app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    yaml_path = tmp_path / "processing_tasks.yaml"

    import config
    monkeypatch.setattr(config, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(config, "PROCESSING_TASKS_YAML", yaml_path)

    from core import engine
    from core.processing_engine import ProcessingEngine
    from core.processing_registry import ProcessingRegistry
    from core.task_manager import TaskManager
    engine.processing_engine = ProcessingEngine()
    engine.processing_registry = ProcessingRegistry(output_dir=out_dir, yaml_path=yaml_path)
    engine.processing_registry.load_from_yaml()
    engine.processing_task_manager = TaskManager(max_workers=1)

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_clahe_end_to_end(client, tmp_path):
    """提交 CLAHE 任务 → 等待完成 → 校验 output 目录与 index.json。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    input_dir = tmp_path / "batch_e2e"
    input_dir.mkdir()
    shutil.copy(fixtures / "small_640.jpg", input_dir / "DJI_0001.jpg")
    shutil.copy(fixtures / "small_640.jpg", input_dir / "DJI_0002.jpg")

    # 提交任务
    r = client.post("/api/processing/clahe", json={
        "name": "E2E CLAHE",
        "input_paths": [str(input_dir)],
        "params": {"clip_limit": 2.0, "grid_size": [8, 8]},
    })
    assert r.status_code == 200
    task_id = r.get_json()["data"]["task_id"]

    # 轮询直到完成
    for _ in range(30):
        time.sleep(0.5)
        r = client.get(f"/api/processing/tasks/{task_id}")
        status = r.get_json()["data"]["status"]
        if status in ("completed", "failed"):
            break
    assert status == "completed", f"任务未完成: status={status}"

    # 校验 output 结构
    r = client.get(f"/api/processing/tasks/{task_id}")
    cfg = r.get_json()["data"]
    assert cfg["processed_images"] == 2
    assert len(cfg["sub_dirs"]) == 1

    # 校验文件清单
    r = client.get(f"/api/processing/tasks/{task_id}/files?sub_dir={cfg['sub_dirs'][0]['sub_dir']}")
    assert r.status_code == 200
    files_data = r.get_json()["data"]
    assert files_data["total"] == 2

    # 校验加工数据列表
    r = client.get("/api/processing/processed")
    items = r.get_json()["data"]["items"]
    assert any(i["task_id"] == task_id for i in items)

    # 校验预览
    r = client.get(f"/api/processing/tasks/{task_id}/preview?filename=DJI_0001.jpg&sub_dir={cfg['sub_dirs'][0]['sub_dir']}&size=thumbnail")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_crop_end_to_end(client, tmp_path):
    """提交裁切任务 → 校验子图命名规范。"""
    fixtures = Path(__file__).parent / "fixtures" / "sample_images"
    input_dir = tmp_path / "crop_e2e"
    input_dir.mkdir()
    shutil.copy(fixtures / "medium_1280.jpg", input_dir / "DJI_0001.JPG")

    r = client.post("/api/processing/crop", json={
        "name": "E2E Crop",
        "input_paths": [str(input_dir)],
        "params": {"tile_size": 640, "overlap_ratio": 0.05},
    })
    task_id = r.get_json()["data"]["task_id"]

    # 等待完成
    for _ in range(30):
        time.sleep(0.5)
        r = client.get(f"/api/processing/tasks/{task_id}")
        status = r.get_json()["data"]["status"]
        if status in ("completed", "failed"):
            break
    assert status == "completed"

    # 校验子图命名
    r = client.get(f"/api/processing/tasks/{task_id}/files?sub_dir=crop_e2e")
    files = r.get_json()["data"]["files"]
    import re
    pattern = r"^DJI_0001_tile_\d{4}_x\d+_y\d+\.jpg$"
    for f in files:
        assert re.match(pattern, f["filename"]), f"命名不符: {f['filename']}"
```

- [ ] **Step 2: 运行集成测试**

```bash
cd backend && python -m pytest tests/test_processing_integration.py -v
```

预期：2 个测试通过。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_processing_integration.py
git commit -m "test(processing): 新增端到端集成测试"
```

---

## Task 12（优先级 LAST）: 前端【加工数据】双 tab 功能

**Files:**
- Create: `frontend/src/components/layout/DataSubTabs.vue`
- Create: `frontend/src/views/data/Processed.vue`
- Create: `frontend/src/views/data/ProcessedDetail.vue`
- Modify: `frontend/src/views/data/Batches.vue`
- Modify: `frontend/src/views/data/BatchNew.vue`
- Modify: `frontend/src/views/data/BatchDetail.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 创建 DataSubTabs.vue**

创建 `frontend/src/components/layout/DataSubTabs.vue`：

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '@/components/common/Icon.vue'

const route = useRoute()
const isBatches = computed(() =>
  route.path.startsWith('/data/batches') || route.path === '/data/batch-new')
const isProcessed = computed(() => route.path.startsWith('/data/processed'))
</script>

<template>
  <div class="flex items-center gap-1 border-b border-surface-border mb-6">
    <router-link to="/data/batches" class="sub-tab" :class="{ active: isBatches }">
      <Icon name="database" :size="14" /> 原始数据
    </router-link>
    <router-link to="/data/processed" class="sub-tab" :class="{ active: isProcessed }">
      <Icon name="augment" :size="14" /> 加工数据
    </router-link>
  </div>
</template>
```

- [ ] **Step 2: 创建 Processed.vue**

创建 `frontend/src/views/data/Processed.vue`：

```vue
<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import { processingApi, type ProcessedItem } from '@/api/processing'
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const router = useRouter()
const items = ref<ProcessedItem[]>([])
const loading = ref(false)
const errorMsg = ref('')

const stats = computed(() => {
  const claheCount = items.value.filter(i => i.task_type === 'clahe').length
  const cropCount = items.value.filter(i => i.task_type === 'crop').length
  const totalImages = items.value.reduce((s, i) => s + (i.image_count || 0), 0)
  return { total: items.value.length, claheCount, cropCount, totalImages }
})

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('completed') || s.includes('完成')) return { cls: 'badge-success', label: '已完成' }
  if (s.includes('fail') || s.includes('错误')) return { cls: 'badge-error', label: '失败' }
  if (s.includes('interrupted')) return { cls: 'badge-pending', label: '中断' }
  if (s.includes('process') || s.includes('进行')) return { cls: 'badge-running', label: '进行中' }
  return { cls: 'badge-pending', label: status || '—' }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.listProcessed()
    items.value = res.data.items
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goDetail(item: ProcessedItem) {
  const id = item.output_path.split('/').pop() || item.task_id
  router.push(`/data/processed/${id}`)
}

async function deleteProcessed(item: ProcessedItem, e: Event) {
  e.stopPropagation()
  if (!confirm(`确定删除加工数据「${item.name}」？\n（output 目录将被一并删除）`)) return
  const id = item.output_path.split('/').pop() || item.task_id
  try {
    await processingApi.deleteProcessed(id, true)
    await load()
  } catch (err: any) {
    alert(err.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="flex items-end justify-between mb-5">
      <div>
        <div class="text-xs text-ink-tertiary mb-1">数据管理 · 加工产物</div>
        <h1 class="text-2xl font-semibold text-ink-primary">加工数据</h1>
        <p class="text-sm text-ink-secondary mt-1">
          浏览数据处理产出的 CLAHE 增强 / 滑窗裁切结果 · 一一对应处理任务
        </p>
      </div>
      <router-link to="/process/task-new" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
        <Icon name="plus" :size="14" /> 新建处理任务
      </router-link>
    </div>

    <DataSubTabs />

    <!-- 统计卡 -->
    <div class="grid grid-cols-4 gap-4 mb-5">
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">加工产物总数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">{{ stats.total }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">CLAHE 增强产物</div>
        <div class="text-2xl font-semibold text-brand-700 mt-1">{{ stats.claheCount }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">滑窗裁切产物</div>
        <div class="text-2xl font-semibold text-amber-600 mt-1">{{ stats.cropCount }}</div>
      </div>
      <div class="bg-white border border-surface-border rounded-card p-4">
        <div class="text-xs text-ink-tertiary">总图片数</div>
        <div class="text-2xl font-semibold text-ink-primary mt-1">{{ stats.totalImages }}</div>
      </div>
    </div>

    <!-- 列表表格 -->
    <div class="bg-white border border-surface-border rounded-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-bg text-xs text-ink-secondary">
          <tr>
            <th class="text-left py-2.5 px-5 font-medium">任务名 / ID</th>
            <th class="text-left py-2.5 px-5 font-medium">类型</th>
            <th class="text-left py-2.5 px-5 font-medium">状态</th>
            <th class="text-left py-2.5 px-5 font-medium">输出路径</th>
            <th class="text-right py-2.5 px-5 font-medium">图片数</th>
            <th class="text-left py-2.5 px-5 font-medium">生成时间</th>
            <th class="text-right py-2.5 px-5 font-medium w-28">操作</th>
          </tr>
        </thead>
        <tbody class="row-hover">
          <tr v-if="loading">
            <td colspan="7" class="py-10 text-center text-ink-tertiary text-sm">
              <Icon name="spinner" :size="16" :spin="true" class="inline mr-2" /> 加载中…
            </td>
          </tr>
          <tr v-else-if="errorMsg">
            <td colspan="7" class="py-10 text-center text-sm">
              <div class="text-red-600 mb-2">{{ errorMsg }}</div>
              <button @click="load" class="text-brand-700 hover:underline text-xs">重试</button>
            </td>
          </tr>
          <tr v-else-if="items.length === 0">
            <td colspan="7" class="py-12 text-center text-ink-tertiary">
              <Icon name="augment" :size="32" class="mx-auto mb-2 opacity-40" />
              <div class="text-sm">暂无加工数据</div>
            </td>
          </tr>
          <tr
            v-for="item in items"
            v-else
            :key="item.task_id"
            class="border-t border-surface-border cursor-pointer"
            @click="goDetail(item)"
          >
            <td class="py-3 px-5">
              <div class="font-medium text-ink-primary hover:text-brand-700">{{ item.name }}</div>
              <div class="text-xs text-ink-tertiary mt-0.5 font-mono">{{ item.task_id }}</div>
            </td>
            <td class="py-3 px-5">
              <span class="tag" :class="item.task_type === 'clahe' ? 'tag-blue' : 'tag-amber'">
                {{ item.task_type === 'clahe' ? 'CLAHE' : '裁切' }}
              </span>
            </td>
            <td class="py-3 px-5">
              <span class="badge" :class="statusBadge(item.status).cls">{{ statusBadge(item.status).label }}</span>
            </td>
            <td class="py-3 px-5 text-ink-tertiary font-mono text-xs">{{ item.output_path }}</td>
            <td class="text-right py-3 px-5 text-ink-primary">{{ item.image_count }}</td>
            <td class="py-3 px-5 text-ink-secondary text-xs">{{ item.created_at }}</td>
            <td class="py-3 px-5 text-right" @click.stop>
              <router-link :to="`/data/processed/${item.output_path.split('/').pop()}`" class="text-xs text-brand-700 hover:underline mr-2">查看</router-link>
              <button @click="deleteProcessed(item, $event)" class="text-xs text-red-500 hover:underline">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AppLayout>
</template>
```

- [ ] **Step 3: 创建 ProcessedDetail.vue**

创建 `frontend/src/views/data/ProcessedDetail.vue`：

```vue
<script setup lang="ts">
import AppLayout from '@/components/layout/AppLayout.vue'
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
import Icon from '@/components/common/Icon.vue'
import { processingApi, type ProcessedItem, type TaskFile } from '@/api/processing'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const item = ref<ProcessedItem | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const files = ref<TaskFile[]>([])
const expandedSubDir = ref<string | null>(null)

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('completed') || s.includes('完成')) return { cls: 'badge-success', label: '已完成' }
  if (s.includes('interrupted')) return { cls: 'badge-pending', label: '中断' }
  return { cls: 'badge-pending', label: status || '—' }
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await processingApi.getProcessed(id.value)
    item.value = res.data
    // 自动展开第一个子目录
    if (item.value.sub_dirs.length > 0) {
      expandedSubDir.value = item.value.sub_dirs[0].sub_dir
      await loadFiles(item.value.sub_dirs[0].sub_dir)
    }
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadFiles(subDir: string) {
  if (!item.value) return
  try {
    const res = await processingApi.listProcessedFiles(id.value, { sub_dir: subDir, page: 1, page_size: 50 })
    files.value = res.data.files
  } catch {
    files.value = []
  }
}

async function toggleSubDir(subDir: string) {
  if (expandedSubDir.value === subDir) {
    expandedSubDir.value = null
    files.value = []
  } else {
    expandedSubDir.value = subDir
    await loadFiles(subDir)
  }
}

async function deleteItem() {
  if (!item.value) return
  if (!confirm(`确定删除加工数据「${item.value.name}」？\n（output 目录将被一并删除）`)) return
  try {
    await processingApi.deleteProcessed(id.value, true)
    router.push('/data/processed')
  } catch (e: any) {
    alert(e.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="flex items-center gap-1 text-xs text-ink-tertiary mb-2">
      <router-link to="/data/processed" class="hover:text-brand-700">加工数据</router-link>
      <Icon name="chevron-right" :size="10" />
      <span class="text-ink-primary">{{ item?.name || id }}</span>
    </div>

    <div v-if="loading" class="py-24 text-center text-ink-tertiary">
      <Icon name="spinner" :size="24" :spin="true" class="inline mr-2" /> 加载中…
    </div>

    <div v-else-if="errorMsg" class="py-24 text-center">
      <div class="text-red-600 mb-3">{{ errorMsg }}</div>
      <button @click="load" class="px-4 py-2 bg-brand-700 text-white rounded-btn text-sm">重试</button>
    </div>

    <template v-else-if="item">
      <DataSubTabs />

      <!-- 头部 -->
      <div class="flex items-end justify-between mb-5">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-semibold text-ink-primary">{{ item.name }}</h1>
            <span class="badge" :class="statusBadge(item.status).cls">{{ statusBadge(item.status).label }}</span>
            <span class="tag" :class="item.task_type === 'clahe' ? 'tag-blue' : 'tag-amber'">
              {{ item.task_type === 'clahe' ? 'CLAHE 增强' : '滑窗裁切' }}
            </span>
          </div>
          <p class="text-sm text-ink-secondary mt-1">
            生成于 {{ item.created_at }} · {{ item.image_count }} 张图片
          </p>
        </div>
        <div class="flex gap-2">
          <router-link :to="`/process/tasks/${item.task_id}`" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-primary inline-flex items-center gap-2">
            <Icon name="augment" :size="14" /> 查看处理任务
          </router-link>
          <button @click="deleteItem" class="px-3 py-2 bg-white border border-red-200 hover:bg-red-50 text-red-600 rounded-btn text-sm inline-flex items-center gap-2">
            <Icon name="trash" :size="14" /> 删除
          </button>
        </div>
      </div>

      <!-- 参数卡 -->
      <div class="bg-white border border-surface-border rounded-card p-5 mb-5">
        <div class="grid grid-cols-4 gap-4 text-sm">
          <div v-for="(val, key) in item.params" :key="key">
            <div class="text-xs text-ink-tertiary">{{ key }}</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ val }}</div>
          </div>
          <div>
            <div class="text-xs text-ink-tertiary">子目录数</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ item.sub_dirs.length }}</div>
          </div>
          <div v-if="item.total_tiles">
            <div class="text-xs text-ink-tertiary">总子图数</div>
            <div class="text-ink-primary font-medium mt-0.5">{{ item.total_tiles }}</div>
          </div>
        </div>
      </div>

      <!-- 子目录折叠面板 -->
      <div class="space-y-3">
        <div v-for="sub in item.sub_dirs" :key="sub.sub_dir" class="bg-white border border-surface-border rounded-card overflow-hidden">
          <div
            class="px-5 py-3 border-b border-surface-border flex items-center justify-between cursor-pointer hover:bg-surface-hover"
            @click="toggleSubDir(sub.sub_dir)"
          >
            <div class="flex items-center gap-2">
              <Icon name="folder" :size="16" class="text-ink-tertiary" />
              <span class="font-medium text-ink-primary">{{ sub.sub_dir }}</span>
              <span class="text-xs text-ink-tertiary">{{ sub.image_count }} 张</span>
            </div>
            <Icon :name="expandedSubDir === sub.sub_dir ? 'chevron-down' : 'chevron-right'" :size="14" class="text-ink-tertiary" />
          </div>
          <div v-if="expandedSubDir === sub.sub_dir" class="p-5">
            <div class="grid grid-cols-6 gap-3">
              <div v-for="f in files" :key="f.filename" class="text-center">
                <img :src="f.thumbnail_url" :alt="f.filename" class="w-full aspect-square object-cover rounded-btn border border-surface-border" />
                <div class="text-xs text-ink-tertiary mt-1 truncate">{{ f.filename }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </AppLayout>
</template>
```

- [ ] **Step 4: 在 Batches.vue 顶部加 DataSubTabs**

打开 `frontend/src/views/data/Batches.vue`，在 `<div class="flex items-end justify-between mb-6">` 之前插入：

```vue
<DataSubTabs />
```

并在 `<script setup>` 中导入：
```typescript
import DataSubTabs from '@/components/layout/DataSubTabs.vue'
```

副标题"原始飞行数据"改为"原始数据"。

- [ ] **Step 5: 在 BatchNew.vue 顶部加 DataSubTabs**

打开 `frontend/src/views/data/BatchNew.vue`，在合适位置插入 `<DataSubTabs />`，并导入组件。

- [ ] **Step 6: 在 BatchDetail.vue 顶部加 DataSubTabs**

打开 `frontend/src/views/data/BatchDetail.vue`，在合适位置插入 `<DataSubTabs />`，并导入组件。

- [ ] **Step 7: 更新路由**

打开 `frontend/src/router/index.ts`，在数据管理路由组中追加：

```typescript
{ path: '/data/processed', name: 'processed', component: () => import('@/views/data/Processed.vue') },
{ path: '/data/processed/:id', name: 'processed-detail', component: () => import('@/views/data/ProcessedDetail.vue') },
```

- [ ] **Step 8: 验证前端编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误。

- [ ] **Step 9: 验证 Vite 构建**

```bash
cd frontend && npm run build
```

预期：构建成功，产物输出到 `backend/static/`。

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/layout/DataSubTabs.vue frontend/src/views/data/ frontend/src/router/index.ts
git commit -m "feat(processing): 新增【加工数据】双 tab 功能（Processed 列表+详情）"
```

---

## Task 13: PRD 同步更新

**Files:**
- Modify: `.lqs/prd/PRD_基于无人机图像的大田农作物智能监测与管理系统_v5.md`

- [ ] **Step 1: 更新 PRD §3.2 FR-P02 子图命名规范**

将：
```
{original_stem}_x{offset_x}_y{offset_y}_{seq:04d}.{ext}
```

改为：
```
{orig_stem}_tile_{seq:04d}_x{offset_x}_y{offset_y}.jpg
```

- [ ] **Step 2: 更新 PRD §3.3 接口列表**

补充加工数据相关端点：
- `GET /api/processing/processed`
- `GET /api/processing/processed/:id`
- `GET /api/processing/processed/:id/files`
- `DELETE /api/processing/processed/:id`

- [ ] **Step 3: 更新 PRD §3.5 输出规范**

补充多架次分子目录结构说明：
```
output/{task_id}/{sub_dir}/*.jpg
output/{task_id}/index.json
```

- [ ] **Step 4: 更新 PRD §1.7 实现状态总览**

模块二状态从 🔶 改为 ✅，新增【加工数据】子模块说明。

- [ ] **Step 5: 更新 PRD §1.8 全局导航**

数据管理下新增【加工数据】子栏目说明。

- [ ] **Step 6: Commit**

```bash
git add .lqs/prd/PRD_基于无人机图像的大田农作物智能监测与管理系统_v5.md
git commit -m "docs(prd): 同步更新 PRD（数据处理模块实现完成 + 加工数据子模块）"
```

---

## 验收检查清单

完成后运行以下命令验证全部功能：

```bash
# 后端测试
cd backend && python -m pytest tests/test_processing_engine.py tests/test_processing_registry.py tests/test_processing_api.py tests/test_processing_integration.py -v

# 前端编译
cd frontend && npx vue-tsc --noEmit && npm run build

# 启动后端验证
cd backend && python -m backend.app
# 访问 http://localhost:5000/api/processing/tasks 应返回 {"success":true,"data":{"tasks":[],"total":0},"message":"获取任务列表成功"}
```

参照 spec §7 验收检查清单逐项验证 19 项功能。
