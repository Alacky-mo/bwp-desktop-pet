"""从 npk 导出的 plist（TexturePacker 的 XML）里建「页 → region 矩形」的名册。

gui.npk 的 TOC 加密，图片 blob 全没有名字；但同一个包里带着几百份 plist，写着
realTextureFileName 和每个 region 的 rect。有了这份名册，把 plist 配到 blob 上之后
就能按资源名出图，命名不用肉眼猜。

用法: python gui_plist_index.py <plist目录> [out.json]
    例: python npk_text.py npk/gui.npk t/gui_text && python gui_plist_index.py t/gui_text out/gui_atlas.json
产物: {'meta': {xml名: {page,w,h,n}}, 'regions': {xml名: {资源名: {x,y,w,h,sw,sh,rot}}}}
      键用 xml 文件名而不是页名——同名页会被多个 plist 版本引用，页名不唯一。
"""
import os, re, sys, json, glob, plistlib

RECT = re.compile(r'\{\s*\{\s*(-?\d+)\s*,\s*(-?\d+)\s*\}\s*,\s*\{\s*(\d+)\s*,\s*(\d+)\s*\}\s*\}')
SIZE = re.compile(r'\{\s*(\d+)\s*,\s*(\d+)\s*\}')

# 这个包里两种 plist 方言混着：TexturePacker 的 textureRect/spriteSize/spriteSourceSize，
# 和 cocos2d 的 frame/size/sourceSize。只读前一种会把后一种的 region 全当成「没有矩形」丢掉。
KEY = {
    'rect': ('textureRect', 'frame'),
    'src': ('spriteSourceSize', 'sourceSize'),
    'spr': ('spriteSize', 'size'),
}


def pick(fr, what):
    for k in KEY[what]:
        if k in fr:
            return fr[k]
    return ''


def one(path):
    """一份 plist -> (meta, regions)；不是 atlas 的返回 None。

    目录里混着游戏自己的 `<FxGroup>` / `<Root>` 材质 XML（npk_text 按后缀发的 .xml），
    它们不是良构 plist，解析会抛，按「不是 atlas」跳过就行。
    """
    try:
        p = plistlib.load(open(path, 'rb'))
    except Exception:
        return None
    if not isinstance(p, dict):
        return None
    md = p.get('metadata') or {}
    page = md.get('realTextureFileName') or md.get('textureFileName')
    if not page or 'frames' not in p:
        return None
    m = SIZE.search(md.get('size', ''))
    if not m:
        return None
    meta = dict(page=page, w=int(m.group(1)), h=int(m.group(2)), n=len(p['frames']))
    regs = {}
    for name, fr in p['frames'].items():
        r = RECT.search(pick(fr, 'rect'))
        if not r:
            continue
        src = SIZE.search(pick(fr, 'src'))
        spr = SIZE.search(pick(fr, 'spr'))
        regs[name] = dict(x=int(r.group(1)), y=int(r.group(2)),
                          w=int(r.group(3)), h=int(r.group(4)),
                          sw=int(src.group(1)) if src else 0,
                          sh=int(src.group(2)) if src else 0,
                          rot=bool(fr.get('textureRotated', fr.get('rotated', False))))
    return meta, regs


def build(plist_dir):
    meta, regions, skipped = {}, {}, 0
    for path in sorted(glob.glob(os.path.join(plist_dir, '*.xml'))):
        got = one(path)
        if got is None:
            skipped += 1
            continue
        key = os.path.basename(path)
        meta[key], regions[key] = got
    print(f'{plist_dir}: plist {len(meta)} 份，region {sum(len(v) for v in regions.values())} 个，'
          f'非 atlas 或读不出 {skipped} 份，rotated 的 {sum(1 for r in regions.values() for v in r.values() if v["rot"])} 个')
    return dict(meta=meta, regions=regions)


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'out', 'gui_atlas.json')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(build(src), open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'-> {dst}')
