# GBK 源文件的安全改法: Read/Edit/Write 会把 DeskSpine 的 Program.cs / ConfigForm.cs 里的中文写坏
# 用法: python apply.py 目标.cs 锚点.txt 替换.txt
# 锚点和替换用 UTF-8 写, 开头会自动补一个换行, 免得 12 空格缩进的锚点命中 16 空格的那一行
import sys

target, find_file, repl_file = sys.argv[1:4]
text = open(target, 'rb').read().decode('gbk')


def clip(path):
    s = open(path, encoding='utf-8').read()
    if s.endswith('\n'):
        s = s[:-1]
    return '\r\n' + s.replace('\r\n', '\n').replace('\n', '\r\n')


find, repl = clip(find_file), clip(repl_file)
hits = text.count(find)
assert hits == 1, f'锚点命中 {hits} 次, 要求 1 次: {find_file}'
open(target, 'wb').write(text.replace(find, repl).encode('gbk'))
print(f'OK {target}')
