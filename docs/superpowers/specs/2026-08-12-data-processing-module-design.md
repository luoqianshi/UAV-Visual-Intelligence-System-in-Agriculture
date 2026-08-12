# 数据处理模块（模块二）真实实现设计文档

**文档版本**：v1
**编制日期**：2026-08-12
**关联 PRD**：PRD_基于无人机图像的大田农作物智能监测与管理系统_v5.md §3（模块二）
**关联代码**：`backend/core/clahe.py`、`backend/core/tiling.py`、`backend/api/processing_api.py`（Mock）、`backend/mock/tasks.json`

---

## 一、设计目标

### 1.1 范围

将 PRD §3 模块二（数据处理）从 Mock 状态升级为真实功能：

- **核心功能**：批量 CLAHE 增强（FR-P01）、批量滑窗裁切（FR-P02）、处理结果预览（FR-P03）、多批次选择与任务管理（FR-P04）
- **附加新功能**（优先级 LAST）：在数据管理下新增【加工数据】栏目，浏览 `output/` 目录下的处理产物，与处理任务一一对应
- **不纳入**：标注相关操作、数据集拆分与导出（模块三）、检测推理（模块四）

### 1.2 用户决策摘要

经 brainstorming 澄清，确定以下关键决策：

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 任务持久化 | YAML 持久化 | `data/processing_tasks.yaml`，参考 `batch_registry` 模式 |
| 多架次输出结构 | 按架次分子目录 | `output/{type}_{ts}/{sub_dir}/*.jpg`，保证可追溯 |
| 子图命名规范 | memory 格式 | `{orig_stem}_tile_{seq:04d}_x{offset_x}_y{offset_y}.jpg` |
| 加工数据栏目布局 | 双 tab | 在 `/data/` 下加 `DataSubTabs`，参考算法广场 SubTabs |
| 加工数据与任务关系 | 一一对应 | 每个 `output/{type}_{ts}/` 目录对应一个处理任务 |
| 异步任务队列 | 独立队列 | 新建 `processing_task_manager`（max_workers=1），与检测/计数队列隔离 |
| 后端架构 | 方案 A | `ProcessingEngine`（执行）+ `ProcessingRegistry`（持久化）双类 |

### 1.3 约束

