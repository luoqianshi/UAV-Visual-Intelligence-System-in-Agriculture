# 低空智瞰 · 基于无人机图像的大田农作物智能监测与管理系统

基于无人机（UAV）图像的大田农作物智能监测平台，覆盖 **数据管理 → 数据处理 → 数据集管理 → 算法广场** 四模块闭环。V1 阶段以**算法广场**（模型注册/热切换/单图检测/作物计数）为真实实现主线，数据管理/处理/数据集三模块以 mock 端点填充界面。

## 目录结构

```
project_root/
├── backend/                    # Flask 后端
│   ├── app.py                  # 应用入口（注册 Blueprint、托管静态资源、SPA 兜底）
│   ├── config.py               # 路径/端口/并发配置
│   ├── api/                    # 路由 Blueprint
│   │   ├── health_api.py       # GET /api/health（真实）
│   │   ├── models_api.py       # /api/models, /switch, /load（真实）
│   │   ├── detect_api.py       # /api/detect 单图同步+批量异步（真实）
│   │   ├── counting_api.py     # /api/counting 异步+轮询+历史（真实）
│   │   ├── batches_api.py      # /api/batches/*（V1 mock）
│   │   ├── processing_api.py   # /api/processing/*（V1 mock）
│   │   └── datasets_api.py     # /api/datasets/*（V1 mock）
│   ├── core/                   # 核心引擎
│   │   ├── registry.py         # 模型注册中心（YAML+LRU+热切换+动态注册）
│   │   ├── detector.py         # 检测引擎（原子化单图 YOLO 推理）
│   │   ├── counter.py          # 计数引擎（CLAHE→分块→检测→NMS→计数编排）
│   │   ├── clahe.py / tiling.py / nms.py   # 共享工具
│   │   ├── task_manager.py     # 异步任务管理（ThreadPoolExecutor, 并发=1）
│   │   ├── engine.py           # 引擎单例容器
│   │   └── result_store.py     # 计数结果持久化
│   ├── mock/                   # mock 数据 JSON（batches/tasks/datasets）
│   ├── tests/                  # 核心引擎 + API TDD 测试（72 项）
│   └── static/                 # Vue 构建产物（gitignore，由前端构建生成）
├── frontend/                   # Vue 3 前端
│   ├── vite.config.ts          # Vite + /api 代理 + build→backend/static
│   ├── tailwind.config.js      # V0.4 色板（brand/ink/surface）
│   └── src/
│       ├── router/             # 15 条路由
│       ├── api/                # axios 模块（models/detect/counting/mock）
│       ├── stores/             # Pinia（model/detect/counting/mock）
│       ├── components/layout/  # AppLayout / Sidebar / SubTabs
│       ├── components/algo/    # DetectionViewer / HeatmapChart / ConfidenceDistChart
│       └── views/              # index / algo / data / process / dataset
├── config/models.yaml          # 模型注册配置（6 个甘蔗模型）
├── models/                     # YOLO 权重放置目录（需手动放入）
├── results/                    # 计数结果输出
├── requirements.txt
├── start.ps1                   # 一键启动脚本
└── README.md
```

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| NVIDIA GPU | RTX 4060 Ti 16G（推荐） | YOLO 推理加速；CPU 亦可运行 |
| PyTorch | ≥2.1.0 | `pip install torch`（含 CUDA） |
| Ultralytics | ≥8.4.60 | `pip install ultralytics` |

> **说明**：未安装 torch/ultralytics 时，系统仍可启动，模型管理/列表/mock 页面正常，但检测与计数推理不可用（API 返回降级提示）。

## 模型权重放置

将 6 个甘蔗幼苗检测权重放入 `models/` 目录，文件名需与 `config/models.yaml` 中 `weight` 字段一致：

```
models/
├── yolov5su_sugarcane.pt
├── yolov8s_sugarcane.pt
├── yolo11s_sugarcane.pt
├── yolo12s_sugarcane.pt
├── yolo12n_sugarcane.pt
└── yolo26s_sugarcane.pt
```

默认激活模型为 `yolo12s-sugarcane`，可在前端「算法广场 → 算法管理」热切换。

## 启动方式

### 方式一：一键脚本（生产部署，单端口）

```powershell
.\start.ps1
```

脚本自动：检查环境 → 安装依赖 → 构建前端（若 `backend/static` 缺失）→ 启动 Flask :5000 → 打开浏览器。

访问 **http://localhost:5000**，Flask 同时提供 API 与前端静态资源。

### 方式二：开发模式（双服务器热更新）

