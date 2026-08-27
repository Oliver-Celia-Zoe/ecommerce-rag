"""AI 助手终端测试脚本。

用法:
    cd backend
    uv run python -m scripts.test_chat

或者指定问题:
    uv run python -m scripts.test_chat "空气炸锅多少钱"
"""

import asyncio
import sys

import httpx

BASE_URL = "http://localhost:8002"

# 预设测试用例
TEST_CASES = [
    # (问题, 期望的intent)
    ("空气炸锅不加热怎么办", "aftersales"),
    ("你们的空气炸锅多少钱", "presales"),
    ("你好，请问在吗", "general"),
    ("我的订单到哪了", "transaction"),
    ("炸红薯要多少度", "aftersales"),
    ("转人工客服", "general"),
]


async def send_chat(message: str) -> dict:
    """发送一条消息到 AI 助手。"""
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat/",
            json={"message": message},
        )
        response.raise_for_status()
        return response.json()


async def test_single(question: str):
    """测试单个问题并打印结果。"""
    print(f"\n{'='*50}")
    print(f"📝 用户问题: {question}")
    print(f"{'='*50}")

    try:
        result = await send_chat(question)
        print(f"\n✅ HTTP 状态: 200")
        print(f"📌 意图识别: {result.get('intent', 'N/A')}")
        print(f"🤖 需要转人工: {result.get('need_human', False)}")
        print(f"📄 AI 回答 ({len(result.get('answer', ''))} 字符):")
        print(f"   {result.get('answer', '')}")
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")


async def test_all():
    """运行所有预设测试用例。"""
    print("🚀 开始批量测试...")
    print(f"API 地址: {BASE_URL}")

    for question, expected_intent in TEST_CASES:
        print(f"\n{'='*50}")
        print(f"📝 问题: {question}")
        print(f"   期望意图: {expected_intent}")

        try:
            result = await send_chat(question)
            actual_intent = result.get('intent', 'N/A')
            status = "✅" if actual_intent == expected_intent else "⚠️"
            print(f"{status} 实际意图: {actual_intent}")
            print(f"   回答长度: {len(result.get('answer', ''))} 字符")
            print(f"   转人工: {result.get('need_human', False)}")
        except Exception as e:
            print(f"❌ 失败: {e}")

    print("\n\n🎉 批量测试完成")


async def interactive():
    """交互式测试。"""
    print("=" * 50)
    print("🤖 AI 助手交互式测试")
    print("=" * 50)
    print("输入问题测试 AI，输入 'exit' 退出\n")

    while True:
        question = input("你: ").strip()
        if question.lower() in ("exit", "quit", "退出"):
            print("👋 再见！")
            break
        if not question:
            continue

        try:
            result = await send_chat(question)
            print(f"\n🤖 AI ({result.get('intent', '?')}):")
            print(f"   {result.get('answer', '')}\n")
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")


async def main():
    # 命令行参数处理
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all" or arg == "-a":
            await test_all()
        elif arg == "--interactive" or arg == "-i":
            await interactive()
        else:
            await test_single(arg)
    else:
        # 默认：测试单个问题
        await test_single("空气炸锅不加热怎么办")
        print("\n" + "=" * 50)
        print("提示: 你可以传入参数:")
        print("  uv run python -m scripts.test_chat '你的问题'")
        print("  uv run python -m scripts.test_chat --all")
        print("  uv run python -m scripts.test_chat --interactive")


if __name__ == "__main__":
    asyncio.run(main())
