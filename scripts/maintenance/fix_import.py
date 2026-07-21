p = r'D:\新建文件夹\New_Goods_Project 2\backend\services\report_export.py'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()
old = '    from reportlab.platypus import Spacer\n\n    if agent_key == "product_analysis":'
new = '    from reportlab.platypus import Paragraph, Spacer\n\n    if agent_key == "product_analysis":'
assert old in s, 'old not found'
assert s.count(old) == 1, 'old found %d times' % s.count(old)
s = s.replace(old, new, 1)
with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print('FIXED')
