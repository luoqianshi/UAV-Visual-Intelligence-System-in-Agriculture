# 算法管理模块优化与模型持久化实施计划

## 一、仓库调研结论

### 当前架构
- **前端**：Vue 3 + TypeScript + Vite + Pinia，使用Gradio风格极简设计
- **后端**：Flask框架，模型注册中心在 `backend/core/registry.py`
- **模型配置**：`config/models.yaml` 存储静态模型配置，当前4个模型均为甘蔗幼苗检测
- **权重目录**：`models/` 目录（当前为空）
- **现有问题**：
  1. `half (FP16)` 字段在后端实际未使用，仅前端展示
  2. 模型注册仅写入内存，不持久化到YAML
  3. 注册表单无文件上传功能，weight字段为文本输入路径
  4. 模型列表表格使用文字徽标（Y5s/Y8s/YOL等），而非统一的SVG图标
  5. 注册表单占位符命名风格不统一（v4后缀等）

### 涉及文件清单

**前端文件（需修改）：**
1. `frontend/src/api/models.ts` - ModelConfig接口移除half字段，新增文件上传API
2. `frontend/src/stores/model.ts` - registerModel支持FormData文件上传
3. `frontend/src/views/algo/Models.vue` - 表格首列图标改为fi-seedling.svg
4. `frontend/src/views/algo/ModelRegister.vue` - 移除half字段、新增文件上传、更新占位符
5. `frontend/src/views/algo/ModelDetail.vue` - 移除half相关展示
6. `frontend/src/views/algo/Detect.vue` - 移除FP16推理参数

**后端文件（需修改）：**
1. `backend/core/registry.py` - 新增save_to_yaml方法，register时持久化
2. `backend/api/models_api.py` - 新增文件上传支持，multipart/form-data处理
3. `backend/config.py` - 确保MODELS_DIR目录存在
4. `config/models.yaml` - 移除所有模型的half字段

**新增文件：**
1. `frontend/assets/fi-algo.svg`（可选） - 算法风格SVG图标（或直接复用fi-seedling.svg）

---

## 二、实施步骤

### 任务1：移除所有 FP16 (half) 相关内容

#### 1.1 后端：从models.yaml中移除half字段
- 文件：`config/models.yaml`
- 操作：删除4个模型配置中的 `half: false` 行

#### 1.2 前端：API类型定义移除half
- 文件：`frontend/src/api/models.ts`
- 操作：从 `ModelConfig` 接口中删除 `half: boolean` 字段
- 操作：移除modelsApi.load相关的half传递

#### 1.3 前端：Store移除half
- 文件：`frontend/src/stores/model.ts`
- 操作：registerModel方法不再传递half参数

#### 1.4 前端：模型详情页移除half展示
- 文件：`frontend/src/views/algo/ModelDetail.vue`
- 操作1：删除推理参数卡片中的"FP16 (half)"展示项（L157-L160）
- 操作2：删除模型信息卡片中的"device / half"行（L232-L235），改为只显示device
- 操作3：页头图标区域同时需要更新（见任务4）

#### 1.5 前端：模型注册页移除half字段
- 文件：`frontend/src/views/algo/ModelRegister.vue`
- 操作1：删除form中的 `half: false` 字段（L25）
- 操作2：删除summary中的 `deviceHalf` 计算属性（L49），改为只显示device
- 操作3：删除推理参数表单中的half (FP16)复选框（L231-L241）
- 操作4：删除注册摘要中的"device / half"行（L263-L266），改为只显示device
- 操作5：删除右侧提示文字中关于不持久化的说明（待任务2更新）
- 操作6：onSubmit中不再传递half参数（L74）

#### 1.6 前端：作物检测页移除FP16参数
- 文件：`frontend/src/views/algo/Detect.vue`
- 操作1：删除 `const half = ref<'false' | 'true'>('false')` 变量定义（L83）
- 操作2：删除推理参数中的FP16下拉选择（L301-L312），device改为独占整行
- 操作3：onDetect调用中移除half参数传递（L97）

---

### 任务2：模型注册持久化到YAML + 权重文件上传

#### 2.1 后端：Registry新增YAML持久化方法
- 文件：`backend/core/registry.py`
- 操作1：在 `__init__` 中确保加载时配置完整默认值
- 操作2：新增 `save_to_yaml()` 方法：
  - 读取现有YAML结构
  - 更新models列表（按name去重更新/追加）
  - 保持default_model不变（除非是第一个模型）
  - 写回 `self._yaml_path`
