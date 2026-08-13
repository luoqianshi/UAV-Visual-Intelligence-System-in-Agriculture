# 数据集管理模块（第一阶段）设计文档

**文档版本**：v1.0
**编制日期**：2026-08-13
**对应 PRD**：PRD_基于无人机图像的大田农作物智能监测与管理系统_v6.md（第四章 模块三）
**实施阶段**：第一阶段（导入注册 + 统计报告 + 浏览删除）

---

## 一、目标与范围

### 1.1 目标

用真实的数据集管理功能替换当前系统中的 Mock 实现（`backend/mock/datasets.json` + `frontend/src/api/mock.ts`），使前端三个数据集页面（Datasets/DatasetNew/DatasetDetail）对接真实后端 API，并以 `datasets/` 目录下真实的 SSDC-UAV 自建数据集（14,220 图 / 89,136 框 / 单类别 Sugarcane Seedling）作为验收基准。

### 1.2 第一阶段范围（本设计覆盖）

| 功能需求 | 状态 | 说明 |
|---------|------|------|
| FR-S01 数据集发现与导入注册 | 实现 | scan 预检 + import 注册 + 启动自动扫描发现 |
| FR-S04 数据集统计分析报告 | 实现 | 实时 API + ECharts 可视化 + 报告缓存 |
| FR-S05 数据集浏览与删除 | 实现 | 样本分页浏览 + 三尺寸预览 + 删除（含物理删除） |

### 1.3 第二阶段范围（本设计不覆盖，预留接口）

| 功能需求 | 说明 |
|---------|------|
| FR-S02 数据集构建与拆分 | 异步任务、7:2:1 拆分、原图粒度分组、list.csv 生成 |
| FR-S03 三格式互转导出 | 异步任务、6 条转换路径、IR 写出器、自动注册新数据集 |

第二阶段产出独立 spec → plan → 实现周期。本设计在格式解析层产出 PRD §4.3 统一中间表示 IR，为阶段二写出器预留同源数据结构。

### 1.4 验收基准（对齐 PRD §8.3 第 21-23、26-29 条）

- `POST /api/datasets/scan` 对 `SSDC-UAV_COCO`/`SSDC-UAV_YOLO`/`SSDC-UAV_PASCAL-VOC` 预检，均正确识别格式并返回规模统计与类别（Sugarcane Seedling）
- `POST /api/datasets/import` 导入三格式目录，注册到 `datasets/datasets.yaml` 并生成 `dataset_meta.json`；COCO 导入时 info 块元信息（version 1.0、contributor）被采信
- `GET /api/datasets/{id}/report` 返回统计与权威值一致——总图片 14,220（train 10,707 / val 1,810 / test 1,703）、总框数 89,136、原图数 230、分辨率 640x640
- `GET /api/datasets/{id}/images?split=` 分页返回样本，preview 端点支持 thumbnail/medium/original
- `DELETE /api/datasets/{id}` 默认仅删注册记录不删文件；`?delete_files=true` 物理删除；自动发现的数据集删除后加入 ignored_folders
- 服务启动时扫描 `datasets/` 自动发现未注册数据集（跳过无法识别的 `SSDC-UAV_Original`）
- 前端数据集列表统计卡片与格式筛选、新建页导入模式、详情页 ECharts 统计报告均正常

---

## 二、架构与模块布局

### 2.1 方案选型

采用**方案 A：注册中心 + 分析器双类**，严格对齐项目已验证的"注册中心（元数据/CRUD/持久化）+ 引擎/分析器（执行逻辑）"分层惯例（参考 `BatchRegistry` + `ProcessingEngine`）。格式解析抽为纯函数模块，既利于单测又为阶段二格式互转写出器预留同源 IR。

### 2.2 后端文件清单

| 文件 | 类型 | 职责 |
|------|------|------|
| `backend/core/dataset_registry.py` | 新增 | `DatasetRegistry`：YAML 持久化、`datasets/` 自动扫描、CRUD、图片索引、样本分页预览 |
| `backend/core/dataset_analyzer.py` | 新增 | `DatasetAnalyzer`：格式识别、统计计算（轻量+重统计）、报告缓存读写 |
| `backend/core/dataset_formats.py` | 新增 | 三格式纯函数解析器 `parse_coco`/`parse_yolo`/`parse_voc` → IR；`detect_format` |
| `backend/api/datasets_api.py` | 重写 | 9 个第一阶段端点，替换 Mock |
| `backend/core/engine.py` | 改动 | 增加 `dataset_registry`/`dataset_analyzer` 单例初始化与 getter |
| `backend/config.py` | 改动 | 增加 `DATASETS_DIR`、`DATASETS_YAML` 常量 |

