import json, urllib.request, urllib.error, time
# 导出report 43为PDF
body = json.dumps({'report_id': 43, 'format': 'pdf'}).encode('utf-8')
req = urllib.request.Request(
    'http://localhost:8000/api/v1/report/export',
    data=body,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
        elapsed = time.time() - t0
        # 保存到文件
        out_path = r'D:\新建文件夹\verify_export_43.pdf'
        with open(out_path, 'wb') as f:
            f.write(data)
        print(f'Export OK: {len(data)} bytes  elapsed={elapsed:.1f}s  path={out_path}')
        # 检查文件签名
        if data[:4] == b'%PDF':
            print('Signature: valid PDF')
        else:
            print(f'Signature: {data[:8]!r}')
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code, e.reason)
    body_err = e.read().decode('utf-8', errors='replace')
    print(body_err[:500])
except Exception as e:
    print('Error:', type(e).__name__, e)
