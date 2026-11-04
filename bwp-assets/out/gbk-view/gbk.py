# 把 GBK 那两个源文件导成 UTF-8 的视图好让 Agent 读; 顺便验锚点命中几次
# 用法: python gbk.py dump <目标.cs> <视图.txt>   |   python gbk.py count <目标.cs> <锚点.txt>
import sys


def dump(target, view):
    text = open(target, 'rb').read().decode('gbk')
    open(view, 'w', encoding='utf-8', newline='').write(text)
    print(f'OK {target} -> {view}  {len(text.splitlines())} 行')


def count(target, anchor_file):
    text = open(target, 'rb').read().decode('gbk')
    anchor = open(anchor_file, encoding='utf-8').read()
    if anchor.endswith('\n'):
        anchor = anchor[:-1]
    anchor = '\r\n' + anchor.replace('\r\n', '\n').replace('\n', '\r\n')
    print(f'命中 {text.count(anchor)} 次')


{'dump': dump, 'count': count}[sys.argv[1]](*sys.argv[2:4])
