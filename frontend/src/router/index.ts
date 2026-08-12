import { createRouter, createWebHistory } from 'vue-router'

// 15 条路由，对应 V0.4 原型全部页面
const routes = [
  { path: '/', name: 'index', component: () => import('@/views/index/Index.vue') },

  // 数据管理
  { path: '/data/batches', name: 'batches', component: () => import('@/views/data/Batches.vue') },
  { path: '/data/batches/:id', name: 'batch-detail', component: () => import('@/views/data/BatchDetail.vue') },
  { path: '/data/batch-new', name: 'batch-new', component: () => import('@/views/data/BatchNew.vue') },
  { path: '/data/processed', name: 'processed', component: () => import('@/views/data/Processed.vue') },
  { path: '/data/processed/:id', name: 'processed-detail', component: () => import('@/views/data/ProcessedDetail.vue') },

  // 数据处理
  { path: '/process/tasks', name: 'tasks', component: () => import('@/views/process/Tasks.vue') },
  { path: '/process/tasks/:id', name: 'task-detail', component: () => import('@/views/process/TaskDetail.vue') },
  { path: '/process/task-new', name: 'task-new', component: () => import('@/views/process/TaskNew.vue') },

  // 数据集管理
  { path: '/dataset/datasets', name: 'datasets', component: () => import('@/views/dataset/Datasets.vue') },
  { path: '/dataset/datasets/:id', name: 'dataset-detail', component: () => import('@/views/dataset/DatasetDetail.vue') },
  { path: '/dataset/dataset-new', name: 'dataset-new', component: () => import('@/views/dataset/DatasetNew.vue') },

  // 算法广场
  { path: '/algo/models', name: 'models', component: () => import('@/views/algo/Models.vue') },
  { path: '/algo/models/:name', name: 'model-detail', component: () => import('@/views/algo/ModelDetail.vue') },
  { path: '/algo/model-register', name: 'model-register', component: () => import('@/views/algo/ModelRegister.vue') },
  { path: '/algo/detect', name: 'detect', component: () => import('@/views/algo/Detect.vue') },
  { path: '/algo/counting', name: 'counting', component: () => import('@/views/algo/Counting.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
