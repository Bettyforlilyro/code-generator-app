"""
LLM客户端集成测试
测试ChatClientBuilder构建的ChatClient能否成功调用大模型API并获得正确回复

使用前请确保:
1. .env 文件中已配置 TONGYI_API_KEY, TONGYI_OPENAI_COMPATIBLE_BASE_URL, TONGYI_MODEL
2. 或者通过代码显式设置相关参数
"""

import os
import sys
import time

from dotenv import load_dotenv

from backend.app.common.emuns.code_file_type import CodeFileType
from backend.app.common.utils.code_file_saver import CodeFileSaverFactory
from backend.app.schemas.ai_generate_results import HtmlCodeResult
from backend.app.services.ai_common.llm_client import ChatClientBuilder, create_default_chat_client
from backend.app.services.ai_common.advisor import (
    PreAdvisor, PostAdvisor, StreamPostAdvisor,
    AdvisorContext, StreamChunk
)
from backend.app.services.ai_generator_facade import AICodeGeneratorFacade

# 加载环境变量
load_dotenv()

# 将项目根目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))


# ============================================================
# 自定义拦截器（用于测试拦截器链是否正常工作）
# ============================================================

class LogPreAdvisor(PreAdvisor):
    """前置日志拦截器"""

    @property
    def name(self) -> str:
        return "LogPreAdvisor"

    def pre_handle(self, context: AdvisorContext) -> AdvisorContext:
        print(f"\n[PreAdvisor] 拦截器触发，当前消息数: {len(context.messages)}")
        context.metadata['pre_time'] = time.time()
        return context


class LogPostAdvisor(PostAdvisor):
    """后置日志拦截器"""

    @property
    def name(self) -> str:
        return "LogPostAdvisor"

    def post_handle(self, context: AdvisorContext) -> AdvisorContext:
        pre_time = context.metadata.get('pre_time', 0)
        elapsed = time.time() - pre_time
        print(f"[PostAdvisor] 拦截器触发，耗时: {elapsed:.2f}s")
        context.metadata['post_time'] = time.time()
        return context


class LogStreamPostAdvisor(StreamPostAdvisor):
    """流式后置日志拦截器"""

    @property
    def name(self) -> str:
        return "LogStreamPostAdvisor"

    def post_handle_stream(self, chunk: StreamChunk, context: AdvisorContext) -> StreamChunk:
        if not chunk.is_last:
            print(f"[StreamPostAdvisor] 收到chunk: '{chunk.content[:30]}...'" if len(chunk.content) > 30 else f"[StreamPostAdvisor] 收到chunk: '{chunk.content}'")
        else:
            print("[StreamPostAdvisor] 流式响应结束")
        return chunk

# ============================================================
# 测试用例
# ============================================================


def test_default_build():
    """测试1: 使用默认配置构建客户端并发送简单消息"""
    print("=" * 60)
    print("测试1: 默认配置构建 + 简单对话")
    print("=" * 60)

    client = create_default_chat_client()

    messages = [
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]

    response = client.chat(messages)
    print(f"AI回复: {response}")
    assert response is not None, "响应不应为None"
    assert len(response) > 0, "响应不应为空"
    print("✅ 测试1通过\n")
    return True


def test_custom_build():
    """测试2: 自定义参数构建客户端 + 结构化输出"""
    print("=" * 60)
    print("测试2: 自定义参数构建 + 结构化输出")
    print("=" * 60)
    from backend.app.services.ai_common.prompts import CODE_GENERATE_HTML_SYSTEM_PROMPT
    client = (ChatClientBuilder()
        .set_temperature(0.3)
        .set_max_tokens(50000)
        .set_response_format(HtmlCodeResult.get_response_format())
        .set_system_prompt(CODE_GENERATE_HTML_SYSTEM_PROMPT)
        .build())

    messages = [
        {"role": "user", "content": "写一个简易的个人博客网页，代码100行以内即可，尽量简单一点"}
    ]

    response = client.chat_structured(messages, HtmlCodeResult)
    print(f"AI回复:\n{response}")
    assert isinstance(response, HtmlCodeResult), "响应应为HtmlCodeResult类型"
    assert response.html_code is not None, "html_code不应为None"
    saver = CodeFileSaverFactory.get_saver(CodeFileType.HTML)
    saver.save_code_file(response, app_id=1)
    print("✅ 测试2通过\n")
    return True


