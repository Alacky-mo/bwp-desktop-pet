"""把剧情脚本里的台词抽成一张表：谁说的、说了什么、绑哪条语音。

scenerio.npk 里那 766 个剧情脚本是 NScripter 那一类的写法 —— `[speaker_name name="不知火"]`
开一句、`[say bank_name=... event_name=...]` 挂语音、正文自己一行、`[l]` 是换行 `[cm]` 是收消息。
`[cm]` 之后再说正文的就是旁白，所以说话人跟着 [cm] 清掉，不能一路挂到最后。

用法: python scenerio_lines.py <脚本目录> <out.tsv>
产物: TSV 每行 文件<TAB>说话人<TAB>台词<TAB>bank<TAB>event
"""
import os, re, sys

SPK = re.compile(r'\[speaker_name name="([^"]*)"\]')
SAY = re.compile(r'\[say bank_name=(\S+?) event_name=(\S+?)\]')


def parse(path):
    spk, bank, ev, out = '', '', '', []
    for raw in open(path, encoding='utf-8', errors='replace').read().splitlines():
        line = raw.strip()
        if not line:
            continue
        m = SPK.search(line)
        if m:
            spk = m.group(1); continue
        m = SAY.search(line)
        if m:
            bank, ev = m.group(1), m.group(2); continue
        if line == '[cm]':
            spk, bank, ev = '', '', ''      # 收了消息，下一条正文没挂名字就是旁白
            continue
        if line.startswith('['):
            continue
        out.append((spk or '旁白', line.replace('[l]', '').strip(), bank, ev))
        bank, ev = '', ''      # 一条 [say] 只配挂在一句上，别漏给同一段的下一句
    return out


def main(src, out_tsv):
    rows = []
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('.txt'):
            continue
        rows.extend((fn, *r) for r in parse(os.path.join(src, fn)) if r[1])
    with open(out_tsv, 'w', encoding='utf-8') as fh:
        fh.write('文件\t说话人\t台词\tbank\tevent\n')
        for r in rows:
            fh.write('\t'.join(r) + '\n')
    who = {}
    for _, spk, *_ in rows:
        who[spk] = who.get(spk, 0) + 1
    print(f'{len(rows)} 句台词，{len(who)} 个说话人 -> {out_tsv}')
    for k, v in sorted(who.items(), key=lambda kv: -kv[1])[:12]:
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