### 首次使用先进行环境配置

```powershell
# 首次使用请先完成后端环境配置和准备
# 此处我首先选择和我本地ultralytics相关的环境
conda create -n uav-vis python=3.8.20 -y
conda activate uav-vis
pip install -r requirements.txt
```

### 以下是开发模式日常启动程序

```powershell
# 终端 1：后端
# 运行后端（日常使用）
conda activate uav-vis
python -m backend.app          # Flask :5000

# 终端 2：前端
cd frontend
npm install
npm run build                  # 建议每次改动完之后都重新build一下~
npm run dev                    # Vite :3000，/api 代理到 :5000
```

访问 **http://localhost:3000**，前端改动热更新。

### 前端构建

```powershell
cd frontend
npm run build                  # 产物输出到 backend/static/
```

## 四模块说明

| 模块 | V1 状态 | 说明 |
|------|---------|------|
| 首页 | ✅ 真实 | 端到端流程卡片、快速入口、最近活动（数字接 mock store） |
| 数据管理 | 🔶 mock | 架次列表/详情/登记（3 架次 840 张，只读浏览） |
| 数据处理 | 🔶 mock | CLAHE/裁切任务列表/详情/新建（7 任务，只读浏览） |
| 数据集管理 | 🔶 mock | 数据集列表/详情/构建（4 数据集，只读浏览） |
| 算法广场-算法管理 | ✅ 真实 | 6 模型列表、热切换激活、动态注册、模型详情 |
| 算法广场-作物检测 | ✅ 真实 | 上传图片 → 选模型 → 同步检测 → 结果图+检测列表 |
| 算法广场-作物计数 | ✅ 真实 | 高分辨率原图 → 异步计数 → 总数/密度/热力图/置信度/标注图 |

## 核心引擎

- **DetectionEngine**：原子化单图 YOLO 推理，无状态可复用。
- **CountingEngine**：高分辨率原图编排 —— CLAHE 增强 → 滑窗分块 → 逐块检测 → 坐标映射 → 全局 NMS → 计数统计（总数/密度/面积/热力图/置信度分布）。
- **ModelRegistry**：YAML 加载 + LRU 缓存（上限 3）+ 热切换 + 动态注册。
- **TaskManager**：ThreadPoolExecutor（并发=1）+ 内存任务表，支持进度回调。

## 技术栈

- **后端**：Flask 2.2.3 · Ultralytics · PyTorch · OpenCV · Pillow · NumPy · PyYAML
- **前端**：Vue 3 · Vite · Tailwind CSS · Pinia · Vue Router · ECharts · Axios · 自定义 SVG 图标组件

## 测试

```powershell
cd backend
python -m pytest -v            # 72 项测试（核心引擎 TDD + API 接线 + mock 端点）
```

## API 概览

统一响应信封：`{ "success": bool, "data": <data>|null, "message": str }`

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + 引擎状态 |
| GET | `/api/models` | 模型列表 + 当前激活 |
| POST | `/api/models/switch` | 热切换激活模型 |
| POST | `/api/models/load` | 动态注册模型 |
| POST | `/api/detect` | 单图同步 / 批量异步检测 |
| GET | `/api/detect/tasks/{id}` | 批量检测任务进度 |
| POST | `/api/counting` | 作物计数（异步） |
| GET | `/api/counting/tasks/{id}` | 计数任务进度 |
| GET | `/api/counting/tasks/{id}/result` | 计数报告 |
| GET | `/api/counting/history` | 历史计数 |
| GET | `/api/batches` `/api/processing/tasks` `/api/datasets` | mock 端点（只读） |

## 算法默认参数

> 以下参数汇总自三个来源：**配置** `config/models.yaml`、**前端表单默认值** `frontend/src/views/algo/{Detect,Counting}.vue`、**引擎代码默认值** `backend/core/{detector,counter,clahe,tiling,nms}.py`。
> 参数生效优先级（detector/counter 内逻辑）：请求参数 > 模型配置（models.yaml）> 引擎内置默认值。
> ⚠️ 多处来源默认值**不一致**，下表已并列标注，请据此与你的算法工程统一对齐。

### 1）模型级推理参数（config/models.yaml，6 个甘蔗模型共用）

| 参数 | 值 | 说明 |
|------|-----|------|
| imgsz | 640 | 推理输入尺寸 |
| conf | 0.25 | 检测置信度阈值 |
| iou | 0.7 | NMS IoU 阈值（模型内，ultralytics 推理阶段） |
| max_det | 300 | 单张最大检测框数 |
| device | null（自动） | GPU 优先，无则 CPU |