- Python 3.8 兼容：使用 `typing.List/Dict/Optional`，禁用 PEP 585 内置泛型（`list[dict]` 等）
- 前端 UI 遵循项目 memory：Gradio-style 简约风、Emerald green (#10B981)、SVG 图标（stroke-width=1.5）、无 emoji
- 引擎降级：`processing_engine` 依赖 `cv2/numpy`，缺失时 `processing_engine=None`，API 返回 `success:false`（503）而非 500
- `clahe.py` / `tiling.py` 零改动：`counter.py` 依赖这两个模块，不可影响算法广场

---

## 二、整体架构

### 2.1 模块结构

```
backend/
├── core/
│   ├── processing_engine.py     # NEW：ProcessingEngine 类（执行 CLAHE/crop 批处理）
│   ├── processing_registry.py   # NEW：ProcessingRegistry 类（YAML 持久化 + output/ 自扫描）
│   ├── task_manager.py          # 扩展：submit() 增加 task_id 参数（向后兼容）
│   ├── engine.py                # 扩展：新增 3 个单例
│   ├── clahe.py                 # 不改动
│   ├── tiling.py                # 不改动
│   └── ...其他模块不变
├── api/
│   └── processing_api.py        # 重写：替换 Mock，提供 8 个端点
├── config.py                    # 扩展：新增 OUTPUT_DIR、PROCESSING_TASKS_YAML
├── mock/
│   └── tasks.json               # 删除（保留 datasets.json 与 batches.json）
└── tests/
    ├── test_processing_engine.py       # NEW
    ├── test_processing_registry.py     # NEW
    ├── test_processing_api.py          # NEW
    └── test_processing_integration.py  # NEW

frontend/src/
├── api/
│   └── processing.ts            # NEW：替换 mock，调用真实 API
├── stores/
│   └── processing.ts            # NEW：Pinia store（任务列表/进度轮询）
├── components/layout/
│   └── DataSubTabs.vue          # NEW：参考 SubTabs.vue
├── views/process/
│   ├── Tasks.vue                # 改造：去 mock store，用真实 API
│   ├── TaskNew.vue              # 改造：submit() 调用真实 API
│   └── TaskDetail.vue          # 改造：真实预览图 + 进度轮询
├── views/data/
│   ├── Batches.vue              # 顶部加 <DataSubTabs />，副标题改"原始数据"
│   ├── BatchNew.vue             # 顶部加 <DataSubTabs />
│   ├── BatchDetail.vue          # 顶部加 <DataSubTabs />
│   ├── Processed.vue            # NEW：加工数据列表
│   └── ProcessedDetail.vue      # NEW：加工数据详情
└── router/index.ts              # 新增 2 条路由
```

### 2.2 数据流

```
┌──────────────────────────────────────────────────────────────┐
│  前端                                                          │
│  ├─ /process/tasks        列表（真实 API）                     │
│  ├─ /process/task-new     4 步向导（提交真实任务）              │
│  ├─ /process/tasks/:id    详情（真实预览 + 进度轮询）          │
│  └─ /data/processed       【加工数据】tab（优先级 LAST）       │
│     /data/processed/:id   加工数据详情                         │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP REST
┌────────────────────▼─────────────────────────────────────────┐
│  processing_api.py（重写）                                     │
│  ├─ POST /api/processing/clahe              提交 CLAHE 任务   │
│  ├─ POST /api/processing/crop               提交裁切任务      │
│  ├─ GET  /api/processing/tasks              任务列表           │
│  ├─ GET  /api/processing/tasks/:id          任务详情           │
│  ├─ GET  /api/processing/tasks/:id/preview  结果图片预览       │
│  ├─ GET  /api/processing/tasks/:id/files    结果文件清单       │
│  ├─ GET  /api/processing/processed         加工数据列表       │
│  ├─ GET  /api/processing/processed/:id     加工数据详情       │
│  ├─ GET  /api/processing/processed/:id/files 加工数据文件清单 │
│  └─ DELETE /api/processing/processed/:id   删除加工数据        │
└────────────────────┬─────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────────┐
│  核心层                                                       │
│  ├─ ProcessingEngine     执行：clahe.enhance / tiling.slide  │
│  ├─ ProcessingRegistry   YAML 持久化 + output/ 自扫描        │
│  └─ processing_task_manager  max_workers=1，独立队列         │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 任务执行时序

1. 前端 `POST /api/processing/clahe` 提交任务（参数 + input_paths）
2. `processing_api` 校验参数，调用 `registry.create_task()` 写入 YAML（status=pending），生成 task_id（如 `clahe_20260812_153000_456`）
3. `processing_task_manager.submit("processing", engine.run_clahe, task_id=cfg["task_id"])` 异步执行
4. `ProcessingEngine.run_clahe`：逐图读 → `clahe.enhance` → 写 `output/{task_id}/{sub_dir}/` → 进度回调
5. 进度回调内调用 `registry.update_task()` 更新 YAML（progress、processed_images、status=processing）
6. 完成后写入 `output/{task_id}/index.json`，registry 标记 status=completed
7. 前端轮询 `GET /api/processing/tasks/:id` 获取进度直到 completed/failed

---

## 三、后端设计

### 3.1 ProcessingEngine（执行层）

**文件**：`backend/core/processing_engine.py`

**职责**：无状态执行器，提供 `run_clahe` 与 `run_crop` 两个公开方法，复用 `core/clahe.py` 与 `core/tiling.py` 的纯算法函数。

**接口规范**：

```python
class ProcessingEngine:
    def __init__(self):
        pass  # 无状态

    def run_clahe(self, task_id: str, input_paths: list,
                  params: dict, output_dir: Path,
                  on_progress=None) -> dict:
        """批量 CLAHE 增强。

        Args:
            task_id: 任务 ID
            input_paths: 输入源路径列表（架次文件夹路径 / 自定义目录路径，相对或绝对）
            params: {clip_limit: float, grid_size: [int, int]}
            output_dir: output/{task_id}/ Path 对象
            on_progress: 回调 fn(processed: int, total: int)

        Returns:
            {total_images, processed_images, output_dir, sub_dirs: [{sub_dir, image_count}]}
        """

    def run_crop(self, task_id: str, input_paths: list,
                 params: dict, output_dir: Path,
                 on_progress=None) -> dict:
        """批量滑窗裁切。

        Args:
            params: {tile_size: int, overlap_ratio: float}
        Returns:
            {total_images, processed_images, total_tiles, output_dir, sub_dirs}
        """

    def write_index(self, output_dir: Path, task_id: str, task_type: str,
                    params: dict, result: dict, created_at: str) -> None:
        """写入 output/{type}_{ts}/index.json（任务参数 + 输出统计快照）。"""
```

**关键实现要点**：

1. **输入源归一化**：`_collect_inputs(input_paths)` 把架次路径与自定义目录统一为 `[(sub_dir_name, [image_paths])]` 列表。`sub_dir_name` 用目录名（架次文件夹名天然就是 `sugarcane_5m` 等有意义的名字）
2. **CLAHE 处理**：`cv2.imread` 读 BGR → `clahe.enhance(img, clip_limit, grid_size)` → `cv2.imwrite` 保持原文件名
3. **裁切处理**：`cv2.imread` → `tiling.slide_window(img, tile_size, overlap_ratio)` → 子图命名为 `{orig_stem}_tile_{seq:04d}_x{offset_x}_y{offset_y}.jpg`
4. **错误隔离**：单张图片失败只警告（`logger.warning`）不中断，符合 PRD"处理过程出错"语义
5. **进度回调**：每张图处理完后调用 `on_progress(processed, total)`，由 API 层包装为更新 task_manager 与 YAML
6. **index.json**：每次任务输出附带 JSON 快照，包含 task_id / task_type / params / created_at / total_images / processed_images / sub_dirs / total_tiles（仅 crop），即使 YAML 丢失也能从 output/ 重建任务记录

**output 目录结构**（多架次合并）：

```
output/clahe_20260812_153000_456/        # 目录名 = task_id
├── sugarcane_5m/                        # 架次 1 子目录（用源目录名）
│   ├── DJI_0001.jpg
│   ├── DJI_0002.jpg
│   └── ...
├── sugarcane_8m/                        # 架次 2 子目录
│   └── ...
├── custom_dir_name/                     # 自定义目录输入
│   └── ...
└── index.json                           # 任务参数快照
```

裁切任务结构相同，子目录下文件名改为 `{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg`。

**子目录命名与冲突处理**：默认使用输入源目录名作为 `sub_dir`。若多个输入源的目录名相同（如两个不同绝对路径都以 `sugarcane_5m` 结尾），则第二个追加 `_2`、第三个 `_3` 以避免冲突。

### 3.2 ProcessingRegistry（持久化层）

**文件**：`backend/core/processing_registry.py`

**职责**：YAML 持久化任务记录 + 启动时自扫描 output/ + CRUD + 加工数据列表查询。

**YAML 文件**：`data/processing_tasks.yaml`

**字段顺序**（统一对齐 batch_registry 风格）：

```python
_TASK_FIELD_ORDER = [
    "task_id", "name", "task_type", "status", "progress",
    "input_paths", "output_path", "params",
    "total_images", "processed_images", "total_tiles",
    "created_at", "started_at", "completed_at", "error",
    "sub_dirs",
]
```

**任务状态机**：

```
pending → processing → completed
                    ↘ failed
                    ↘ interrupted（重启时由 processing 标记）
```

**接口规范**：

```python
class ProcessingRegistry:
    def __init__(self, output_dir: Path = OUTPUT_DIR,
                 yaml_path: Path = PROCESSING_TASKS_YAML): ...

    # 加载与持久化
    def load_from_yaml(self) -> None:
        """启动时：
        1. 读取 processing_tasks.yaml
        2. processing 状态的任务标记为 interrupted（重启后无法恢复进程）
        3. 扫描 output/ 目录，发现未注册的 index.json 自动补全
        """

    def save_to_yaml(self) -> None: ...

    # CRUD
    def create_task(self, name: str, task_type: str,
                    input_paths: list, params: dict) -> dict:
        """创建任务记录。生成 task_id 与 output_path。
        task_id 格式：{task_type}_{ts}_{ms:03d}，如 clahe_20260812_153000_456
        output_path 格式：output/{task_type}_{ts}_{ms:03d}（与 task_id 完全一致，避免同秒创建冲突）
        """

    def update_task(self, task_id: str, **fields) -> dict:
        """更新任务字段（progress/status/processed_images 等）。"""

    def get_task(self, task_id: str) -> dict: ...
    def list_tasks(self, task_type: Optional[str] = None,
                   status: Optional[str] = None) -> List[dict]: ...

    def delete_task(self, task_id: str, delete_output: bool = False) -> None:
        """删除任务记录。delete_output=True 时同时删除 output 目录。"""

    # 加工数据列表（output 扫描）
    def list_processed(self) -> list:
        """列出 output/ 下所有处理产物，每个产物对应一个 output/{type}_{ts}/ 目录。
        返回字段：output_path, task_id, task_type, name, status, params,
                 image_count, total_tiles, created_at, sub_dirs, has_task
        """

    # 私有
    def _auto_discover_output(self) -> None:
        """扫描 output/ 目录，发现未注册的 index.json 自动重建任务记录。"""

    def _count_input_images(self, input_paths: list) -> int: ...
    def _resolve_path(self, path_str: str) -> Path: ...
    def _ordered_config(self, cfg: dict) -> dict: ...
```

**关键实现要点**：

1. **重启容错**：`load_from_yaml()` 时把 `processing` 状态的任务标记为 `interrupted`，避免假死
2. **task_id 与目录名映射**：task_id 与 output 目录名完全一致，如 `clahe_20260812_153000_456` ↔ `output/clahe_20260812_153000_456/`，避免同秒创建多个任务时目录冲突，且可双向反查
3. **output/ 自扫描**：基于 `index.json` 重建任务记录，即使 YAML 丢失也能恢复；同时服务于【加工数据】列表
4. **路径解析**：`_resolve_path()` 与 `batch_registry` 一致，相对路径相对 `PROJECT_ROOT`
5. **删除策略**：`delete_task(task_id, delete_output=True)` 删除记录同时清理文件

### 3.3 task_manager.py 扩展

增加 `task_id` 参数支持自定义 ID（向后兼容）：

```python
def submit(self, task_type: str, func, *args, task_id: str = None, **kwargs) -> str:
    task_id = task_id or f"{task_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    # ... 其余逻辑不变
```

### 3.4 engine.py 扩展

新增 3 个单例：

```python
# 全局变量
processing_engine = None
processing_registry = None
processing_task_manager = None

def init_engines():
    # ...（原有逻辑不变）

    # ⑤ 处理引擎：依赖 cv2/numpy，缺失时降级
    global processing_engine, processing_registry, processing_task_manager
    try:
        from core.processing_engine import ProcessingEngine
        from core.processing_registry import ProcessingRegistry
        processing_engine = ProcessingEngine()
        processing_registry = ProcessingRegistry()
        processing_registry.load_from_yaml()
        processing_task_manager = TaskManager(max_workers=1)  # 独立队列
    except Exception as exc:
        logger.warning("处理引擎初始化失败（数据处理功能不可用）：%s", exc)

def get_processing_engine(): return processing_engine
def get_processing_registry(): return processing_registry
def get_processing_task_manager(): return processing_task_manager
```

### 3.5 config.py 扩展

```python
# 新增
OUTPUT_DIR = PROJECT_ROOT / "output"
PROCESSING_TASKS_YAML = DATA_DIR / "processing_tasks.yaml"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
```

### 3.6 processing_api.py 重写

**文件**：`backend/api/processing_api.py`

**端点清单**：

| 方法 | 路由 | 用途 |
|------|------|------|
| POST | `/api/processing/clahe` | 提交 CLAHE 任务（异步） |
| POST | `/api/processing/crop` | 提交裁切任务（异步） |
| GET | `/api/processing/tasks` | 任务列表（支持 `?type=` & `?status=` 过滤） |
| GET | `/api/processing/tasks/<task_id>` | 任务详情 |
| GET | `/api/processing/tasks/<task_id>/preview` | 结果图片预览（`?filename=&sub_dir=&size=`） |
| GET | `/api/processing/tasks/<task_id>/files` | 结果文件清单（分页，`?sub_dir=&page=&page_size=`） |
| GET | `/api/processing/processed` | 加工数据列表 |
| GET | `/api/processing/processed/<processed_id>` | 加工数据详情 |
| GET | `/api/processing/processed/<processed_id>/files` | 加工数据文件清单 |
| DELETE | `/api/processing/processed/<processed_id>` | 删除加工数据（`?delete_output=true`） |

**关键实现要点**：

1. **任务提交流程**（POST clahe / crop）：
   - 校验 `input_paths` 非空、`params` 字段合法
   - `registry.create_task()` 写入 YAML（status=pending）生成 task_id
   - `processing_task_manager.submit("processing", _run, task_id=cfg["task_id"])`
   - `_run` 闭包内：调用 `engine.run_*` + `engine.write_index` + `registry.update_task` 标记完成/失败

2. **任务状态查询来源**：`GET /api/processing/tasks/:id` 始终从 `registry` 读取（持久化层）。`task_manager` 仅用于异步执行机制，不作为查询源。`on_progress` 回调实时更新 registry，保证 registry 始终持有最新状态。

3. **预览端点**：复用 Pillow 缩略图逻辑（thumbnail=400px / medium=1920px / original），与 `batch_registry._generate_thumbnail` 实现一致

4. **文件清单端点**：列出 `output/{task_id}/[sub_dir]/` 下的图片文件，支持分页（默认 page_size=50），返回 `filename / size_bytes / width / height / format / thumbnail_url / preview_url`

5. **加工数据列表**：直接调用 `registry.list_processed()`，无需重复扫描

6. **统一响应格式**：所有响应遵循 `{success: bool, data: <data>|None, message: str}`

7. **错误降级**：`processing_engine` 为 None 时返回 `success:false`（503），非 500

### 3.7 Mock 清理

- 删除 `backend/mock/tasks.json`
- `backend/tests/test_mock_api.py` 中移除 processing 相关测试（保留 datasets 部分）
- 前端 `frontend/src/api/mock.ts` 移除 `ProcessingTask` 类型与 `fetchTasks` / `fetchTask`
- 前端 `frontend/src/stores/mock.ts` 移除 `tasks` / `fetchTasks` 相关逻辑

---

## 四、前端设计

### 4.1 API 客户端

**文件**：`frontend/src/api/processing.ts`

```typescript
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

export const processingApi = {
  list: (params?: { type?: string; status?: string }) =>
    apiClient.get('/api/processing/tasks', { params }),
  get: (taskId: string) =>
    apiClient.get(`/api/processing/tasks/${taskId}`),
  submitClahe: (data: { name: string; input_paths: string[]; params: any }) =>
    apiClient.post('/api/processing/clahe', data),
  submitCrop: (data: { name: string; input_paths: string[]; params: any }) =>
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

### 4.2 Pinia Store

**文件**：`frontend/src/stores/processing.ts`

封装任务列表加载、过滤、轮询逻辑，参考 `stores/model.ts` 模式。关键 state：`tasks / loading / error / filterType / filterStatus`，actions：`fetchTasks / applyFilters`。

### 4.3 Tasks.vue 改造

**改动范围**：
- 移除 `useMockStore` 依赖，改用 `useProcessingStore`
- 筛选栏、分组表格、状态徽章 UI 保留不变（已符合设计语言）
- 数据源从 mock 改为真实 API

### 4.4 TaskNew.vue 改造

**改动范围**：
- 4 步向导 UI 保持不变
- `submit()` 函数改造：收集 `input_paths`（架次路径列表或自定义目录）→ 调用 `processingApi.submitClahe` 或 `submitCrop` → 跳转到 `/process/tasks/:task_id`
- 移除"V1 演示模式"提示

**grid_size 字段处理**：前端表单中 `grid` 字段为字符串 `"8 × 8"`，提交前解析为 `[8, 8]`：

```typescript
function parseGrid(gridStr: string): [number, number] {
  const m = gridStr.match(/(\d+)\s*[×x]\s*(\d+)/)
  return m ? [parseInt(m[1]), parseInt(m[2])] : [8, 8]
}
```

### 4.5 TaskDetail.vue 改造

**改动范围**：
- 移除 `mockApi.fetchTask` 依赖，改用 `processingApi.get`
- 预览网格：从真实文件清单 API 加载，使用 `processingApi.previewUrl` 拼接预览 URL
- 进度轮询：处理中任务每 2 秒拉取一次状态，完成后停止
- `onUnmounted` 清理定时器
- 对比预览模式（原图 vs 结果）：原图用 `batchesApi.previewUrl`，结果用 `processingApi.previewUrl`

### 4.6 DataSubTabs.vue（新增）

**文件**：`frontend/src/components/layout/DataSubTabs.vue`

参考 `SubTabs.vue` 实现：

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

### 4.7 Batches.vue / BatchNew.vue / BatchDetail.vue 改造

在三个页面顶部插入 `<DataSubTabs />`：
- `Batches.vue` 副标题"原始飞行数据"改为"原始数据"
- 其余 UI 不变

### 4.8 Processed.vue（新增）

**文件**：`frontend/src/views/data/Processed.vue`

**布局**（参考 `Batches.vue`）：
- 顶部：标题"加工数据" + 副标题
- `<DataSubTabs />`
- 统计卡（4 列）：产物总数 / CLAHE 数 / 裁切数 / 总图片数
- 表格列：任务名 / 类型（CLAHE/裁切） / 状态 / 输出路径 / 图片数 / 子目录数 / 生成时间 / 操作（查看/删除）
- 行点击跳转 `/data/processed/:id`

### 4.9 ProcessedDetail.vue（新增）

**文件**：`frontend/src/views/data/ProcessedDetail.vue`

**布局**（参考 `BatchDetail.vue`）：
- 面包屑：加工数据 / 任务名
- 头部：任务名 + 状态标签 + 类型标签 + "查看处理任务"跳转按钮（跳 `/process/tasks/:task_id`）
- 参数卡：clip_limit/grid_size 或 tile_size/overlap_ratio + 输入源 + 总图片/总子图
- 子目录折叠面板：每个 `sub_dir` 一个面板，展开后显示图片缩略图网格（分页 50 张）
- 删除按钮（带二次确认）

### 4.10 路由更新

```typescript
// frontend/src/router/index.ts 新增
{ path: '/data/processed', name: 'processed',
  component: () => import('@/views/data/Processed.vue') },
{ path: '/data/processed/:id', name: 'processed-detail',
  component: () => import('@/views/data/ProcessedDetail.vue') },
```

总路由数从 15 条增至 17 条。

---

## 五、测试策略

### 5.1 单元测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_processing_engine.py` | `run_clahe` / `run_crop` 单图与多图处理、命名规范、子目录结构、错误隔离、`_collect_inputs` 归一化、`write_index` 输出 |
| `test_processing_registry.py` | YAML 持久化、CRUD、自扫描 output/、任务状态转换（pending→processing→completed/failed/interrupted）、task_id 与目录名映射、`list_processed` |
| `test_processing_api.py` | 8+2 个端点的状态码、响应格式、参数校验、错误降级（engine=None 时返回 503） |
| `test_processing_integration.py` | 端到端：提交任务 → 轮询状态 → 完成后校验 output 结构与 index.json |

### 5.2 测试 Fixture

`backend/tests/fixtures/sample_images/`：
- `small_640.jpg`（640×640，单块场景）
- `medium_1280.jpg`（1280×960，2×2 分块）
- `large_2000.jpg`（2000×1500，4×3 分块）

### 5.3 现有测试调整

- `test_mock_api.py`：移除 processing 相关测试（保留 datasets 部分）
- `test_task_manager.py`：增加 `task_id` 自定义参数的测试

---

## 六、迁移策略

### 6.1 步骤化迁移

| 步骤 | 动作 | 风险 | 回滚 |
|------|------|------|------|
| 1 | 新增 `processing_engine.py` / `processing_registry.py` | 无 | 删除文件 |
| 2 | `engine.py` / `config.py` 扩展 | 引擎初始化失败时降级 | 注释新增初始化 |
| 3 | `task_manager.py` 增加 `task_id` 参数 | 向后兼容 | 默认 None |
| 4 | 重写 `processing_api.py` | 前端 API 契约需对齐 | git revert |
| 5 | 新增 `frontend/src/api/processing.ts`，删除 mock 中 processing 部分 | 前端调用点需替换 | git revert |
| 6 | 改造 `Tasks.vue` / `TaskNew.vue` / `TaskDetail.vue` | UI 行为需回归 | git revert |
| 7 | 删除 `backend/mock/tasks.json` | mock 测试需先迁移 | git revert |
| 8 | 新增【加工数据】tab 与组件（最后做） | 新增路由与组件 | git revert |

### 6.2 PRD 同步更新项

设计文档定稿后，需要在 PRD v6 中更新以下条目：

| PRD 章节 | 更新内容 |
|---------|---------|
| §3.2 FR-P02 | 子图命名规范改为 `{orig_stem}_tile_{seq:04d}_x{offset_x}_y{offset_y}.jpg` |
| §3.3 接口列表 | 补充 `/api/processing/processed` 系列（加工数据） |
| §3.5 输出规范 | 补充多架次分子目录结构（按 batch_id 子目录） |
| §1.7 实现状态总览 | 模块二状态从 🔶 改为 ✅，新增【加工数据】子模块说明 |
| §1.8 全局导航 | 数据管理下新增【加工数据】子栏目说明 |

---

## 七、验收检查清单

### 7.1 后端验收

1. **任务持久化**：提交任务后重启后端，任务列表仍可见；processing 状态的任务被标记为 interrupted
2. **CLAHE 增强**：`POST /api/processing/clahe` 提交多架次任务，生成 `output/{task_id}/{sub_dir}/*.jpg` 与 `index.json`
3. **滑窗裁切**：`POST /api/processing/crop` 提交任务，生成 `{orig_stem}_tile_{seq:04d}_x{ox}_y{oy}.jpg` 命名规范的子图
4. **任务列表**：`GET /api/processing/tasks` 支持 `?type=` & `?status=` 过滤
5. **任务详情**：`GET /api/processing/tasks/:id` 返回完整任务记录
6. **结果预览**：`GET /api/processing/tasks/:id/preview?filename=&sub_dir=&size=thumbnail/medium/original` 返回 JPEG 流
7. **结果文件清单**：`GET /api/processing/tasks/:id/files` 分页返回图片列表
8. **加工数据列表**：`GET /api/processing/processed` 返回 output/ 下所有处理产物
9. **加工数据详情**：`GET /api/processing/processed/:id` 返回详情
10. **加工数据文件**：`GET /api/processing/processed/:id/files` 分页返回文件
11. **删除加工数据**：`DELETE /api/processing/processed/:id?delete_output=true` 删除记录与文件
12. **引擎降级**：`cv2` 缺失时 `processing_engine=None`，API 返回 503

### 7.2 前端验收

13. **任务列表页**：`/process/tasks` 显示真实任务列表，支持类型/状态筛选
14. **新建任务**：`/process/task-new` 4 步向导提交成功后跳转任务详情
15. **任务详情**：`/process/tasks/:id` 显示进度条、参数卡、预览网格；处理中任务自动轮询
16. **数据管理 tab**：`/data/batches` 顶部显示【原始数据 / 加工数据】双 tab
17. **加工数据列表**：`/data/processed` 显示所有 output/ 下的处理产物
18. **加工数据详情**：`/data/processed/:id` 显示参数卡 + 子目录折叠面板 + 图片网格

### 7.3 端到端验收

19. **完整流程**：登记架次 → 提交 CLAHE 任务 → 完成 → 提交裁切任务（输入选 CLAHE 输出目录） → 完成 → 在【加工数据】中查看两个产物 → 删除一个加工数据 → 确认 output 目录已清理

---

## 八、附录

### 8.1 task_id 与目录名映射规则

- task_id 格式：`{task_type}_{ts}_{ms:03d}`，如 `clahe_20260812_153000_456`
- output 目录名：与 task_id 完全相同，如 `clahe_20260812_153000_456`
- 反查：目录名即 task_id，无需解析
- 正向：`task_id = f"{task_type}_{ts}_{ms:03d}"`；`output_path = f"output/{task_id}"`
- 同秒创建冲突避免：ms 后缀（001-999）确保唯一性，若同毫秒仍有冲突则自增直到唯一

### 8.2 index.json 结构示例

```json
{
  "task_id": "clahe_20260812_153000_456",
  "task_type": "clahe",
  "params": {
    "clip_limit": 2.0,
    "grid_size": [8, 8]
  },
  "input_paths": ["data/sugarcane_5m", "data/sugarcane_8m"],
  "created_at": "2026-08-12T15:30:00",
  "total_images": 160,
  "processed_images": 160,
  "sub_dirs": [
    {"sub_dir": "sugarcane_5m", "image_count": 80},
    {"sub_dir": "sugarcane_8m", "image_count": 80}
  ]
}
```

裁切任务额外字段：

```json
{
  "task_type": "crop",
  "params": {"tile_size": 640, "overlap_ratio": 0.05},
  "total_tiles": 420,
  "sub_dirs": [
    {"sub_dir": "sugarcane_5m", "image_count": 80, "tiles_count": 210}
  ]
}
```

### 8.3 关键依赖

- 复用模块：`core/clahe.py::enhance`、`core/tiling.py::slide_window`
- 复用模式：`core/batch_registry.py`（YAML 持久化）、`core/task_manager.py`（异步队列）、`core/engine.py`（单例容器）
- 新增依赖：无（仅使用 cv2、numpy、Pillow、PyYAML 等项目已用依赖）
