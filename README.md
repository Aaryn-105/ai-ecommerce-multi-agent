# AI E-Commerce Multi-Agent System

智能电商选品分析多智能体系统，基于 FastAPI + React + LangGraph 构建。

## 系统架构

```
用户输入 → 意图识别 → 编排器（Plan & Execute）→ 7个领域智能体 → 报告组装
```

**核心智能体：**
| 智能体 | 功能 | LLM需求 |
|--------|------|---------|
| 意图识别 | 判断用户查询是否为电商相关 | 规则优先，LLM降级 |
| 产品分析 | 多维度评分、排序、筛选 | 纯代码 |
| 趋势预测 | 时间序列分析、增长识别 | 纯代码 |
| 竞品分析 | 类目内基准对比 | 纯代码 |
| 营销文案 | 标签、描述、社交媒体文案生成 | **需 LLM** |
| 库存管理 | 补货建议、库存健康评估 | 纯代码 |
| 定价策略 | 三因子定价模型、价格区间 | 纯代码 |
| 促销规划 | 促销类型推荐、折扣计算 | 纯代码 |

## 环境要求

- **Python** >= 3.13（[下载](https://www.python.org/downloads/)）
- **Node.js** >= 22（[下载](https://nodejs.org/)）
- **pnpm** >= 9（`npm install -g pnpm`）
- **OpenAI API Key**（用于营销文案智能体，可选）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Aaryn-105/ai-ecommerce-multi-agent.git
cd ai-ecommerce-multi-agent
```

### 2. 环境配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY（可选）
```

### 3. 启动后端

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

### 4. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端页面：http://localhost:5173

### 5. 运行测试

```bash
pytest tests/ -v --timeout=120
```

## Docker 部署

### 前提条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.0+
- Docker Compose v2+

### 构建并启动

```bash
# 构建镜像
docker compose build

# 启动服务（后台运行）
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端页面 | http://localhost | React SPA |
| 后端 API | http://localhost:8000 | FastAPI |
| API 文档 | http://localhost:8000/docs | Swagger UI |

### 查看容器状态

```bash
docker compose ps
docker compose stats
```

### 完整清理

```bash
docker compose down -v --rmi all --remove-orphans
```

## 项目结构

```
├── backend/
│   ├── agents/          # 智能体（每个子目录一个）
│   │   ├── orchestrator/    # 编排器（Plan & Execute）
│   │   ├── intent_recognition/  # 意图识别
│   │   ├── product_analysis/    # 产品分析
│   │   ├── trend_forecast/      # 趋势预测
│   │   ├── competitor_analysis/ # 竞品分析
│   │   ├── marketing_copy/      # 营销文案
│   │   ├── inventory/          # 库存管理
│   │   ├── pricing/            # 定价策略
│   │   └── promotion/          # 促销规划
│   ├── core/            # 配置、数据库
│   ├── models/          # 数据模型、Schema
│   ├── routers/         # API 路由
│   └── services/        # 公共服务
├── frontend/
│   ├── src/
│   │   ├── api/         # API 客户端
│   │   ├── components/  # React 组件
│   │   └── types.ts     # TypeScript 类型
│   └── nginx.conf       # Nginx 配置（Docker）
├── tests/               # 测试用例
├── data/                # SQLite 数据库
├── .env.example         # 环境变量模板
├── docker-compose.yml   # Docker 编排
├── Makefile             # 常用命令
└── AGENTS.md            # 贡献指南
```