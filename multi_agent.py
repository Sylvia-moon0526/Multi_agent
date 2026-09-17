import os
import asyncio

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient

def _search_bing(query: str, max_results: int = 5) -> str:
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET
    import re

    url = ("https://cn.bing.com/search?q=" + urllib.parse.quote(query)
           + f"&format=rss&count={max_results}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        xml_text = resp.read().decode("utf-8", errors="ignore")

    results = []
    for item in ET.fromstring(xml_text).iter("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
        results.append(
            f"\n[{len(results) + 1}] {title}\n"
            f"    链接: {link}\n"
            f"    摘要: {desc[:300]}"
        )
    if not results:
        return f"未找到「{query}」相关结果。"
    return f"查询：{query}\n" + "\n".join(results)


def _search_tavily(query: str, max_results: int = 5) -> str:
    import requests

    resp = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": max_results},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return f"未找到「{query}」相关结果。"
    lines = [f"查询：{query}"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"\n[{i}] {r.get('title', '')}\n"
            f"    链接: {r.get('url', '')}\n"
            f"    摘要: {r.get('content', '')[:300]}"
        )
    return "\n".join(lines)


async def search_web(query: str, max_results: int = 5) -> str:
    def _run() -> str:
        if os.environ.get("TAVILY_API_KEY"):
            return _search_tavily(query, max_results)
        return _search_bing(query, max_results)

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:  # noqa: BLE001
        return (f"搜索失败（{type(e).__name__}: {e}）。"
                "请检查网络连接(cn.bing.com 是否需要可访问)。当前查询：" + query)

model_client = OpenAIChatCompletionClient(
    model=os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url="https://api.siliconflow.cn/v1",
    temperature=0.3,
    timeout=300,
    model_info={
        "family": "qwen",
        "context_window": 131072,
        "function_calling": True,
        "vision": False,
        "json_output": True,
    },
)

researcher = AssistantAgent(
    name="Researcher",
    system_message=(
        "你是研究助理，负责根据任务需求检索资料。\n"
        "工作规则：\n"
        "1. 必须调用 search_web 工具获取最新资料，可针对不同关键词多次调用\n"
        "2. 从搜索结果中提取关键数据和事实，并保留来源 URL\n"
        "3. 将整理好的带来源的资料一次性传递给 Analyst\n"
        "注意：你只负责搜索与信息整理，不做分析、不撰写报告。"
    ),
    model_client=model_client,
    tools=[search_web],
)

analyst = AssistantAgent(
    name="Analyst",
    system_message=(
        "你是数据分析师，基于 Researcher 提供的资料进行分析。\n"
        "工作规则：\n"
        "1. 对资料做结构化分析（现状、趋势、驱动力、风险等）\n"
        "2. 识别关键趋势与数据点，明确区分事实与推断\n"
        "3. 输出结构化分析结论，传递给 Writer\n"
        "注意：只负责分析，不撰写最终报告。"
    ),
    model_client=model_client,
)

writer = AssistantAgent(
    name="Writer",
    system_message=(
        "你是专业报告撰写者，基于 Analyst 的分析结论撰写研究报告。\n"
        "报告格式要求：\n"
        "1. 标题 — 简洁有力\n"
        "2. 摘要 — 100 字以内概括核心发现\n"
        "3. 正文 — 分章节，有数据支撑并标注来源\n"
        "4. 结论 — 明确的观点和建议\n"
        "5. 参考来源 — 列出主要信息来源\n"
        "完成后输出完整报告，等待人类评审。"
    ),
    model_client=model_client,
)
async def human_input_func(prompt: str = "", *args, **kwargs) -> str:
    print("\n" + "=" * 40, flush=True)
    print(" 人类评审面板", flush=True)
    print(" - APPROVE : 报告通过，结束任务", flush=True)
    print(" - DONE    : 直接结束任务", flush=True)
    print(" - 其他文本: 作为修改意见，让 Writer 重新修改", flush=True)
    print("=" * 40, flush=True)
    if prompt:
        print(f"[系统] {prompt}", flush=True)
    return await asyncio.to_thread(input, ">>> ")


human = UserProxyAgent(
    name="Human",
    description="人类评审员，负责审批研究报告。",
    input_func=human_input_func,
)

termination = (
    TextMentionTermination("DONE", sources=["Human"])
    | TextMentionTermination("APPROVE", sources=["Human"])
    | MaxMessageTermination(60)
)

team = RoundRobinGroupChat(
    [researcher, analyst, writer, human],
    max_turns=24,
    termination_condition=termination,
)

# ============================================================
# 6. 运行主流程
# ============================================================
async def run_research_task(topic: str) -> None:
    print(f"\n启动研究任务:{topic}\n" + "=" * 50, flush=True)

    task_prompt = (
        f"请研究并撰写一份关于「{topic}」的深度报告。\n\n"
        "流程：\n"
        "1. Researcher 调用 search_web 搜索并整理最新资料(必须带来源 URL)\n"
        "2. Analyst 对资料进行结构化分析\n"
        "3. Writer 撰写完整报告\n"
        "4. Human 审批：输入 APPROVE 通过并结束；输入修改意见则 Writer 重写；"
        "输入 DONE 直接结束任务"
    )

    result = None
    try:
        async for event in team.run_stream(task=task_prompt):
            event_type = type(event).__name__
            if event_type == "TaskResult":
                result = event
                continue

            content = getattr(event, "content", None)
            source = getattr(event, "source", None)
            if event_type == "TextMessage" and content:
                print(f"\n【{source}】\n{content}", flush=True)
            elif event_type == "FunctionExecutionResult":
                print(f"\n[工具结果 {source}]\n{str(content)[:600]}", flush=True)
    except KeyboardInterrupt:
        print("\n用户中断任务。", flush=True)
        return

    stop_reason = getattr(result, "stop_reason", "未知") if result else "未知"
    print(f"\n任务结束(终止原因：{stop_reason})", flush=True)


if __name__ == "__main__":
    topic = "2025-2026 年 AI Agent 技术发展趋势"
    asyncio.run(run_research_task(topic))
