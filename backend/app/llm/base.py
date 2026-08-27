"""LLM 抽象接口。

定义所有 LLM 实现必须遵循的统一接口。
业务代码只依赖这个接口，不关心底层是 Ollama 还是 OpenAI。

这是策略模式（Strategy Pattern）的核心：
  - BaseLLM = 抽象策略接口
  - OllamaLLM / OpenAILLM = 具体策略实现
  - 调用方 = 上下文，通过接口选择策略
"""

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 抽象基类。

    所有 LLM 实现（Ollama、OpenAI、智谱等）都必须继承这个类，
    并实现 chat 方法。
    """

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]]) -> str:
        """发送对话消息列表，返回 LLM 的文本回复。

        Args:
            messages: OpenAI 格式的消息列表
                [
                    {"role": "system", "content": "你是..."},
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！"},
                    {"role": "user", "content": "空气炸锅怎么用？"},
                ]

        Returns:
            LLM 生成的回复文本
        """
        ...
