# Counting 逻辑诊断与偏色修复计划

## 摘要

本次任务包含两部分：

1. **诊断滑窗分块逻辑**：经代码核查，滑窗分块链路**已正确实现**（CLAHE→滑窗切块→逐块检测→坐标映射→全局NMS→统计→渲染）。用户"感觉没分块"的真实原因是：当原图两维度均 ≤ `tile_size`（默认 640）时，`tiling.slide_window` 仅返回 1 个 tile（整图），等价于未分块；且输出图不画 tile 边界，视觉上无法感知。本次将在前端结果区增加 `tile_count=1` 时的可观测性提示。
2. **修复偏蓝色图片**：根因是 `counter.py` 的 `_draw` 把 RGB 图直接交给期望 BGR 的 `cv2.imencode`，导致 R/B 通道对调（红框变蓝、整图偏冷色）。`detector.py` 的 `_draw` 存在同源 bug（BGR 图上用了 RGB 顺序的红色元组，框也是蓝色）。本次统一两条绘制链路的通道约定。

---

## 现状分析

### 问题 1：滑窗分块逻辑是否真的执行？

**结论：逻辑已正确实现，完整链路如下（[counter.py:21-80](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/counter.py#L21-L80)）：**

| 步骤 | 代码位置 | 说明 |
|------|----------|------|
| ① 加载原图 | `counter.py:30-34` | 路径→`cv2.imread`→`cvtColor(BGR2RGB)`，得 RGB 图 |
| ② CLAHE | `counter.py:40` → [clahe.py:5-11](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/clahe.py#L5-L11) | RGB→LAB→L 通道 CLAHE→RGB |
| ③ 滑窗切块 | `counter.py:43` → [tiling.py:4-19](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/tiling.py#L4-L19) | 步长=`tile_size×(1-overlap_ratio)`，重叠切窗，边缘回退 |
| ④ 逐块检测+映射 | `counter.py:48-54` | 每个 tile 独立 `detector.detect(draw=False)`，bbox 经 `tiling.map_to_original` 加偏移回原图坐标 |
| ⑤ 全局 NMS | `counter.py:57` → `nms.global_nms` | 跨 tile 去重合并 |
| ⑥ 统计 | `counter.py:62-64` | 计数/面积/密度 |
| ⑦ 渲染 | `counter.py:67` → `_draw` | 在原图上画框+编号 |
| 返回 | `counter.py:68-80` | 含 `tile_count: len(tiles)` |

**用户"感觉没分块"的真实原因（[tiling.py:7-13](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/tiling.py#L7-L13)）：**

```python
def calc_starts(length):
    if length <= tile_size:
        return [0]   # ← 维度 ≤ tile_size 时只返回 1 个起点
    starts = list(range(0, length - tile_size + 1, step))
    ...
```

- 当原图**任一维度 ≤ 640** 时，该维度只产生 1 个 tile；若**两维度均 ≤ 640**，则 `tile_count=1`，整图作为单块送检，等价于未分块。
- 输出标注图不绘制 tile 边界，用户视觉上无法感知分块是否发生。
- `tile_count` 已在结果头展示（[Counting.vue:638](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue#L638)），但缺乏对 `tile_count=1` 的语义解释，用户不易据此判断。

### 问题 2：为什么输出图偏蓝？

**根因：`cv2.imencode` 通道顺序不匹配（[counter.py:105-121](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/counter.py#L105-L121)）。**

颜色流转追踪：

1. `counter.py:31-32`：`cv2.imread`（BGR）→ `cvtColor(BGR2RGB)` → `original` 为 **RGB**
2. `counter.py:40`：CLAHE 按 RGB→LAB→RGB 处理，`enhanced` 仍为 **RGB**
3. `counter.py:67`：`_draw(original, ...)` 传入 **RGB** 图
4. `counter.py:107`：`img = image.copy()` → **RGB**
5. `counter.py:110`：`cv2.rectangle(img, ..., (229, 57, 53), 2)` → 元组写入 RGB 数组，R=229,G=57,B=53 = **红**（在 RGB 数组里是对的）
6. `counter.py:120`：`cv2.imencode(".jpg", img)` ← **BUG**：`imencode` 期望 **BGR**，但 `img` 是 **RGB**

**后果**：`imencode` 把 R/B 通道对调编码：
- 红色检测框 `(229,57,53)` → 编码后变 **蓝色**
- 图像内容红↔蓝对调：偏红的土壤/植被变蓝调，整图偏冷色（即用户感知的"偏蓝"）

**同源 bug（[detector.py:119-135](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/detector.py#L119-L135)）：**

检测流程中 `detector.detect` 始终以**文件路径**调用（[detect_api.py:80-82](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/api/detect_api.py#L80-L82) 单图、[detect_api.py:130-132](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/api/detect_api.py#L130-L132) 批量），故 `_draw` 中 `cv2.imread` 得到的是 **BGR** 图。

- `detector.py:121`：`img = cv2.imread(image)` → **BGR**（图色正确）
- `detector.py:124`：`cv2.rectangle(img, ..., (229, 57, 53), 2)` → 元组写入 BGR 数组，B=229,G=57,R=53 = **蓝**（BUG：本意红色）
- `detector.py:134`：`imencode` 得 BGR，编码正确，但**框是蓝色**

即：检测页图色正常但框为蓝色；计数页图色与框全偏蓝。两处都需修。

> 注：计数流程 `counter.py:51` 调用 `detector.detect(tile, ..., draw=False)`，`draw=False` 不触发 `_draw`，故计数偏蓝只由 `counter.py:_draw` 负责。

---

## 变更方案

### 变更 1：修复 `counter.py` 偏色（核心）

**文件**：[backend/core/counter.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/counter.py)

**改动**：`_draw` 方法，统一到 BGR 再绘制与编码。`image` 入参为 RGB，先 `cvtColor(RGB2BGR)`，颜色元组改用 BGR 顺序的红色 `(53, 57, 229)`。

**当前代码（L105-L121）**：
```python
def _draw(self, image, dets):
    """在原图上绘制检测框与编号，返回 base64 JPEG 字符串。"""
    img = image.copy()
    for d in dets:
        x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (229, 57, 53), 2)
        cv2.putText(
            img,
            str(d["id"]),
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (229, 57, 53),
            1,
        )
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
```

**改为**：
```python
def _draw(self, image, dets):
    """在原图上绘制检测框与编号，返回 base64 JPEG 字符串。

    image 为 RGB 顺序（count() 中已 BGR→RGB）；cv2 绘制与 imencode 均以
    BGR 为准，故先转 BGR，颜色元组按 BGR 顺序书写，否则 R/B 对调致偏蓝。
    """
    img = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)  # RGB → BGR
    for d in dets:
        x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (53, 57, 229), 2)  # BGR: 红
        cv2.putText(
            img,
            str(d["id"]),
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (53, 57, 229),  # BGR: 红
            1,
        )
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
```

**为什么 `(53, 57, 229)`**：BGR 元组 (B=53, G=57, R=229) 即红色。原 `(229,57,53)` 在 BGR 下是 (B=229,G=57,R=53) 即蓝色，正是 bug 来源。

### 变更 2：修复 `detector.py` 同源偏色

**文件**：[backend/core/detector.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/detector.py)

**改动**：`_draw` 方法，统一"先到 BGR 再绘制+编码"。路径入参 `cv2.imread` 已是 BGR；数组入参（计数流程传 RGB tile，虽然当前 `draw=False` 不触发，但为健壮性保留）按 RGB 处理并转 BGR。颜色元组统一用 BGR 红 `(53, 57, 229)`。

**当前代码（L119-L135）**：
```python
def _draw(self, image, detections):
    """在图像上绘制检测框与置信度，返回 base64 JPEG 字符串。"""
    img = cv2.imread(image) if isinstance(image, str) else image.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (229, 57, 53), 2)
        cv2.putText(
            img,
            f'{det["confidence"]:.2f}',
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (229, 57, 53),
            1,
        )
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
```

**改为**：
```python
def _draw(self, image, detections):
    """在图像上绘制检测框与置信度，返回 base64 JPEG 字符串。

    image 可为文件路径（cv2.imread 得 BGR）或 RGB 数组；统一到 BGR 后再
    绘制与编码，颜色元组按 BGR 顺序书写，避免 R/B 对调致框色偏蓝。
    """
    if isinstance(image, str):
        img = cv2.imread(image)  # BGR
    elif image.ndim == 3:
        img = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)  # RGB → BGR
    else:
        img = image.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (53, 57, 229), 2)  # BGR: 红
        cv2.putText(
            img,
            f'{det["confidence"]:.2f}',
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (53, 57, 229),  # BGR: 红
            1,
        )
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf).decode("utf-8")
```

### 变更 3：前端增加 `tile_count=1` 校验提示

**文件**：[frontend/src/views/algo/Counting.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue)

**改动**：在"检测结果图"卡片头部下方（`</div>` 头部闭合与 `<DetectionViewer>` 之间，即当前 L642 与 L643 之间）插入条件提示条。当 `tile_count === 1` 时显示琥珀色提示，解释为何未触发分块。使用 `params_snapshot.tile_size`（后端实际使用的值，见 `counter.py:77`）保证历史回看也准确。

**插入位置**：L642 `</div>`（头部容器闭合）之后、L643 `<DetectionViewer` 之前。

**插入内容**：
```html
<!-- 分块未触发提示：tile_count=1 时说明原图未超过 tile_size -->
<div
  v-if="countingStore.result && countingStore.result.tile_count === 1"
  class="mb-4 px-3 py-2 bg-amber-50 border border-amber-200 rounded-btn text-xs text-amber-700 flex items-start gap-2"
>
  <i class="fa-solid fa-circle-info mt-0.5 flex-shrink-0"></i>
  <div>
    本次仅生成 1 个分块：原图尺寸（{{ countingStore.result.image_size?.[0] }}×{{ countingStore.result.image_size?.[1] }}）
    未超过 tile_size（{{ countingStore.result.params_snapshot?.tile_size ?? 640 }}），整图作为单块送检，未触发滑窗分块。
    如需分块检测，请上传更大尺寸图片或调小 tile_size。
  </div>
</div>
```

**样式依据**：复用页面既有琥珀色系（参见 [Counting.vue:606](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue#L606) `bg-amber-50 text-amber-600`）与 Font Awesome 图标，无需新增依赖。

---

## 假设与决策

1. **通道约定决策**：两条绘制链路（counter / detector）统一采用"先转 BGR、BGR 元组绘制、`imencode` 直接编码"的约定，与 cv2 原生 BGR 习惯一致，避免后续维护混淆。
2. **颜色元组可读性**：BGR 红 `(53, 57, 229)` 不如 RGB 直观，故在元组后加 `# BGR: 红` 注释说明。
3. **detector.py 数组分支保留**：虽然当前计数流程 `draw=False` 不触发 `_draw` 的数组分支，但保留 RGB→BGR 转换以保证未来 `draw=True` 调用数组时正确，零额外成本。
4. **tile_count 提示阈值**：仅 `tile_count === 1` 时提示；`tile_count > 1` 时不打扰用户。不画 tile 边界（避免污染标注图）。
5. **不动 tiling.py 逻辑**：滑窗实现本身正确，`length <= tile_size` 返回单 tile 是合理行为，非 bug。
6. **不动 CLAHE**：`clahe.py` 的 RGB→LAB→RGB 处理正确，偏色根因在编码端而非 CLAHE。

---

## 验证步骤

### 后端验证（counter.py 偏色修复）

1. 启动后端（uav-vis 环境，含 cv2）。
2. 在计数页上传一张含红色/暖色调的场景图，执行检测与计数。
3. 确认返回的 `annotated_image`：
   - 检测框为**红色**（非蓝色）
   - 图像内容颜色自然（土壤不偏蓝、植被绿色正常）
4. 检查 `tile_count`：若图 > 640 两维度，应 > 1；若 ≤ 640，应为 1 且前端出现琥珀色提示。

### 后端验证（detector.py 偏色修复）

1. 在检测页（非计数页）上传同一张图执行单图检测。
2. 确认 `result_image` 中检测框为**红色**（非蓝色），图色正常。

### 前端验证（tile_count 提示）

1. 上传一张 ≤ 640×640 的小图 → 结果区头部下方应出现琥珀色提示条，文案含图片尺寸与 tile_size。
2. 上传一张 > 640 的大图（如 2000×1500）→ 不出现提示条，`分块数` 显示 > 1。
3. 查看历史记录中的小图结果 → 提示条仍能正确显示（依赖 `params_snapshot.tile_size`，不依赖当前输入框值）。

### 回归检查

- 计数流程 `count()` 返回字段不变（`tile_count` / `annotated_image` / `params_snapshot` 等结构与原一致），前端 store 与 API 无需改动。
- `detector.detect` 返回结构不变，`detect_api.py` 无需改动。
