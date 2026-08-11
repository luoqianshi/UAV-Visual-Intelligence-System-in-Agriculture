# 设计文档：数据管理模块 - 真实功能替代 Mock

**日期**: 2026-08-11
**模块**: 模块一 · 数据管理（原始架次管理）
**目标**: 将架次管理从 mock 数据替换为基于本机文件系统的真实功能，使用 YAML 持久化，支持自动扫描注册已有数据。

---

## 一、概述

### 1.1 背景

当前数据管理模块使用静态 mock 数据（`backend/mock/batches.json`），前端通过 mock store 读取。需要替换为真实功能，对接本机文件系统，实现：
- 按架次登记 UAV 采集的原始图片数据
- 启动时自动扫描 `data/` 目录注册已有批次
- 架次信息以 YAML 格式持久化在 `data/batches.yaml`
- 支持本机任意可访问路径作为图片数据来源
- 图片浏览支持分页、动态缩略图、懒加载

### 1.2 真实数据集

`data/` 目录下已有 3 个批次的甘蔗幼苗采集数据：
- `sugarcane_20250419_5m/` — 约 84 张，5m 高度
- `sugarcane_20250419_8m/` — 约 85 张，8m 高度
- `sugarcane_20250419_10m/` — 约 79 张，10m 高度

图片格式：JPEG (`.JPG`)，分辨率 5472×3648，单张约 4-8MB。

### 1.3 设计原则

- **一致性**: 后端 `BatchRegistry` 参考现有 `ModelRegistry`（`backend/core/registry.py`）的代码风格与模式
- **轻量级**: 不引入数据库，纯 YAML 配置 + 内存索引，符合项目现有技术栈
- **不复制文件**: 原始图片保留在用户指定路径，系统不做文件复制，仅登记路径与索引
- **可编辑**: 自动注册的架次支持元数据编辑与删除（删除不删原始文件）

---

## 二、目录与文件结构

### 2.1 新增/修改文件清单

```
backend/
├── core/
│   └── batch_registry.py         ← 新增：架次注册中心
├── api/
│   └── batches_api.py            ← 修改：替换 mock 为真实实现
├── config.py                     ← 修改：添加 DATA_DIR 等常量
└── app.py                        ← 修改：初始化 BatchRegistry

data/
├── batches.yaml                  ← 新增（启动时自动生成）：架次配置
├── sugarcane_20250419_5m/        ← 已有数据
├── sugarcane_20250419_8m/        ← 已有数据
└── sugarcane_20250419_10m/       ← 已有数据

frontend/src/
├── api/
│   └── batches.ts                ← 新增：架次 API 客户端
├── views/data/
│   ├── Batches.vue               ← 修改：替换 mock，真实 API
│   ├── BatchNew.vue              ← 修改：真实路径扫描+提交
│   └── BatchDetail.vue           ← 修改：编辑+分页图片浏览
└── stores/
    └── mock.ts                   ← 修改：移除 batches 相关 mock
```

---

## 三、后端设计

### 3.1 config.py 新增常量

```python
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
```

### 3.2 batches.yaml 格式

参考 `config/models.yaml` 的风格：

```yaml
batches:
  - batch_id: batch_sugarcane_20250419_5m
    batch_name: sugarcane_20250419_5m
    crop_type: 甘蔗
    flight_date: "2025-04-19"
    plot_name: ""
    drone_model: DJI Mavic 3 M
    flight_altitude_m: 5.0
    overlap_front: 0.8
    overlap_side: 0.7
    image_folder_path: data/sugarcane_20250419_5m
    image_count: 84
    total_size_bytes: 723456789
    created_at: "2026-08-11T10:00:00"
    image_formats: [JPEG]
    status: ready
    description: "自动扫描注册：甘蔗幼苗，5m高度采集"
  # ... 其他架次
ignored_folders: []
```

字段说明：
- `batch_id`: 自动生成，格式 `batch_{sanitized_folder_name}`，唯一且不可修改
- `image_folder_path`: 支持相对路径（相对 PROJECT_ROOT）和绝对路径
- `image_formats`: 使用内联列表格式（与 models.yaml 中 classes 一致）
- `ignored_folders`: 用户主动删除的自动发现文件夹名列表，下次扫描跳过