### 2.3 依赖降级设计（对齐 PRD §6.5）

- `DatasetRegistry` 仅依赖 PyYAML + Pillow + stdlib → 始终初始化成功
- `DatasetAnalyzer` 仅依赖 stdlib（json/xml/yaml）→ 始终初始化成功
- 不引入 cv2/numpy/torch，数据集管理功能不受算法依赖缺失影响

### 2.4 引擎初始化（engine.py 新增 ⑥）

```python
# ⑥ 数据集注册中心 + 分析器：仅依赖 PyYAML + stdlib，必须成功
global dataset_registry, dataset_analyzer
dataset_registry = DatasetRegistry(DATASETS_DIR, DATASETS_YAML)
dataset_registry.load_from_yaml()
dataset_analyzer = DatasetAnalyzer(dataset_registry)
```

配套 getter：`get_dataset_registry()` / `get_dataset_analyzer()`。

---

## 三、数据模型与存储

### 3.1 `datasets/datasets.yaml`（对齐 `batches.yaml` 就地持久化）

```yaml
datasets:
- dataset_id: dataset_ssdc-uav_coco      # dataset_{sanitize(name).lower()}，保留连字符
  name: SSDC-UAV (COCO)                   # 推断名（见 §4.3.1）；用户可覆盖
  format: COCO                            # COCO/YOLO/VOC
  source: imported                        # imported（阶段一唯一来源；built 留阶段二）
  path: datasets/SSDC-UAV_COCO            # 实际目录（保留真实大小写）
  classes: [Sugarcane Seedling]           # flow style
  splits:
    train: {image_count: 10707, object_count: 66420}
    val: {image_count: 1810, object_count: 11453}
    test: {image_count: 1703, object_count: 11263}
  image_count: 14220
  object_count: 89136
  origin_image_count: 230                 # tile 文件名聚合的原图数
  image_size: 640x640                     # 主导分辨率
  version: '1.0'                          # COCO info.version；其余默认 '1.0'
  description: A Dataset for Field Sugarcane Seedling Detection...
  created_at: '2026-08-13T10:00:00'
  status: ready                           # ready/building/failed；阶段一恒 ready
ignored_folders: []
```

YAML dump 参数：`allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2, width=1000`（与 `batches.yaml` 一致）。`classes` 与 `image_formats` 类似使用 `_InlineList` 保持 flow style。字段顺序固定（`_DATASET_FIELD_ORDER`）。

### 3.2 `datasets/{name}/dataset_meta.json`（每数据集目录内）

```json
{
  "dataset_id": "dataset_ssdc-uav_coco",
  "name": "SSDC-UAV (COCO)",
  "format": "COCO",
  "classes": ["Sugarcane Seedling"],
  "splits": {"train": {"image_count": 10707, "object_count": 66420},
             "val": {"image_count": 1810, "object_count": 11453},
             "test": {"image_count": 1703, "object_count": 11263}},
  "image_count": 14220,
  "object_count": 89136,
  "origin_image_count": 230,
  "image_size": "640x640",
  "version": "1.0",
  "source_path": "datasets/SSDC-UAV_COCO",
  "layout": {"images": "{split}/", "annotations": "annotations/{split}.json"},
  "report_cache": null,
  "report_cached_at": null,
  "generated_at": "2026-08-13T10:00:00"
}
```

`report_cache` 初次为 null；首次请求报告时填入完整统计并记 `report_cached_at`；重新导入/删除时失效（置 null）。`layout` 描述该数据集实际的图片/标注目录布局，供浏览端点路径解析使用。

### 3.3 dataset_id 与路径规范

- 实际目录名保留大小写：`SSDC-UAV_COCO`/`SSDC-UAV_YOLO`/`SSDC-UAV_PASCAL-VOC`
- `dataset_id = "dataset_" + re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()` → `dataset_ssdc-uav_coco`
- `path` 字段存相对项目根的真实路径 `datasets/SSDC-UAV_COCO`
- `SSDC-UAV_Original` 无法识别格式（含 xlsx + 原图，非三标准格式）→ 自动扫描跳过，不报错

---

## 四、核心逻辑与数据流

### 4.1 `dataset_formats.py` — 纯函数解析器

#### 4.1.1 统一中间表示 IR（对齐 PRD §4.3，为阶段二互转预留）

