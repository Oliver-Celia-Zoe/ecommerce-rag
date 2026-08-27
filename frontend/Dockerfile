# ==========================================
# 前端生产 Dockerfile（多阶段构建）
# 构建：docker build -t air-fryer-frontend:prod -f frontend/Dockerfile frontend/
# ==========================================
# 两阶段：
#   1. builder：node 环境装依赖 + vite build → 产出 dist/ 静态文件
#   2. runtime：nginx 托管 dist/，并反向代理 /api 到后端容器
# 最终镜像只有 nginx + 静态文件，体积小、启动快、无 node 运行时

# ---------- 阶段 1：构建阶段 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制 package.json 和 lock 文件（利用缓存层，依赖不变就跳过 npm ci）
COPY package.json package-lock.json ./

# 安装依赖（ci 比 install 更严格，按 lock 文件装，保证可复现）
RUN npm ci

# 复制源码
COPY . .

# 构建（vite build 产出 dist/ 目录）
# 此时 VITE_API_BASE_URL 默认 /api/v1（相对路径），nginx 会代理
RUN npm run build

# ---------- 阶段 2：运行阶段 ----------
FROM nginx:alpine AS runtime

# 复制构建产物到 nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 nginx 配置（反向代理 /api → 后端）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx 前台运行（不加这个容器会立即退出）
CMD ["nginx", "-g", "daemon off;"]
