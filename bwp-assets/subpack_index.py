"""Summarise what the game's download manifest actually offers.

subpack_version.json is the channel server's list of every downloadable unit. Names are the
only place the game's own asset taxonomy survives, so grouping them answers "does X exist"
without having to guess resource-name hashes.
usage: python subpack_index.py [manifest]
"""
import collections
import json
import re
import sys
from pathlib import Path

KEYWORD = re.compile(
    r'touxiang|avatar|icon|head|portrait|frame|medal|badge|toux|skin|room|house|courtyard|'
    r'tingyuan|zhuye|home|lobby|main|spine|live', re.I)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else 'meta/subpack_version.json')
    data = json.loads(path.read_text(encoding='utf-8', errors='replace'))
    # a few entries are bare version strings rather than {type,size,...} records
    data = {k: v if isinstance(v, dict) else {'type': 'plain'} for k, v in data.items()}

    lines = []
    groups = collections.defaultdict(list)
    for k, v in data.items():
        groups[re.sub(r'\d+', '#', k)].append((k, v))
    for g, its in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        types = sorted({str(v.get('type', '?')) for _, v in its})
        size = sum(int(v.get('size', 0) or 0) for _, v in its)
        lines.append(f'{g:32s} {len(its):4d}  {"/".join(types):9s} {size/1e6:8.1f}MB  ex={its[0][0]}')

    lines.append('')
    lines.append('--- names matching avatar/home/live keywords ---')
    for k, v in sorted(data.items()):
        if KEYWORD.search(k):
            lines.append(f'{k:40s} {v.get("type","?"):9s} {int(v.get("size",0) or 0)/1e6:8.2f}MB')

    text = '\n'.join(lines)
    Path('out/subpack_index.txt').write_text(text, encoding='utf-8')
    print(f'{len(groups)} name patterns, {len(data)} units -> out/subpack_index.txt')


if __name__ == '__main__':
    main()