```python
IR = {
    "images": [
        {
            "filename": str,            # 图片文件名
            "split": str,               # train/val/test
            "width": int, "height": int,
            "origin_stem": str,         # tile 文件名解析的原图 stem，无后缀则等于 stem
            "boxes": [
                {"bbox": [x, y, w, h],  # 绝对像素坐标（左上角 + 宽高），统一内部表示
                 "class_id": int,        # 统一从 0 开始
                 "class_name": str}
            ]
        }
    ],
    "classes": [str],                   # 类别名列表，索引即内部 class_id
    "meta": {                           # 元信息（COCO info 块 / YOLO yaml / VOC 推断）
        "format": str, "version": str, "description": str,
        "contributor": str, "date_created": str
    },
}
```

#### 4.1.2 解析函数

```python
def detect_format(dataset_dir: Path) -> str | None
    """PRD §4.2 识别规则：
    - COCO: 存在 annotations/*.json 且 JSON 含 images/annotations/categories 键
    - YOLO: 存在 images/{split} + labels/{split}，且根目录有含 names 字段的 .yaml
    - VOC:  存在 {split}/images + {split}/annotations/*.xml，或 JPEGImages/ + Annotations/
    - 无法识别: 返回 None"""

def parse_coco(dataset_dir: Path) -> IR
    """读 annotations/{split}.json；图片布局兼容 {split}/ 直放与 images/{split}/ 两种
    （优先判定 {split}/ 直放，SSDC-UAV 形态；无图时回退 images/{split}/）；
    采信 info 块（description/version/contributor/date_created）作为 meta；
    category_id 从 1 起 → 内部 class_id 减 1；bbox 原样 [x,y,w,h] 绝对像素。"""

def parse_yolo(dataset_dir: Path) -> IR
    """读 *.yaml 的 names 字段获取类别；images/{split}+labels/{split}；
    忽略 yaml.path（过期绝对路径）；归一化坐标 × 宽高 → 绝对像素；
    class_id 从 0 起，原样保留。空标注 .txt 保留空 boxes 列表。"""

def parse_voc(dataset_dir: Path) -> IR
    """扫 {split}/annotations/*.xml 或 JPEGImages/+Annotations/；
    忽略 <path>/<folder>（过期路径）；<bndbox> xmin/ymin/xmax/ymax → [x,y,w,h]；
    类别按 <name> 出现顺序聚合，class_id 从 0 起。"""
```

**坐标统一约定**：IR 内 bbox 一律 `[x,y,w,h]` 绝对像素。
- COCO：原样（已是绝对像素）
- YOLO：`x = x_center*w_norm - w_norm*width/2`，宽高 = `w_norm*width`
- VOC：`x=xmin, y=ymin, w=xmax-xmin, h=ymax-ymin`

**类别 ID 统一从 0 起**：COCO `category_id-1`；YOLO 原样；VOC 按出现顺序。互转差 1 问题在阶段二写出器处理。

**tile 文件名解析**：`origin_stem = re.sub(r'_tile_\d+_x\d+_y\d+$', '', stem)`，无 tile 后缀则等于 stem。

#### 4.1.3 格式识别细节

COCO 识别需读取 JSON 顶层键判断；YOLO 识别需读取 yaml 的 `names` 字段；VOC 识别需检查 split 目录结构。`detect_format` 应快速返回，不解析全部标注（仅读必要的目录/文件头）。

### 4.2 `dataset_analyzer.py` — 格式识别 + 统计

```python
class DatasetAnalyzer:
    def __init__(self, registry: DatasetRegistry):
        self._registry = registry

    def scan(self, path: str) -> dict:
        """路径预检（FR-S01 步骤1）：格式识别 + 轻量统计，不持久化。
        返回 {
            valid: bool, format: str|None, classes: [str],
            image_count, object_count,
            splits: {split: {image_count, object_count}},
            origin_image_count, image_size, version, description,
            message: str
        }
        valid=False 时 format=None，message 说明原因（路径不存在/非目录/无法识别格式）。"""

    def compute_report(self, dataset_id: str, force: bool = False) -> dict:
        """FR-S04 统计报告。
        1. 取 dataset 配置 + dataset_meta.json
        2. report_cache 命中且非 force → 直接返回
        3. 否则 parse → IR → _compute_heavy_stats → 回写 report_cache/report_cached_at → 返回
        返回结构见 §5.5 report 响应。"""

    def _compute_heavy_stats(self, ir: IR) -> dict:
        """遍历全部 boxes 计算：
        - bbox avg_width / avg_height
        - area_hist: 面积分布直方图（20 桶，返回 [[下限,上限], 计数]）
        - size_dist: {small: <32², medium: 32²~96², large: >96²} 占比
        - resolutions: {分辨率字符串: 图片数}
        - aspect_ratios: {宽高比字符串: 图片数}
        - class_dist: [{name, class_id, count, pct}]
        - non_empty_images: 非空样本数
        - warnings: [str]（如最大类占比 >90% 给出失衡告警）"""

    def _write_meta(self, dataset_dir: Path, meta: dict) -> None
    def _read_meta(self, dataset_dir: Path) -> dict | None
```