### 2）单图检测（算法广场-单图检测，Detect.vue）

| 参数 | 前端表单默认 | models.yaml | 引擎内置默认(detector.py) | 说明 |
|------|------|------|------|------|
| conf | 0.25 | 0.25 | 0.25 | 已统一 |
| iou | 0.7 | 0.7 | 0.7 | 已统一 |
| imgsz | 640 | 640 | 640 | 一致 |
| max_det | 300 | 300 | 300 | 一致 |
| device | 空 | null | null | 自动 |

> 已移除单图检测前端的分块参数（overlap_ratio / nms_iou）与 half 字段，单图无分块逻辑，与后端 detect_api 仅解析 imgsz/conf/iou/max_det/device 保持一致。

### 3）作物计数（算法广场-作物计数，Counting.vue / counter.py）

| 参数 | 前端表单默认 | 引擎内置默认(counter.py) | 说明 |
|------|------|------|------|
| conf | 0.25 | （走 detector，见上） | 逐块检测置信度 |
| iou | 0.7 | （走 detector，见上） | 逐块检测 NMS |
| imgsz | — | 640 | 逐块检测推理尺寸 |
| tile_size | 640 | 640 | 滑窗分块边长（px） |
| overlap_ratio | 0.05 | 0.05 | 分块重叠比例，步长=tile_size×(1-overlap) |
| nms_iou | 0.5 | 0.5 | **全局 NMS**（合并分块边界重复框），nms.py 默认 0.5 |
| max_det | 300 | 300 | 已统一 |
| global_conf | 0.5 | 0.0（关闭） | 全局二次过滤阈值（合并后按置信度过滤） |
| batch_size | 16 | 8 | 批量分块推理 batch 大小 |
| enhance | true | false | 是否启用 CLAHE 预处理（单块模式自动禁用） |
| save_tiles | false | false | 是否保存分块调试数据（子块原图+标注+tiles_meta.json） |
| ground_resolution | 0.85 | 0.85 | 地面分辨率 cm/px，用于面积/密度换算 |
| grid_n | 8 | 8 | 热力图网格 n×n |

### 4）预处理 / 后处理常量（引擎代码内置，不可配置）

| 参数 | 值 | 位置 |
|------|-----|------|
| CLAHE clip_limit | 2.0 | clahe.py |
| CLAHE grid_size | (8, 8) | clahe.py |
| 全局 NMS IoU | 0.5 | nms.py（与计数 nms_iou 同源） |
| 置信度分档（high/mid/low） | ≥0.7 / ≥0.4 / 其余 | counter.py `_conf_dist` |

### 5）后端并发 / 资源常量（config.py）

| 参数 | 值 | 说明 |
|------|-----|------|
| MAX_WORKERS | 1 | TaskManager 并发=1 |
| LRU_CACHE_SIZE | 3 | 模型引擎实例缓存上限 |

### 待统一的对齐点

1. ~~**conf**~~：✅ 已按 models.yaml=0.25 统一（前端表单 + detector 内置默认均已修正）。
2. ~~**iou**~~：✅ 已按 models.yaml=0.7 统一（前端表单 + detector 内置默认均已修正）。
3. ~~**max_det**~~：✅ 计数前端已从 500 对齐为配置 300。
4. ~~**单图检测分块**~~：✅ 已从前端移除 overlap_ratio / nms_iou（单图无分块逻辑，后端也未接入）。
5. ~~**half**~~：✅ 已从前端与 models.yaml 移除 half 字段（FP16 未启用，detector.py 仅透传 imgsz/conf/iou/max_det/device）。
6. 🔶 **计数增强开关（enhance）**：前端表单默认 `true`（开启 CLAHE），引擎内置默认 `false`（关闭，训练未用 CLAHE 致分布偏移）。请与算法工程确认统一方向。
7. 🔶 **计数 batch_size**：前端默认 `16`，引擎内置默认 `8`，请统一。
8. 🔶 **计数 global_conf**：前端默认 `0.5`，引擎内置默认 `0.0`（关闭全局二次过滤），请统一。

## 后续阶段

- **V2**：数据管理真实化（架次登记/图片扫描/元数据持久化）
- **V3**：数据处理真实化（复用 clahe.py/tiling.py，异步处理任务）
- **V4**：数据集管理真实化（构建/拆分/多格式导出/统计报告）

各阶段 mock 端点逐个替换为真实 handler，前端 API 契约不变、零改动。
