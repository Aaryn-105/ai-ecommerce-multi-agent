import json, urllib.request, urllib.error
req = urllib.request.Request('http://localhost:8000/api/v1/report/', method='GET')
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode('utf-8'))
        reports = data if isinstance(data, list) else data.get('items', data.get('reports', []))
        print(f'Total reports: {len(reports)}')
        for rep in reports[:10]:
            rid = rep.get('id')
            title = rep.get('title','')[:50]
            created = rep.get('created_at','')
            sections = rep.get('sections') or {}
            print(f'id={rid}  title={title}  created={created}  sections={len(sections)}')
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code, e.reason)
    print(e.read().decode('utf-8', errors='replace'))
except Exception as e:
    print('Error:', type(e).__name__, e)