**轻量统计**（scan/import 时）：仅遍历 images 元数据 + annotations 计数，不解析全部框的几何。计算图片数、框数、类别、划分计数、原图数（origin_stem 去重）、主导分辨率。

**重统计**（report 时，仅首次）：遍历全部 boxes 算面积/尺度分布，结果缓存到 `dataset_meta.json.report_cache`。

### 4.3 `dataset_registry.py` — 注册中心

镜像 `BatchRegistry` 设计模式：YAML 加载、自动扫描、CRUD、图片索引、缩略图生成。

```python
_DATASET_FIELD_ORDER = [
    "dataset_id", "name", "format", "source", "path", "classes",
    "splits", "image_count", "object_count", "origin_image_count",
    "image_size", "version", "description", "created_at", "status",
]

class DatasetRegistry:
    def __init__(self, datasets_dir=DATASETS_DIR, yaml_path=DATASETS_YAML):
        self._datasets_dir = Path(datasets_dir)
        self._yaml_path = Path(yaml_path)
        self._datasets: Dict[str, dict] = {}
        self._ignored_folders: set = set()
        self._analyzer = None  # 由 engine 注入

    def set_analyzer(self, analyzer): self._analyzer = analyzer

    def load_from_yaml(self):
        """1. 读 datasets.yaml → _datasets / _ignored_folders
        2. _auto_discover_datasets()：扫描 datasets/ 子目录
           - 跳过隐藏目录（.开头）和 ignored_folders
           - detect_format() 识别；None 则跳过（如 SSDC-UAV_Original）
           - 未注册且识别成功 → _analyzer.scan() 取轻量统计 → 注册
        3. 有新增则 save_to_yaml()"""

    def save_to_yaml(self): ...
    def scan_path(self, path) -> dict          # 委托 analyzer.scan()，不持久化
    def import_dataset(self, path, name=None, description=None) -> dict
    def get_dataset(self, dataset_id) -> dict
    def list_datasets(self, fmt=None) -> list
    def format_dist(self) -> dict              # {"YOLO":n, "COCO":n, "VOC":n}
    def delete_dataset(self, dataset_id, delete_files=False)
    def list_images(self, dataset_id, split, page, page_size) -> dict
    def get_image_preview(self, dataset_id, filename, split, size) -> bytes
```

#### 4.3.1 import_dataset 流程

```
1. analyzer.scan(path) 预检 → format=None 抛 ValueError("无法识别数据集格式")
2. 重名校验：name 与现有 dataset.name 冲突 → ValueError
   同路径校验：path 已被注册 → ValueError
3. name 取值优先级：用户传入 > 推断名
   推断名规则：若文件夹名以 `_{FORMAT}`（大小写不敏感，如 `_coco`/`_yolo`/`_pascal-voc`/`_voc`）
   结尾，则 `"{去格式后缀的 stem} ({FORMAT})"`（如 `SSDC-UAV_COCO` → `SSDC-UAV (COCO)`）；
   否则用文件夹名。该规则产出与 PRD §4.2 示例一致的 name。
   description 取值优先级：用户传入 > COCO info.description > ""
   version：COCO info.version > "1.0"
4. dataset_id = "dataset_" + sanitize(name).lower()，确保唯一
5. 写 dataset_meta.json（含轻量统计，report_cache=null）
6. 注册到 _datasets + save_to_yaml()
7. 返回完整 dataset 配置
```

#### 4.3.2 delete_dataset 流程

```
1. 不存在抛 KeyError
2. delete_files=True：shutil.rmtree(数据集目录)
3. 否则：仅删 dataset_meta.json（保留原始文件）
4. 若 path 在 datasets/ 下 → 文件夹名加入 _ignored_folders
5. del _datasets[id] + save_to_yaml()
```

#### 4.3.3 样本图片路径解析（按格式+split）

| 格式 | 图片目录 |
|------|---------|
| COCO | `{split}/`（SSDC-UAV 形态，图片直放）；兼容 `images/{split}/` |
| YOLO | `images/{split}/` |
| VOC | `{split}/images/` |