### 3.3 BatchRegistry 类设计

文件：`backend/core/batch_registry.py`

```python
class BatchRegistry:
    """架次注册中心：YAML加载 + 自动扫描 + CRUD + 图片索引 + 缩略图生成"""

    def __init__(self, data_dir: Path, yaml_path: Path):
        self._data_dir = data_dir
        self._yaml_path = yaml_path
        self._batches: dict[str, dict] = {}       # batch_id -> config
        self._image_index: dict[str, list] = {}   # batch_id -> image list
        self._ignored_folders: set[str] = set()

    def load_from_yaml(self) -> None:
        """加载 YAML → 自动发现新架次 → 构建内存索引 → 如有新增则保存回 YAML"""
        # 1. 读取 YAML（不存在则初始化为空）
        # 2. 加载 ignored_folders
        # 3. 扫描 _data_dir 一级子目录，发现未注册且未忽略的有效图片文件夹
        # 4. 对每个新发现的文件夹，调用 _auto_register_batch 自动注册
        # 5. 对已注册架次，调用 _scan_images 构建内存图片索引
        # 6. 如果有新增自动注册的架次，调用 save_to_yaml()

    def save_to_yaml(self) -> None:
        """将 _batches 和 _ignored_folders 持久化到 YAML"""

    def _ordered_config(self, cfg: dict) -> dict:
        """按标准字段顺序排列，确保 YAML 输出格式一致"""
        # 字段顺序与 batches.yaml 示例一致
        # image_formats 列表使用内联格式（flow_style）

    def list_batches(self, crop_type=None, flight_date=None, plot_name=None) -> list[dict]:
        """返回架次列表，支持过滤条件"""

    def get_batch(self, batch_id: str) -> dict:
        """获取单个架次详情，不存在抛 KeyError"""

    def create_batch(self, config: dict) -> dict:
        """
        创建新架次（表单提交）：
        1. 校验必填字段（batch_name, crop_type, flight_date, image_folder_path）
        2. 校验路径存在、可读、是目录
        3. 扫描图片，校验数量≤2000、单张≤50MB
        4. 检查名称重名、路径重复
        5. 生成 batch_id，设置 created_at、status=ready
        6. 持久化到 YAML，更新内存索引
        返回新创建的架次 config
        """

    def update_batch(self, batch_id: str, updates: dict) -> dict:
        """
        更新架次元数据：
        - 不可变字段：batch_id, image_folder_path, image_count, total_size_bytes, created_at
        - 可更新字段：batch_name, crop_type, flight_date, plot_name, drone_model,
                      flight_altitude_m, overlap_front, overlap_side, description
        - 如果 batch_name 变更，batch_id 保持不变（避免引用失效）
        """

    def delete_batch(self, batch_id: str) -> None:
        """
        删除架次登记（不删除原始文件）：
        - 如果该架次是自动扫描注册的（路径在 _data_dir 下），将文件夹名加入 ignored_folders
        - 从 _batches 和 _image_index 中移除
        - 持久化到 YAML
        """

    def scan_path(self, folder_path: str) -> dict:
        """
        路径预检（表单扫描按钮使用）：
        - 不持久化，仅返回路径有效性、图片数量、总大小、格式分布
        - 返回 {valid, image_count, total_size_bytes, formats, message}
        """

    def list_images(self, batch_id: str, page=1, page_size=50,
                    sort_by='filename', order='asc') -> dict:
        """
        分页获取架次下的图片列表：
        - 从 _image_index[batch_id] 返回分页切片
        - 每张图片附带 thumbnail_url 和 preview_url
        - 返回 {images, total, page, page_size, total_pages}
        """

    def get_image_preview(self, batch_id: str, filename: str, size='thumbnail') -> bytes:
        """
        生成图片预览字节流：
        - size='thumbnail': 长边 400px JPEG（quality=80）
        - size='medium': 长边 1920px JPEG（quality=85）
        - size='original': 返回原图
        - 使用 Pillow 动态生成，不缓存
        - 返回 JPEG 字节流
        """

    def _scan_images(self, folder_path: Path) -> tuple[list, int, int, list]:
        """
        扫描文件夹下所有合法图片：
        - 遍历 IMAGE_EXTENSIONS 后缀的文件
        - 用 Pillow 读取每张图片的 width/height
        - 统计 total_size_bytes、formats 集合
        - 返回 (images_list, count, total_bytes, formats_list)
        - 过滤超过 MAX_IMAGE_SIZE_BYTES 的文件（记录警告但不中断）
        """

    def _generate_thumbnail(self, image_path: Path, max_size: int, quality: int) -> bytes:
        """使用 Pillow 生成缩略图 JPEG 字节流：
        - 等比例缩放，长边不超过 max_size
        - 使用 LANCZOS 重采样
        - 保存为 JPEG，返回字节流
        """

    def _auto_discover_batches(self) -> list[Path]:
        """扫描 _data_dir 下的一级子目录，返回未注册且未忽略的有效图片文件夹路径"""

    def _infer_metadata(self, folder_name: str, folder_path: Path) -> dict:
        """
        从文件夹名推断元数据：
        - 格式：{crop}_{date}_{altitude}m（如 sugarcane_20250419_5m）
        - crop: 前缀在 CROP_NAME_MAP 中查找中文映射
        - date: 8位数字解析为 YYYY-MM-DD
        - altitude: 数字部分（去除 'm' 后缀）
        - 无法解析时：crop_type="未知作物"，flight_date=文件夹mtime，altitude=None
        - 默认值：drone_model=DEFAULT_DRONE_MODEL，overlap_front=0.8，overlap_side=0.7
        """

    def _sanitize_name(self, name: str) -> str:
        """将名称转换为安全 ID 字符串（只保留字母数字下划线连字符）"""

    def _resolve_path(self, path_str: str) -> Path:
        """将路径字符串解析为绝对 Path（相对路径相对 PROJECT_ROOT）"""
```

