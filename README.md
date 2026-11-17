# 👥 AutoGen 多 Agent 协作研究系统

<div align="center">

[Python](https://www.python.org/) · [AutoGen](https://microsoft.github.io/autogen/) · [asyncio](https://docs.python.org/3/library/asyncio.html) · [License: MIT](LICENSE)

</div>

> 基于微软 **AutoGen AgentChat** 构建的多 Agent 协作系统。它模拟一个小型研究团队，由不同职责的 Agent 分工协作，自动完成 **信息检索 → 数据分析 → 报告撰写 → 人工审批** 的完整研究流程。

---

## 📋 目录

- [核心功能](#-核心功能)
- [系统架构](#-系统架构)
- [Agent 角色说明](#-agent-角色说明)
- [搜索引擎设计](#-搜索引擎设计)
- [快速开始](#-快速开始)
- [关键配置](#-关键配置)
- [项目结构](#-项目结构)
- [技术要点](#-技术要点)
- [常见问题](#-常见问题)
- [后续优化方向](#-后续优化方向)

---

## 🎯 核心功能

- **多角色 Agent 协作**：研究员、分析师、撰稿人、人工评审四个角色分工明确，各司其职
- **自动联网搜索**：内置双数据源搜索引擎（必应国内版 RSS + Tavily API），无需 API Key 即可使用
- **人工审批机制**：支持 `APPROVE`（通过）/ `DONE`（结束）/ 输入修改意见（打回重写）三种人工干预方式
- **轮转对话编排**：基于 `RoundRobinGroupChat` 实现 Agent 间有序轮流发言，流程稳定可控
- **异步执行架构**：全链路 `async/await`，搜索工具通过 `asyncio.to_thread` 线程池隔离，避免阻塞事件循环

---

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────┐
│           RoundRobinGroupChat（轮转编排，max_turns=24）   │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────┐   │
│  │Researcher│──>│ Analyst  │──>│  Writer  │──>│Human │   │
│  │ 研究助理  │   │ 数据分析师│   │  报告撰稿 │   │评审员│   │
│  └────┬─────┘   └──────────┘   └──────────┘   └──┬───┘   │
│       │                                          │       │
│  ┌────▼─────┐                                    │       │
│  │search_web│ ◄──── 必应RSS / Tavily API         │       │
│  │ 联网搜索  │                                    │       │
│  └──────────┘                                    │       │
│                                                  │       │
│  终止条件：TextMention("APPROVE"/"DONE", Human)  │       │
│           | MaxMessageTermination(60)            │       │
└──────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent 角色说明

| 角色 | Agent 类型 | 职责 | 工具 |
| --- | --- | --- | --- |
| **Researcher** | `AssistantAgent` | 联网检索资料，提取关键数据，保留来源 URL | `search_web` |
| **Analyst** | `AssistantAgent` | 对资料做结构化分析（现状、趋势、驱动力、风险） | 无 |
| **Writer** | `AssistantAgent` | 基于分析结论撰写完整研究报告 | 无 |
| **Human** | `UserProxyAgent` | 审批报告：`APPROVE` 通过 / `DONE` 结束 / 其他文本作为修改意见 | `input()` |

---

## 🔍 搜索引擎设计

采用**双源降级策略**，优先级如下：

```
search_web()
    │
    ├── 有 TAVILY_API_KEY → Tavily Search API（更精准、支持摘要）
    │
    └── 无 → 必应国内版 cn.bing.com RSS（零配置、免费、国内可访问）
```

- **必应 RSS 模式**：纯标准库实现（`urllib` + `xml.etree.ElementTree` + `re`），无需额外 pip 包
- **Tavily 模式**：通过 `requests.post` 调用 API，返回结构化搜索结果
- **异步隔离**：`search_web` 是 `async` 函数，实际搜索逻辑通过 `asyncio.to_thread(_run)` 在子线程执行

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- 硅基流动（SiliconFlow）API Key（[siliconflow.cn](https://siliconflow.cn)）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> `requirements.txt` 内容为：`pyautogen>=0.4.0`、`duckduckgo-search>=7.0.0`
> 如需单独安装：`pip install autogen-agentchat autogen-ext[openai] requests`

### 3. 配置环境变量

```bash
# 必须：硅基流动 API Key
export SILICONFLOW_API_KEY="your-api-key-here"
# Windows PowerShell: $env:SILICONFLOW_API_KEY="your-api-key-here"

# 可选：指定模型（默认 Qwen/Qwen2.5-7B-Instruct）
export SILICONFLOW_MODEL="Qwen/Qwen2.5-7B-Instruct"

# 可选：Tavily API Key（不配置则自动使用必应 RSS 降级）
export TAVILY_API_KEY="your-tavily-key-here"
```

### 4. 运行

```bash
python multi_agent.py
```

> ⚠️ 入口文件是 `multi_agent.py`（仓库根目录唯一的主程序），不是 `main.py`。

默认研究主题为「2025-2026 年 AI Agent 技术发展趋势」。自定义主题请修改文件末尾 `__main__` 中的 `topic` 变量：

```python
if __name__ == "__main__":
    topic = "你的自定义研究主题"
    asyncio.run(run_research_task(topic))
```

---

## ⚙️ 关键配置

### 模型配置（代码实际值）

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `model` | `Qwen/Qwen2.5-7B-Instruct`（可通过 `SILICONFLOW_MODEL` 覆盖） | 通义千问，支持 Function Calling |
| `base_url` | `https://api.siliconflow.cn/v1` | 硅基流动 OpenAI 兼容接口 |
| `temperature` | `0.3` | 低温度保证输出稳定 |
| `timeout` | `300` | 5 分钟超时，防止长时间卡死 |
| `model_info.context_window` | `131072` | 128K 上下文窗口 |

### 终止条件

采用多重终止策略（OR 组合）：

- `TextMentionTermination("APPROVE", sources=["Human"])` — 人工审批通过，正常结束
- `TextMentionTermination("DONE", sources=["Human"])` — 直接结束任务
- `MaxMessageTermination(60)` — 最大消息数兜底，防止无限循环

此外 `RoundRobinGroupChat` 设置了 `max_turns=24` 作为团队轮次上限。

---

## 📁 项目结构

```
Multi_agent/
├── multi_agent.py     # 主程序：搜索工具 + 4 个 Agent + 编排 + 运行入口
├── requirements.txt   # 依赖清单（pyautogen, duckduckgo-search）
└── README.md
```

---

## 🔧 技术要点

1. **轮转对话 vs 选择器对话**：选用 `RoundRobinGroupChat` 而非 `SelectorGroupChat`。后者需要额外调用 LLM 选择发言人，在 API 不稳定场景下容易卡死；轮转机制用固定的有序发言换取稳定性。
2. **异步输入处理**：`UserProxyAgent` 的 `human_input_func` 是 `async` 函数，内部用 `await asyncio.to_thread(input, ">>> ")` 读取输入，避免阻塞事件循环。
3. **兼容性设计**：`human_input_func(prompt: str = "", *args, **kwargs)` 用可变参数兼容新旧版 `autogen-agentchat` 的签名差异（旧版只传 `prompt`，新版额外传 `cancellation_token`）。
4. **输出刷新**：所有 `print` 均设置 `flush=True`，确保流式输出即时可见。
5. **失败降级不崩溃**：`search_web` 捕获异常后返回带错误类型的可读信息，搜索失败不会中断整个协作流程。

---

## ❓ 常见问题

`KeyError: 'SILICONFLOW_API_KEY'`
未设置环境变量，按快速开始第 3 步设置。

**必应 RSS 搜索失败**
检查 `cn.bing.com` 是否可访问；或配置 `TAVILY_API_KEY` 切换到 Tavily 数据源。

**审批时输入什么？**

- `APPROVE` → 报告通过，任务结束
- `DONE` → 直接结束任务
- 任意其他文本 → 作为修改意见，Writer 会据此重写报告

**任务跑了很久不停**
已有三重保险：`MaxMessageTermination(60)`、`max_turns=24`、模型 `timeout=300`。也可以按 `Ctrl+C` 主动中断（代码捕获了 `KeyboardInterrupt`）。

---

## 📌 后续优化方向

- 将 Agent 与搜索工具定义拆分为独立模块（`config.py` / `agents.py` / `tools/`），提升可维护性
- 增加报告导出功能（Markdown / PDF）
- 支持更多搜索数据源（Google Scholar、arXiv 等）
- 添加流式输出展示，实时呈现生成过程
- 补充 pytest 测试（搜索降级逻辑、终止条件触发、Agent 角色数）

---

## 📄 License

MIT License
