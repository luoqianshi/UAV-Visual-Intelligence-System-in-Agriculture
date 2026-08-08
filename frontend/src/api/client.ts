import axios from 'axios'

// 统一 axios 实例：baseURL /api，开发期经 Vite 代理到 Flask:5000
const client = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 响应拦截：解包 { success, data, message } 信封
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // 网络错误或非 2xx，统一抛出可读消息
    const msg = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