def test_multi_turn_conversation():
    """测试3: 多轮对话"""
    print("=" * 60)
    print("测试3: 多轮对话")
    print("=" * 60)

    client = ChatClientBuilder().build()

    messages = [
        {"role": "user", "content": "我的名字是小明。"},
        {"role": "assistant", "content": "你好小明！有什么可以帮你的吗？"},
        {"role": "user", "content": "我刚才说我叫什么名字？"}
    ]

    response = client.chat(messages)
    print(f"AI回复: {response}")
    assert "小明" in response, f"AI应该记住名字'小明'，实际回复: {response}"
    print("✅ 测试3通过\n")
    return True


def test_chat_without_system():
    """测试4: 不使用系统提示词的对话"""
    print("=" * 60)
    print("测试4: chat_without_system")
    print("=" * 60)

    client = ChatClientBuilder().set_system_prompt("你是一个助手。").build()

    messages = [
        {"role": "user", "content": "1+1等于几？"}
    ]

    response = client.chat_without_system(messages)
    print(f"AI回复: {response}")
    assert "2" in response or "二" in response, f"1+1应该等于2，实际回复: {response}"
    print("✅ 测试4通过\n")
    return True


def test_stream_chat():
    """测试5: 流式对话"""
    print("=" * 60)
    print("测试5: 流式对话")
    print("=" * 60)

    client = ChatClientBuilder().build()

    messages = [
        {"role": "user", "content": "用三句话描述春天。"}
    ]

    full_response = ""
    chunk_count = 0
    for chunk in client.chat_stream(messages):
        chunk_count += 1
        if not chunk.is_last:
            full_response += chunk.content
        else:
            print(f"\n[最后一块] is_last=True, 累计chunk数: {chunk_count}")

    print(f"完整回复: {full_response}")
    assert len(full_response) > 0, "流式响应不应为空"
    assert chunk_count > 1, f"应该收到多个chunk，实际只收到{chunk_count}个"
    print("✅ 测试5通过\n")
    return True


def test_interceptor_chain():
    """测试6: 拦截器链"""
    print("=" * 60)
    print("测试6: 拦截器链（前置+后置+流式后置）")
    print("=" * 60)

    client = (ChatClientBuilder()
        .add_pre_advisor(LogPreAdvisor())
        .add_post_advisor(LogPostAdvisor())
        .add_stream_post_advisor(LogStreamPostAdvisor())
        .build())

    messages = [
        {"role": "user", "content": "说一句名言。"}
    ]

    # 测试带拦截器的普通对话
    print("--- 普通对话 (带拦截器) ---")
    response = client.chat(messages, conversation_id="test-conv-001")
    print(f"AI回复: {response[:100]}...")

    # 测试带拦截器的流式对话
    print("\n--- 流式对话 (带拦截器) ---")
    full_response = ""
    for chunk in client.chat_stream(messages, conversation_id="test-conv-002"):
        if not chunk.is_last:
            full_response += chunk.content
    print(f"流式完整回复: {full_response[:100]}...")

    print("✅ 测试6通过\n")
    return True