### 3.4 API 接口设计

所有接口统一响应信封：`{"success": bool, "data": ..., "message": str}`

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/batches` | 架次列表（支持 crop_type/flight_date/plot_name 过滤） |
| POST | `/api/batches` | 注册新架次 |
| GET | `/api/batches/{batch_id}` | 架次详情 |
| PUT | `/api/batches/{batch_id}` | 更新架次元数据 |
| DELETE | `/api/batches/{batch_id}` | 删除架次登记 |
| GET | `/api/batches/{batch_id}/images` | 架次图片列表（分页） |
| GET | `/api/batches/{batch_id}/images/{filename}/preview` | 图片预览（?size=thumbnail|medium|original） |
| POST | `/api/batches/scan` | 路径预检扫描（表单扫描按钮使用） |

**GET /api/batches 响应 data 结构：**
```json
{
  "batches": [...],
  "total": 3,
  "summary": {
    "total_batches": 3,
    "total_images": 245,
    "total_size_bytes": 2145678901,
    "resolutions": ["5472x3648"],
    "formats": ["JPEG"]
  }
}
```

**POST /api/batches 请求体：**
```json
{
  "batch_name": "sugarcane_20260805_001",
  "crop_type": "甘蔗",
  "flight_date": "2026-08-05",
  "plot_name": "A区",
  "drone_model": "DJI Mavic 3 M",
  "flight_altitude_m": 5,
  "overlap_front": 0.8,
  "overlap_side": 0.7,
  "image_folder_path": "D:/data/images"
}
```

**GET /api/batches/{batch_id}/images 查询参数：**
- `page`: 页码，默认 1
- `page_size`: 每页数量，默认 50
- `sort_by`: 排序字段（filename/size），默认 filename
- `order`: 排序方向（asc/desc），默认 asc

**图片预览响应：** `image/jpeg` 二进制流，带 `Cache-Control: public, max-age=3600` 头。

### 3.5 错误处理

| 场景 | HTTP 状态码 | message |
|------|------------|---------|
| 架次不存在 | 404 | `架次不存在: {batch_id}` |
| 图片路径不存在/不可读 | 400 | `图片路径不存在或不可访问: {path}` |
| 路径不是目录 | 400 | `指定的路径不是文件夹` |
| 无合法图片 | 400 | `指定路径下未找到合法图片文件` |
| 图片数量超 2000 张 | 400 | `图片数量超过上限（2000张），当前: {n}张` |
| 架次名称重名 | 409 | `架次名称已存在: {name}` |
| 路径已被注册 | 409 | `该路径已被架次 {batch_id} 注册` |
| 尝试修改不可变字段 | 400 | `图片路径不可修改，如需更换请删除后重新注册` |

### 3.6 自动扫描注册流程

1. `BatchRegistry.load_from_yaml()` 被调用时（Flask 应用启动）
2. 加载已有 batches.yaml 中的架次配置和 ignored_folders
3. 遍历 `data/` 目录下一级子目录
4. 跳过：隐藏目录、ignored_folders 中的目录、无合法图片的目录
5. 对每个未注册的有效目录：
   - 调用 `_infer_metadata()` 推断元数据
   - 调用 `_scan_images()` 扫描图片并统计
   - 生成 batch_id，设置 created_at=当前时间，status=ready
   - 添加到 _batches
6. 对所有已注册架次（包括 YAML 中已有的），调用 `_scan_images()` 构建内存索引
7. 如果有新增自动注册的架次，保存回 YAML

---

## 四、前端设计

### 4.1 batches.ts API 客户端

新建 `frontend/src/api/batches.ts`，参考 `models.ts` 的风格：

```typescript
export interface Batch {
  batch_id: string
  batch_name: string
  crop_type: string
  flight_date: string
  plot_name?: string
  drone_model?: string
  flight_altitude_m?: number
  overlap_front?: number
  overlap_side?: number
  image_folder_path: string
  image_count: number
  total_size_bytes: number
  created_at: string
  image_formats: string[]
  status: string
  description?: string
}

