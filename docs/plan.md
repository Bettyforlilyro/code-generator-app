# AI 零代码应用生产平台 — 开发计划

## 目标

实现前后端分离的 AI 零代码应用生产平台。用户输入自然语言描述后，AI Agent 自动完成：

素材搜集 → 规格生成 → 代码生成 → 质量检查 → 构建 → 打包 → 部署

最终生成可访问的 Web 应用。

## 技术栈

- **后端**：Flask + Python 3.11
- **Agent 框架**：LangChain + LangGraph
- **LLM**：OpenAI（可替换为其他模型）
- **搜索**：DuckDuckGo / Tavily（并发查询）
- **构建产物**：MVP 先支持纯静态 HTML/CSS/JS，后续支持 Vite / Docker
- **任务状态**：MVP 使用内存字典，后续接入 Redis / Celery
- **前端**：独立项目（Vue / React 可选），通过 HTTP 调用后端 API

## 目录结构（初始化）

```
ai-app-platform/
├── backend/                   # Flask + LangGraph
│   ├── app/
│   │   ├── api/               # REST 路由
│   │   ├── services/
│   │   │   ├── graph/         # LangGraph 工作流
│   │   │   │   └── nodes/     # 各阶段节点
│   │   │   ├── tools.py       # 搜索、执行工具
│   │   │   └── prompts.py     # LLM 提示词
│   │   ├── models.py
│   │   ├── config.py
│   │   └── __init__.py
│   ├── tests/
│   ├── requirements.txt
│   └── run.py
├── frontend/                  # 独立前端
│   ├── src/
│   ├── public/
│   └── package.json
├── generated_apps/            # 已部署应用
├── packages/                  # zip 产物
├── docs/
│   └── plan.md
├── .env.example
├── .gitignore
└── README.md
```

## 开发阶段

1. **架构设计**：定义 `AgentState`、节点函数、条件分支；确定生成物格式。
2. **后端骨架**：Flask 应用工厂、配置、Pydantic 模型、REST API 路由。
3. **LangGraph 工作流**：
   - `init_job`：生成 ID，初始化任务。
   - `gather_materials`：并发搜索素材。
   - `define_spec`：LLM 生成应用规格。
   - `generate_code`：LLM 生成文件清单。
   - `qa_check`：必要文件检查 + LLM 审查。
   - `build_project`：写入构建目录并生成 `dist`。
   - `package_project`：打包 zip。
   - `deploy_project`：部署到 `generated_apps/<app_id>`。
4. **工具集成**：LLM 调用、DuckDuckGo 搜索、Shell 命令执行。
5. **前端开发**：提交表单、轮询/SSE 查看状态、展示访问链接。
6. **测试与日志**：pytest 单元测试、错误处理、日志记录。
7. **扩展**：Docker 打包、云部署、数据库持久化、更复杂生成目标。

## 依赖（详见 `backend/requirements.txt`）

- `flask`
- `python-dotenv`
- `pydantic`
- `langchain`
- `langchain-openai`
- `langchain-community`
- `langgraph`
- `openai`

## 风险与注意

- 需要可用的 OpenAI API Key（或替换为其他模型）。
- 网络搜索可能失败，节点需降级处理。
- LLM 输出不稳定，需 JSON 解析兜底与错误处理。
- MVP 使用内存任务状态，服务重启后任务丢失。
