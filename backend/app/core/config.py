"""应用配置管理。

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
支持开发环境和生产环境的无缝切换。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类。

    所有配置项都有默认值，开发时不需要每个都配。
    生产环境通过环境变量覆盖。
    """

    # ========== pydantic-settings 基础配置 ==========
    model_config = SettingsConfigDict(
        env_file=".env",          # 从 .env 文件读取
        env_file_encoding="utf-8",
        extra="ignore",           # 忽略未定义的环境变量（防止报错）
    )

    # ========== 应用基础配置 ==========
    app_name: str = Field(default="Air Fryer AI Assistant", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    # 环境标识：dev=本地开发（Ollama）、prod=生产（DeepSeek）
    # 通过 docker-compose 的 environment 注入，决定走哪套 LLM 配置
    app_env: Literal["dev", "prod"] = Field(default="dev", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # ========== 数据库配置 ==========
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ecommerce_rag",
        description="数据库连接字符串",
    )

    # ========== 向量库配置 ==========
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant 地址")
    qdrant_collection_name: str = Field(
        default="knowledge_chunks", description="Qdrant Collection 名称"
    )

    # ========== 缓存配置 ==========
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis 连接字符串")

    # ========== LLM 配置 ==========
    # 策略模式入口：factory.py 根据此字段选择对应的 LLM 实现
    # dev 环境 → ollama；prod 环境 → deepseek
    llm_provider: Literal["ollama", "openai", "deepseek"] = Field(
        default="ollama", description="LLM 提供商"
    )

    # Ollama（dev 环境用，本地部署免费）
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    ollama_model: str = Field(default="qwen3.5:2b", description="Ollama 对话模型")
    ollama_embedding_model: str = Field(
        default="nomic-embed-text", description="Ollama Embedding 模型"
    )

    # OpenAI（兼容接口，可指向任何 OpenAI 兼容服务）
    openai_api_key: str | None = Field(default=None, description="OpenAI API Key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", description="OpenAI 兼容 API 地址"
    )
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI 对话模型")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI Embedding 模型"
    )

    # DeepSeek（prod 环境用，国内访问稳定、价格低、中文友好）
    # API 100% 兼容 OpenAI 格式，复用 OpenAILLM 实现，只换 base_url 和模型名
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API Key")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1", description="DeepSeek API 地址"
    )
    deepseek_model: str = Field(default="deepseek-chat", description="DeepSeek 对话模型")

    # ========== RAG 配置 ==========
    rag_top_k: int = Field(default=5, description="RAG 检索返回文档数")
    rag_similarity_threshold: float = Field(
        default=0.7, description="RAG 相似度阈值", ge=0.0, le=1.0
    )
    # 知识文档目录：本地为 backend/data/knowledge，容器内为 /app/data/knowledge
    # 通过 docker volume 挂载，本地改文档后容器立即可见
    knowledge_dir: str = Field(
        default="data/knowledge", description="知识文档目录（相对路径）"
    )

    # ========== 安全配置 ==========
    secret_key: str = Field(default="dev-secret-key", description="JWT 签名密钥")
    access_token_expire_minutes: int = Field(default=60, description="Token 过期时间（分钟）")

    # ========== 限流配置 ==========
    rate_limit_enabled: bool = Field(
        default=True, description="是否启用请求限流"
    )
    rate_limit_requests: int = Field(
        default=10, description="限流：窗口内允许的请求数"
    )
    rate_limit_window: int = Field(
        default=60, description="限流：时间窗口（秒）"
    )

    # ========== 超时配置 ==========
    request_timeout_seconds: int = Field(
        default=120, description="全局请求超时时间（秒）"
    )
    chat_timeout_seconds: int = Field(
        default=90, description="对话工作流超时时间（秒）"
    )

    # ========== CORS 配置 ==========
    allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许的跨域来源（逗号分隔）",
    )

    # ========== 校验器 ==========
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list) -> str:
        """确保 allowed_origins 始终是字符串。"""
        if isinstance(v, list):
            return ",".join(v)
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """将逗号分隔的字符串转为列表，供 FastAPI CORS 使用。"""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（单例模式）。

    使用 @lru_cache 确保全局只有一个 Settings 实例，
    避免每次 import 都重新读取 .env 文件。
    """
    return Settings()


# 全局配置实例（供其他模块直接 import）
settings = get_settings()
