import httpx, json, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://localhost:8000'
timeout = httpx.Timeout(180.0)

print('=== Diagnostic (180s timeout) ===')
t0 = time.time()
try:
    r = httpx.post(f'{BASE}/api/v1/chat', timeout=timeout,
        json={'message': '\u5e2e\u6211\u5206\u6790\u7535\u5b50\u4ea7\u54c1\u7c7b\u76ee\u7684\u9009\u54c1\u673a\u4f1a'})
    print(f'Elapsed: {time.time()-t0:.1f}s, Status: {r.status_code}')
    data = r.json()
    sections = data.get('sections', {})
    summary = data.get('executive_summary', '')
    print(f'Sections count: {len(sections)}')
    print(f'Exec summary: {summary}')
    print(f'Reply (first 500 chars):')
    print(data.get('reply', '')[:500])
except Exception as e:
    print(f'ERROR after {time.time()-t0:.1f}s: {e}')