# ==========================================
# Air Fryer AI Assistant - Docker 一键脚本
# ==========================================
# 用法：
#   make dev        启动开发环境（前台，看实时日志）
#   make dev-d       启动开发环境（后台）
#   make dev-build  重建镜像后启动开发环境
#   make dev-down   停止开发环境
#   make prod       启动生产环境（后台，需先配 .env.prod）
#   make prod-build 重建镜像后启动生产环境
#   make prod-down  停止生产环境
#   make logs       查看开发环境日志
#   make ps        查看容器状态
#   make ollama-pull 拉取 Ollama 模型
#   make clean      停止并删除数据卷（慎用！数据会丢）
#   make help       显示帮助
#
# Windows 用户：如果没装 make，可直接用下面等价的 docker compose 命令
# 或装 make：scoop install make / choco install make

# Compose 文件路径
DEV_COMPOSE = -f docker-compose.yml -f docker-compose.dev.yml
PROD_COMPOSE = --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: help dev dev-d dev-build dev-down prod prod-build prod-down logs ps ollama-pull clean

help:
	@echo "Air Fryer AI Assistant - Docker 命令"
	@echo ""
	@echo "开发环境："
	@echo "  make dev         启动（前台，看日志）"
	@echo "  make dev-d        启动（后台）"
	@echo "  make dev-build   重建镜像并启动"
	@echo "  make dev-down    停止"
	@echo ""
	@echo "生产环境："
	@echo "  make prod        启动（后台，需先配 .env.prod）"
	@echo "  make prod-build  重建镜像并启动"
	@echo "  make prod-down   停止"
	@echo ""
	@echo "工具："
	@echo "  make logs        查看日志"
	@echo "  make ps          查看容器"
	@echo "  make ollama-pull 拉取 Ollama 模型"
	@echo "  make clean      停止并删除卷（慎用！）"

# ---------- 开发环境 ----------
dev:
	docker compose $(DEV_COMPOSE) up

dev-d:
	docker compose $(DEV_COMPOSE) up -d

dev-build:
	docker compose $(DEV_COMPOSE) up --build

dev-down:
	docker compose $(DEV_COMPOSE) down

# ---------- 生产环境 ----------
prod:
	@test -f .env.prod || (echo "错误：请先创建 .env.prod（参考 .env.prod.example）" && exit 1)
	docker compose $(PROD_COMPOSE) up -d

prod-build:
	@test -f .env.prod || (echo "错误：请先创建 .env.prod（参考 .env.prod.example）" && exit 1)
	docker compose $(PROD_COMPOSE) up -d --build

prod-down:
	docker compose $(PROD_COMPOSE) down

# ---------- 工具 ----------
logs:
	docker compose $(DEV_COMPOSE) logs -f

ps:
	docker compose $(DEV_COMPOSE) ps

ollama-pull:
	@echo "拉取 Ollama 模型（首次需要，约 2GB）..."
	docker exec air-fryer-ollama-prod ollama pull nomic-embed-text
	docker exec air-fryer-ollama-prod ollama pull qwen3.5:2b || true
	@echo "完成！模型已存储在 ollama_models 卷中"

clean:
	@echo "警告：将停止所有服务并删除数据卷（数据会丢失）！"
	@read -p "确认？(y/N) " confirm; [ "$$confirm" = "y" ] || exit 1
	docker compose $(DEV_COMPOSE) down -v
	docker compose $(PROD_COMPOSE) down -v