def test_parameter_validation():
    """测试7: 参数校验"""
    print("=" * 60)
    print("测试7: 参数校验（异常情况）")
    print("=" * 60)

    # 测试temperature范围
    try:
        ChatClientBuilder().set_temperature(-1.0)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ Temperature下限校验: {e}")

    try:
        ChatClientBuilder().set_temperature(3.0)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ Temperature上限校验: {e}")

    # 测试top_p范围
    try:
        ChatClientBuilder().set_top_p(1.5)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ TopP上限校验: {e}")

    # 测试max_tokens
    try:
        ChatClientBuilder().set_max_tokens(-1)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ MaxTokens校验: {e}")

    # 测试timeout
    try:
        ChatClientBuilder().set_timeout(0)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ Timeout校验: {e}")

    # 测试max_retries
    try:
        ChatClientBuilder().set_max_retries(-1)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ MaxRetries校验: {e}")

    # 测试frequency_penalty范围
    try:
        ChatClientBuilder().set_frequency_penalty(-3.0)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ FrequencyPenalty校验: {e}")

    # 测试presence_penalty范围
    try:
        ChatClientBuilder().set_presence_penalty(3.0)
        assert False, "应该抛出ValueError"
    except ValueError as e:
        print(f"✅ PresencePenalty校验: {e}")

    print("✅ 测试7通过\n")
    return True


def test_system_prompt_update():
    """测试8: 动态更新系统提示词"""
    print("=" * 60)
    print("测试8: 动态更新系统提示词")
    print("=" * 60)

    client = ChatClientBuilder().set_system_prompt("你是一个数学老师。").build()

    messages = [
        {"role": "user", "content": "3乘以7等于多少？"}
    ]

    response1 = client.chat(messages)
    print(f"初始系统提示词回复: {response1}")

    # 动态修改系统提示词
    client.system_prompt = "你是一个语文老师，回答时用诗句作答。"
    response2 = client.chat(messages)
    print(f"修改后系统提示词回复: {response2}")

    assert response1 != response2, "不同系统提示词应产生不同回复"
    print("✅ 测试8通过\n")
    return True

# ============================================================
# 主测试入口
# ============================================================


def test_ai_code_generator_facade():
    res_file_path1 = AICodeGeneratorFacade.generate_code_and_save_file("生成一个登录页面，代码不超过50行", CodeFileType.HTML, app_id=1)
    assert res_file_path1 is not None, "生成的文件路径应为非空字符串"
    res_file_path2 = AICodeGeneratorFacade.generate_code_and_save_file("生成一个注册页面，代码不超过100行", CodeFileType.MULTI_FILE, app_id=1)
    assert res_file_path2 is not None, "生成的文件路径应为非空字符串"


def main():
    print("\n" + "=" * 60)
    print("   LLM_Client 集成测试")
    print("=" * 60)

    # 检查必要的环境变量
    api_key = os.getenv('TONGYI_API_KEY')
    base_url = os.getenv('TONGYI_OPENAI_COMPATIBLE_BASE_URL')
    model = os.getenv('TONGYI_MODEL')

    if not api_key:
        print("❌ 错误: 未设置 TONGYI_API_KEY 环境变量")
        print("   请在 .env 文件中配置或通过环境变量设置")
        return False

    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print()

    tests = [
        ("默认配置构建 + 简单对话", test_default_build),
        ("自定义参数构建", test_custom_build),
        ("多轮对话", test_multi_turn_conversation),
        ("chat_without_system", test_chat_without_system),
        ("流式对话", test_stream_chat),
        ("拦截器链", test_interceptor_chain),
        ("参数校验", test_parameter_validation),
        ("动态更新系统提示词", test_system_prompt_update),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "PASS" if result else "FAIL"))
        except Exception as e:
            print(f"❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"ERROR: {e}"))

    # 汇总结果
    print("\n" + "=" * 60)
    print("   测试结果汇总")
    print("=" * 60)
    for name, status in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {name}: {status}")

    passed = sum(1 for _, s in results if s == "PASS")
    total = len(results)
    print(f"\n  通过: {passed}/{total}")
    print(f"  通过率: {passed/total*100:.1f}%")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)