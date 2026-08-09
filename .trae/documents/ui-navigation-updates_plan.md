# UI 导航更新实施计划

## 一、需求概述

完成三项 UI 更新任务：
1. 首页快速入口增加【计数工作台】卡片，引导用户进入作物计数页面
2. 算法广场页面顶部子导航栏新增【作物检测】标签（位于【算法管理】与【作物计数】之间）
3. 使用 `frontend/assets/` 中的 favicon 更新浏览器标签页图标，同时将侧边栏【田间智监】左侧的 🌾 emoji 替换为正式应用图标

---

## 二、仓库调研结论

### 技术栈
- Vue 3 + TypeScript + Vite + Tailwind CSS
- 路由：Vue Router（history 模式）
- 图标：Font Awesome 6（CDN 引入）
- 布局：AppLayout（侧边栏 + 主内容区）

### 关键文件定位
| 文件 | 作用 |
|------|------|
| `frontend/src/views/index/Index.vue` | 首页，含「快速入口」区域（2×2 网格，4 张卡片） |
| `frontend/src/components/layout/SubTabs.vue` | 算法广场子导航栏（当前仅「算法管理」「作物计数」2 个 tab） |
| `frontend/src/components/layout/Sidebar.vue` | 左侧边栏，含 logo 区域（当前用 🌾 emoji） |
| `frontend/index.html` | HTML 入口，当前未设置 favicon |
| `frontend/assets/favicon.svg` | 正式 favicon（48×48，无人机+作物设计） |
| `frontend/assets/app-icon-sm.svg` | 小号应用图标（32×32，与 favicon 同风格） |

### 现有实现分析
- **快速入口**：`grid-cols-2 gap-3` 布局，4 张卡片分别指向 `/data/batch-new`、`/process/task-new`、`/dataset/dataset-new`、`/algo/detect`
- **SubTabs**：通过 `route.path.startsWith('/algo/counting')` 判断当前激活 tab，仅区分「算法管理」和「作物计数」两类
- **侧边栏 logo**：`<span class="text-2xl">🌾</span>` 使用 emoji，无 SVG 图标
- **Detect.vue 和 Counting.vue**：均引入 `<SubTabs />`，但当前 Detect 页面的面包屑仍指向「算法管理」，子导航未正确高亮检测页面

---

## 三、修改文件与步骤

### 任务 1：首页快速入口增加【计数工作台】

