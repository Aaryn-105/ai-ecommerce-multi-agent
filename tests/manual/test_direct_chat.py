import asyncio, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Test the chat endpoint via direct import (no uvicorn)
import sys
sys.path.insert(0, r'D:/新建文件夹/New_Goods_Project 2')

async def test():
    from backend.routers.chat import chat, _ensure_agents_registered
    from backend.models.schemas import ChatRequest
    from backend.core.database import init_db, SessionLocal
    from backend.services.conversation import ConversationService
    from backend.models.conversation import Conversation
    from sqlalchemy.orm import Session

    _ensure_agents_registered()
    print(f'Registered: {len(__import__("backend.agents.registry", fromlist=["AgentRegistry"]).AgentRegistry.list_agents())} agents')

    init_db()
    db = SessionLocal()
    try:
        req = ChatRequest(message='帮我分析电子产品类目的选品机会')
        t0 = time.time()
        resp = await chat(req, db)
        print(f'Elapsed: {time.time()-t0:.1f}s')
        sections = resp.sections or {}
        plan = resp.plan or []
        print(f'Plan steps: {len(plan)}')
        print(f'Sections: {len(sections)}')
        for k in sections:
            print(f'  - {k}')
        print(f'Reply (first 200): {resp.reply[:200]}')
    finally:
        db.close()

asyncio.run(test())