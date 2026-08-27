"""LLM 工厂函数。

根据配置中的 LLM_PROVIDER 自动选择对应的实现。
业务代码不需要知道具体用的是哪个 LLM。

这是策略模式的"上下文"部分——选择并持有策略实例。

环境策略：
  - dev  环境（app_env=dev）   → 默认 LLM_PROVIDER=ollama，调用本地 Ollama
  - prod 环境（app_env=prod）  → 默认 LLM_PROVIDER=deepseek，调用 DeepSeek 云端 API

切换模型只需改 .env 中的 LLM_PROVIDER：
    LLM_PROVIDER=ollama   → OllamaLLM
    LLM_PROVIDER=openai    → OpenAILLM（指向官方 OpenAI）
    LLM_PROVIDER=deepseek  → OpenAILLM（指向 DeepSeek，复用兼容实现）
"""

from app.core.config import settings


def get_llm() -> "BaseLLM":
    """根据配置获取 LLM 实例。

    用法:
        from app.llm.factory import get_llm
        llm = get_llm()
        answer = await llm.chat(messages)

    返回值由 LLM_PROVIDER 环境变量决定：
        - "ollama"   → OllamaLLM（dev 环境）
        - "openai"   → OpenAILLM（指向 OpenAI 官方）
        - "deepseek" → OpenAILLM（指向 DeepSeek，复用兼容实现）
    """
    from app.llm.base import BaseLLM

    provider = settings.llm_provider

    if provider == "ollama":
        from app.llm.ollama_llm import OllamaLLM
        return OllamaLLM()

    if provider == "openai":
        from app.llm.openai_llm import OpenAILLM
        # 依赖注入：把配置作为参数传进去，OpenAILLM 自身不读 settings
        return OpenAILLM(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            provider_name="openai",
        )

    if provider == "deepseek":
        from app.llm.openai_llm import OpenAILLM
        # DeepSeek 100% 兼容 OpenAI 协议，直接复用 OpenAILLM，只换配置
        return OpenAILLM(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key or "",
            model=settings.deepseek_model,
            provider_name="deepseek",
        )

    raise ValueError(f"不支持的 LLM 提供商: {provider}")
