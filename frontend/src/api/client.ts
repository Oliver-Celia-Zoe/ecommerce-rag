import axios from 'axios';

// API 基础路径：
// - 开发模式：/api/v1（由 vite dev server 的 proxy 转发到后端容器）
// - 生产模式：/api/v1（由 nginx 反向代理转发到后端容器）
// 两种环境都用相对路径，前端代码与环境解耦
// 特殊场景可用 VITE_API_BASE_URL 覆盖（如直连后端调试）
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器：自动从 localStorage 取 Token 加到 Header
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 时自动清除 Token 跳转登录
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
