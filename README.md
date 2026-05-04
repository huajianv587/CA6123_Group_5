# Customer Service Agentic RAG

准生产版电商客服 Agentic RAG 演示项目，包含 FastAPI 后端、React 前端、数据库持久化、数据生成、RAG、人工升级和质量安全层。

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example ..\.env
python scripts/seed_data.py
python demo.py --test
uvicorn backend.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认 API 地址为 `http://localhost:8000`。如需连接 Supabase，请在外层 `.env` 中配置：

```env
DATABASE_URL=postgresql+psycopg://postgres:password@db.xxxxx.supabase.co:5432/postgres
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
APP_ENV=development
```

如果没有配置 `DATABASE_URL`，系统会使用本地 `sqlite:///./demo.db`，便于离线演示。

## Structure

```text
backend/              FastAPI API
frontend/             React + Vite UI
scripts/seed_data.py  Demo data generator
orchestration/        Router + orchestrator
agents/               Order, logistics, refund, complaint agents
knowledge/            FAQ, retriever, indexer
quality_safety/       PII redaction, guardrails, HITL, evaluation
shared/               Config, DB models, store
integrations/         OpenAI adapter
```

## API

- `POST /api/chat`
- `GET /api/sessions/{session_id}`
- `GET /api/orders/{order_id}`
- `GET /api/admin/metrics`
- `GET /api/admin/escalations`
- `POST /api/admin/escalations/{id}/resolve`

## Data

`python scripts/seed_data.py` 会重复生成：

- 20 customers
- 100 orders
- shipments and shipment events
- refund requests
- complaint records
- 50 knowledge documents

## Tests

```bash
pytest
```
