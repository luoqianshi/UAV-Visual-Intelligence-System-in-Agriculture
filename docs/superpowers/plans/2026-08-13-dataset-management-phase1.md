# 数据集管理模块（第一阶段）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用真实数据集管理后端替换 Mock，实现导入注册 + 统计报告 + 浏览删除，对接前端三个页面与首页，以 SSDC-UAV 数据集为验收基准。

**Architecture:** 注册中心（`DatasetRegistry`，YAML 持久化 + 自动扫描 + CRUD + 图片索引）+ 分析器（`DatasetAnalyzer`，格式识别 + 统计计算 + 报告缓存）双类，格式解析抽为纯函数（`dataset_formats.py` → 统一中间表示 IR）。镜像 `BatchRegistry`/`ProcessingRegistry` 模式，仅依赖 PyYAML+Pillow+stdlib。

**Tech Stack:** Flask 2.2.3 / PyYAML / Pillow / Vue 3 + Pinia + ECharts + Vite / pytest

**对应设计文档：** `docs/superpowers/specs/2026-08-13-dataset-management-phase1-design.md`

---

## 文件结构

**后端新增/改动：**
- `backend/config.py` — 改动：新增 `DATASETS_DIR`、`DATASETS_YAML` 常量
- `backend/core/dataset_formats.py` — 新增：`detect_format`/`parse_coco`/`parse_yolo`/`parse_voc` → IR
- `backend/core/dataset_analyzer.py` — 新增：`DatasetAnalyzer`（scan 轻量统计 + compute_report 重统计 + 缓存）
- `backend/core/dataset_registry.py` — 新增：`DatasetRegistry`（YAML/自动扫描/CRUD/图片索引/预览）
- `backend/api/datasets_api.py` — 重写：9 个端点替换 Mock
- `backend/core/engine.py` — 改动：装配 `dataset_registry`/`dataset_analyzer` 单例
- `backend/app.py` — 改动：注册 datasets_bp（已存在，确认即可）

**后端测试新增：**
- `backend/tests/dataset_factory.py` — 新增：mini 数据集夹具构建器（在 tmp_path 构建 COCO/YOLO/VOC 小数据集）
- `backend/tests/test_dataset_formats.py`
- `backend/tests/test_dataset_analyzer.py`
- `backend/tests/test_dataset_registry.py`
- `backend/tests/test_datasets_api.py`

**前端新增/改动：**
- `frontend/src/api/datasets.ts` — 新增：typed Dataset 接口 + API 函数
- `frontend/src/stores/datasets.ts` — 新增：Pinia store
- `frontend/src/views/dataset/Datasets.vue` — 改动：对接真实 store + 框数/来源列 + 导入入口
- `frontend/src/views/dataset/DatasetNew.vue` — 改动：双 tab（导入可用/构建禁用）
- `frontend/src/views/dataset/DatasetDetail.vue` — 改动：ECharts 报告 + 样本浏览 + 删除
- `frontend/src/views/index/Index.vue` — 改动：数据集统计改用新 store
- `frontend/src/api/mock.ts` / `frontend/src/stores/mock.ts` — 删除

---

## Task 1: config.py 新增数据集常量

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: 新增数据集目录与 YAML 路径常量**

在 `backend/config.py` 末尾（`OUTPUT_DIR.mkdir(...)` 之后）追加：

```python
# ── 数据集管理（模块三）─────────────────────────────────────────────
DATASETS_DIR = PROJECT_ROOT / "datasets"
DATASETS_YAML = DATASETS_DIR / "datasets.yaml"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: 验证导入无报错**

Run: `python -c "from config import DATASETS_DIR, DATASETS_YAML; print(DATASETS_DIR, DATASETS_YAML)"`
Expected: 打印绝对路径，无异常。

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat(dataset): 新增数据集目录与 YAML 路径常量"
```

---

## Task 2: dataset_formats.py — detect_format + parse_coco（TDD）

**Files:**
- Create: `backend/tests/dataset_factory.py`
- Create: `backend/tests/test_dataset_formats.py`
- Create: `backend/core/dataset_formats.py`

- [ ] **Step 1: 编写夹具构建器 `dataset_factory.py`**

创建 `backend/tests/dataset_factory.py`，提供在 `tmp_path` 下构建 mini 三格式数据集的函数。使用 Pillow 生成 1x1 占位 jpg，避免提交二进制文件：

```python
"""mini 数据集夹具构建器：在 tmp_path 下构建 COCO/YOLO/VOC 小数据集。"""
import json
from pathlib import Path

import yaml
from PIL import Image


def _make_jpg(path: Path, w=640, h=640):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (128, 128, 128)).save(path, "JPEG")


def build_mini_coco(root: Path):
    """构建 COCO mini 数据集（{split}/ 直放布局，对齐 SSDC-UAV）。
    train: 2 图 3 框；val: 1 图 1 框；test: 1 图 1 框。
    返回期望统计 dict 供断言。"""
    splits = {
        "train": [
            ("img_t1.jpg", 640, 640, [[10, 20, 30, 40], [100, 100, 50, 50], [200, 200, 60, 60]]),
            ("img_t2.jpg", 640, 640, [[5, 5, 20, 20]]),
        ],
        "val": [("img_v1.jpg", 640, 640, [[300, 300, 40, 40]])],
        "test": [("img_e1.jpg", 640, 640, [[400, 400, 100, 100]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "annotations").mkdir(exist_ok=True)
    for split, imgs in splits.items():
        images, anns = [], []
        aid = 1
        for fn, w, h, boxes in imgs:
            _make_jpg(root / split / fn, w, h)
            images.append({"id": len(images) + 1, "file_name": fn, "width": w, "height": h})
            for x, y, bw, bh in boxes:
                anns.append({"id": aid, "image_id": images[-1]["id"], "category_id": 1,
                             "bbox": [x, y, bw, bh], "area": bw * bh, "iscrowd": 0})
                aid += 1
        coco = {
            "info": {"description": "Mini COCO for test", "version": "1.0",
                     "contributor": "tester", "date_created": "2026-01-01"},
            "images": images, "annotations": anns,
            "categories": [{"id": 1, "name": "Sugarcane Seedling"}],
        }
        (root / "annotations" / f"{split}.json").write_text(
            json.dumps(coco), encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}


def build_mini_yolo(root: Path):
    """构建 YOLO mini 数据集。归一化坐标。train: 2 图 4 框；val: 1 图 1 框；test: 1 图 1 框。"""
    splits = {
        "train": [("img_t1.jpg", [[0.078125, 0.34375, 0.046875, 0.0625],
                                  [0.1953125, 0.1953125, 0.078125, 0.078125]]),
                  ("img_t2.jpg", [[0.5, 0.5, 0.1, 0.1]])],
        "val": [("img_v1.jpg", [[0.6, 0.6, 0.0625, 0.0625]])],
        "test": [("img_e1.jpg", [[0.7, 0.7, 0.15625, 0.15625]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    for split, imgs in splits.items():
        for fn, boxes in imgs:
            _make_jpg(root / "images" / split / fn)
            lbl = root / "labels" / split / (Path(fn).stem + ".txt")
            lbl.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"0 {xc} {yc} {w} {h}" for xc, yc, w, h in boxes]
            lbl.write_text("\n".join(lines), encoding="utf-8")
    cfg = {"path": "D:/stale/path", "train": "images/train", "val": "images/val",
           "test": "images/test", "nc": 1, "names": {0: "Sugarcane Seedling"}}
    (root / "mini.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}


def build_mini_voc(root: Path):
    """构建 VOC mini 数据集（{split}/images + {split}/annotations 布局）。
    train: 2 图 4 框；val: 1 图 1 框；test: 1 图 1 框。"""
    splits = {
        "train": [("img_t1.jpg", [[10, 20, 40, 60], [100, 100, 150, 150], [200, 200, 260, 260]]),
                  ("img_t2.jpg", [[5, 5, 25, 25]])],
        "val": [("img_v1.jpg", [[300, 300, 340, 340]])],
        "test": [("img_e1.jpg", [[400, 400, 500, 500]])],
    }
    root.mkdir(parents=True, exist_ok=True)
    for split, imgs in splits.items():
        for fn, boxes in imgs:
            _make_jpg(root / split / "images" / fn)
            xml = root / split / "annotations" / (Path(fn).stem + ".xml")
            xml.parent.mkdir(parents=True, exist_ok=True)
            objs = "".join(
                f"<object><name>Sugarcane Seedling</name>"
                f"<bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin>"
                f"<xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object>"
                for x1, y1, x2, y2 in boxes)
            xml.write_text(
                f"<annotation><folder>images</folder><filename>{fn}</filename>"
                f"<path>G:/stale/{fn}</path>"
                f"<size><width>640</width><height>640</height><depth>3</depth></size>"
                f"{objs}</annotation>", encoding="utf-8")
    return {"image_count": 4, "object_count": 6,
            "splits": {"train": 2, "val": 1, "test": 1},
            "classes": ["Sugarcane Seedling"]}
```

- [ ] **Step 2: 编写 detect_format 与 parse_coco 的失败测试**

创建 `backend/tests/test_dataset_formats.py`：

```python
"""dataset_formats 纯函数解析器测试。"""
from pathlib import Path

from dataset_formats import detect_format, parse_coco

from dataset_factory import build_mini_coco


def test_detect_coco(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    assert detect_format(root) == "COCO"


def test_detect_unknown(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    assert detect_format(root) is None


def test_parse_coco_coordinates_and_classes(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    ir = parse_coco(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert ir["meta"]["version"] == "1.0"
    assert ir["meta"]["contributor"] == "tester"
    # 4 张图
    assert len(ir["images"]) == 4
    # 第一张图 3 个框，绝对像素坐标 [x,y,w,h]
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    assert len(t1["boxes"]) == 3
    assert t1["boxes"][0]["bbox"] == [10, 20, 30, 40]
    assert t1["boxes"][0]["class_id"] == 0  # COCO category_id 1 → 内部 0
    assert t1["split"] == "train"
    # origin_stem 无 tile 后缀时等于 stem
    assert t1["origin_stem"] == "img_t1"


def test_parse_coco_tile_origin_stem(tmp_path):
    root = tmp_path / "mini_coco"
    expected = build_mini_coco(root)
    # 重命名为 tile 文件名验证 origin_stem 解析
    ir = parse_coco(root)
    img = ir["images"][0]
    # 夹具用普通名，手动验证解析函数逻辑
    import dataset_formats as df
    assert df._tile_origin_stem("DJI_2025051172207_0003_D_tile_0000_x0_y0") == \
        "DJI_20250511172207_0003_D"
    assert df._tile_origin_stem("plain_img") == "plain_img"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_formats.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'dataset_formats'`）

- [ ] **Step 4: 实现 detect_format + parse_coco + 辅助函数**

创建 `backend/core/dataset_formats.py`：

