p = r'D:\新建文件夹\New_Goods_Project 2\backend\services\report_export.py'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()

# Remove all `chart.bars[X].barWidth = N` lines (unsupported in current reportlab)
import re
before = s.count('barWidth')
s = re.sub(r'\s*chart\.bars\[\d\]\.barWidth\s*=\s*\d+\n', '\n', s)
# Also remove the line that just sets the width and leave a blank-free version
s = re.sub(r'\n\s*\n(\s*chart\.groupSpacing)', r'\n\1', s)
print('Removed %d barWidth lines' % before)
with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
