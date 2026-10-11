# AI 零代码网页应用生成平台

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.1-lightgrey.svg)
![LangChain](https://img.shields.io/badge/LangChain-1.3-15803D.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-AE560E.svg)
![Vue](https://img.shields.io/badge/Vue-3.5-42b883.svg)

> 通过对话快速创建网页应用，支持实时预览、代码编辑与一键部署。

---

## 📖 简介

本项目是一个 **AI 驱动的零代码网页应用生成平台**。用户只需通过自然语言描述需求，系统即可自动完成：

- 🧠 需求理解与任务拆解
- 📝 多文件代码生成（HTML / Vue / JS / CSS）
- 🖼️ 素材智能搜索与文生图（Logo、封面图）
- 🧪 自动构建验证（Node 构建 + 静态托管）
- 👀 生成结果的实时预览与源码下载

后端基于 **LangGraph** 构建多 Agent 协作工作流，前端采用 Vue 3 + Ant Design Vue 打造现代化交互界面。

---

## 🎯 功能特性

- **对话式生成**：用一句话描述你的想法，AI 自动生成可用的网页应用
- **多轮迭代**：生成后可继续对话修改、补充功能，持续演进
- **实时预览**：内置浏览器预览面板，所见即所得
- **代码可编辑**：支持查看和手动修改生成的代码文件
- **一键部署**：生成的应用可独立部署，获得可访问的 URL
- **用户体系**：注册/登录、作品管理（查看、删除、部署）
- **封面截图**：自动为生成的应用生成封面图（可选）

---

## 📋 技术栈

### 后端
| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11.13 |
| Web 框架 | Flask 3.1.3 |
| AI 框架 | LangChain 1.3 + LangGraph 1.2 |
| LLM | 通义千问系列（OpenAI 兼容接口） |
| 数据库 | PostgreSQL + SQLAlchemy |
| 认证 | JWT (PyJWT) |
| API 文档 | Flasgger (Swagger) |
| ORM 迁移 | Flask-Migrate (Alembic) |

### 前端
| 组件 | 技术 |
|------|------|
| 框架 | Vue 3.5 + TypeScript |
| 构建工具 | Vite 7 |
| UI 库 | Ant Design Vue 4 |
| 状态管理 | Pinia 3 |
| 路由 | Vue Router 4 |

### 基础设施
- Nginx（生产反向代理 + 静态托管）
- Node.js ≥ 18（前端构建）
- easyimages 2.0（本地图床，可选自实现）
- Chrome 浏览器（封面截图功能，可选）

---

## 📂 项目结构

```
code-generator-app/
├── backend/                    # Flask 后端
│   ├── app/
│   │   ├── api/v1/             # REST API 路由
│   │   │   ├── code_generate_api/   # 代码生成接口
│   │   │   ├── app_management/      # 应用管理接口
│   │   │   └── user_management/     # 用户接口
│   │   ├── common/             # 通用枚举、异常、工具
│   │   ├── extensions/         # 扩展实例（DB 等）
│   │   ├── middleware/         # CORS、限速、日志
│   │   ├── models/             # SQLAlchemy 数据模型
│   │   ├── schemas/            # Pydantic 请求/响应 schema
│   │   ├── services/
│   │   │   ├── ai_common/      # LLM 通用封装、Tools
│   │   │   ├── graph/          # LangGraph 工作流核心
│   │   │   └── prompts/        # 所有提示词模板
│   │   ├── run.py              # Flask 启动入口
│   │   └── config.py           # 配置加载
│   ├── migrations/             # Alembic 数据库迁移
│   ├── tests/                  # Pytest 单元测试
│   └── requirements.txt
├── frontend/                   # Vue 3 前端
│   ├── .env.development
│   ├── .env.production
│   └── package.json
├── docs/                       # 设计文档与流程图
└── .env.example                # 环境变量模板
```

---

## 🚀 快速开始（本地开发）

### 1. 环境准备

- Python 3.11.13+
- Node.js 18+
- PostgreSQL 14+

### 2. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv
# Windows 激活：
venv\Scripts\activate
# Linux/macOS 激活：
# source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板并填写
cp ../.env.example ../.env
# 编辑 .env，至少配置：
#   - SECRET_KEY / REFRESH_SECRET_KEY（JWT）
#   - DB_*（PostgreSQL 连接）
#   - MODEL_*（通义千问 API Key & 模型）
#   - IMAGE_BED_*（图床，可选本地部署 easyimages）

# 初始化数据库
flask db upgrade

# 启动 Flask 开发服务器（默认 http://127.0.0.1:5000）
export FLASK_APP=backend.app.run:app
python -m backend.app.run
```

> 💡 Windows PowerShell 请使用 `$env:FLASK_APP = "backend.app.run:app"`

### 3. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 配置开发环境 .env.development（默认已指向 http://127.0.0.1:5000/api）
# 启动开发服务器（默认 http://127.0.0.1:5173）
npm run dev
```

打开浏览器访问 [http://127.0.0.1:5173](http://127.0.0.1:5173) 即可使用。

---

## ⚙️ 配置说明

所有配置通过项目根目录的 `.env` 文件管理（参考 `.env.example`）。

### 核心变量速查

| 分类 | 变量 | 说明 |
|------|------|------|
| **Flask** | `FLASK_DEBUG` | 调试模式，生产环境设为 `False` |
| | `FLASK_HOST` / `FLASK_PORT` | 监听地址与端口 |
| | `SECRET_KEY` / `REFRESH_SECRET_KEY` | JWT 签名密钥，**务必换成随机长字符串** |
| **数据库** | `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME` | PostgreSQL 连接信息 |
| **LLM 生成** | `MODEL_OPENAI_COMPATIBLE_BASE_URL` | 通义千问兼容接口地址 |
| | `MODEL_API_KEY` | 通义千问 API Key |
| | `ROUTER_MODEL_OPENAI_COMPATIBLE` | 轻量路由模型（推荐 `qwen-flash`） |
| | `CODE_GENERATOR_MODEL_EASY_OPENAI_COMPATIBLE` | 简单任务代码模型（推荐 `qwen-plus` / `qwen3.7-plus`） |
| | `CODE_GENERATOR_MODEL_COMPLEX_OPENAI_COMPATIBLE` | 复杂任务代码模型（推荐 `qwen-max`） |
| **文生图** | `TONGYI_DASHSCOPE_BASE_URL` / `TONGYI_IMAGE_GEN_API_KEY` / `TONGYI_IMAGE_GEN_MODEL` | 通义图像生成配置 |
| **图床** | `IMAGE_BED_URL` / `IMAGE_BED_TOKEN` | 图片上传接口；也可修改 `backend/app/common/utils/external/upload_image.py` 自行实现 |
| **本地路径** | `GENERATE_ROOT` | 生成项目的根目录 |
| | `DEFAULT_ROOT` | 已部署应用的静态文件目录 |
| | `SCREENSHOT_DIR` | 截图临时目录 |

### 模型选择建议

> 代码模型需要支持 **JSON_SCHEMA**（结构化输出）。若你使用的模型不支持，请在 `backend/app/services/prompts/` 对应提示词文件中，让模型显式输出 JSON 格式，并在解析层做兼容。

---

## 🌐 生产部署（Ubuntu 22.04）

### 前置依赖

```bash
sudo apt update
sudo apt install -y nginx postgresql nodejs npm

# 建数据库
# 1. 启动 PostgreSQL
sudo service postgresql start

# 2. 切换到 postgres 超级用户
sudo -u postgres psql

# 3. 在 psql 里手动创建数据库 + 用户
CREATE USER your_username WITH PASSWORD 'your_password';
CREATE DATABASE code_generator OWNER your_username;
GRANT ALL PRIVILEGES ON DATABASE code_generator TO your_username;
```

可选：
- Chrome 浏览器：仅影响封面截图功能
- [easyimages2.0](https://github.com/icret/EasyImages2.0)：本地图床，用于上传截图/Logo
  - 若不想部署，可修改 `backend/app/common/utils/external/upload_image.py` 按注释实现自定义上传逻辑

### Step 1 — 部署后端

```bash
# 创建目录
sudo mkdir -p /home/projects/python
cd /home/projects/python
sudo git clone <your_repo> code-generator-app

cd code-generator-app/backend

# Python 3.11
wget https://www.python.org/ftp/python/3.11.13/Python-3.11.13.tgz
tar xf Python-3.11.13.tgz && cd Python-3.11.13
./configure && make -j$(nproc) && sudo make altinstall
cd ..

# 虚拟环境 + 依赖
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置 .env
cp ../.env.example ../.env
vim ../.env

# 设置 Flask 入口环境变量（flask-migrate 需要）
# 也可以写入 .env 文件，flask-dotenv 会自动加载
export FLASK_APP=backend.app.run:app

# 首次迁移：生成所有表（基于 migrations 目录已有的版本）
# 如果 migrations 目录为空（首次使用），先执行：
#   flask db init        # 初始化 alembic
#   flask db migrate -m "init tables"   # 从 model 生成迁移脚本
flask db upgrade
```

创建 **systemd** 服务 `sudo vim /etc/systemd/system/codegen.service`：

```ini
[Unit]
Description=Code Generator App Backend
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/home/projects/python/code-generator-app
# FLASK_APP 环境变量，flask-migrate 等 CLI 依赖它
Environment=FLASK_APP=backend.app.run:app
# 把 venv 的 bin 放到 PATH，方便直接调用 flask、pytest 等
Environment=PATH=/home/projects/python/code-generator-app/backend/venv/bin
# 用 python -m 方式启动模块，__main__ 会自动执行 backend/app/run.py
ExecStart=/home/projects/python/code-generator-app/backend/venv/bin/python -m backend.app.run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable codegen
sudo systemctl start codegen
sudo systemctl status codegen
```

### Step 2 — 部署前端

```bash
cd frontend
cp .env.development .env.production
vim .env.production   # 改为生产 API 地址

npm install
npm run build

# 将 dist 拷贝到 Nginx 根目录
sudo mkdir -p /var/www/code-generator-app
sudo cp -r dist/* /var/www/code-generator-app/
```

### Step 3 — Nginx 配置

编辑 `/etc/nginx/sites-available/codegen`：

```nginx
server {
    listen 80;
    server_name localhost;

    # 前端（单页应用）
    location / {
        root /var/www/code-generator-app;
        index index.html;
        try_files $uri $uri/ /index.html =404;
    }

    # 后端生成应用的静态资源
    location ~ "^/dist/([A-Za-z0-9]{6})(/.*)?$" {
        rewrite ^/dist(/.*)$ $1 break;
        root /home/projects/python/code-generator-app/generated_apps/deployed;
        try_files $uri/dist$2 $uri/dist/index.html $uri $uri/index.html =404;
    }

    # 后端 API 反向代理
    location /api {
        proxy_pass http://127.0.0.1:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 长连接配置
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;

        # 超时
        proxy_connect_timeout 30s;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/codegen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```


## ❓ 常见问题

### Q1：提示 `ModuleNotFoundError: No module named 'backend'`

确保你在项目根目录下执行命令，并且虚拟环境已激活，flask app环境变量已添加。

### Q2：LLM 返回格式不对，JSON 解析失败

请检查你选用的模型是否支持 **JSON_SCHEMA** 输出。不支持的模型请修改 `backend/app/services/prompts/` 下的对应提示词，显式让模型输出纯 JSON。

### Q3：生成的 Vue 项目部署时报 `npm run build` 失败

后端执行构建时依赖系统的 Node.js，请确认 Node 版本 ≥ 18，且生成的项目里没有用到需要额外 `npm install` 的本地私有包。

### Q4：想换掉 easyimages 图床？

直接修改 `backend/app/common/utils/external/upload_image.py`，文件内注释已经给出实现约定（返回公开可访问的图片 URL）。

### Q5：如何更换模型供应商（非通义）？

代码已统一走 LangChain 的 OpenAI 兼容接口。只要你的模型提供 `/chat/completions` 兼容端点，填入 `.env` 的 `MODEL_OPENAI_COMPATIBLE_BASE_URL` 和 `MODEL_API_KEY` 即可。

---