```python
"""三格式数据集纯函数解析器。

产出统一中间表示 IR（对齐 PRD §4.3），为阶段二格式互转写出器预留同源结构。
仅依赖 stdlib（json/xml/yaml）+ pathlib，无副作用。
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

SUPPORTED_FORMATS = ("COCO", "YOLO", "VOC")
SPLITS = ("train", "val", "test")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
_TILE_RE = re.compile(r"_tile_\d+_x\d+_y\d+$")


def _tile_origin_stem(stem: str) -> str:
    """解析 tile 文件名 stem 得原图 stem；无 tile 后缀时原样返回。"""
    return _TILE_RE.sub("", stem)


def _empty_ir(format_name: str) -> dict:
    return {"images": [], "classes": [], "meta": {
        "format": format_name, "version": "", "description": "",
        "contributor": "", "date_created": ""}}


def _list_images(folder: Path):
    return sorted([f for f in folder.iterdir()
                   if f.is_file() and f.suffix.lower() in _IMAGE_EXTS])


# ── 格式识别 ──────────────────────────────────────────────
def detect_format(dataset_dir: Path) -> str | None:
    """识别数据集格式。无法识别返回 None。"""
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        return None
    # COCO: annotations/*.json 含 images/annotations/categories
    ann_dir = dataset_dir / "annotations"
    if ann_dir.is_dir():
        for jf in ann_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if {"images", "annotations", "categories"} <= set(data.keys()):
                    return "COCO"
            except Exception:
                continue
    # YOLO: images/{split} + labels/{split} + 根目录含 names 的 .yaml
    has_yolo_dirs = all((dataset_dir / "images" / s).is_dir() for s in SPLITS) and \
                    all((dataset_dir / "labels" / s).is_dir() for s in SPLITS)
    if has_yolo_dirs:
        for yf in dataset_dir.glob("*.yaml"):
            try:
                cfg = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
                if "names" in cfg:
                    return "YOLO"
            except Exception:
                continue
    # VOC: {split}/images + {split}/annotations/*.xml，或 JPEGImages/+Annotations/
    voc_split = all((dataset_dir / s / "images").is_dir() and
                    (dataset_dir / s / "annotations").is_dir() for s in SPLITS)
    if voc_split:
        return "VOC"
    if (dataset_dir / "JPEGImages").is_dir() and (dataset_dir / "Annotations").is_dir():
        return "VOC"
    return None


# ── COCO 解析 ──────────────────────────────────────────────
def _coco_image_dir(dataset_dir: Path, split: str) -> Path:
    """COCO 图片布局：优先 {split}/ 直放（SSDC-UAV），回退 images/{split}/。"""
    direct = dataset_dir / split
    if direct.is_dir() and any(f.suffix.lower() in _IMAGE_EXTS for f in direct.iterdir()):
        return direct
    return dataset_dir / "images" / split


def parse_coco(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("COCO")
    ann_dir = dataset_dir / "annotations"
    cat_map = {}  # category_id → 内部 class_id
    for split in SPLITS:
        jf = ann_dir / f"{split}.json"
        if not jf.exists():
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        # 元信息（首个非空 info 块采信）
        info = data.get("info") or {}
        if info:
            ir["meta"].update({
                "format": "COCO",
                "version": str(info.get("version", "")),
                "description": info.get("description", ""),
                "contributor": info.get("contributor", ""),
                "date_created": info.get("date_created", ""),
            })
        # 类别映射（category_id 从 1 起 → 内部从 0 起）
        for cat in data.get("categories", []):
            cid = cat["id"]
            if cid not in cat_map:
                cat_map[cid] = len(ir["classes"])
                ir["classes"].append(cat["name"])
        # 图片索引
        img_by_id = {}
        for im in data.get("images", []):
            entry = {
                "filename": im["file_name"],
                "split": split,
                "width": im["width"], "height": im["height"],
                "origin_stem": _tile_origin_stem(Path(im["file_name"]).stem),
                "boxes": [],
            }
            img_by_id[im["id"]] = entry
            ir["images"].append(entry)
        # 标注
        for ann in data.get("annotations", []):
            entry = img_by_id.get(ann["image_id"])
            if entry is None:
                continue
            x, y, w, h = ann["bbox"]
            entry["boxes"].append({
                "bbox": [float(x), float(y), float(w), float(h)],
                "class_id": cat_map.get(ann["category_id"], 0),
                "class_name": ir["classes"][cat_map.get(ann["category_id"], 0)],
            })
    return ir
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_formats.py -v`
Expected: 4 个测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/tests/dataset_factory.py backend/tests/test_dataset_formats.py backend/core/dataset_formats.py
git commit -m "feat(dataset): detect_format 与 COCO 解析器（IR 产出）"
```

---

## Task 3: dataset_formats.py — parse_yolo + parse_voc（TDD）

**Files:**
- Modify: `backend/tests/test_dataset_formats.py`
- Modify: `backend/core/dataset_formats.py`

- [ ] **Step 1: 追加 YOLO/VOC 失败测试**

在 `backend/tests/test_dataset_formats.py` 末尾追加：

```python
from dataset_factory import build_mini_yolo, build_mini_voc
from dataset_formats import detect_format, parse_yolo, parse_voc