export interface BatchImage {
  filename: string
  size_bytes: number
  width: number
  height: number
  format: string
  thumbnail_url: string
  preview_url: string
}

export const batchesApi = {
  list(params?),
  get(batchId),
  create(data),
  update(batchId, data),
  delete(batchId),
  listImages(batchId, params?),
  imagePreviewUrl(batchId, filename, size?),
  scanPath(image_folder_path),
}
```

### 4.2 字段映射（mock → PRD 标准）

| mock 字段 | PRD 标准字段 | 说明 |
|-----------|-------------|------|
| id | batch_id | 架次唯一标识 |
| name | batch_name | 架次名称 |
| crop_type | crop_type | 不变 |
| flight_date | flight_date | 不变 |
| location / plot_id | plot_name | 地块名称 |
| drone_model | drone_model | 不变 |
| altitude_m | flight_altitude_m | 飞行高度 |
| image_count | image_count | 不变 |
| resolution | 来自 summary | 从列表 summary 获取 |
| status | status | ready/editing |
| created_at | created_at | 不变 |
| path | image_folder_path | 图片路径 |
| total_size_gb | total_size_bytes | 前端转换显示 |
| sensor | 移除 | PRD 中无此字段 |

### 4.3 Batches.vue（架次列表页）变更

- 移除 `useMockStore`，改用 `batchesApi.list()` 获取数据
- 总览卡片数据从 API 返回的 `summary` 渲染
- 表格列名和字段名按映射表更新
- 增加"删除"操作（带确认弹窗）
- 替换 Font Awesome 图标为自定义 SVG Icon 组件
- 删除架次成功后刷新列表

### 4.4 BatchNew.vue（新建架次页）变更

- 表单字段对齐 PRD：batch_name、crop_type、flight_date、plot_name、drone_model、flight_altitude_m、overlap_front、overlap_side、image_folder_path、description
- "扫描"按钮真实调用 `batchesApi.scanPath()`，显示真实扫描结果
- 表单验证：必填字段校验、路径格式校验
- 提交成功后跳转到 `/data/batches/{batch_id}`
- 替换 Font Awesome 图标为 SVG Icon

### 4.5 BatchDetail.vue（架次详情页）变更

- **编辑功能**：添加"编辑"按钮，内联展开编辑表单（不单独建组件），编辑可更新字段，保存后刷新
- **图片分页加载**：
  - 默认 page_size=50，首次加载第一页
  - 图片网格使用 `<img loading="lazy">` 原生懒加载
  - 底部"加载更多"按钮，追加下一页图片
  - Lightbox 支持在已加载的图片间翻页
- **删除功能**："删除架次"按钮，二次确认弹窗
- 移除 mock 的关联任务/所属数据集静态卡片（模块二、三尚未实现）
- 元数据字段按 PRD 标准更新
- 替换 Font Awesome 图标为 SVG Icon

### 4.6 mock.ts 变更

- 移除 batches 相关 state（batches、batchTotal、loading）
- 移除 fetchBatches、createBatch、fetchBatch、fetchBatchImages 等方法
- 移除 batchImagePreviewUrl 方法（由 batches.ts 提供）
- 保留 datasets 和 processing tasks 的 mock 数据（后续模块替换）

---

## 五、关键技术细节

### 5.1 缩略图生成

使用 Pillow（PIL）生成，项目已有 Pillow 依赖：
- thumbnail(400px): `Image.open().thumbnail((400, 400), Image.LANCZOS)` → JPEG quality=80
- medium(1920px): 长边缩放至 1920 → JPEG quality=85
- 不缓存到磁盘，每次请求动态生成（响应带 Cache-Control 头，浏览器缓存）

### 5.2 图片尺寸读取

在 `_scan_images()` 阶段用 Pillow 读取每张图片的尺寸（`Image.open().size`），存储在内存 `_image_index` 中。不持久化到 YAML（避免 YAML 过大），重启时重新扫描（3 个批次约 245 张图，预计 1-2 秒）。

### 5.3 路径处理

- 存储：相对路径（相对于 PROJECT_ROOT）优先，绝对路径保持原样
- 使用：统一转换为 `Path.resolve()` 绝对路径
- Windows 路径分隔符由 pathlib 自动处理
- 支持本机任意可访问路径（不限于 data/ 目录下）

### 5.4 忽略列表机制

- 用户删除自动扫描注册的架次时，其文件夹名加入 `ignored_folders`
- `ignored_folders` 持久化在 batches.yaml 中
- 下次启动自动扫描时跳过这些文件夹
- 用户仍可通过"新建架次"表单手动指定该路径重新注册

### 5.5 .gitignore 处理

当前 `.gitignore` 中已有 `data/` 规则，会忽略整个 data 目录（包括 batches.yaml）。这是合理的——batches.yaml 中的路径是本机特定的，不同开发环境路径不同，不应纳入版本控制。每个环境在启动时会自动扫描 data/ 目录生成自己的 batches.yaml。**不需要修改 .gitignore。**

---

## 六、测试要点

1. **自动扫描测试**：启动时自动发现并注册 data/ 下 3 个批次
2. **CRUD 测试**：创建、读取、更新、删除架次
3. **路径校验测试**：不存在路径、非目录路径、无图片路径、超限图片路径
4. **图片分页测试**：分页参数、排序、空列表
5. **缩略图生成测试**：不同 size 参数、图片不存在、非图片文件
6. **删除忽略测试**：删除自动扫描架次后，重启不会重新注册
7. **外部路径测试**：注册 data/ 目录外的绝对路径

---

## 七、实现顺序

1. 修改 `backend/config.py`：添加常量
2. 创建 `backend/core/batch_registry.py`：实现 BatchRegistry 类
3. 修改 `backend/api/batches_api.py`：替换 mock 为真实 API
4. 修改 `backend/app.py`：初始化 BatchRegistry
5. 创建 `frontend/src/api/batches.ts`：API 客户端
6. 修改 `frontend/src/views/data/Batches.vue`：真实 API + 字段映射
7. 修改 `frontend/src/views/data/BatchNew.vue`：真实扫描+提交
8. 修改 `frontend/src/views/data/BatchDetail.vue`：编辑+分页图片浏览
9. 修改 `frontend/src/stores/mock.ts`：清理 batches 相关 mock
10. 运行 TypeScript 检查和 Python 测试，构建验证
