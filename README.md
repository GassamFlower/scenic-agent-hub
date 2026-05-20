# 门神文化景区 · LangGraph 多智能体运营中枢

> 文旅行业 AI 智能体系统 — 智能客服 · 票务查询 · 内容运营 · 数据分析  
> **一站式部署，开箱即用**

---

## 系统架构

```
用户入口（小程序 / 公众号 / Web / iframe 嵌入）
        │
        ▼
┌──────────────────────────────────────┐
│          FastAPI 网关                 │
│  (认证 / CORS / 限流 / 错误处理)      │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│     LangGraph 中枢核心               │
│  ┌────────┬────────┬──────────┐      │
│  │ 记忆    │ 状态    │ Human-in │      │
│  │ Memory  │ State   │ -loop    │      │
│  └────────┴────────┴──────────┘      │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│   CrewAI 多智能体团队                 │
│  ┌────┬────┬────┬────┬────┬────┐     │
│  │客服 │票务 │研学 │内容 │电商 │管理 │     │
│  └────┴────┴────┴────┴────┴────┘     │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│   工具层 / 数据层                     │
│  Dify RAG · 知识库 · 票务 API · SQLite│
└──────────────────────────────────────┘
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python + FastAPI + Uvicorn |
| 智能体编排 | LangGraph（状态图 + 循环工作流） |
| 多智能体框架 | CrewAI（角色设定 + 任务协同） |
| 知识库 | Dify RAG（BM25 + 向量 + Rerank 混合检索） |
| 网关/工具链 | OpenClaw / Hermes Agent / API Tool Calling |
| 认证存储 | SQLite（零配置持久化） |
| 部署 | Docker + docker-compose |
| 前端 | Vue 3 / 嵌入式 iframe 组件 |
| LLM | DeepSeek / Qwen / GPT-4（通过 litellm 统一接入） |

---

## 快速开始（Docker）

### 前置要求
- Docker + docker-compose
- 一个 LLM API Key（DeepSeek / DashScope / OpenAI）

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/GassamFlower/ai-agent-methodology.git
cd ai-agent-methodology/05-工程实践/门神景区多智能体运营中枢

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 3. 启动
docker-compose up -d

# 4. 访问
#   对话测试: http://localhost:8000/
#   管理后台: http://localhost:8000/admin/login.html
#   API 文档: http://localhost:8000/docs
#   嵌入组件: http://localhost:8000/widget/chat.html
```

---

## 核心功能

### 🤖 AI 智能客服
- 6 大垂直角色智能体：客服、票务、研学、内容运营、文创电商、管理后台
- 意图识别（LLM 优先 + 关键词兜底）
- 对话记忆持久化（支持多轮对话）
- Human-in-the-loop 人工审核

### 📚 知识库管理
- 内置 15 条景区默认 FAQ
- 管理后台可视化编辑（增删改查）
- 按关键词匹配，自动跟踪未命中问题
- 热门问题 Top 10 统计

### ⚙️ 景区运营配置
- 11 项可配置参数（票价/时间/地址/电话/购票链接）
- 修改后 Agent 回复立即生效
- 管理后台一键修改

### 🎨 嵌入式对话组件
- iframe 嵌入，兼容任何网站
- CSS 变量自定义品牌色
- 移动端自适应
- 快捷回复按钮

### 👁️ 管理后台
- 登录保护（环境变量配置密码）
- 知识库管理 | 未命中问题 | 对话记录 | 审核队列
- 景区配置 | 热门问题统计

---

## API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/v1/chat` | 智能体对话主入口 |
| `GET /api/v1/sessions` | 会话列表 |
| `GET /api/v1/sessions/{id}/history` | 会话历史 |
| `GET /api/v1/reviews` | 待审核列表 |
| `POST /api/v1/reviews/{id}/complete` | 完成审核 |
| `POST /api/v1/admin/login` | 管理后台登录 |
| `GET/POST/PUT/DELETE /api/v1/admin/knowledge` | 知识库 CRUD |
| `GET /api/v1/admin/unanswered` | 未命中问题 |
| `POST /api/v1/admin/unanswered/{id}/to-faq` | 未命中→FAQ |
| `GET /api/v1/admin/hot-questions` | 热门问题 Top 10 |
| `GET/PUT /api/v1/admin/scenic-config` | 景区配置 |
| `GET /health` | 健康检查 |

---

## 项目结构

```
├── Dockerfile
├── docker-compose.yml          # 一键部署
├── .env.example                # 环境变量模板
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI 入口（API + admin + widget）
│   ├── graph.py                # LangGraph 工作流定义
│   ├── state.py                # 共享状态类型
│   ├── core/
│   │   ├── config.py           # 项目配置
│   │   ├── auth.py             # 管理后台认证
│   │   ├── memory.py           # 会话记忆（SQLite）
│   │   ├── review.py           # 审核队列（SQLite）
│   │   ├── knowledge_base.py   # 知识库（SQLite）
│   │   ├── unanswered.py       # 未命中问题跟踪
│   │   └── scenic_config.py    # 景区配置
│   ├── agents/
│   │   ├── cs_agent.py         # 客服智能体
│   │   ├── ticket_agent.py     # 票务智能体
│   │   ├── study_agent.py      # 研学智能体
│   │   ├── content_agent.py    # 内容运营智能体
│   │   ├── ecommerce_agent.py  # 文创电商智能体
│   │   └── admin_agent.py      # 管理后台智能体
│   └── tools/
│       ├── api_tools.py        # 工具函数
│       └── crewai_tools.py     # CrewAI @tool 包装
├── static/
│   ├── index.html              # 对话测试页面
│   ├── admin/
│   │   ├── login.html          # 管理后台登录
│   │   └── dashboard.html      # 管理后台仪表盘
│   └── widget/
│       └── chat.html           # 嵌入式对话组件
└── docs/
    ├── 产品规划书_三项目.md
    ├── devlog-phase1.md
    └── devlog-phase2.md
```

---

## 部署到客户环境

详见 [DEPLOY.md](DEPLOY.md) — 面向非技术人员的部署指引（含常见问题排查）。

---

## 项目背景

本项目基于真实的文旅行业需求设计，面向中小型景区（博物馆、文化景点、主题园区），解决以下痛点：

- 线上线下服务触点分散，缺乏统一的 AI 服务能力
- 人工客服成本高、响应慢、无法 24 小时在线
- 通用大模型问答幻觉多，不懂景区业务
- 运营数据分析依赖人工，效率低

---

## 许可证

MIT License
