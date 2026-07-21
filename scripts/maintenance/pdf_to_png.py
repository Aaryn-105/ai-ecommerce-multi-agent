import fitz, os
src = r'D:\新建文件夹\verify_export_43.pdf'
doc = fitz.open(src)
print(f'Pages: {doc.page_count}')
out_dir = r'D:\新建文件夹\verify_pages'
os.makedirs(out_dir, exist_ok=True)
for i in range(doc.page_count):
    page = doc.load_page(i)
    pix = page.get_pixmap(dpi=120)
    out = os.path.join(out_dir, f'page_{i+1}.png')
    pix.save(out)
    # 输出页面文本前200字符
    text = page.get_text()[:200].replace(chr(10), ' | ')
    print(f'Page {i+1}: {pix.width}x{pix.height}  text-preview={text[:160]}')