def test_detect_yolo(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    assert detect_format(root) == "YOLO"


def test_detect_voc(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    assert detect_format(root) == "VOC"


def test_parse_yolo_ignores_stale_path(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    ir = parse_yolo(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert ir["meta"]["format"] == "YOLO"
    assert len(ir["images"]) == 4
    # 归一化坐标 → 绝对像素（640x640）
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    # 第一框 0.078125*640=50, 0.34375*640=220, 0.046875*640=30, 0.0625*640=40
    bx = t1["boxes"][0]["bbox"]
    assert abs(bx[0] - 50.0) < 1 and abs(bx[1] - 220.0) < 1
    assert abs(bx[2] - 30.0) < 1 and abs(bx[3] - 40.0) < 1
    assert t1["boxes"][0]["class_id"] == 0
    assert t1["split"] == "train"


def test_parse_voc_ignores_stale_path(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    ir = parse_voc(root)
    assert ir["classes"] == ["Sugarcane Seedling"]
    assert len(ir["images"]) == 4
    t1 = next(im for im in ir["images"] if im["filename"] == "img_t1.jpg")
    # VOC xmin,ymin,xmax,ymax → [x,y,w,h]
    assert t1["boxes"][0]["bbox"] == [10.0, 20.0, 30.0, 40.0]  # 10,20,40,60 → 10,20,30,40
    assert t1["boxes"][0]["class_id"] == 0
    assert t1["split"] == "train"


def test_parse_yolo_empty_label(tmp_path):
    """空标注 .txt 保留空 boxes。"""
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    # 追加一张空标注图
    from dataset_factory import _make_jpg
    _make_jpg(root / "images" / "train" / "empty.jpg")
    (root / "labels" / "train" / "empty.txt").write_text("", encoding="utf-8")
    ir = parse_yolo(root)
    empty = next(im for im in ir["images"] if im["filename"] == "empty.jpg")
    assert empty["boxes"] == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_formats.py -v -k "yolo or voc"`
Expected: FAIL（`parse_yolo`/`parse_voc` 未定义）

- [ ] **Step 3: 实现 parse_yolo + parse_voc**

在 `backend/core/dataset_formats.py` 末尾追加：

```python
# ── YOLO 解析 ──────────────────────────────────────────────
def _load_yolo_config(dataset_dir: Path) -> dict:
    for yf in dataset_dir.glob("*.yaml"):
        try:
            cfg = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
            if "names" in cfg:
                return cfg
        except Exception:
            continue
    return {}


def parse_yolo(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("YOLO")
    cfg = _load_yolo_config(dataset_dir)
    names = cfg.get("names", {})
    # names 可能是 dict {0: name} 或 list [name]
    if isinstance(names, dict):
        for k in sorted(names.keys()):
            ir["classes"].append(names[k])
    elif isinstance(names, list):
        ir["classes"] = list(names)
    ir["meta"]["format"] = "YOLO"
    # 忽略 cfg['path']（过期绝对路径）

    for split in SPLITS:
        img_dir = dataset_dir / "images" / split
        lbl_dir = dataset_dir / "labels" / split
        if not img_dir.is_dir():
            continue
        for img in _list_images(img_dir):
            lbl = lbl_dir / (img.stem + ".txt")
            boxes = []
            if lbl.exists():
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    cid = int(parts[0])
                    xc, yc, w, h = map(float, parts[1:5])
                    # 归一化→绝对像素（需要宽高，YOLO 无尺寸字段，读图片元信息开销大；
                    # 此处用同目录图片的 PIL 读取尺寸）
                    width, height = _image_size(img)
                    abs_w, abs_h = w * width, h * height
                    abs_x = xc * width - abs_w / 2
                    abs_y = yc * height - abs_h / 2
                    cname = ir["classes"][cid] if cid < len(ir["classes"]) else str(cid)
                    boxes.append({"bbox": [abs_x, abs_y, abs_w, abs_h],
                                  "class_id": cid, "class_name": cname})
            ir["images"].append({
                "filename": img.name, "split": split,
                "width": width, "height": height,
                "origin_stem": _tile_origin_stem(img.stem),
                "boxes": boxes,
            })
    return ir


def _image_size(img_path: Path):
    """读取图片宽高（YOLO 标注无尺寸字段，需读图片元信息）。"""
    from PIL import Image
    with Image.open(img_path) as im:
        return im.size


# ── VOC 解析 ──────────────────────────────────────────────
def _voc_split_dirs(dataset_dir: Path):
    """返回 [(split, images_dir, annotations_dir)]。"""
    result = []
    for split in SPLITS:
        img_dir = dataset_dir / split / "images"
        ann_dir = dataset_dir / split / "annotations"
        if img_dir.is_dir() and ann_dir.is_dir():
            result.append((split, img_dir, ann_dir))
    if not result:  # 标准 JPEGImages/+Annotations/ 布局（阶段二构建产物）
        jpg = dataset_dir / "JPEGImages"
        ann = dataset_dir / "Annotations"
        if jpg.is_dir() and ann.is_dir():
            # 标准 VOC 无 split 目录，全部归 train（导入兼容用；SSDC-UAV 走 split 布局）
            result.append(("train", jpg, ann))
    return result


def parse_voc(dataset_dir: Path) -> dict:
    dataset_dir = Path(dataset_dir)
    ir = _empty_ir("VOC")
    name_to_id = {}
    for split, img_dir, ann_dir in _voc_split_dirs(dataset_dir):
        for img in _list_images(img_dir):
            xml = ann_dir / (img.stem + ".xml")
            boxes = []
            width = height = 0
            if xml.exists():
                try:
                    tree = ET.fromstring(xml.read_text(encoding="utf-8"))
                except ET.ParseError:
                    tree = None
                if tree is not None:
                    size = tree.find("size")
                    if size is not None:
                        w = size.find("width")
                        h = size.find("height")
                        if w is not None:
                            width = int(w.text)
                        if h is not None:
                            height = int(h.text)
                    for obj in tree.findall("object"):
                        name_el = obj.find("name")
                        bnd = obj.find("bndbox")
                        if name_el is None or bnd is None:
                            continue
                        cname = name_el.text or ""
                        if cname not in name_to_id:
                            name_to_id[cname] = len(ir["classes"])
                            ir["classes"].append(cname)
                        xmin = float(bnd.find("xmin").text)
                        ymin = float(bnd.find("ymin").text)
                        xmax = float(bnd.find("xmax").text)
                        ymax = float(bnd.find("ymax").text)
                        boxes.append({"bbox": [xmin, ymin, xmax - xmin, ymax - ymin],
                                      "class_id": name_to_id[cname],
                                      "class_name": cname})
            if width == 0 or height == 0:
                width, height = _image_size(img)
            ir["images"].append({
                "filename": img.name, "split": split,
                "width": width, "height": height,
                "origin_stem": _tile_origin_stem(img.stem),
                "boxes": boxes,
            })
    ir["meta"]["format"] = "VOC"
    return ir
```

- [ ] **Step 4: 运行全部格式测试确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_formats.py -v`
Expected: 全部测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dataset_formats.py backend/core/dataset_formats.py
git commit -m "feat(dataset): YOLO/VOC 解析器与坐标转换"
```

---

## Task 4: DatasetAnalyzer — scan 轻量统计（TDD）

**Files:**
- Create: `backend/tests/test_dataset_analyzer.py`
- Create: `backend/core/dataset_analyzer.py`

- [ ] **Step 1: 编写 scan 失败测试**

创建 `backend/tests/test_dataset_analyzer.py`：

```python
"""DatasetAnalyzer 测试。"""
from dataset_analyzer import DatasetAnalyzer
from dataset_factory import build_mini_coco, build_mini_yolo, build_mini_voc


def _make_analyzer(tmp_path, monkeypatch):
    """构建一个 analyzer，其 registry 仅用于路径解析（scan 不需要注册表）。"""
    from dataset_analyzer import DatasetAnalyzer
    return DatasetAnalyzer(registry=None)


def test_scan_coco(tmp_path):
    root = tmp_path / "mini_coco"
    expected = build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "COCO"
    assert result["image_count"] == expected["image_count"]
    assert result["object_count"] == expected["object_count"]
    assert result["classes"] == expected["classes"]
    assert result["splits"]["train"]["image_count"] == 2
    assert result["splits"]["val"]["object_count"] == 1
    assert result["image_size"] == "640x640"
    assert result["version"] == "1.0"
    assert "Mini COCO" in result["description"]


def test_scan_yolo(tmp_path):
    root = tmp_path / "mini_yolo"
    build_mini_yolo(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "YOLO"
    assert result["image_count"] == 4
    assert result["object_count"] == 6


def test_scan_voc(tmp_path):
    root = tmp_path / "mini_voc"
    build_mini_voc(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is True
    assert result["format"] == "VOC"
    assert result["image_count"] == 4


def test_scan_invalid_path(tmp_path):
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(tmp_path / "nope"))
    assert result["valid"] is False
    assert result["format"] is None


def test_scan_unrecognized(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    assert result["valid"] is False
    assert result["format"] is None


def test_scan_origin_image_count(tmp_path):
    """tile 文件名聚合原图数。"""
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    result = az.scan(str(root))
    # mini_coco 4 张图文件名各异 → 4 张原图
    assert result["origin_image_count"] == 4
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_analyzer.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 DatasetAnalyzer.scan**

创建 `backend/core/dataset_analyzer.py`：

```python
"""数据集分析器：格式识别 + 轻量统计 + 报告重统计 + 缓存。

scan() 做轻量统计（不解析全部框几何），compute_report() 做重统计并缓存到
dataset_meta.json.report_cache。
"""
import json
import logging
from collections import Counter
from pathlib import Path

from config import PROJECT_ROOT
from dataset_formats import detect_format, parse_coco, parse_voc, parse_yolo

logger = logging.getLogger(__name__)

_PARSERS = {"COCO": parse_coco, "YOLO": parse_yolo, "VOC": parse_voc}


class DatasetAnalyzer:
    def __init__(self, registry=None):
        self._registry = registry

    # ── 路径预检（轻量统计）──────────────────────────────
    def scan(self, path: str) -> dict:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if not p.exists():
            return self._invalid(f"路径不存在: {path}")
        if not p.is_dir():
            return self._invalid("指定路径不是文件夹")
        fmt = detect_format(p)
        if fmt is None:
            return self._invalid("无法识别数据集格式（非 COCO/YOLO/VOC 标准布局）")
        ir = _PARSERS[fmt](p)
        return self._summarize(fmt, ir, p)

    def _invalid(self, msg: str) -> dict:
        return {"valid": False, "format": None, "classes": [], "image_count": 0,
                "object_count": 0, "splits": {}, "origin_image_count": 0,
                "image_size": "", "version": "", "description": "", "message": msg}

    def _summarize(self, fmt: str, ir: dict, dataset_dir: Path) -> dict:
        classes = ir["classes"]
        splits = {}
        origin_stems = set()
        res_set = Counter()
        total_objs = 0
        for im in ir["images"]:
            sp = im["split"]
            s = splits.setdefault(sp, {"image_count": 0, "object_count": 0})
            s["image_count"] += 1
            s["object_count"] += len(im["boxes"])
            total_objs += len(im["boxes"])
            origin_stems.add(im["origin_stem"])
            res_set[f"{im['width']}x{im['height']}"] += 1
        image_size = res_set.most_common(1)[0][0] if res_set else ""
        meta = ir["meta"]
        return {
            "valid": True, "format": fmt, "classes": classes,
            "image_count": len(ir["images"]), "object_count": total_objs,
            "splits": splits, "origin_image_count": len(origin_stems),
            "image_size": image_size,
            "version": meta.get("version") or "1.0",
            "description": meta.get("description", ""),
            "message": f"识别为 {fmt} 格式，{len(ir['images'])} 张图片",
        }

    # compute_report 将在 Task 5 实现
    def compute_report(self, dataset_id: str, force: bool = False) -> dict:
        raise NotImplementedError
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_analyzer.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dataset_analyzer.py backend/core/dataset_analyzer.py
git commit -m "feat(dataset): DatasetAnalyzer.scan 轻量统计"
```

---

## Task 5: DatasetAnalyzer — compute_report 重统计 + 缓存（TDD）

**Files:**
- Modify: `backend/tests/test_dataset_analyzer.py`
- Modify: `backend/core/dataset_analyzer.py`

- [ ] **Step 1: 追加 compute_report 失败测试**

在 `backend/tests/test_dataset_analyzer.py` 末尾追加：

```python
def test_compute_report_heavy_stats_and_cache(tmp_path):
    """报告重统计 + 缓存命中。"""
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    # 伪造一个 dataset 配置（registry 为 None 时直接传配置）
    cfg = {"dataset_id": "ds1", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    rep1 = az.compute_report(cfg, force=False)
    assert rep1["summary"]["total_images"] == 4
    assert rep1["summary"]["total_objects"] == 6
    assert rep1["summary"]["non_empty_images"] == 4
    assert abs(rep1["bbox_stats"]["avg_width"] - 43.75) < 1  # (30+50+60+20+40+40)/6
    assert rep1["cached"] is False
    # size_dist 三段之和 = 1
    sd = rep1["bbox_stats"]["size_dist"]
    assert abs(sd["small"] + sd["medium"] + sd["large"] - 1.0) < 0.01
    # 缓存命中
    rep2 = az.compute_report(cfg, force=False)
    assert rep2["cached"] is True


def test_compute_report_force_recompute(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    cfg = {"dataset_id": "ds2", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    az.compute_report(cfg, force=False)
    rep = az.compute_report(cfg, force=True)
    assert rep["cached"] is False


def test_compute_report_class_imbalance_warning(tmp_path):
    root = tmp_path / "mini_coco"
    build_mini_coco(root)
    az = DatasetAnalyzer(registry=None)
    cfg = {"dataset_id": "ds3", "format": "COCO", "path": str(root),
           "classes": ["Sugarcane Seedling"], "image_count": 4, "object_count": 6,
           "splits": {"train": {"image_count": 2, "object_count": 4},
                      "val": {"image_count": 1, "object_count": 1},
                      "test": {"image_count": 1, "object_count": 1}},
           "origin_image_count": 4}
    rep = az.compute_report(cfg, force=True)
    # 单类别占比 100% > 90% → 失衡告警
    assert any("失衡" in w or "imbalance" in w.lower() for w in rep["warnings"])
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_analyzer.py -v -k report`
Expected: FAIL（`NotImplementedError`）

- [ ] **Step 3: 实现 compute_report + 重统计 + 缓存**

在 `backend/core/dataset_analyzer.py` 中替换 `compute_report` 占位实现，并新增辅助方法：

```python
    # ── 报告重统计 + 缓存 ──────────────────────────────────
    def compute_report(self, dataset_cfg, force: bool = False) -> dict:
        """dataset_cfg 可以是 dataset_id 字符串（需 registry）或配置 dict。"""
        cfg = self._resolve_cfg(dataset_cfg)
        dataset_dir = self._resolve_path(cfg["path"])
        meta_path = dataset_dir / "dataset_meta.json"
        meta = self._read_meta(meta_path)
        cache = (meta or {}).get("report_cache")
        if cache and not force:
            report = dict(cache)
            report["cached"] = True
            report["dataset_id"] = cfg["dataset_id"]
            return report
        ir = _PARSERS[cfg["format"]](dataset_dir)
        heavy = self._compute_heavy_stats(ir)
        splits = self._splits_from_ir(ir)
        report = {
            "dataset_id": cfg["dataset_id"],
            "summary": {
                "total_images": len(ir["images"]),
                "total_objects": sum(len(im["boxes"]) for im in ir["images"]),
                "origin_image_count": len({im["origin_stem"] for im in ir["images"]}),
                "non_empty_images": sum(1 for im in ir["images"] if im["boxes"]),
                "splits": splits,
            },
            "class_dist": heavy["class_dist"],
            "bbox_stats": heavy["bbox_stats"],
            "image_stats": heavy["image_stats"],
            "warnings": heavy["warnings"],
            "cached": False,
            "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        # 回写缓存
        meta = meta or {"dataset_id": cfg["dataset_id"]}
        meta["report_cache"] = {k: v for k, v in report.items() if k != "cached"}
        meta["report_cached_at"] = report["generated_at"]
        self._write_meta(meta_path, meta)
        return report

    def _resolve_cfg(self, dataset_cfg):
        if isinstance(dataset_cfg, dict):
            return dataset_cfg
        if self._registry is None:
            raise RuntimeError("analyzer 无 registry，无法按 id 查询")
        return self._registry.get_dataset(dataset_cfg)

    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _splits_from_ir(self, ir: dict) -> dict:
        splits = {}
        for im in ir["images"]:
            s = splits.setdefault(im["split"], {"image_count": 0, "object_count": 0})
            s["image_count"] += 1
            s["object_count"] += len(im["boxes"])
        return splits

    def _compute_heavy_stats(self, ir: dict) -> dict:
        class_counter = Counter()
        resolutions = Counter()
        aspect_ratios = Counter()
        widths, heights, areas = [], [], []
        non_empty = 0
        for im in ir["images"]:
            resolutions[f"{im['width']}x{im['height']}"] += 1
            ar = round(im["width"] / im["height"], 2) if im["height"] else 0
            aspect_ratios[f"{ar:.2f}"] += 1
            if im["boxes"]:
                non_empty += 1
            for b in im["boxes"]:
                _, _, w, h = b["bbox"]
                widths.append(w)
                heights.append(h)
                areas.append(w * h)
                class_counter[b["class_name"]] += 1
        total_objs = sum(class_counter.values())
        class_dist = [{"name": n, "class_id": i, "count": c,
                       "pct": round(c / total_objs * 100, 2) if total_objs else 0}
                      for i, (n, c) in enumerate(sorted(class_counter.items()))]
        warnings = []
        if class_dist and total_objs:
            if class_dist[0]["pct"] > 90:
                warnings.append(
                    f"类别分布失衡：{class_dist[0]['name']} 占比 {class_dist[0]['pct']}% > 90%")
        # 面积直方图（20 桶）
        area_hist = self._histogram(areas, 20)
        # COCO small/medium/large
        size_dist = self._coco_size_dist(areas)
        bbox_stats = {
            "avg_width": round(sum(widths) / len(widths), 2) if widths else 0,
            "avg_height": round(sum(heights) / len(heights), 2) if heights else 0,
            "area_hist": area_hist,
            "size_dist": size_dist,
        }
        return {
            "class_dist": class_dist,
            "bbox_stats": bbox_stats,
            "image_stats": {"resolutions": dict(resolutions),
                            "aspect_ratios": dict(aspect_ratios)},
            "warnings": warnings,
            "non_empty_images": non_empty,
        }

    @staticmethod
    def _histogram(values, bins):
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi == lo:
            return [[[lo, hi], len(values)]]
        step = (hi - lo) / bins
        edges = [lo + i * step for i in range(bins + 1)]
        counts = [0] * bins
        for v in values:
            idx = min(int((v - lo) / step), bins - 1)
            counts[idx] += 1
        return [[[round(edges[i], 2), round(edges[i + 1], 2)], counts[i]]
                for i in range(bins)]

    @staticmethod
    def _coco_size_dist(areas):
        if not areas:
            return {"small": 0, "medium": 0, "large": 0}
        small = sum(1 for a in areas if a < 32 * 32)
        medium = sum(1 for a in areas if 32 * 32 <= a <= 96 * 96)
        large = sum(1 for a in areas if a > 96 * 96)
        total = len(areas)
        return {"small": round(small / total, 4),
                "medium": round(medium / total, 4),
                "large": round(large / total, 4)}

    @staticmethod
    def _read_meta(meta_path: Path):
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_meta(meta_path: Path, meta: dict):
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def invalidate_cache(self, dataset_dir: Path):
        """重新导入时失效报告缓存。"""
        meta_path = Path(dataset_dir) / "dataset_meta.json"
        meta = self._read_meta(meta_path)
        if meta:
            meta["report_cache"] = None
            meta["report_cached_at"] = None
            self._write_meta(meta_path, meta)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_analyzer.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dataset_analyzer.py backend/core/dataset_analyzer.py
git commit -m "feat(dataset): compute_report 重统计 + 缓存 + 失衡告警"
```

---

## Task 6: DatasetRegistry — YAML 持久化 + CRUD + 自动扫描（TDD）

**Files:**
- Create: `backend/tests/test_dataset_registry.py`
- Create: `backend/core/dataset_registry.py`

- [ ] **Step 1: 编写持久化/CRUD/自动扫描失败测试**

创建 `backend/tests/test_dataset_registry.py`：

```python
"""DatasetRegistry 测试。"""
from dataset_registry import DatasetRegistry
from dataset_analyzer import DatasetAnalyzer
from dataset_factory import build_mini_coco


def _make_registry(tmp_path):
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    yaml_path = tmp_path / "datasets.yaml"
    reg = DatasetRegistry(datasets_dir=datasets_dir, yaml_path=yaml_path)
    az = DatasetAnalyzer(registry=reg)
    reg.set_analyzer(az)
    return reg, datasets_dir, yaml_path


def test_auto_discover_registers_coco(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    reg.load_from_yaml()
    ds = reg.list_datasets()
    assert len(ds) == 1
    assert ds[0]["format"] == "COCO"
    assert ds[0]["source"] == "imported"
    assert ds[0]["image_count"] == 4
    assert ds[0]["dataset_id"] == "dataset_mini_(coco)"


def test_auto_discover_skips_unrecognized(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    (datasets_dir / "not_a_dataset").mkdir()
    (datasets_dir / "not_a_dataset" / "random.txt").write_text("x")
    reg.load_from_yaml()
    assert reg.list_datasets() == []


def test_yaml_persistence_roundtrip(tmp_path):
    reg, datasets_dir, yaml_path = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    # 重新加载验证持久化
    reg2, _, _ = _make_registry(tmp_path)
    reg2.load_from_yaml()
    assert len(reg2.list_datasets()) == 1
    assert yaml_path.exists()


def test_get_dataset_missing_raises(tmp_path):
    reg, _, _ = _make_registry(tmp_path)
    reg.load_from_yaml()
    try:
        reg.get_dataset("nope")
        assert False, "应抛 KeyError"
    except KeyError:
        pass


def test_format_dist(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    dist = reg.format_dist()
    assert dist["COCO"] == 1
    assert dist["YOLO"] == 0


def test_list_datasets_format_filter(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    build_mini_coco(datasets_dir / "Mini_COCO")
    reg.load_from_yaml()
    assert len(reg.list_datasets(fmt="COCO")) == 1
    assert len(reg.list_datasets(fmt="YOLO")) == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_registry.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 实现 DatasetRegistry 核心部分**

创建 `backend/core/dataset_registry.py`（本任务实现持久化 + 自动扫描 + CRUD 查询；import/delete/images 在 Task 7 实现）：

```python
"""数据集注册中心：YAML 持久化 + 自动扫描 + CRUD + 图片索引 + 预览。

镜像 BatchRegistry 模式：datasets/datasets.yaml 就地持久化，启动扫描 datasets/ 自动注册。
"""
import io
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from PIL import Image

from config import DATASETS_DIR, DATASETS_YAML, IMAGE_EXTENSIONS, PROJECT_ROOT, \
    PREVIEW_MEDIUM_SIZE, THUMBNAIL_MAX_SIZE
from dataset_formats import detect_format

_DATASET_FIELD_ORDER = [
    "dataset_id", "name", "format", "source", "path", "classes",
    "splits", "image_count", "object_count", "origin_image_count",
    "image_size", "version", "description", "created_at", "status",
]


class _InlineList(list):
    """flow style 列表输出。"""
    pass


def _inline_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


yaml.add_representer(_InlineList, _inline_list_representer)


def _sanitize(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def _infer_name(folder_name: str, fmt: str) -> str:
    """推断数据集名：文件夹名以 _{fmt} 结尾则 → '{stem} ({FMT})'，否则用文件夹名。"""
    lower = folder_name.lower()
    suffixes = {f"_{fmt.lower()}", "_pascal-voc", "_voc"}
    for suf in suffixes:
        if lower.endswith(suf):
            stem = folder_name[: -len(suf)]
            return f"{stem} ({fmt})"
    return folder_name


class DatasetRegistry:
    def __init__(self, datasets_dir=DATASETS_DIR, yaml_path=DATASETS_YAML):
        self._datasets_dir = Path(datasets_dir)
        self._yaml_path = Path(yaml_path)
        self._datasets: Dict[str, dict] = {}
        self._ignored_folders: set = set()
        self._analyzer = None

    def set_analyzer(self, analyzer):
        self._analyzer = analyzer

    # ── 加载与持久化 ───────────────────────────────────────
    def load_from_yaml(self):
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for d in data.get("datasets", []) or []:
                self._datasets[d["dataset_id"]] = d
            self._ignored_folders = set(data.get("ignored_folders", []) or [])
        if self._auto_discover():
            self.save_to_yaml()

    def save_to_yaml(self):
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        datasets_list = [self._ordered(d) for d in self._datasets.values()]
        data = {"datasets": datasets_list,
                "ignored_folders": sorted(self._ignored_folders)}
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False,
                      default_flow_style=False, indent=2, width=1000)

    def _ordered(self, cfg: dict) -> dict:
        ordered = {}
        for k in _DATASET_FIELD_ORDER:
            if k in cfg:
                v = cfg[k]
                if k == "classes" and isinstance(v, list):
                    v = _InlineList(v)
                ordered[k] = v
        for k, v in cfg.items():
            if k not in ordered:
                ordered[k] = v
        return ordered

    def _auto_discover(self) -> bool:
        if not self._datasets_dir.is_dir():
            return False
        registered_paths = set()
        for cfg in self._datasets.values():
            try:
                registered_paths.add(str(self._resolve_path(cfg["path"]).resolve()))
            except Exception:
                pass
        added = False
        for entry in sorted(self._datasets_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name in self._ignored_folders:
                continue
            try:
                resolved = str(entry.resolve())
            except Exception:
                continue
            if resolved in registered_paths:
                continue
            fmt = detect_format(entry)
            if fmt is None:
                continue
            self._register_from_scan(entry, fmt)
            added = True
        return added

    def _register_from_scan(self, folder: Path, fmt: str):
        """自动发现注册（轻量统计）。"""
        summary = self._analyzer.scan(str(folder)) if self._analyzer else None
        name = _infer_name(folder.name, fmt)
        dataset_id = "dataset_" + _sanitize(name).lower()
        dataset_id = self._ensure_unique_id(dataset_id)
        cfg = self._build_cfg(dataset_id, name, fmt, "imported",
                              str(self._to_relative(folder)), summary)
        self._datasets[dataset_id] = cfg
        # 自动发现也写 dataset_meta.json
        if self._analyzer:
            self._analyzer._write_meta(folder / "dataset_meta.json",
                                       self._meta_from_cfg(cfg, folder))

    def _build_cfg(self, dataset_id, name, fmt, source, rel_path, summary) -> dict:
        summary = summary or {}
        return {
            "dataset_id": dataset_id, "name": name, "format": fmt, "source": source,
            "path": rel_path, "classes": _InlineList(summary.get("classes", [])),
            "splits": summary.get("splits", {}),
            "image_count": summary.get("image_count", 0),
            "object_count": summary.get("object_count", 0),
            "origin_image_count": summary.get("origin_image_count", 0),
            "image_size": summary.get("image_size", ""),
            "version": summary.get("version", "1.0"),
            "description": summary.get("description", ""),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "ready",
        }

    def _meta_from_cfg(self, cfg, folder):
        return {"dataset_id": cfg["dataset_id"], "name": cfg["name"],
                "format": cfg["format"], "classes": list(cfg["classes"]),
                "splits": cfg["splits"], "image_count": cfg["image_count"],
                "object_count": cfg["object_count"],
                "origin_image_count": cfg["origin_image_count"],
                "image_size": cfg["image_size"], "version": cfg["version"],
                "source_path": cfg["path"], "layout": {},
                "report_cache": None, "report_cached_at": None,
                "generated_at": cfg["created_at"]}

    def _ensure_unique_id(self, dataset_id: str) -> str:
        if dataset_id not in self._datasets:
            return dataset_id
        i = 2
        while f"{dataset_id}_{i}" in self._datasets:
            i += 1
        return f"{dataset_id}_{i}"

    # ── 查询 ───────────────────────────────────────────────
    def list_datasets(self, fmt: Optional[str] = None) -> List[dict]:
        result = list(self._datasets.values())
        if fmt:
            result = [d for d in result if d["format"] == fmt]
        return sorted(result, key=lambda d: d["created_at"], reverse=True)

    def get_dataset(self, dataset_id: str) -> dict:
        if dataset_id not in self._datasets:
            raise KeyError(f"数据集不存在: {dataset_id}")
        return self._datasets[dataset_id]

    def format_dist(self) -> dict:
        dist = {"YOLO": 0, "COCO": 0, "VOC": 0}
        for d in self._datasets.values():
            f = d.get("format")
            dist[f] = dist.get(f, 0) + 1
        return dist

    # ── 路径工具 ───────────────────────────────────────────
    def _resolve_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    def _to_relative(self, abs_path: Path) -> str:
        try:
            return str(abs_path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")

    # 以下方法在 Task 7 实现
    def scan_path(self, path: str) -> dict:
        raise NotImplementedError

    def import_dataset(self, path: str, name=None, description=None) -> dict:
        raise NotImplementedError

    def delete_dataset(self, dataset_id: str, delete_files: bool = False):
        raise NotImplementedError

    def list_images(self, dataset_id, split, page, page_size) -> dict:
        raise NotImplementedError

    def get_image_preview(self, dataset_id, filename, split, size) -> bytes:
        raise NotImplementedError
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_registry.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dataset_registry.py backend/core/dataset_registry.py
git commit -m "feat(dataset): DatasetRegistry YAML 持久化 + 自动扫描 + 查询"
```

---

## Task 7: DatasetRegistry — import/scan/delete/images/preview（TDD）

**Files:**
- Modify: `backend/tests/test_dataset_registry.py`
- Modify: `backend/core/dataset_registry.py`

- [ ] **Step 1: 追加 import/delete/images 失败测试**

在 `backend/tests/test_dataset_registry.py` 末尾追加：

```python
from pathlib import Path


def test_scan_path(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    result = reg.scan_path(str(coco_dir))
    assert result["valid"] is True
    assert result["format"] == "COCO"


def test_import_dataset(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    assert cfg["dataset_id"] == "dataset_mini_(coco)"
    assert cfg["format"] == "COCO"
    assert cfg["source"] == "imported"
    # dataset_meta.json 生成
    assert (coco_dir / "dataset_meta.json").exists()
    # 已注册
    assert reg.get_dataset(cfg["dataset_id"])["image_count"] == 4


def test_import_duplicate_name_raises(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    reg.import_dataset(str(coco_dir))
    try:
        reg.import_dataset(str(coco_dir))
        assert False, "重复导入应抛 ValueError"
    except ValueError:
        pass


def test_import_unrecognized_raises(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    bad = datasets_dir / "bad"
    bad.mkdir()
    try:
        reg.import_dataset(str(bad))
        assert False
    except ValueError:
        pass


def test_delete_registry_only(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    reg.delete_dataset(cfg["dataset_id"], delete_files=False)
    # 注册删除，文件保留
    assert coco_dir.exists()
    # 加入 ignored_folders
    assert "Mini_COCO" in reg._ignored_folders


def test_delete_with_files(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    reg.delete_dataset(cfg["dataset_id"], delete_files=True)
    assert not coco_dir.exists()


def test_list_images_pagination(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    result = reg.list_images(cfg["dataset_id"], split="train", page=1, page_size=2)
    assert result["total"] == 2
    assert len(result["images"]) == 2
    assert result["images"][0]["thumbnail_url"].startswith(
        f"/api/datasets/{cfg['dataset_id']}/images/")


def test_list_images_missing_split(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    result = reg.list_images(cfg["dataset_id"], split="train", page=1, page_size=50)
    assert result["total"] == 2


def test_get_image_preview(tmp_path):
    reg, datasets_dir, _ = _make_registry(tmp_path)
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    cfg = reg.import_dataset(str(coco_dir))
    img_bytes = reg.get_image_preview(cfg["dataset_id"], "img_t1.jpg",
                                      split="train", size="thumbnail")
    assert len(img_bytes) > 0
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_dataset_registry.py -v -k "scan_path or import or delete or list_images or preview"`
Expected: FAIL（`NotImplementedError`）

- [ ] **Step 3: 实现 import/scan/delete/images/preview**

在 `backend/core/dataset_registry.py` 中替换 5 个 `NotImplementedError` 方法：

```python
    # ── 路径预检 ───────────────────────────────────────────
    def scan_path(self, path: str) -> dict:
        if self._analyzer is None:
            raise RuntimeError("analyzer 未注入")
        return self._analyzer.scan(path)

    # ── 导入注册 ───────────────────────────────────────────
    def import_dataset(self, path: str, name=None, description=None) -> dict:
        if self._analyzer is None:
            raise RuntimeError("analyzer 未注入")
        folder = self._resolve_path(path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"路径不存在或非目录: {path}")
        summary = self._analyzer.scan(path)
        if not summary["valid"]:
            raise ValueError(summary["message"])
        fmt = summary["format"]
        inferred_name = _infer_name(folder.name, fmt)
        name = name or inferred_name
        # 重名校验
        for d in self._datasets.values():
            if d["name"] == name:
                raise ValueError(f"数据集名称已存在: {name}")
            if self._resolve_path(d["path"]).resolve() == folder.resolve():
                raise ValueError(f"该路径已注册为数据集 {d['dataset_id']}")
        dataset_id = "dataset_" + _sanitize(name).lower()
        dataset_id = self._ensure_unique_id(dataset_id)
        rel_path = self._to_relative(folder)
        cfg = self._build_cfg(dataset_id, name, fmt, "imported", rel_path, summary)
        if description:
            cfg["description"] = description
        self._datasets[dataset_id] = cfg
        # 写 dataset_meta.json
        self._analyzer._write_meta(folder / "dataset_meta.json",
                                   self._meta_from_cfg(cfg, folder))
        self.save_to_yaml()
        return cfg

    # ── 删除 ───────────────────────────────────────────────
    def delete_dataset(self, dataset_id: str, delete_files: bool = False):
        if dataset_id not in self._datasets:
            raise KeyError(f"数据集不存在: {dataset_id}")
        cfg = self._datasets[dataset_id]
        folder = self._resolve_path(cfg["path"])
        if delete_files and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
        else:
            meta = folder / "dataset_meta.json"
            if meta.exists():
                meta.unlink()
        # datasets/ 下的自动发现数据集加入 ignored_folders
        try:
            folder.resolve().relative_to(self._datasets_dir.resolve())
            self._ignored_folders.add(folder.name)
        except ValueError:
            pass
        del self._datasets[dataset_id]
        self.save_to_yaml()

    # ── 样本浏览 ───────────────────────────────────────────
    def _image_dir_for_split(self, cfg: dict, split: str) -> Path:
        folder = self._resolve_path(cfg["path"])
        fmt = cfg["format"]
        if fmt == "COCO":
            direct = folder / split
            if direct.is_dir() and any(f.suffix.lower() in IMAGE_EXTENSIONS
                                        for f in direct.iterdir() if f.is_file()):
                return direct
            return folder / "images" / split
        if fmt == "YOLO":
            return folder / "images" / split
        # VOC
        return folder / split / "images"

    def list_images(self, dataset_id: str, split: str = "train",
                    page: int = 1, page_size: int = 50) -> dict:
        cfg = self.get_dataset(dataset_id)
        img_dir = self._image_dir_for_split(cfg, split)
        images = []
        if img_dir.is_dir():
            for entry in sorted(img_dir.iterdir()):
                if not entry.is_file() or entry.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                try:
                    stat = entry.stat()
                    with Image.open(entry) as im:
                        w, h = im.size
                        fmt = im.format or entry.suffix.lstrip('.').upper()
                except Exception:
                    continue
                images.append({"filename": entry.name, "split": split,
                               "size_bytes": stat.st_size, "width": w, "height": h,
                               "format": fmt})
        total = len(images)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        paged = images[start:start + page_size]
        for im in paged:
            fn = im["filename"]
            im["thumbnail_url"] = (
                f"/api/datasets/{dataset_id}/images/{fn}/preview?split={split}&size=thumbnail")
            im["preview_url"] = (
                f"/api/datasets/{dataset_id}/images/{fn}/preview?split={split}&size=medium")
        return {"images": paged, "total": total, "page": page,
                "page_size": page_size, "total_pages": total_pages, "split": split}

    def get_image_preview(self, dataset_id: str, filename: str,
                          split: str = "train", size: str = "thumbnail") -> bytes:
        cfg = self.get_dataset(dataset_id)
        img_dir = self._image_dir_for_split(cfg, split)
        image_path = img_dir / filename
        if not image_path.is_file():
            raise FileNotFoundError(f"图片不存在: {filename}")
        if size == "original":
            with open(image_path, "rb") as f:
                return f.read()
        max_size = THUMBNAIL_MAX_SIZE if size == "thumbnail" else PREVIEW_MEDIUM_SIZE
        quality = 80 if size == "thumbnail" else 85
        with Image.open(image_path) as im:
            im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
            im.thumbnail((max_size, max_size), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue()
```

- [ ] **Step 4: 运行全部 registry 测试确认通过**

Run: `cd backend && python -m pytest tests/test_dataset_registry.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_dataset_registry.py backend/core/dataset_registry.py
git commit -m "feat(dataset): import/scan/delete/images/preview 实现"
```

---

## Task 8: datasets_api.py 重写 9 端点（TDD）

**Files:**
- Modify: `backend/api/datasets_api.py`
- Create: `backend/tests/test_datasets_api.py`

- [ ] **Step 1: 编写 API 失败测试**

创建 `backend/tests/test_datasets_api.py`：

```python
"""数据集 API 集成测试。"""
import json

import pytest

from dataset_factory import build_mini_coco


@pytest.fixture
def app_with_datasets(tmp_path, monkeypatch):
    """构造一个独立 Flask app + 注入临时 datasets 目录。"""
    from config import DATASETS_DIR, DATASETS_YAML
    import dataset_registry as dr_mod
    import dataset_analyzer as az_mod
    import engine as engine_mod

    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir()
    yaml_path = tmp_path / "datasets.yaml"

    reg = dr_mod.DatasetRegistry(datasets_dir=datasets_dir, yaml_path=yaml_path)
    az = az_mod.DatasetAnalyzer(registry=reg)
    reg.set_analyzer(az)
    reg.load_from_yaml()

    # 注入到 engine 模块全局
    monkeypatch.setattr(engine_mod, "dataset_registry", reg)
    monkeypatch.setattr(engine_mod, "dataset_analyzer", az)

    from app import create_app
    app = create_app()
    return app, datasets_dir


def test_list_datasets_empty(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.get("/api/datasets")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["data"]["total"] == 0
    assert body["data"]["format_dist"] == {"YOLO": 0, "COCO": 0, "VOC": 0}


def test_scan_and_import_flow(app_with_datasets):
    app, datasets_dir = app_with_datasets
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    client = app.test_client()
    # scan
    r = client.post("/api/datasets/scan", json={"path": str(coco_dir)})
    assert r.status_code == 200
    assert r.get_json()["data"]["format"] == "COCO"
    # import
    r = client.post("/api/datasets/import", json={"path": str(coco_dir)})
    assert r.status_code == 201
    did = r.get_json()["data"]["dataset_id"]
    # list
    r = client.get("/api/datasets")
    assert r.get_json()["data"]["total"] == 1
    # detail
    r = client.get(f"/api/datasets/{did}")
    assert r.status_code == 200
    assert r.get_json()["data"]["dataset_id"] == did
    # report
    r = client.get(f"/api/datasets/{did}/report")
    assert r.status_code == 200
    rep = r.get_json()["data"]
    assert rep["summary"]["total_images"] == 4
    assert rep["cached"] is False
    # report 缓存命中
    r = client.get(f"/api/datasets/{did}/report")
    assert r.get_json()["data"]["cached"] is True
    # images
    r = client.get(f"/api/datasets/{did}/images?split=train")
    assert r.status_code == 200
    assert r.get_json()["data"]["total"] == 2
    # preview
    r = client.get(f"/api/datasets/{did}/images/img_t1.jpg/preview?split=train&size=thumbnail")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_scan_invalid_returns_400(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.post("/api/datasets/scan", json={"path": "/nope/missing"})
    assert r.status_code == 400


def test_get_missing_404(app_with_datasets):
    app, _ = app_with_datasets
    client = app.test_client()
    r = client.get("/api/datasets/nope")
    assert r.status_code == 404


def test_delete_registry_only(app_with_datasets):
    app, datasets_dir = app_with_datasets
    coco_dir = datasets_dir / "Mini_COCO"
    build_mini_coco(coco_dir)
    client = app.test_client()
    did = client.post("/api/datasets/import", json={"path": str(coco_dir)}).get_json()["data"]["dataset_id"]
    r = client.delete(f"/api/datasets/{did}")
    assert r.status_code == 200
    assert coco_dir.exists()  # 文件保留
    r = client.get(f"/api/datasets/{did}")
    assert r.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_datasets_api.py -v`
Expected: FAIL（Mock 实现不匹配新契约）

- [ ] **Step 3: 重写 datasets_api.py**

替换 `backend/api/datasets_api.py` 全部内容：

```python
"""数据集管理 API（第一阶段：导入注册 + 统计报告 + 浏览删除）。

对齐 batches_api 风格：统一响应信封 {"success", "data", "message"}。
ValueError → 400，KeyError → 404，创建成功 → 201。
"""
from flask import Blueprint, Response, jsonify, request

from core.engine import get_dataset_analyzer, get_dataset_registry

datasets_bp = Blueprint("datasets", __name__)


def _error(message: str, status_code: int = 400):
    return jsonify({"success": False, "data": None, "message": message}), status_code


def _registry():
    reg = get_dataset_registry()
    if reg is None:
        _error("dataset_registry 未初始化", 500)
    return reg


@datasets_bp.route("/api/datasets", methods=["GET"])
def list_datasets():
    """GET /api/datasets → 数据集列表，?format= 过滤，返回格式分布。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    fmt = request.args.get("format") or None
    datasets = reg.list_datasets(fmt=fmt)
    return jsonify({
        "success": True,
        "data": {"datasets": datasets, "total": len(datasets),
                 "format_dist": reg.format_dist()},
        "message": "获取数据集列表成功",
    })


@datasets_bp.route("/api/datasets/scan", methods=["POST"])
def scan_dataset():
    """POST /api/datasets/scan → 路径预检：格式识别 + 轻量统计。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("path", "")
    if not path:
        return _error("缺少 path 参数", 400)
    try:
        result = reg.scan_path(path)
    except Exception as exc:
        return _error(f"扫描失败: {exc}", 500)
    status = 200 if result["valid"] else 400
    return jsonify({
        "success": result["valid"],
        "data": result,
        "message": result.get("message", ""),
    }), status


@datasets_bp.route("/api/datasets/import", methods=["POST"])
def import_dataset():
    """POST /api/datasets/import → 导入注册。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    body = request.get_json(silent=True) or {}
    path = body.get("path", "")
    if not path:
        return _error("缺少 path 参数", 400)
    try:
        cfg = reg.import_dataset(path, name=body.get("name"),
                                 description=body.get("description"))
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception as exc:
        return _error(f"导入失败: {exc}", 500)
    return jsonify({
        "success": True, "data": cfg, "message": "数据集导入成功",
    }), 201


@datasets_bp.route("/api/datasets/<dataset_id>", methods=["GET"])
def get_dataset(dataset_id):
    """GET /api/datasets/<dataset_id> → 数据集详情。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    try:
        cfg = reg.get_dataset(dataset_id)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    return jsonify({
        "success": True, "data": cfg, "message": "获取数据集详情成功",
    })


@datasets_bp.route("/api/datasets/<dataset_id>", methods=["DELETE"])
def delete_dataset(dataset_id):
    """DELETE /api/datasets/<dataset_id> → 删除（?delete_files=true 物理删除）。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    delete_files = request.args.get("delete_files", "false").lower() == "true"
    try:
        reg.delete_dataset(dataset_id, delete_files=delete_files)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    msg = "数据集目录已物理删除" if delete_files else "数据集已删除（原始文件未删除）"
    return jsonify({"success": True, "data": None, "message": msg})


@datasets_bp.route("/api/datasets/<dataset_id>/report", methods=["GET"])
def dataset_report(dataset_id):
    """GET /api/datasets/<dataset_id>/report → 统计报告（?force=true 强制重算）。"""
    reg = get_dataset_registry()
    az = get_dataset_analyzer()
    if reg is None or az is None:
        return _error("数据集引擎未初始化", 500)
    force = request.args.get("force", "false").lower() == "true"
    try:
        cfg = reg.get_dataset(dataset_id)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    try:
        report = az.compute_report(cfg, force=force)
    except Exception as exc:
        return _error(f"生成报告失败: {exc}", 500)
    return jsonify({"success": True, "data": report, "message": "ok"})


@datasets_bp.route("/api/datasets/<dataset_id>/images", methods=["GET"])
def list_dataset_images(dataset_id):
    """GET /api/datasets/<dataset_id>/images → 样本分页浏览。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    split = request.args.get("split", "train")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    try:
        result = reg.list_images(dataset_id, split=split, page=page, page_size=page_size)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    except Exception as exc:
        return _error(f"读取样本列表失败: {exc}", 500)
    return jsonify({"success": True, "data": result, "message": "获取样本列表成功"})


@datasets_bp.route("/api/datasets/<dataset_id>/images/<path:filename>/preview", methods=["GET"])
def dataset_image_preview(dataset_id, filename):
    """GET /api/datasets/<dataset_id>/images/<filename>/preview → 样本预览。"""
    reg = get_dataset_registry()
    if reg is None:
        return _error("dataset_registry 未初始化", 500)
    split = request.args.get("split", "train")
    size = request.args.get("size", "thumbnail")
    if size not in ("thumbnail", "medium", "original"):
        size = "thumbnail"
    try:
        img_bytes = reg.get_image_preview(dataset_id, filename, split=split, size=size)
    except KeyError:
        return _error(f"数据集不存在: {dataset_id}", 404)
    except FileNotFoundError:
        return _error(f"图片不存在: {filename}", 404)
    except Exception as exc:
        return _error(f"读取图片失败: {exc}", 500)
    resp = Response(img_bytes, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@datasets_bp.route("/api/datasets/pick-folder", methods=["POST"])
def pick_folder():
    """POST /api/datasets/pick-folder → 系统原生文件夹选择对话框。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return _error("当前环境未安装 tkinter，请手动输入路径", 500)
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="选择数据集目录")
        root.destroy()
    except Exception as exc:
        return _error(f"打开文件夹对话框失败: {exc}", 500)
    if not folder:
        return jsonify({"success": False, "data": {"cancelled": True},
                        "message": "用户取消选择"}), 200
    return jsonify({"success": True, "data": {"path": folder.replace("\\", "/")},
                    "message": "文件夹选择成功"})
```

- [ ] **Step 4: 运行 API 测试确认通过**

Run: `cd backend && python -m pytest tests/test_datasets_api.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/api/datasets_api.py backend/tests/test_datasets_api.py
git commit -m "feat(dataset): 重写 datasets_api 9 端点真实实现"
```

---

## Task 9: engine.py 装配 + app.py 路由确认

**Files:**
- Modify: `backend/core/engine.py`
- Verify: `backend/app.py`

- [ ] **Step 1: engine.py 注入数据集单例**

在 `backend/core/engine.py` 顶部全局变量区追加：

```python
dataset_registry = None
dataset_analyzer = None
```

在 `init_engines()` 末尾（处理引擎块之后）追加：

```python
    # ⑥ 数据集注册中心 + 分析器：仅依赖 PyYAML + stdlib，必须成功
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
```

在文件末尾追加 getter：

```python
def get_dataset_registry():
    return dataset_registry


def get_dataset_analyzer():
    return dataset_analyzer
```

- [ ] **Step 2: 确认 app.py 已注册 datasets_bp**

Run: `cd backend && python -c "import re,Path; t=Path('app.py').read_text(encoding='utf-8'); print('datasets_bp' in t)"`
Expected: `True`（已有注册）。若 False，在 app.py 的 Blueprint 注册区追加 `app.register_blueprint(datasets_bp)` 并 `from api.datasets_api import datasets_bp`。

- [ ] **Step 3: 启动后端验证自动扫描 SSDC-UAV**

Run: `cd backend && python -c "from core.engine import init_engines, get_dataset_registry; init_engines(); r=get_dataset_registry(); print(len(r.list_datasets()), [d['format'] for d in r.list_datasets()])"`
Expected: 打印 `3 ['COCO', 'YOLO', 'VOC']`（顺序可能不同），SSDC-UAV_Original 被跳过。

- [ ] **Step 4: 运行全部后端测试回归**

Run: `cd backend && python -m pytest tests/test_dataset_formats.py tests/test_dataset_analyzer.py tests/test_dataset_registry.py tests/test_datasets_api.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/core/engine.py backend/app.py
git commit -m "feat(dataset): engine 装配数据集单例 + 自动扫描"
```

---

## Task 10: 前端 api/datasets.ts + stores/datasets.ts

**Files:**
- Create: `frontend/src/api/datasets.ts`
- Create: `frontend/src/stores/datasets.ts`

- [ ] **Step 1: 创建 api/datasets.ts**

创建 `frontend/src/api/datasets.ts`：

```typescript
import client from './client'

export type DatasetFormat = 'YOLO' | 'COCO' | 'VOC'
export type DatasetSource = 'imported' | 'built'

export interface DatasetSplit { image_count: number; object_count: number }

export interface Dataset {
  dataset_id: string
  name: string
  format: DatasetFormat
  source: DatasetSource
  path: string
  classes: string[]
  splits: Record<'train' | 'val' | 'test', DatasetSplit>
  image_count: number
  object_count: number
  origin_image_count: number
  image_size: string
  version: string
  description: string
  created_at: string
  status: 'ready' | 'building' | 'failed'
  // 兼容旧模板的派生字段
  id: string
  sample_count: number
  train_count: number
  val_count: number
  test_count: number
}

export interface ScanResult {
  valid: boolean
  format: DatasetFormat | null
  classes: string[]
  image_count: number
  object_count: number
  splits: Record<string, DatasetSplit>
  origin_image_count: number
  image_size: string
  version: string
  description: string
  message: string
}

export interface DatasetReport {
  dataset_id: string
  summary: {
    total_images: number
    total_objects: number
    origin_image_count: number
    non_empty_images: number
    splits: Record<string, DatasetSplit>
  }
  class_dist: { name: string; class_id: number; count: number; pct: number }[]
  bbox_stats: {
    avg_width: number; avg_height: number
    area_hist: [number[], number][]
    size_dist: { small: number; medium: number; large: number }
  }
  image_stats: { resolutions: Record<string, number>; aspect_ratios: Record<string, number> }
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface DatasetImage {
  filename: string; split: string; size_bytes: number
  width: number; height: number; format: string
  thumbnail_url: string; preview_url: string
}

function normalize(d: any): Dataset {
  const s = d.splits || {}
  return {
    ...d,
    id: d.dataset_id,
    sample_count: d.image_count,
    train_count: s.train?.image_count || 0,
    val_count: s.val?.image_count || 0,
    test_count: s.test?.image_count || 0,
  }
}

export const datasetsApi = {
  fetchDatasets: (params?: { format?: string }) =>
    client.get<unknown, { data: { datasets: Dataset[]; total: number; format_dist: Record<string, number> } }>(
      '/datasets', { params }).then((res: any) => ({
        ...res,
        data: { ...res.data, datasets: (res.data.datasets || []).map(normalize) },
      })),
  fetchDataset: (id: string) =>
    client.get<unknown, { data: Dataset }>(`/datasets/${id}`).then((res: any) => ({
      ...res, data: normalize(res.data),
    })),
  scan: (path: string) =>
    client.post<unknown, { data: ScanResult }>('/datasets/scan', { path }),
  import: (path: string, name?: string, description?: string) =>
    client.post<unknown, { data: Dataset }>('/datasets/import', { path, name, description }),
  fetchReport: (id: string, force = false) =>
    client.get<unknown, { data: DatasetReport }>(`/datasets/${id}/report`, { params: { force } }),
  fetchImages: (id: string, params: { split?: string; page?: number; page_size?: number }) =>
    client.get<unknown, { data: { images: DatasetImage[]; total: number; page: number; page_size: number; total_pages: number; split: string } }>(
      `/datasets/${id}/images`, { params }),
  delete: (id: string, deleteFiles = false) =>
    client.delete<unknown, { data: null }>(`/datasets/${id}`, { params: { delete_files: deleteFiles } }),
  pickFolder: () => client.post<unknown, { data: { path?: string; cancelled?: boolean } }>('/datasets/pick-folder'),
}
```

- [ ] **Step 2: 创建 stores/datasets.ts**

创建 `frontend/src/stores/datasets.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { datasetsApi, type Dataset } from '@/api/datasets'

export const useDatasetsStore = defineStore('datasets', () => {
  const datasets = ref<Dataset[]>([])
  const total = ref(0)
  const formatDist = ref<Record<string, number>>({ YOLO: 0, COCO: 0, VOC: 0 })
  const loading = ref(false)
  const error = ref('')

  async function fetchDatasets(params?: { format?: string }) {
    loading.value = true
    error.value = ''
    try {
      const res = await datasetsApi.fetchDatasets(params)
      datasets.value = res.data.datasets
      total.value = res.data.total
      formatDist.value = res.data.format_dist
    } catch (e: any) {
      error.value = e.message || '加载失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  return { datasets, total, formatDist, loading, error, fetchDatasets }
})
```

- [ ] **Step 3: TypeScript 检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无新增错误（datasets.ts/stores 编译通过）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/datasets.ts frontend/src/stores/datasets.ts
git commit -m "feat(dataset): 前端 datasets API 客户端与 Pinia store"
```

---

## Task 11: Datasets.vue + Index.vue 迁移 + mock 清理

**Files:**
- Modify: `frontend/src/views/dataset/Datasets.vue`
- Modify: `frontend/src/views/index/Index.vue`
- Delete: `frontend/src/api/mock.ts`, `frontend/src/stores/mock.ts`

- [ ] **Step 1: Datasets.vue 切换 store + 新增框数/来源列 + 导入入口**

在 `frontend/src/views/dataset/Datasets.vue` `<script setup>` 中替换 mock 引用：

```typescript
import AppLayout from '@/components/layout/AppLayout.vue'
import { useDatasetsStore } from '@/stores/datasets'
import { ref, onMounted } from 'vue'
import type { Dataset } from '@/api/datasets'

const store = useDatasetsStore()
const filterFormat = ref('')
const errorMsg = ref('')

const formats = [
  { key: 'YOLO', label: 'YOLO', color: 'text-blue-600', bg: 'bg-blue-50' },
  { key: 'COCO', label: 'COCO', color: 'text-amber-600', bg: 'bg-amber-50' },
  { key: 'VOC', label: 'Pascal VOC', color: 'text-purple-600', bg: 'bg-purple-50' },
]

function formatTagStyle(fmt: string) {
  if (fmt === 'YOLO') return { cls: 'tag tag-blue', style: '' }
  if (fmt === 'COCO') return { cls: 'tag', style: 'background:#FEF3C7;color:#B45309;' }
  if (fmt === 'VOC') return { cls: 'tag', style: 'background:#F3E8FF;color:#7E22CE;' }
  return { cls: 'tag', style: '' }
}

function formatCount(key: string): number {
  return store.formatDist[key] || 0
}

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('ready')) return { cls: 'badge-success', label: '已就绪' }
  if (s.includes('build')) return { cls: 'badge-running', label: '构建中' }
  if (s.includes('fail')) return { cls: 'badge-pending', label: '失败' }
  return { cls: 'badge-info', label: status || '—' }
}

function splitRatio(d: Dataset): string {
  const total = d.train_count + d.val_count + (d.test_count || 0)
  if (!total) return '—'
  if (!d.test_count) return `${d.train_count}:${d.val_count}`
  return `${d.train_count}:${d.val_count}:${d.test_count}`
}

function sourceLabel(s: string): string {
  return s === 'built' ? '构建' : '导入'
}

async function applyFilter(fmt?: string) {
  filterFormat.value = fmt || ''
  errorMsg.value = ''
  try {
    await store.fetchDatasets({ format: filterFormat.value || undefined })
  } catch (e: any) {
    errorMsg.value = e.message || '加载失败'
  }
}

onMounted(() => applyFilter())
```

在 template 中：头部「导出」按钮替换为「导入数据集」入口（router-link to `/dataset/dataset-new`）；统计卡片网格新增总框数卡片；表格新增「标注框数」与「来源」列。具体：将头部导出按钮改为：

```html
<router-link to="/dataset/dataset-new" class="px-4 py-2 bg-brand-700 hover:bg-brand-900 text-white rounded-btn text-sm font-medium inline-flex items-center gap-2">
  <i class="fa-solid fa-file-import text-xs"></i> 导入数据集
</router-link>
```

统计卡片区在 4 列网格后追加总框数卡片（改为 5 列 `grid-cols-5`）：

```html
<div class="bg-white border border-surface-border rounded-card p-4">
  <div class="flex items-center justify-between">
    <div>
      <div class="text-xs text-ink-tertiary">总标注框数</div>
      <div class="text-2xl font-semibold text-ink-primary mt-1">{{ store.datasets.reduce((s, d) => s + (d.object_count || 0), 0).toLocaleString() }}</div>
    </div>
    <div class="w-9 h-9 rounded-btn bg-brand-50 flex items-center justify-center text-brand-700"><i class="fa-solid fa-vector-square text-sm"></i></div>
  </div>
</div>
```

表格表头新增「标注框数」「来源」两列，表体对应新增 `<td>`：

```html
<th class="text-right py-2.5 px-5 font-medium">标注框数</th>
<th class="text-left py-2.5 px-5 font-medium">来源</th>
```

```html
<td class="text-right py-3 px-5 text-ink-secondary">{{ d.object_count.toLocaleString() }}</td>
<td class="py-3 px-5"><span class="tag" :class="d.source === 'built' ? 'tag-blue' : ''">{{ sourceLabel(d.source) }}</span></td>
```

将所有 `store.datasetTotal` 改为 `store.total`，`d.sample_count` 保留（兼容字段已映射），`store.formatDist` 改为 `store.formatDist`（已是响应式 ref，模板自动解包）。

- [ ] **Step 2: Index.vue 切换 store**

在 `frontend/src/views/index/Index.vue` 中：
- 将 `import { useMockStore } from '@/stores/mock'` 改为 `import { useDatasetsStore } from '@/stores/datasets'`
- 将 `const mockStore = useMockStore()` 改为 `const datasetsStore = useDatasetsStore()`
- 将 `mockStore.datasets` → `datasetsStore.datasets`
- 将 `mockStore.datasetTotal` → `datasetsStore.total`
- 将 `mockStore.fetchDatasets()` → `datasetsStore.fetchDatasets()`
- `totalSamples` 计算保持用 `sample_count`（兼容字段已映射）

- [ ] **Step 3: 删除 mock 文件**

删除 `frontend/src/api/mock.ts` 与 `frontend/src/stores/mock.ts`。删除前确认无其他引用（Datasets.vue/Index.vue 已迁移，DatasetDetail.vue 将在 Task 13 迁移——本步先不删，等 Task 13 完成后再删）。**调整：本步仅迁移 Datasets.vue 与 Index.vue，mock 文件保留至 Task 13 完成后统一删除。**

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build`
Expected: 通过（mock.ts 仍存在，DatasetDetail.vue 仍引用 mock，不报错）。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/dataset/Datasets.vue frontend/src/views/index/Index.vue
git commit -m "feat(dataset): Datasets.vue 与首页对接真实数据集 store"
```

---

## Task 12: DatasetNew.vue 双 tab（导入可用 / 构建禁用）

**Files:**
- Modify: `frontend/src/views/dataset/DatasetNew.vue`

- [ ] **Step 1: 重构为双 tab 顶部切换**

在 `frontend/src/views/dataset/DatasetNew.vue` `<script setup>` 中新增导入模式逻辑（保留现有构建向导 `form`/`steps`/`tree` 等）：

```typescript
import AppLayout from '@/components/layout/AppLayout.vue'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { datasetsApi, type ScanResult } from '@/api/datasets'

const router = useRouter()
const mode = ref<'import' | 'build'>('import')

// ── 导入模式 ──
const importPath = ref('')
const scanResult = ref<ScanResult | null>(null)
const importName = ref('')
const importDesc = ref('')
const scanning = ref(false)
const importing = ref(false)
const scanError = ref('')
const importError = ref('')

async function pickFolder() {
  try {
    const res = await datasetsApi.pickFolder()
    if (res.data.path) importPath.value = res.data.path
  } catch (e: any) {
    scanError.value = e.message || '选择文件夹失败'
  }
}

async function doScan() {
  scanError.value = ''
  scanResult.value = null
  if (!importPath.value) { scanError.value = '请输入数据集目录路径'; return }
  scanning.value = true
  try {
    const res = await datasetsApi.scan(importPath.value)
    scanResult.value = res.data
    if (!importName.value && res.data.valid) importName.value = ''
  } catch (e: any) {
    scanError.value = e.response?.data?.message || e.message || '扫描失败'
  } finally {
    scanning.value = false
  }
}

async function doImport() {
  importError.value = ''
  if (!scanResult.value?.valid) { importError.value = '请先扫描并确认数据集'; return }
  importing.value = true
  try {
    const res = await datasetsApi.import(importPath.value, importName.value || undefined, importDesc.value || undefined)
    router.push(`/dataset/datasets/${res.data.dataset_id}`)
  } catch (e: any) {
    importError.value = e.response?.data?.message || e.message || '导入失败'
  } finally {
    importing.value = false
  }
}
```

保留现有构建向导变量与函数（`steps`/`currentStep`/`form`/`formats`/`tree`/`submit` 等）。

- [ ] **Step 2: template 顶部新增 tab 切换 + 导入面板 + 构建面板包裹**

在 `<h1>` 之后、步骤指示器之前插入 tab 切换，并用 `v-show` 包裹两套面板：

```html
<!-- 模式切换 -->
<div class="flex gap-2 mb-6 border-b border-surface-border">
  <button @click="mode = 'import'" class="px-4 py-2 text-sm font-medium border-b-2 -mb-px"
    :class="mode === 'import' ? 'border-brand-700 text-brand-700' : 'border-transparent text-ink-tertiary hover:text-ink-secondary'">
    <i class="fa-solid fa-file-import mr-1.5"></i> 导入已有数据集
  </button>
  <button @click="mode = 'build'" class="px-4 py-2 text-sm font-medium border-b-2 -mb-px"
    :class="mode === 'build' ? 'border-brand-700 text-brand-700' : 'border-transparent text-ink-tertiary hover:text-ink-secondary'">
    <i class="fa-solid fa-hammer mr-1.5"></i> 构建新数据集
  </button>
</div>

<!-- 导入模式 -->
<div v-show="mode === 'import'" class="grid grid-cols-3 gap-5">
  <div class="col-span-2 space-y-5">
    <div class="bg-white border border-surface-border rounded-card p-6">
      <h2 class="text-base font-semibold text-ink-primary mb-4">■ 数据集路径</h2>
      <div class="flex gap-2 mb-3">
        <input v-model="importPath" type="text" placeholder="如 datasets/SSDC-UAV_COCO 或绝对路径"
          class="flex-1 px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
        <button @click="pickFolder" class="px-3 py-2 bg-white border border-surface-border hover:bg-surface-hover rounded-btn text-sm text-ink-secondary">
          <i class="fa-solid fa-folder-open"></i> 选择
        </button>
        <button @click="doScan" :disabled="scanning"
          class="px-4 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium">
          {{ scanning ? '扫描中…' : '扫描预检' }}
        </button>
      </div>
      <div v-if="scanError" class="mb-3 text-xs text-red-600 flex items-center gap-1.5">
        <i class="fa-solid fa-circle-exclamation"></i>{{ scanError }}
      </div>
      <!-- 预检结果 -->
      <div v-if="scanResult && scanResult.valid" class="bg-brand-50/50 border border-brand-100 rounded-btn p-4">
        <div class="flex items-center gap-2 mb-3">
          <i class="fa-solid fa-circle-check text-brand-700"></i>
          <span class="text-sm font-medium text-ink-primary">{{ scanResult.message }}</span>
          <span :class="formatTagStyle(scanResult.format!).cls" :style="formatTagStyle(scanResult.format!).style">{{ scanResult.format }}</span>
        </div>
        <div class="grid grid-cols-4 gap-3 text-xs">
          <div><div class="text-ink-tertiary">图片数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.image_count.toLocaleString() }}</div></div>
          <div><div class="text-ink-tertiary">标注框数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.object_count.toLocaleString() }}</div></div>
          <div><div class="text-ink-tertiary">原图数</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.origin_image_count }}</div></div>
          <div><div class="text-ink-tertiary">分辨率</div><div class="text-ink-primary font-semibold mt-0.5">{{ scanResult.image_size }}</div></div>
        </div>
        <div class="mt-2 text-xs text-ink-tertiary">类别：{{ scanResult.classes.join('、') }}</div>
      </div>
    </div>
    <div class="bg-white border border-surface-border rounded-card p-6">
      <h2 class="text-base font-semibold text-ink-primary mb-4">■ 导入选项（可选）</h2>
      <div class="space-y-3">
        <div>
          <label class="block text-xs font-medium text-ink-primary mb-1.5">数据集名称（留空用推断名）</label>
          <input v-model="importName" type="text" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm font-mono focus:outline-none focus:border-brand-300" />
        </div>
        <div>
          <label class="block text-xs font-medium text-ink-primary mb-1.5">描述</label>
          <textarea v-model="importDesc" rows="2" class="w-full px-3 py-2 bg-white border border-surface-border rounded-btn text-sm focus:outline-none focus:border-brand-300 resize-none"></textarea>
        </div>
      </div>
    </div>
  </div>
  <div class="space-y-5">
    <div class="bg-white border border-surface-border rounded-card p-5 sticky top-5">
      <h3 class="text-sm font-semibold text-ink-primary mb-3">导入摘要</h3>
      <div class="space-y-2.5 text-xs">
        <div class="flex justify-between"><span class="text-ink-tertiary">路径</span><span class="font-mono text-[11px] text-right">{{ importPath || '—' }}</span></div>
        <div class="flex justify-between"><span class="text-ink-tertiary">格式</span><span class="text-ink-primary">{{ scanResult?.format || '—' }}</span></div>
        <div class="flex justify-between"><span class="text-ink-tertiary">图片数</span><span class="text-ink-primary">{{ scanResult?.image_count || 0 }}</span></div>
      </div>
      <div v-if="importError" class="mt-3 text-xs text-red-600">{{ importError }}</div>
      <button @click="doImport" :disabled="importing || !scanResult?.valid"
        class="mt-4 w-full px-3 py-2 bg-brand-700 hover:bg-brand-900 disabled:opacity-50 text-white rounded-btn text-sm font-medium">
        {{ importing ? '导入中…' : '确认导入' }}
      </button>
      <router-link to="/dataset/datasets" class="mt-2 block text-center text-xs text-ink-tertiary hover:text-brand-700">取消</router-link>
    </div>
  </div>
</div>

<!-- 构建模式（现有向导，提交禁用 + 阶段二提示） -->
<div v-show="mode === 'build'">
  <div class="mb-4 bg-amber-50 border border-amber-200 rounded-card p-3 text-xs text-amber-700 flex items-center gap-2">
    <i class="fa-solid fa-triangle-exclamation"></i>
    数据集构建功能将在第二阶段实现，当前仅支持导入已有数据集。
  </div>
  <!-- 保留原 steps 指示器与步骤面板 -->
  ...原有构建向导模板...
</div>
```

`formatTagStyle` 函数在导入面板用到，从 script setup 中保留/复用（构建模式已有同名函数）。构建向导的 `submit` 按钮改为 `disabled` 并提示。

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build`
Expected: 通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/dataset/DatasetNew.vue
git commit -m "feat(dataset): DatasetNew 双 tab（导入可用/构建禁用提示）"
```

---

## Task 13: DatasetDetail.vue ECharts 报告 + 样本浏览 + 删除

**Files:**
- Modify: `frontend/src/views/dataset/DatasetDetail.vue`
- Delete: `frontend/src/api/mock.ts`, `frontend/src/stores/mock.ts`

- [ ] **Step 1: script setup 切换真实 API + 加载报告与样本**

在 `frontend/src/views/dataset/DatasetDetail.vue` `<script setup>` 中：

```typescript
import AppLayout from '@/components/layout/AppLayout.vue'
import { datasetsApi, type Dataset, type DatasetReport, type DatasetImage } from '@/api/datasets'
import { useRoute, useRouter } from 'vue-router'
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const dataset = ref<Dataset | null>(null)
const report = ref<DatasetReport | null>(null)
const reportLoading = ref(false)
const reportError = ref('')
const loading = ref(true)
const errorMsg = ref('')

// 样本浏览
const currentSplit = ref<'train' | 'val' | 'test'>('train')
const images = ref<DatasetImage[]>([])
const imagesTotal = ref(0)
const imagesPage = ref(1)
const imagesPageSize = 50
const imagesTotalPages = ref(1)
const viewerImage = ref<string | null>(null)

// ECharts 容器引用
const classChartRef = ref<HTMLElement | null>(null)
const areaChartRef = ref<HTMLElement | null>(null)
const sizeChartRef = ref<HTMLElement | null>(null)
let classChart: echarts.ECharts | null = null
let areaChart: echarts.ECharts | null = null
let sizeChart: echarts.ECharts | null = null

function statusBadge(status: string): { cls: string; label: string } {
  const s = (status || '').toLowerCase()
  if (s.includes('ready')) return { cls: 'badge-success', label: '已就绪' }
  if (s.includes('build')) return { cls: 'badge-running', label: '构建中' }
  if (s.includes('fail')) return { cls: 'badge-pending', label: '失败' }
  return { cls: 'badge-info', label: status || '—' }
}
function formatTagStyle(fmt: string) {
  if (fmt === 'YOLO') return { cls: 'tag tag-blue', style: '' }
  if (fmt === 'COCO') return { cls: 'tag', style: 'background:#FEF3C7;color:#B45309;' }
  if (fmt === 'VOC') return { cls: 'tag', style: 'background:#F3E8FF;color:#7E22CE;' }
  return { cls: 'tag', style: '' }
}
function formatLabel(fmt: string) { return fmt === 'VOC' ? 'Pascal VOC' : fmt }
function sourceLabel(s: string) { return s === 'built' ? '构建' : '导入' }

const summaryRows = computed(() => {
  const d = dataset.value
  if (!d) return []
  return [
    { set: 'train', images: d.train_count, pct: d.sample_count ? ((d.train_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'val', images: d.val_count, pct: d.sample_count ? ((d.val_count / d.sample_count) * 100).toFixed(1) : '—' },
    { set: 'test', images: d.test_count || 0, pct: d.sample_count ? (((d.test_count || 0) / d.sample_count) * 100).toFixed(1) : '—' },
  ]
})

async function loadDataset() {
  loading.value = true; errorMsg.value = ''
  try {
    const res = await datasetsApi.fetchDataset(id.value)
    dataset.value = res.data
    await loadReport()
    await loadImages()
  } catch (e: any) {
    errorMsg.value = e.message || '加载数据集详情失败'
  } finally {
    loading.value = false
  }
}

async function loadReport(force = false) {
  reportLoading.value = true; reportError.value = ''
  try {
    const res = await datasetsApi.fetchReport(id.value, force)
    report.value = res.data
    await nextTick()
    renderCharts()
  } catch (e: any) {
    reportError.value = e.message || '报告未生成'
  } finally {
    reportLoading.value = false
  }
}

function renderCharts() {
  const r = report.value
  if (!r) return
  // 类别分布柱状
  if (classChartRef.value) {
    classChart?.dispose()
    classChart = echarts.init(classChartRef.value)
    classChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: r.class_dist.map(c => c.name) },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: r.class_dist.map(c => c.count),
        itemStyle: { color: '#10B981' } }],
    })
  }
  // bbox 面积直方图
  if (areaChartRef.value) {
    areaChart?.dispose()
    areaChart = echarts.init(areaChartRef.value)
    const hist = r.bbox_stats.area_hist
    areaChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: hist.map(h => `${h[0][0]}~${h[0][1]}`),
        axisLabel: { rotate: 45, fontSize: 9 } },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: hist.map(h => h[1]),
        itemStyle: { color: '#10B981' } }],
    })
  }
  // small/medium/large 堆叠条
  if (sizeChartRef.value) {
    sizeChart?.dispose()
    sizeChart = echarts.init(sizeChartRef.value)
    const sd = r.bbox_stats.size_dist
    sizeChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ['目标尺度分布'] },
      yAxis: { type: 'value', max: 1, axisLabel: { formatter: '{value}' } },
      series: [
        { name: 'small', type: 'bar', stack: 'size', data: [sd.small], itemStyle: { color: '#FBBF24' } },
        { name: 'medium', type: 'bar', stack: 'size', data: [sd.medium], itemStyle: { color: '#10B981' } },
        { name: 'large', type: 'bar', stack: 'size', data: [sd.large], itemStyle: { color: '#3B82F6' } },
      ],
      legend: { bottom: 0 },
    })
  }
}

async function loadImages() {
  try {
    const res = await datasetsApi.fetchImages(id.value, { split: currentSplit.value, page: imagesPage.value, page_size: imagesPageSize })
    images.value = res.data.images
    imagesTotal.value = res.data.total
    imagesTotalPages.value = res.data.total_pages
  } catch (e: any) {
    images.value = []
  }
}

function switchSplit(s: 'train' | 'val' | 'test') {
  currentSplit.value = s; imagesPage.value = 1; loadImages()
}
function changePage(p: number) {
  imagesPage.value = p; loadImages()
}
function openPreview(url: string) { viewerImage.value = url }

const deleting = ref(false)
const deleteFiles = ref(false)
async function doDelete() {
  if (!confirm(deleteFiles.value ? '将物理删除数据集目录，不可恢复，确认？' : '将仅删除注册记录（保留文件），确认？')) return
  deleting.value = true
  try {
    await datasetsApi.delete(id.value, deleteFiles.value)
    router.push('/dataset/datasets')
  } catch (e: any) {
    errorMsg.value = e.response?.data?.message || e.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

onMounted(loadDataset)
```

- [ ] **Step 2: template 重写统计卡片、报告区（ECharts）、样本浏览、删除、基本信息**

统计卡片改为 5 列：样本总数、训练集、验证集、测试集、标注框数（替换存储占用）。统计分析报告区在原"类别分布"块下方新增 ECharts 容器：

```html
<div class="grid grid-cols-5 gap-4 mb-5">
  <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">样本总数</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.sample_count.toLocaleString() }}</div></div>
  <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">训练集</div><div class="text-2xl font-semibold text-brand-700 mt-1">{{ dataset.train_count.toLocaleString() }}</div></div>
  <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">验证集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.val_count.toLocaleString() }}</div></div>
  <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">测试集</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ (dataset.test_count || 0).toLocaleString() }}</div></div>
  <div class="bg-white border border-surface-border rounded-card p-4"><div class="text-xs text-ink-tertiary">标注框数</div><div class="text-2xl font-semibold text-ink-primary mt-1">{{ dataset.object_count.toLocaleString() }}</div></div>
</div>
```

报告区：保留数据规模表格 + 类别分布（柱状图容器）+ bbox 面积直方图容器 + 尺度堆叠条容器 + 失衡告警 + 重新生成按钮：

```html
<!-- 类别分布 ECharts -->
<div ref="classChartRef" class="w-full h-64"></div>
<!-- bbox 面积直方图 -->
<div ref="areaChartRef" class="w-full h-64"></div>
<!-- 尺度分布堆叠条 -->
<div ref="sizeChartRef" class="w-full h-48"></div>
<!-- 告警 -->
<div v-if="report && report.warnings.length" class="mt-3 bg-amber-50 border border-amber-200 rounded-btn p-3 text-xs text-amber-700">
  <i class="fa-solid fa-triangle-exclamation mr-1"></i>{{ report.warnings.join('；') }}
</div>
<button @click="loadReport(true)" :disabled="reportLoading" class="px-3 py-1.5 bg-brand-50 border border-brand-100 text-brand-700 rounded-btn text-xs">
  <i class="fa-solid fa-rotate mr-1"></i>{{ reportLoading ? '生成中…' : '重新生成' }}
</button>
```

样本浏览区（新增）：

```html
<div class="bg-white border border-surface-border rounded-card p-5">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-sm font-semibold text-ink-primary">样本浏览</h3>
    <div class="flex gap-2">
      <button v-for="s in ['train','val','test']" :key="s" @click="switchSplit(s as any)"
        class="px-3 py-1 text-xs rounded-btn"
        :class="currentSplit === s ? 'bg-brand-700 text-white' : 'bg-white border border-surface-border text-ink-secondary'">{{ s }}</button>
    </div>
  </div>
  <div class="grid grid-cols-6 gap-3">
    <div v-for="img in images" :key="img.filename" class="border border-surface-border rounded-btn overflow-hidden cursor-pointer hover:border-brand-300" @click="openPreview(img.preview_url)">
      <img :src="img.thumbnail_url" :alt="img.filename" class="w-full aspect-square object-cover" />
      <div class="text-[10px] text-ink-tertiary px-1 py-0.5 truncate">{{ img.filename }}</div>
    </div>
  </div>
  <div class="mt-4 flex items-center justify-between text-xs text-ink-tertiary">
    <span>共 {{ imagesTotal }} 张 · 第 {{ imagesPage }}/{{ imagesTotalPages }} 页</span>
    <div class="flex gap-2">
      <button @click="changePage(imagesPage - 1)" :disabled="imagesPage <= 1" class="px-2 py-1 border border-surface-border rounded-btn disabled:opacity-40">上一页</button>
      <button @click="changePage(imagesPage + 1)" :disabled="imagesPage >= imagesTotalPages" class="px-2 py-1 border border-surface-border rounded-btn disabled:opacity-40">下一页</button>
    </div>
  </div>
</div>
```

基本信息侧栏新增：来源、原图数、格式转换导出按钮（禁用 + 阶段二提示）、删除操作（复选 delete_files + 按钮）。头部"导出数据集"按钮改为禁用 + tooltip 提示阶段二。

- [ ] **Step 3: 删除 mock 文件**

确认 DatasetDetail.vue 已不引用 `mockApi`/`useMockStore` 后，删除 `frontend/src/api/mock.ts` 与 `frontend/src/stores/mock.ts`。

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build`
Expected: 通过，无 mock 引用残留。

- [ ] **Step 5: 全量后端回归测试**

Run: `cd backend && python -m pytest tests/ -v --ignore=tests/test_mock_api.py`
Expected: 全部通过（test_mock_api.py 中数据集用例已废弃，可删除该文件或保留 batches 部分）。

- [ ] **Step 6: 端到端手动验证**

启动前后端，访问数据集页面：
1. 列表自动显示 SSDC-UAV 三格式数据集（COCO/YOLO/VOC），统计卡片与格式分布正确
2. 新建页导入 tab：输入 `datasets/SSDC-UAV_COCO` → 扫描预检显示 14220 图/89136 框 → 确认导入 → 跳转详情
3. 详情页 ECharts 报告：总图 14220、总框 89136、原图 230、640x640；类别分布/面积直方图/尺度分布正常渲染
4. 样本浏览：切换 train/val/test，缩略图分页，单击大图预览
5. 删除：默认仅删注册，文件保留；勾选物理删除后目录消失
6. 首页数据集统计卡显示真实数量

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/dataset/DatasetDetail.vue
git rm frontend/src/api/mock.ts frontend/src/stores/mock.ts
git commit -m "feat(dataset): DatasetDetail ECharts 报告 + 样本浏览 + 删除，移除 mock"
```

---

## 自审记录

**Spec 覆盖核对：**
- FR-S01 发现与导入注册 → Task 2/3（解析器）+ Task 4（scan）+ Task 6/7（registry import/auto-discover）+ Task 8（API）✓
- FR-S04 统计报告 → Task 5（compute_report + 缓存）+ Task 8（report 端点）+ Task 13（ECharts）✓
- FR-S05 浏览与删除 → Task 7（list_images/preview/delete）+ Task 8（端点）+ Task 13（样本浏览 UI）✓
- SSDC-UAV 缺陷应对（过期 path/tile 解析/无 meta）→ Task 2/3 解析器忽略 path + origin_stem + Task 7 写 meta ✓
- 9 个 API 端点 → Task 8 全覆盖 ✓
- 前端三页 + 首页迁移 → Task 11/12/13 ✓
- mock 清理 → Task 13 ✓

**类型一致性核对：** `compute_report` 在 Task 5 接收 `dataset_cfg`（dict 或 id），Task 8 API 传 `cfg`（dict）✓；`DatasetRegistry.import_dataset` 返回 cfg dict，Task 8 API 直接返回 ✓；前端 `normalize` 映射 `dataset_id→id`、`image_count→sample_count` 与三个组件旧模板一致 ✓。

**已知简化项（不影响验收）：** ECharts 仅渲染三类图表（类别/面积/尺度），划分占比用现有三色条而非饼图（保持与现有 UI 一致）；`test_mock_api.py` 中数据集用例在 Task 13 后失效，建议删除该文件中数据集部分或整体（batches 部分无对应，可整体删除）。
