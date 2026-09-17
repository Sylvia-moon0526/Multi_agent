# AutoGen 多Agent协作研究系统（Project 2）

## 📋 项目简介

基于微软 [AutoGen AgentChat](https://github.com/microsoft/autogen) 框架构建的多Agent协作系统。系统模拟了一个**小型研究团队**，由多个具有不同职责的 Agent 角色组成，通过轮转对话机制协同完成从**信息检索 → 数据分析 → 报告撰写 → 人工审批**的完整研究流程。

---

## 🎯 核心功能

- **多角色Agent协作**：研究员、分析师、撰稿人、人工评审四个角色分工明确，各司其职
- **自动联网搜索**：内置双数据源搜索引擎（必应国内版 RSS + Tavily API），无需 API Key 即可使用
- **人工审批机制**：支持 APPROVE（通过）/ DONE（直接结束）/ 修改意见（打回重写）三种人工干预方式
- **轮转对话编排**：基于 `RoundRobinGroupChat` 实现 Agent 间有序轮流发言，确保流程稳定可控
- **异步执行架构**：全链路 async/await 设计，搜索工具通过线程池隔离避免阻塞事件循环

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────┐
│              RoundRobinGroupChat（轮转编排）              │
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
│  终止条件：APPROVE / DONE / 最大轮次60            │       │
└──────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent 角色说明

| 角色 | Agent类型 | 职责 | 工具 |
|------|-----------|------|------|
| **Researcher** | `AssistantAgent` | 联网检索资料，提取关键数据，保留来源URL | `search_web` |
| **Analyst** | `AssistantAgent` | 对资料进行结构化分析（现状、趋势、驱动力、风险） | 无 |
| **Writer** | `AssistantAgent` | 基于分析结论撰写完整研究报告 | 无 |
| **Human** | `UserProxyAgent` | 审批报告：APPROVE通过 / DONE结束 / 输入修改意见 | `input()` |

---

## 🔍 搜索引擎设计

采用**双源降级策略**，优先使用 Tavily（需配置 API Key），否则自动回退到必应国内版 RSS：

```
search_web()
    │
    ├── 有 TAVILY_API_KEY → Tavily Search API（更精准、支持摘要）
    │
    └── 无 → 必应国内版 cn.bing.com RSS（零配置、免费、国内可访问）
```

- **必应 RSS 模式**：纯标准库实现（`urllib` + `xml.etree`），无需额外 pip 包
- **Tavily 模式**：通过 HTTP POST 调用，返回结构化搜索结果

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- 硅基流动（SiliconFlow）API Key

### 2. 安装依赖

```bash
pip install autogen-agentchat autogen-ext[openai] requests
```

### 3. 配置环境变量

```bash
# 必须：硅基流动 API Key
export SILICONFLOW_API_KEY="your-api-key-here"

# 可选：指定模型（默认 Qwen/Qwen2.5-7B-Instruct）
export SILICONFLOW_MODEL="Qwen/Qwen2.5-7B-Instruct"

# 可选：Tavily API Key（不配置则自动使用必应RSS）
export TAVILY_API_KEY="your-tavily-key-here"
```

### 4. 运行

```bash
python main.py
```

默认研究主题为「2025-2026 年 AI Agent 技术发展趋势」，可修改 `__main__` 中的 `topic` 变量自定义。

---

## ⚙️ 关键配置

### 模型配置

| 参数 | 值 | 说明 |
|------|-----|------|
| model | Qwen/Qwen2.5-7B-Instruct | 通义千问，支持 Function Calling |
| base_url | https://api.siliconflow.cn/v1 | 硅基流动 API |
| temperature | 0.3 | 低温度保证输出稳定性 |
| timeout | 300s | 5分钟超时，防止长时间卡死 |
| context_window | 131072 | 128K 上下文窗口 |

### 终止条件

采用多重终止策略（OR 组合）：

- `TextMentionTermination("APPROVE")` — 人工审批通过，正常结束
- `TextMentionTermination("DONE")` — 直接结束任务
- `MaxMessageTermination(60)` — 最大对话轮次兜底，防止无限循环

---

## 📁 项目结构

```
project2/
├── main.py          # 主程序入口（完整可运行代码）
├── README.md        # 本文件
└── requirements.txt # 依赖清单（可选）
```

---

## 🔧 技术要点

1. **轮转对话 vs 选择器对话**：选用 `RoundRobinGroupChat` 而非 `SelectorGroupChat`，后者需额外调用 LLM 选择发言人，在 API 不稳定场景下容易卡死
2. **异步输入处理**：`UserProxyAgent` 的 `input_func` 在子线程中执行（`asyncio.to_thread`），避免阻塞事件循环
3. **兼容性设计**：`input_func` 使用 `*args/**kwargs` 兼容新旧版 autogen-agentchat 签名差异（旧版只传 `prompt`，新版还传 `cancellation_token`）
4. **输出刷新**：所有 `print` 调用均设置 `flush=True`，确保流式输出即时可见

---

## 📌 后续优化方向

- [ ] 将 Agent 定义拆分为独立模块，提升代码可维护性
- [ ] 引入 SelectorGroupChat（动态选择发言人），提升协作效率
- [ ] 增加报告导出功能（Markdown / PDF）
- [ ] 支持更多搜索数据源（Google Scholar、Arxiv 等）
- [ ] 添加流式输出（Streaming）支持，实时展示生成过程

---

## 📄 License

MIT License

---
