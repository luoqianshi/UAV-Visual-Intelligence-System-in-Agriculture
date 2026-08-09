# 作物计数工作台交互与渲染问题修复计划

## 问题分析总结

### 问题1：点击选择图片窗口未弹出

**根本原因**：
- [Counting.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue#L292-L298) 的 dropzone 区域只有视觉样式，**没有绑定 `@click` 事件**，也没有隐藏的 `<input type="file">` 元素
- 对比 [Detect.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Detect.vue#L184-L195) 正确实现了：
  - `@click="fileInput?.click()"` 触发文件选择
  - 隐藏的 `<input type="file" ref="fileInput">` 元素
  - `onFileChange` 事件处理函数
- 后端 [counting_api.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/api/counting_api.py) 目前**只支持 `image_path`（本机路径）模式**，不支持 multipart 文件上传

### 问题2：检测结果图无法渲染

**根本原因**：
- [result_store.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/result_store.py#L41) 保存结果时，**`annotated_image` 字段被显式排除**：
  ```python
  counting_data = {k: v for k, v in result.items() if k != "annotated_image"}
  ```
- [result_store.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/result_store.py#L73-L78) `load_counting_result()` 只读取 `counting_data.json`，没有把 `result_image.jpg` 重新编码为 base64 加回结果中
- 前端 [Counting.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue#L539-L544) 中 `v-if="countingStore.result.annotated_image"` 条件为 falsy，导致图片不渲染

---

## 修复方案

### 修复范围

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/core/result_store.py` | Bug修复 | `load_counting_result()` 重新读取图片并编码回base64 |
| `backend/api/counting_api.py` | 功能增强 | 增加 multipart 文件上传支持（类似 detect_api.py） |
| `frontend/src/api/counting.ts` | 功能增强 | 增加文件上传API方法 |
| `frontend/src/stores/counting.ts` | 功能增强 | 支持文件上传提交 |
| `frontend/src/views/algo/Counting.vue` | Bug修复+功能 | 1) 添加文件选择点击事件 2) 支持文件上传预览 3) 复用DetectionViewer组件 |

---

## 详细修改步骤

### 步骤1：修复后端结果加载 - 补全 annotated_image 字段

**文件**：[backend/core/result_store.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/core/result_store.py)

修改 `load_counting_result()` 函数：
- 读取 `counting_data.json` 后
- 检查同目录下 `result_image.jpg` 是否存在
- 如果存在，读取并 base64 编码，赋值给 `annotated_image` 字段

```python
def load_counting_result(result_id: str) -> dict:
    """加载指定结果的完整计数数据。"""
    data_file = RESULTS_DIR / result_id / "counting_data.json"
    if not data_file.exists():
        raise FileNotFoundError(f"结果不存在: {result_id}")
    data = json.loads(data_file.read_text(encoding="utf-8"))
    # 补全 annotated_image：从 result_image.jpg 重新编码
    img_file = RESULTS_DIR / result_id / "result_image.jpg"
    if img_file.exists():
        data["annotated_image"] = base64.b64encode(
            img_file.read_bytes()
        ).decode("utf-8")
    return data
```

---

### 步骤2：后端 counting_api.py 增加文件上传支持

**文件**：[backend/api/counting_api.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/api/counting_api.py)

参考 [detect_api.py](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/backend/api/detect_api.py#L69-L103) 的实现，在 `/api/counting` POST 路由中增加 multipart 文件上传分支：

1. 检测 `request.files` 中是否有 `image` 文件
2. 保存到临时文件
3. 使用临时文件路径作为 `image_path` 调用计数
4. 清理临时文件
5. 保持原有的 JSON `image_path`/`image_dir` 逻辑不变

---

### 步骤3：前端 API 层增加文件上传方法

**文件**：[frontend/src/api/counting.ts](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/api/counting.ts)

增加文件上传方法，使用 FormData：

```typescript
export const countingApi = {
  submit: (payload: ...) => client.post(...),
  // 新增：文件上传
  submitWithFile: (file: File, model_name?: string, params?: CountingParams) => {
    const formData = new FormData()
    formData.append('image', file)
    if (model_name) formData.append('model_name', model_name)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) formData.append(k, String(v))
      })
    }
    return client.post<unknown, { data: { task_id: string } }>('/counting', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getTask: ...,
  getResult: ...,
  history: ...,
}
```

---

### 步骤4：Counting Store 支持文件上传

**文件**：[frontend/src/stores/counting.ts](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/stores/counting.ts)

修改 `submit` 方法，支持接收 File 对象：
- 如果传入 `file` 参数，调用 `submitWithFile`
- 否则调用原有的 JSON 提交

---

### 步骤5：Counting.vue 完整修复

**文件**：[frontend/src/views/algo/Counting.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue)

需要的修改：

1. **新增文件选择相关状态和方法**（参考 Detect.vue）：
   - `selectedFile` / `previewUrl` / `fileInput` ref
   - `onFileChange()` / `clearFile()` / `revokePreview()` / `formatSize()`
   - `imgDimensions` 用于显示图片尺寸

2. **dropzone 区域修复**：
   - 添加 `@click="fileInput?.click()"`
   - 添加隐藏的 `<input type="file" ref="fileInput" accept="image/*" class="hidden" @change="onFileChange">`
   - 添加拖拽支持（dragover/drop 事件）

3. **已选文件展示**：
   - 类似 Detect.vue，选中文件后显示缩略图、文件名、大小、尺寸
   - 提供清除按钮

4. **原图预览修复**：
   - 如果是文件上传模式（有 `previewUrl`），显示浏览器预览
   - 如果是本机路径模式，保持原有的"无法预览"提示
   - 复用 [DetectionViewer](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/components/algo/DetectionViewer.vue) 组件统一展示原图和结果图，而不是自己写两套图片渲染逻辑

5. **提交逻辑修改**：
   - 优先使用 `selectedFile`（文件上传）
   - 否则使用 `imagePath`（本机路径）

6. **onUnmounted 清理**：
   - 调用 `revokePreview()` 释放 object URL

---

## 验证步骤

1. **启动后端和前端**
2. **测试文件选择点击**：
   - 进入作物计数页面
   - 点击 dropzone 区域
   - 验证文件选择对话框弹出
   - 选择一张图片后验证缩略图显示
3. **测试检测结果渲染**：
   - 选择图片/输入路径后执行计数
   - 等待任务完成
   - 验证右侧检测结果图正常显示（不是占位符）
   - 验证下载结果图按钮正常工作
4. **测试历史记录查看**：
   - 点击历史记录的"查看"按钮
   - 验证历史结果的图片也能正常加载显示
5. **测试本机路径模式**（如适用）：
   - 输入有效本机路径执行计数
   - 验证原图区域显示"无法预览"但检测结果图正常显示

---

## 风险与注意事项

1. **大文件上传**：计数通常处理高分辨率图像（5000+像素），需要确保：
   - 后端临时文件正确清理
   - axios timeout 已设置为 120000ms（已满足）
   - Flask MAX_CONTENT_LENGTH 配置可能需要调整

2. **向后兼容**：保持原有的 `image_path`/`image_dir` JSON 模式不变，文件上传是新增分支，不破坏原有接口

3. **颜色空间问题**：检查 counter.py 中 cv2 读取/编码的颜色空间是否正确（当前代码 BGR→RGB 后绘制，再用 cv2.imencode 编码 JPEG，需要确认浏览器显示颜色正常）
