import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 反向代理目标：
// - 前端在容器里跑（docker dev）：指向后端容器 http://backend:8000
// - 前端在宿主机直接 npm run dev：指向 localhost:8000（默认）
// 通过环境变量 VITE_PROXY_TARGET 切换
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    // React 插件：让 Vite 能识别 .tsx/.jsx 中的 JSX 语法
    react(),
  ],
  server: {
    port: 5173,   // 开发服务器端口
    open: false,  // 容器内跑时不能自动开浏览器，关闭
    // 反向代理：把 /api/* 请求转发到后端，避免浏览器跨域
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