- 操作3：修改 `register()` 方法：
  - 接收config后调用 `save_to_yaml()` 持久化
  - 确保weight路径相对于项目根目录

#### 2.2 后端：config.py确保models目录存在
- 文件：`backend/config.py`
- 操作：添加 `MODELS_DIR.mkdir(parents=True, exist_ok=True)` （类似RESULTS_DIR）

#### 2.3 后端：models_api支持文件上传
- 文件：`backend/api/models_api.py`
- 操作1：修改 `load_model()` 路由支持 `multipart/form-data`
- 操作2：接收上传的权重文件（字段名：weight_file）
- 操作3：根据name字段自动生成文件名：`{name}.pt`（将name中的"-"替换为"_"以匹配现有风格，如yolo12s-sugarcane → yolo12s_sugarcane.pt）
- 操作4：保存文件到 `MODELS_DIR / 生成的文件名`
- 操作5：自动设置weight字段为 `models/{生成的文件名}`
- 操作6：其余字段从form中解析（name, display_name, engine, category, classes需split为数组, imgsz, conf, iou, max_det, device）
- 操作7：文件上传大小限制（通过Flask MAX_CONTENT_LENGTH配置，设为500MB）

#### 2.4 后端：app.py配置文件上传
- 文件：`backend/app.py`
- 操作：在create_app中设置 `app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024`

#### 2.5 前端：API客户端支持FormData上传
- 文件：`frontend/src/api/models.ts`
- 操作1：修改modelsApi.load方法，接收FormData而非JSON
- 操作2：确保client.ts正确发送multipart/form-data（不设置Content-Type，让浏览器自动设置boundary）

#### 2.6 前端：model store适配
- 文件：`frontend/src/stores/model.ts`
- 操作：registerModel方法支持接收包含File的对象，构建FormData发送

#### 2.7 前端：模型注册页改造
- 文件：`frontend/src/views/algo/ModelRegister.vue`
- 操作1：将weight文本输入改为文件上传组件
  - 支持拖拽上传
  - 显示文件名和大小
  - 限制扩展名：.pt
  - 必填校验
- 操作2：自动根据name生成weight路径（展示用，实际后端生成）
- 操作3：更新页面标题和描述，移除"不持久化到YAML"的说明，改为"注册后模型配置将写入config/models.yaml，权重文件保存到models目录"
- 操作4：更新右侧摘要卡片提示文字
- 操作5：更新提交逻辑：
  - 选择文件后，构建FormData
  - 将classes字符串转为数组（前端处理或后端处理均可，建议后端处理form中的classes字符串）
  - 提交时显示上传进度或加载状态

---

### 任务3：更新注册表单占位词命名风格

- 文件：`frontend/src/views/algo/ModelRegister.vue`
- 操作1：name字段placeholder从 `yolov8s-sugarcane-v4` 改为 `yolo12s-sugarcane`
- 操作2：display_name字段placeholder从 `YOLOv8s 甘蔗幼苗 v4` 改为 `YOLOv12s 甘蔗幼苗`
- 操作3：weight字段（改为文件上传后不再需要placeholder，但提示文字需更新）
- 操作4：更新提示文字，说明命名规范：`{model_version}-{category}` 格式，如 `yolo12s-sugarcane`
- 操作5：移除表单中weight的文本输入，完全替换为文件上传区域

---

### 任务4：更新模型列表/详情页的图标

#### 4.1 创建算法图标（或直接复用fi-seedling.svg）
- 决策：直接使用已有的 `fi-seedling.svg`（因为所有模型都是甘蔗幼苗检测，该图标语义匹配）
- 如需统一算法图标风格，可复制fi-seedling.svg为fi-algo.svg，调整颜色为品牌绿色一致
- 选择：直接在组件中引用fi-seedling.svg

#### 4.2 前端：模型列表表格首列图标替换
- 文件：`frontend/src/views/algo/Models.vue`
- 操作1：删除badgeLabel函数（L16-L20）
- 操作2：将原来的文字徽标div（L100-L105）替换为img标签显示SVG图标
- 操作3：图标尺寸w-7 h-7，激活状态用brand-700绿色滤镜或背景色，非激活状态用灰度
- 实现方式：使用内联SVG或img标签引用assets
  - 方案：将SVG作为组件导入，或使用img src引用（需配置vite-svg-loader或直接作为静态资源引用）
  - 更简单的方案：直接写内联SVG，与fi-seedling.svg内容一致，通过CSS class控制颜色