路径解析失败（split 目录不存在）→ 返回空列表 + total=0，不报错。

#### 4.3.4 缩略图生成

复用 `BatchRegistry._generate_thumbnail` 同款 Pillow 逻辑：thumbnail 最长边 400px / medium 1920px / original 原图，JPEG 编码。`Cache-Control: public, max-age=3600`。

### 4.4 自动发现（启动时）

`engine.init_engines()` → `dataset_registry.load_from_yaml()` → `_auto_discover_datasets()`：
- 扫描 `datasets/` 一级子目录
- 跳过隐藏目录（`.`开头）和 `ignored_folders`
- `detect_format()` 识别：COCO/YOLO/VOC 三目录自动注册；`SSDC-UAV_Original` 返回 None → 跳过
- 未注册且识别成功 → `analyzer.scan()` 取轻量统计 → 注册

### 4.5 报告懒计算流（FR-S04）

`GET /api/datasets/{id}/report`：
1. analyzer 取 dataset 配置 + dataset_meta.json
2. `report_cache` 命中且非 force → 直接返回（<10ms）
3. 否则 `parse_*` → IR → `_compute_heavy_stats` → 回写 `report_cache`/`report_cached_at` → 返回
4. 万级样本首次约 3-8s，后续 <10ms

缓存失效：重新导入（import 同路径覆盖）→ 置 `report_cache=null`；删除时随 meta 一起清除。

### 4.6 SSDC-UAV 已知缺陷应对

| 缺陷 | 实现 |
|------|------|
| YOLO yaml `path` 过期绝对路径 | parse_yolo 忽略 `path` 字段；导入时不重写（阶段二导出才重写） |
| VOC XML `<path>`/`<folder>` 过期 | parse_voc 忽略 `<path>`/`<folder>` |
| 无 README / dataset_meta.json | 导入时自动生成 dataset_meta.json |
| tile 序号不连续（空片丢弃） | 按实际文件统计；原图聚合以 origin_stem 去重计数 |

---

## 五、API 设计

### 5.1 通用约定（对齐 batches_api 风格）

- 统一响应信封：`{"success": bool, "data": <data>|null, "message": str}`
- 错误语义：`ValueError` → 400，`KeyError` → 404，创建成功 → 201
- 路径支持绝对路径或相对项目根的路径
- `_error(message, status_code)` 辅助函数与 batches_api 一致

