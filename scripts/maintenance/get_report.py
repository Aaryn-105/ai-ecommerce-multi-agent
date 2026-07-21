import json, urllib.request, urllib.error
req = urllib.request.Request('http://localhost:8000/api/v1/report/43', method='GET')
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode('utf-8'))
        sections = data.get('sections', {})
        agent_sections = sections.get('_agent_sections', {})
        print(f'Agent sections: {list(agent_sections.keys())}')
        for name, sec in agent_sections.items():
            if isinstance(sec, dict):
                print(f'  {name}: keys={list(sec.keys())[:8]}')
                if 'summary' in sec:
                    print(f'    summary: {sec["summary"][:120]}')
                # 检查是否有数据可以画图
                data_field = sec.get('data') or sec.get('products') or sec.get('items') or {}
                if isinstance(data_field, list):
                    print(f'    data list len: {len(data_field)}')
                elif isinstance(data_field, dict):
                    print(f'    data dict keys: {list(data_field.keys())[:6]}')
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code, e.reason)
    print(e.read().decode('utf-8', errors='replace'))