#### 4.3 前端：模型详情页图标替换
- 文件：`frontend/src/views/algo/ModelDetail.vue`
- 操作1：删除badgeLabel函数（L26-L30）
- 操作2：将页头的文字徽标（L55-L60）替换为与列表页一致的SVG图标
- 操作3：图标尺寸w-10 h-10

#### 4.4 SVG颜色处理
- fi-seedling.svg当前stroke为#2E7D32，需要：
  - 激活状态：使用品牌绿色 #10B981 或保持 #2E7D32（与用户偏好Emerald green #10B981协调）
  - 非激活状态：使用text-ink-tertiary颜色 #9CA3AF
- 实现：使用CSS filter或直接在模板中写内联SVG，通过currentColor控制stroke颜色

---

## 三、技术实现细节

### 文件上传前后端交互流程
1. 用户在注册表单选择.pt权重文件
2. 用户填写name（如yolo12s-sugarcane-demo）
3. 前端构建FormData：
   - 所有文本字段作为form field
   - 权重文件作为weight_file field
   - classes作为逗号分隔字符串
4. 后端POST /api/models/load接收：
   - 验证name唯一性
   - 生成安全文件名：`{name.replace('-', '_')}.pt`（匹配现有命名风格yolov5su_sugarcane.pt）
   - 保存到 `models/` 目录
   - 设置weight = `models/{filename}`
   - 合并到配置并持久化到YAML
   - 注册到内存registry
   - 返回最新模型列表

### YAML持久化逻辑
- 读取现有YAML配置
- 检查name是否已存在：存在则更新，不存在则追加到models列表
- 如果是第一个注册的模型且default_model未设置，设为default_model
- 使用yaml.dump写回，保留原有格式顺序（尽量）
- 注意：现有YAML中字段顺序为：name, engine, weight, display_name, category, imgsz, conf, iou, device, classes, max_det，新注册模型保持相同顺序

### SVG图标组件化
为了方便控制颜色，在Vue模板中直接使用内联SVG：
```vue
<div class="w-7 h-7 flex items-center justify-center">
  <svg class="w-5 h-5" :class="m.is_active ? 'text-brand-700' : 'text-ink-tertiary'" ...>
    <!-- 使用currentColor作为stroke -->
  </svg>
</div>
```
需要修改fi-seedling.svg中的stroke="#2E7D32"为stroke="currentColor"以便CSS控制。

---

## 四、风险与注意事项

1. **文件覆盖风险**：如果上传同名模型（name重复），权重文件会被覆盖。需要在后端做name唯一性校验，或提示确认覆盖。
   - 处理方案：注册时检查name是否已存在，若存在返回错误提示"模型名称已存在"

2. **YAML格式一致性**：写回YAML时需确保字段顺序与原有一致，避免git diff混乱
   - 处理方案：使用OrderedDict或按固定顺序构造dict

3. **大文件上传**：.pt权重文件通常较大（几十MB），需要确保：
   - Flask MAX_CONTENT_LENGTH足够大
   - 前端显示上传中状态
   - 后端使用流式保存（Flask默认已是流式）

4. **路径安全**：防止路径遍历攻击，文件名只保留安全字符（字母、数字、下划线、连字符）
   - 处理方案：后端对name进行正则校验 `^[a-zA-Z0-9_-]+$`

5. **前端SVG加载**：Vite中导入SVG作为组件需要配置，但直接内联SVG最可靠
   - 处理方案：在模板中直接内联SVG代码，使用currentColor

6. **现有models目录为空**：当前config/models.yaml中配置的4个模型权重文件实际不存在（models目录为空），这是历史遗留问题，不在本次修改范围内，不影响注册新模型功能。

---

## 五、验证清单

实施完成后需验证：
1. ✅ 所有页面（模型列表、详情、注册、作物检测）不再出现"FP16"、"half"字样
2. ✅ 注册新模型时可以上传.pt文件
3. ✅ 上传后文件保存到models目录，文件名按name自动转换（如demo-model → demo_model.pt）
4. ✅ 注册成功后config/models.yaml中新增了该模型配置
5. ✅ 刷新页面后新注册的模型仍然存在（持久化生效）
6. ✅ 注册表单占位符为yolo12s-sugarcane风格
7. ✅ 模型列表表格和详情页显示幼苗SVG图标，激活状态为绿色，非激活为灰色
8. ✅ 作物检测页面推理参数不再有FP16选项
9. ✅ 模型详情页不再显示FP16(half)字段
