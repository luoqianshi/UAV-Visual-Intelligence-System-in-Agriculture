import axios from 'axios'

// 统一 axios 实例：baseURL /api，开发期经 Vite 代理到 Flask:5000
const client = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 响应拦截：解包 { success, data, message } 信封
// 成功时返回信封体（含 data 字段），使调用方 res.data 即为业务 payload；
// success:false（后端用 HTTP 200 返回的业务失败）统一转 reject，便于 catch 捕获。
client.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && body.success === false) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (error) => {
    // 网络错误或非 2xx，统一抛出可读消息
    const msg = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
