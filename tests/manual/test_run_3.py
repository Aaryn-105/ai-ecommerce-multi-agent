
import asyncio, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from backend.routers.chat import chat, _ensure_agents_registered
from backend.models.schemas import ChatRequest
from backend.core.database import init_db, SessionLocal
async def test():
    _ensure_agents_registered()
    init_db()
    db = SessionLocal()
    try:
        req = ChatRequest(message='帮我分析电子产品类目的选品机会')
        t0 = time.time()
        resp = await chat(req, db)
        elapsed = time.time() - t0
        plan_n = len(resp.plan or [])
        sec_n = len(resp.sections or {})
        keys = list((resp.sections or {}).keys())
        print('Run 3: ' + str(round(elapsed,1)) + 's, plan=' + str(plan_n) + ', sections=' + str(sec_n) + ', keys=' + str(keys))
    finally:
        db.close()
asyncio.run(test())