**文件**：[Index.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/index/Index.vue#L225-L282)

**修改内容**：
- 在现有 4 张卡片（2×2 网格）之后，新增第 5 张卡片「计数工作台」
- 路由指向 `/algo/counting`
- 图标使用 `fa-solid fa-calculator`（与作物计数 tab 一致）
- 描述文字：「单图 / 批量作物计数」
- 保留 `grid-cols-2` 布局，第 5 张卡片自然占据第三行第一列，与截图红框位置一致

**具体改动位置**：第 268-281 行「检测工作台」卡片之后插入新卡片。

---

### 任务 2：算法广场子导航栏增加【作物检测】标签

**文件**：[SubTabs.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/components/layout/SubTabs.vue)

**修改内容**：
1. 新增路由状态判断：
   - `isModels`：`route.path.startsWith('/algo/models')`（含模型详情、模型注册）
   - `isDetect`：`route.path === '/algo/detect'`
   - `isCounting`：`route.path.startsWith('/algo/counting')`
2. 新增「作物检测」tab，顺序为：**算法管理 → 作物检测 → 作物计数**
3. 图标使用 `fa-solid fa-bolt`（与检测工作台入口一致）
4. 三个 tab 的 `active` class 分别绑定对应状态
5. 确保 Models.vue、Detect.vue、Counting.vue 三个页面中 SubTabs 的高亮正确

**文件**：[Detect.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Detect.vue#L143-L147)

**修改内容**：
- 更新面包屑导航：当前为「算法管理 > 检测工作台」，应改为「作物检测」页头独立展示（面包屑可简化或移除，因为作物检测已成为独立一级子 tab）

**文件**：[Counting.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/views/algo/Counting.vue)

**修改内容**：
- 检查页头面包屑/标题是否需要调整，确保与新导航一致（作物计数作为第三个 tab）

---

### 任务 3：更新 favicon 与应用图标

**文件**：[index.html](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/index.html)

**修改内容**：
- 在 `<head>` 中添加 favicon 链接：
  ```html
  <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg" />
  <link rel="icon" type="image/svg+xml" sizes="16x16" href="/assets/favicon-16.svg" />
  ```
- 注意：Vite 项目中 `public/` 目录是静态资源服务根目录，但当前 favicon.svg 在 `frontend/assets/` 下（源码 assets），需要：
  - **方案 A**：将 `favicon.svg` 和 `favicon-16.svg` 复制到 `frontend/public/` 目录，引用路径为 `/favicon.svg`
  - **方案 B**：直接在 index.html 中通过相对路径引用源码 assets（Vite 会处理）
  - 选择方案 A（Vite 惯例：public 目录放不需要构建处理的静态资源如 favicon）

**文件**：[Sidebar.vue](file:///d:/Data/New_Codes/Composite_Projects/UAV-Visual-Intelligence-System-in-Agriculture/frontend/src/components/layout/Sidebar.vue#L28-L29)

**修改内容**：
- 将 `<span class="text-2xl">🌾</span>` 替换为 SVG 图标
- 使用 `frontend/assets/app-icon-sm.svg`（32×32）作为侧边栏 logo
- 实现方式：在 Vue 模板中内联 SVG 或通过 `<img>` 标签引入
- 为保持与整体设计风格一致，使用 `<img>` 标签配合固定尺寸（w-8 h-8）引入 app-icon-sm.svg
- 同时检查首页 Index.vue 页头标题旁是否有 emoji（当前没有，仅 Sidebar 有）

---

## 四、潜在依赖与注意事项

1. **public 目录**：当前 `frontend/` 下可能没有 `public/` 目录（Vite 默认创建），需要确认是否存在；若不存在需创建。
2. **Detect.vue 面包屑**：当前面包屑为「算法管理 > 检测工作台」，将作物检测提升为独立 tab 后，面包屑应调整为反映新导航结构（如移除面包屑，因为 SubTabs 已提供同级导航）。
3. **模型注册/详情页**：`/algo/model-register` 和 `/algo/models/:name` 页面也使用 SubTabs，需确保这些页面中「算法管理」tab 正确高亮（`isModels` 判断需覆盖这些路径）。
4. **SVG 引入方式**：在 Vue SFC 中引入 SVG 作为 `<img src>` 时，Vite 会处理 assets 路径；使用内联 SVG 可避免路径问题但代码冗余。推荐 `<img>` 方式配合 import 或直接使用 public 路径。
5. **favicon 缓存**：更新后浏览器可能缓存旧 favicon，需提示用户硬刷新（Ctrl+F5）验证。

---

## 五、风险与处理

| 风险 | 影响 | 处理方式 |
|------|------|----------|
| public 目录不存在 | favicon 404 | 检查并创建 public 目录，复制 favicon 文件 |
| SubTabs 高亮状态覆盖不全 | 模型详情/注册页 tab 高亮错误 | `isModels` 使用 `startsWith('/algo/models')` 覆盖所有模型相关子路由 |
| SVG 图标尺寸不适配侧边栏 | logo 显示异常 | 设置固定 `w-8 h-8`，与原 emoji 视觉大小一致 |
| 快速入口 5 张卡片在 2 列布局下排列不美观 | 最后一行仅 1 张卡片 | 保持 2 列布局，5 张卡片自然排列（上 2 行满，第 3 行 1 张），与用户截图示意一致 |

---

## 六、验证步骤

1. **首页快速入口**：访问 `/`，确认「计数工作台」卡片可见，点击跳转至 `/algo/counting`
2. **子导航三 tab**：分别访问 `/algo/models`、`/algo/detect`、`/algo/counting`，确认三个 tab 正确高亮且可互相切换
3. **模型详情/注册页**：访问 `/algo/models/xxx` 和 `/algo/model-register`，确认「算法管理」tab 高亮
4. **favicon**：浏览器标签页显示无人机+作物图标，非默认空白/🌾
5. **侧边栏 logo**：左侧边栏【田间智监】左侧显示正式 SVG 图标，非 🌾 emoji
6. **整体构建**：运行 `npm run build` 确认无编译错误