### 5.2 端点清单（第一阶段 9 个）

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/datasets` | GET | 数据集列表，`?format=` 过滤，返回 `{datasets, total, format_dist}` |
| `/api/datasets/scan` | POST | 路径预检：格式识别 + 轻量统计（请求体 `{path}`） |
| `/api/datasets/import` | POST | 导入注册（请求体 `{path, name?, description?}`）→ 201 |
| `/api/datasets/<dataset_id>` | GET | 数据集详情 |
| `/api/datasets/<dataset_id>` | DELETE | 删除（`?delete_files=true` 物理删除目录） |
| `/api/datasets/<dataset_id>/report` | GET | 实时统计报告（`?force=true` 强制重算） |
| `/api/datasets/<dataset_id>/images` | GET | 样本分页浏览（`?split=&page=&page_size=`） |
| `/api/datasets/<dataset_id>/images/<path:filename>/preview` | GET | 样本预览（`?split=&size=thumbnail/medium/original`） |
| `/api/datasets/pick-folder` | POST | 系统原生文件夹选择对话框（复用 tkinter 逻辑） |

### 5.3 GET /api/datasets

**查询参数**：`format`（可选，YOLO/COCO/VOC）

**响应**：
```json
{
  "success": true,
  "data": {
    "datasets": [<dataset 配置>],
    "total": 3,
    "format_dist": {"YOLO": 1, "COCO": 1, "VOC": 1}
  },
  "message": "获取数据集列表成功"
}
```

### 5.4 POST /api/datasets/scan

**请求**：`{"path": "datasets/SSDC-UAV_COCO"}`

**响应**（valid=true 时 200，valid=false 时 400）：
```json
{
  "success": true,
  "data": {
    "valid": true,
    "format": "COCO",
    "classes": ["Sugarcane Seedling"],
    "image_count": 14220,
    "object_count": 89136,
    "splits": {"train": {"image_count": 10707, "object_count": 66420},
               "val": {"image_count": 1810, "object_count": 11453},
               "test": {"image_count": 1703, "object_count": 11263}},
    "origin_image_count": 230,
    "image_size": "640x640",
    "version": "1.0",
    "description": "A Dataset for Field Sugarcane Seedling Detection...",
    "message": "识别为 COCO 格式，14220 张图片"
  },
  "message": "ok"
}
```

### 5.5 POST /api/datasets/import

**请求**：`{"path": "datasets/SSDC-UAV_COCO", "name": "SSDC-UAV (COCO)", "description": "..."}`（name/description 可选）

**响应**（201）：
```json
{
  "success": true,
  "data": {<完整 dataset 配置>},
  "message": "数据集导入成功"
}
```

### 5.6 GET /api/datasets/<dataset_id>/report

**查询参数**：`force`（可选，true 强制重算）

**响应**（对齐 PRD §4.4 report 结构）：
```json
{
  "success": true,
  "data": {
    "dataset_id": "dataset_ssdc-uav_coco",
    "summary": {
      "total_images": 14220, "total_objects": 89136,
      "origin_image_count": 230, "non_empty_images": 14220,
      "splits": {"train": {"image_count": 10707, "object_count": 66420},
                  "val": {"image_count": 1810, "object_count": 11453},
                  "test": {"image_count": 1703, "object_count": 11263}}
    },
    "class_dist": [{"name": "Sugarcane Seedling", "class_id": 0, "count": 89136, "pct": 100.0}],
    "bbox_stats": {"avg_width": 41.2, "avg_height": 47.8,
                    "area_hist": [[[0,2000], 120], [[2000,4000], 3400]],
                    "size_dist": {"small": 0.12, "medium": 0.75, "large": 0.13}},
    "image_stats": {"resolutions": {"640x640": 14220}, "aspect_ratios": {"1.00": 14220}},
    "warnings": [],
    "cached": false,
    "generated_at": "2026-08-13T10:30:00"
  },
  "message": "ok"
}
```

`cached` 字段标识本次是否命中缓存。

### 5.7 GET /api/datasets/<dataset_id>/images

**查询参数**：`split`（train/val/test，默认 train）、`page`（默认 1）、`page_size`（默认 50）

**响应**：
```json
{
  "success": true,
  "data": {
    "images": [{"filename": "...", "split": "train", "size_bytes": 12345,
                 "width": 640, "height": 640, "format": "JPG",
                 "thumbnail_url": "/api/datasets/{id}/images/{filename}/preview?split=train&size=thumbnail",
                 "preview_url": "/api/datasets/{id}/images/{filename}/preview?split=train&size=medium"}],
    "total": 10707, "page": 1, "page_size": 50, "total_pages": 215,
    "split": "train"
  },
  "message": "获取样本列表成功"
}
```

### 5.8 GET /api/datasets/<dataset_id>/images/<filename>/preview

**查询参数**：`split`（必填）、`size`（thumbnail/medium/original，默认 thumbnail）

**响应**：图片二进制流（`image/jpeg`），`Cache-Control: public, max-age=3600`。filename 缺失 → 400；文件不存在 → 404。

### 5.9 POST /api/datasets/pick-folder

复用 batches_api 的 tkinter 逻辑，返回 `{"path": "..."}` 或 `{"cancelled": true}`。

---

## 六、前端设计

### 6.1 新增/改动文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `frontend/src/api/datasets.ts` | 新增 | 替换 `mock.ts` 数据集部分；typed Dataset 接口 + API 函数 |
| `frontend/src/stores/datasets.ts` | 新增 | Pinia store（list/current/report/loading/formatDist） |
| `frontend/src/views/dataset/Datasets.vue` | 改动 | 对接真实 store；补 object_count/source 列；新增"导入"入口 |
| `frontend/src/views/dataset/DatasetNew.vue` | 改动 | 双 tab：导入（功能完整）/ 构建（现有向导，提交禁用+阶段二提示） |
| `frontend/src/views/dataset/DatasetDetail.vue` | 改动 | 对接真实 API；ECharts 统计报告；样本浏览网格；删除操作 |
| `frontend/src/views/index/Index.vue` | 改动 | 数据集统计改用新 store（替换 useMockStore） |
| `frontend/src/api/mock.ts` | 删除 | 数据集部分迁移完成后删除 |
| `frontend/src/stores/mock.ts` | 删除 | 同上 |

### 6.2 Dataset 类型（api/datasets.ts）

```typescript
export interface DatasetSplit { image_count: number; object_count: number }
export interface Dataset {
  dataset_id: string              // 替代原 id
  name: string
  format: 'YOLO' | 'COCO' | 'VOC'
  source: 'imported' | 'built'
  path: string
  classes: string[]
  splits: Record<'train'|'val'|'test', DatasetSplit>
  image_count: number             // 替代 sample_count
  object_count: number
  origin_image_count: number
  image_size: string
  version: string
  description: string
  created_at: string
  status: 'ready' | 'building' | 'failed'
}
// 兼容层：提供 sample_count/train_count/val_count/test_count 计算属性或映射，
// 降低三个 Vue 组件改动量
```

为降低现有三个组件改动量，store/类型层提供向后兼容映射：`sample_count←image_count`、`train_count←splits.train.image_count`、`id←dataset_id` 等。

### 6.3 Datasets.vue 改动

- 数据源：`useMockStore` → `useDatasetsStore`
- 统计卡片保留（总数 + 三格式数 + 总样本数），新增总框数
- 表格列：名称（+路径副行）、格式 tag、样本数、**标注框数（新增）**、数据划分三色条、**来源 tag（导入/构建）**、状态、创建时间、操作（查看/删除）
- 头部按钮：「导入数据集」入口（跳转 DatasetNew 导入 tab）

### 6.4 DatasetNew.vue 改动（双 tab）

- 顶部双 tab：「导入已有数据集」（可用）/「构建新数据集」（向导保留，提交按钮禁用，置顶提示"数据集构建功能将在第二阶段实现"）
- **导入 tab 流程**：
  1. 路径输入框 + pick-folder 按钮 → 点击「扫描预检」
  2. 调 `POST /scan` → 展示预检结果卡片（格式/规模/类别/划分）
  3. 名称、描述输入（可选，默认取预检返回的 name/description）
  4. 「确认导入」→ `POST /import` → 成功跳转详情页
- 构建向导步骤 4「目录结构预览」保留现状，仅提交按钮禁用 + 提示

### 6.5 DatasetDetail.vue 改动

- 数据源：`mockApi` → `useDatasetsStore` + `datasetsApi`
- 统计卡片：样本总数、训练集、验证集、测试集、**标注框数（替换存储占用）**
- 数据划分三色条：数据来自 splits
- **统计分析报告区（ECharts 可视化，复用现有 ECharts 依赖）**：
  - 数据规模表格（按 split 汇总图片数/框数/占比）
  - 类别分布柱状图
  - bbox 面积分布直方图
  - small/medium/large 占比堆叠条
  - 分辨率分布（文字/条形）
  - 失衡告警展示（warnings 非空时提示）
  - 「重新生成」按钮 → `?force=true`
- **样本浏览区（新增）**：split 切换（train/val/test）+ 缩略图网格分页（每页 50）+ 单击大图预览（复用 ImageViewer 组件，三尺寸）
- 基本信息：ID、版本、格式、来源、类别数、原图数、存储路径、创建时间、描述
- 删除操作：确认弹窗 → `?delete_files=false`（仅删注册）/ `?delete_files=true`（物理删除）二选一
- 格式转换导出按钮：保留但禁用 + 阶段二提示

### 6.6 Index.vue 改动

- `useMockStore` → `useDatasetsStore`
- `mockStore.datasets` → `datasetsStore.datasets`
- `mockStore.datasetTotal` → `datasetsStore.total`
- `mockStore.fetchDatasets()` → `datasetsStore.fetchDatasets()`
- `totalSamples` 用 `image_count` 求和

### 6.7 UI 规范遵循

遵循用户偏好与项目约束：
- 浅色主题、Emerald 绿（#10B981）主色
- 禁止 glass morphism / neon / pulse 动画
- SVG 图标（stroke-width=1.5），复用 `components/common/Icon.vue`
- 表单分组布局、■ 段落标题
- 状态色：ready 绿、building 琥珀、failed 红（语义色，200ms 内过渡）
- ECharts 配色采用中性灰 + Emerald 绿主调

---

## 七、错误处理与边界

### 7.1 错误语义

| 场景 | 异常/返回 | HTTP |
|------|----------|------|
| 路径不存在 / 非目录 | ValueError | 400 |
| 无法识别格式 | ValueError("无法识别数据集格式") | 400 |
| 名称/路径重复 | ValueError | 400 |
| 数据集不存在 | KeyError | 404 |
| 图片文件不存在 | FileNotFoundError | 404 |
| split 目录不存在 | 返回空列表 total=0 | 200 |
| 引擎未初始化 | （不会发生，始终初始化） | — |
| 内部异常 | Exception | 500 |

### 7.2 边界情况

- **空标注图片**：COCO images 无对应 annotation、YOLO 空 .txt、VOC 无 object → boxes=[]，计入 image_count 不计入 object_count，计入 non_empty_images 判断
- **tile 序号不连续**：按实际文件统计，不假设 63 片齐全
- **COCO 两种图片布局**：`{split}/` 直放（SSDC-UAV）与 `images/{split}/`，detect/parse 均需兼容
- **大文件预览**：original 直接读字节；thumbnail/medium 用 Pillow 缩放
- **并发**：MAX_WORKERS=1 不涉及；DatasetRegistry 单例内存操作，YAML 写入非并发安全（单机单进程，可接受）
- **路径含中文/空格**：Path 处理，前端 URL encode filename

### 7.3 性能边界（对齐 PRD §7.3）

- 数据集统计报告（万级样本，首次）：<=10s（仅解析标注文件，不解码图片）
- 报告缓存命中：<10ms
- 样本分页（50 张）：<500ms
- 缩略图生成：单张 <100ms

---

## 八、测试策略

### 8.1 后端单元测试

| 测试文件 | 覆盖 |
|---------|------|
| `backend/tests/test_dataset_formats.py` | parse_coco/parse_yolo/parse_voc 坐标转换、类别 ID 映射、tile stem 解析、过期路径忽略；detect_format 三格式识别 + 无法识别 |
| `backend/tests/test_dataset_analyzer.py` | scan 轻量统计、compute_report 重统计、缓存命中/失效、失衡告警、small/medium/large 边界 |
| `backend/tests/test_dataset_registry.py` | YAML 持久化、自动扫描发现、CRUD、import 重名校验、delete + ignored_folders、list_images 分页、preview 三尺寸 |
| `backend/tests/test_datasets_api.py` | 9 端点集成测试，错误语义（400/404/201） |

### 8.2 测试夹具

- `tests/fixtures/datasets/`：构造小规模三格式数据集（每格式 train/val/test 各 2-3 张图 + 标注），覆盖坐标转换与解析逻辑
- SSDC-UAV 真实数据集作为集成冒烟测试（可选，标记 slow，CI 跳过）

### 8.3 前端验证

- `npm run build`（TypeScript 检查 + Vite 构建）通过
- 手动验证：导入 SSDC-UAV 三格式 → 列表统计 → 详情 ECharts 报告 → 样本浏览 → 删除

---

## 九、改动影响与迁移

### 9.1 Mock 清理

- 删除 `backend/mock/datasets.json` 中数据集部分（batches.json 保留）
- 删除 `frontend/src/api/mock.ts`、`frontend/src/stores/mock.ts`
- 移除 `backend/tests/test_mock_api.py` 中数据集相关用例（或迁移到 test_datasets_api.py）

### 9.2 不受影响模块

- 模块一（数据管理）、模块二（数据处理）、模块四（算法广场）后端逻辑不变
- 首页 Index.vue 仅替换数据集统计来源（mock → datasets store），其余流程卡片不变

### 9.3 第二阶段预留

- IR 数据结构已定义，阶段二写出器（`write_coco`/`write_yolo`/`write_voc`）直接消费 IR
- `source` 字段支持 `built`（阶段二构建产物）
- `status` 字段支持 `building`/`failed`（阶段二异步任务）
- dataset_meta.json 的 `layout` 字段为构建产物目录解析预留
- API 路由 `POST /api/datasets`（构建）、`POST /api/datasets/{id}/export`（导出）、`GET /api/datasets/tasks/{id}` 阶段二补充，不影响阶段一路由

---

## 十、验收检查清单（第一阶段）

- [ ] `POST /api/datasets/scan` 对 SSDC-UAV 三格式目录预检，正确识别格式 + 规模 + 类别
- [ ] `POST /api/datasets/import` 导入三格式目录，写入 datasets.yaml + dataset_meta.json；COCO info 元信息被采信
- [ ] `GET /api/datasets/{id}/report` 统计与权威值一致（14220 图 / 89136 框 / 230 原图 / 640x640）
- [ ] `GET /api/datasets/{id}/images?split=` 分页返回，preview 三尺寸可用
- [ ] `DELETE /api/datasets/{id}` 默认仅删注册；`?delete_files=true` 物理删除；自动发现的加入 ignored_folders
- [ ] 启动自动扫描 datasets/，注册三格式目录，跳过 SSDDC-UAV_Original
- [ ] 前端列表统计卡片 + 格式筛选 + 导入入口正常
- [ ] 前端新建页导入 tab 功能完整，构建 tab 禁用提示
- [ ] 前端详情页 ECharts 报告 + 样本浏览 + 删除正常
- [ ] 首页数据集统计对接真实 store
- [ ] 后端单元测试通过，前端 `npm run build` 通过
