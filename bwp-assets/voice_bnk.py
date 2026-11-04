"""读 Wwise sound bank(.bnk): 数出每个语音单元有几句、估每句时长, 并查结构里有没有「表情」分组。

用法:
  python voice_bnk.py list <bank 或目录> [...]        每个 bank 一行: media 数/对象分布/估总时长/分组
  python voice_bnk.py parse <bank 或目录>... -o out/voice_clips.tsv
        每条语音一行 + 每个单元一行汇总, 末尾给判据(见 verdict)
  python voice_bnk.py slots <目录> [--cat emotion]
        查「各包之间有没有共用同一个 event/分组 id」—— 有共用才谈得上「按表情分槽」

现场事实(2026-10-28 实测): 百闻牌语音 = Wwise 2021 一代 bank(BKHD version=125),
media 是 WAV 壳包的压缩流: wFormatTag=0xFFFF、单声道、采样率按条不同(24k/32k/44.1k 都见过)、
平均字节率也按条不同(实测 3.4k~8.6k B/s), 头里没有 OggS/vorbis/Opus/FLAC 魔数 —— 是 Wwise 自家的
分帧, 所以能数出几句、能按 数据段/平均字节率 估时长, 但本机没有 Wwise 解码器就播不出声。
bank 里**没有任何字符串表**(没有 STNG/PLTg 段): media/event 只有 32 位数字 id,
名字在游戏侧的触发表里(script.npk 条目非明文, 已确认读不出来, 不去破)。
另有少数语音的音频不在包里, 而是同目录下的 <media id>.wem(传记包最常见, 见 parse 的 external 清单)。
"""
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

SECTIONS = ('BKHD', 'DIDX', 'DATA', 'HIRC', 'STNG', 'PLTg')

# HIRC 对象类型号是从这块 bank 里数出来的(2026-10-28 实测, 与 Wwise 文档不保证一致):
# 7 是媒体容器, 5 只出现在战斗包和共享包里、也当语音的父用, 类名没法从包内证实(bank 里没有字符串表)。
SOUND, ACTION, EVENT, TYPE5, GROUP = 2, 3, 4, 5, 7
TYPE_NAME = {SOUND: 'Sound', ACTION: 'Action', EVENT: 'Event', TYPE5: 'type5', GROUP: 'Container'}


def category(stem):
    """vo_battle_146_fanqie -> battle; 非 vo_ 前缀的叫 (其他)。"""
    m = re.match(r'vo_(battle|biography|emotion|street)', stem)
    return m.group(1) if m else '(其他)'


UNIT_RE = re.compile(r'^vo_(battle|biography|emotion|street)(_player)?(?:_(\d+))?(?:_([0-9a-z_]+))?$')


def unit_parts(stem):
    """把单元名拆成 类别/视角/式神数字id/拼音: 语音素材的「谁」只有这一层信息可读。

    vo_battle_player_265_wuchen  -> battle, 玩家, 265, wuchen
    vo_emotion_185_sanmu          -> emotion, 式神, 185, sanmu
    vo_battle_101                 -> battle, 式神, 101, ''(名字里没带拼音)
    vo_emotion                      -> 共享包(不是某个式神的单元)
    """
    m = UNIT_RE.match(stem)
    if not m:
        return None
    cat, player, hid, slug = m.groups()
    return {'cat': cat, 'view': '玩家' if player else '式神', 'id': hid or '', 'slug': slug or '',
            'unit': bool(hid or slug)}


def is_unit(stem):
    """vo_emotion_185_sanmu 这种「一个式神一个包」; vo_emotion 是共享包, 结构不一样。"""
    p = unit_parts(stem)
    return bool(p and p['unit'])


def sections(d):
    """BKHD/DIDX/DATA/HIRC 一路串到底, 返回 [(tag, body)]。"""
    out, off = [], 0
    while off + 8 <= len(d):
        tag = d[off:off + 4].decode('latin1')
        size = struct.unpack_from('<I', d, off + 4)[0]
        end = off + 8 + size
        if end > len(d):
            raise ValueError(f'{tag} 越界: {end} > {len(d)}')
        out.append((tag, d[off + 8:end]))
        off = end
    return out


def media_index(didx):
    """(media id, DATA 内偏移, 字节数)。"""
    return [struct.unpack_from('<III', didx, i * 12) for i in range(len(didx) // 12)]


def objects(hirc):
    """HIRC 对象 = [u8 类型][u32 长度][u32 id][长度-4 字节的体]; 必须正好走完。"""
    cnt = struct.unpack_from('<I', hirc, 0)[0]
    off, out = 4, []
    for _ in range(cnt):
        typ = hirc[off]
        size = struct.unpack_from('<I', hirc, off + 1)[0]
        oid = struct.unpack_from('<I', hirc, off + 5)[0]
        out.append((typ, oid, hirc[off + 9:off + 5 + size]))
        off += 5 + size
    if off != len(hirc) or len(out) != cnt:
        raise ValueError(f'HIRC 没走平: 停在 {off}/{len(hirc)}, 读出 {len(out)}/{cnt}')
    return out


def wav_info(blob):
    """WAV 壳里的声道/采样率/平均字节率/数据段位置和大小 —— 时长 = 数据段 / 平均字节率。

    壳不是一种长度: 表情包里的 media 是 94 字节壳, 战斗包的 media 多了 JUNK + akd 两个块(120 字节),
    所以这里量出来的 start 才是真实壳长, 不写死常数。
    """
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return None
    fmt = data = None
    start = off = 12
    while off + 8 <= len(blob):
        cid = blob[off:off + 4]
        csz = struct.unpack_from('<I', blob, off + 4)[0]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', blob, off + 8)
        elif cid == b'data':
            data, start = csz, off + 8
            break
        off += 8 + csz + (csz & 1)
    if not fmt or data is None:
        return None
    tag, ch, rate, byterate, align, bits = fmt
    return {'tag': tag, 'ch': ch, 'rate': rate, 'byterate': byterate, 'bits': bits,
            'data': data, 'start': start}


class Bank:
    def __init__(self, path):
        self.path = Path(path)
        self.stem = self.path.stem
        self.d = self.path.read_bytes()
        self.secs = dict(sections(self.d))
        self.media = {m[0]: (m[1], m[2]) for m in media_index(self.secs.get('DIDX', b''))}
        self.objs = objects(self.secs['HIRC']) if 'HIRC' in self.secs else []
        self.data = self.secs.get('DATA', b'')
        self.sound_ids = {o for t, o, _ in self.objs if t == SOUND}

    def clips(self):
        """每条 Sound 一行: sound id、它指的 media、父分组 id、字节数、估时长。

        media 不在本包 DIDX 里的算「外部 media」: 音频在设备 wwise 目录下的同名 <media id>.wem
        (189/190 条实测能在设备清单里找到, 见 voice_pull.py wem)。这种包里 Sound 体里的长度字段
        和 .wem 实际大小不一致, 所以包外的一律不报字节数、不估时长。
        """
        rows = []
        for typ, oid, body in self.objs:
            if typ != SOUND:
                continue
            mid = struct.unpack_from('<I', body, 5)[0]
            parent = struct.unpack_from('<I', body, 21)[0]
            rec = self.media.get(mid)
            blen = rec[1] if rec else None
            info = wav_info(self.data[rec[0]:rec[0] + blen]) if rec else None
            rows.append({'sound': oid, 'media': mid, 'media_in_bank': rec is not None,
                         'bytes': blen, 'parent': parent, 'info': info})
        return rows

    def groups(self):
        """按 Sound 自己记的父对象分组(不做启发式猜): 返回 [(父 id, [sound id...])]。"""
        by = {}
        for c in self.clips():
            by.setdefault(c['parent'], []).append(c['sound'])
        return sorted(((k, v) for k, v in by.items()), key=lambda g: -len(g[1]))

    def group_ids(self):
        """能当父用的对象: 容器(7)和 type5 —— 战斗包里一句句语音是挂在 type5 分组上的。"""
        return {o for t, o, _ in self.objs if t in (GROUP, TYPE5)}

    def kinds(self):
        out = {}
        for t, _, _ in self.objs:
            name = TYPE_NAME.get(t, f'type{t}')
            out[name] = out.get(name, 0) + 1
        return dict(sorted(out.items()))

    def seconds(self, clips=None):
        clips = self.clips() if clips is None else clips
        return sum(c['info']['data'] / c['info']['byterate'] for c in clips if c['info'])

    def verdict(self):
        """算得出的判据; one_event_per_sound 只对逐式神包有意义(共享包是多对一)。"""
        clips = self.clips()
        inner = [c for c in clips if c['media_in_bank']]
        n_sound = len(self.sound_ids)
        n_event = sum(1 for t, _, _ in self.objs if t == EVENT)
        groups = self.groups()
        gids = self.group_ids()
        return {
            'unit': is_unit(self.stem),
            'clips': n_sound,
            'external': sum(1 for c in clips if not c['media_in_bank']),
            'one_event_per_sound': n_sound == n_event and n_sound > 0,
            # 包内 media: 数据段长度 + 实测壳长 要等于 DIDX 记的字节数(差 1 是奇数对齐填充)。
            # 全走外部 .wem 的包(inner 为空)没东西可对, 视为通过, 另在报告里数出来。
            'shell_ok': all(c['info'] and c['info']['data'] + c['info']['start']
                            in (c['bytes'], c['bytes'] - 1) for c in inner),
            'sound_in_group': all(k in gids for k, _ in groups),
            'groups': groups,
            'seconds': self.seconds(clips),
        }


def targets(argv):
    out = []
    for a in argv:
        p = Path(a)
        out.extend(sorted(p.glob('*.bnk')) if p.is_dir() else [p])
    return out


def fmt_kinds(k):
    return ' '.join(f'{name}={n}' for name, n in k.items())


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    argv = sys.argv[2:]
    out_path = Path('out/voice_clips.tsv')
    if '-o' in argv:
        i = argv.index('-o')
        out_path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if mode == 'list':
        for p in targets(argv):
            b = Bank(p)
            v = b.verdict()
            g = ','.join(str(len(ids)) for _, ids in v['groups']) or '-'
            print(f'{p.stem:38} {"单元" if v["unit"] else "共享"} media={len(b.media):4} '
                  f'sound={v["clips"]:4} 估时长={v["seconds"]:6.1f}s 分组={g:8} {fmt_kinds(b.kinds())}')
        sys.exit(0)
    if mode == 'parse':
        rows = ['unit\tcategory\tview\thero_id\tslug\tsound_id\tmedia_id\tmedia_in_bank\tbytes\trate\tch\tdata_bytes\tbyterate\test_seconds\tparent_group']
        sums = ['unit\tcategory\tview\thero_id\tslug\tclips\texternal\tseconds\tgroup_sizes\tmin_s\tmax_s']
        ext = ['unit\tcategory\thero_id\tslug\tmedia_id']
        agg = {}
        for p in [q for q in targets(argv) if q.suffix == '.bnk']:
            b = Bank(p)
            v = b.verdict()
            agg[p.stem] = v
            u = unit_parts(p.stem) or {'cat': category(p.stem), 'view': '', 'id': '', 'slug': ''}
            clips = b.clips()
            ests = [c['info']['data'] / c['info']['byterate'] for c in clips if c['info']]
            for c in clips:
                i = c['info'] or {}
                est = f"{i['data'] / i['byterate']:.2f}" if i else ''
                rows.append(f'{p.stem}\t{u["cat"]}\t{u["view"]}\t{u["id"]}\t{u["slug"]}\t'
                            f'{c["sound"]}\t{c["media"]}\t{"是" if c["media_in_bank"] else "否"}\t'
                            f'{c["bytes"] if c["bytes"] is not None else ""}\t{i.get("rate", "")}\t{i.get("ch", "")}\t'
                            f'{i.get("data", "")}\t{i.get("byterate", "")}\t{est}\t{c["parent"]}')
                if not c['media_in_bank']:
                    ext.append(f'{p.stem}\t{u["cat"]}\t{u["id"]}\t{u["slug"]}\t{c["media"]}')
            sums.append(f'{p.stem}\t{u["cat"]}\t{u["view"]}\t{u["id"]}\t{u["slug"]}\t{v["clips"]}\t'
                        f'{v["external"]}\t{v["seconds"]:.1f}\t'
                        f'{",".join(str(len(ids)) for _, ids in v["groups"])}\t'
                        f'{(min(ests) if ests else 0):.2f}\t{(max(ests) if ests else 0):.2f}')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text('\n'.join(rows) + '\n', encoding='utf-8')
        unit_path = out_path.with_name(out_path.stem + '_unit' + out_path.suffix)
        unit_path.write_text('\n'.join(sums) + '\n', encoding='utf-8')
        ext_path = out_path.with_name(out_path.stem + '_external' + out_path.suffix)
        ext_path.write_text('\n'.join(ext) + '\n', encoding='utf-8')

        units = {k: v for k, v in agg.items() if v['unit']}
        # 硬判据: 包内 media 的「数据段 + 实测壳长 = DIDX 记的字节数」。对象走歪了这条一定挂。
        hard = {k: v for k, v in units.items() if v['shell_ok']}
        soft = {'一句一 event': [k for k, v in units.items() if not v['one_event_per_sound']],
                '语音都挂在本包的分组上': [k for k, v in units.items() if not v['sound_in_group']]}
        n_ext = len(ext) - 1
        print(f'VOICE BANK {"OK" if units and len(hard) == len(units) else "FAIL"}: '
              f'{len(agg)} 个 bank(单元包 {len(units)}), {sum(v["clips"] for v in agg.values()):,} 条语音, '
              f'其中 {n_ext} 条的音频不在包里、走同名 .wem(清单 {ext_path})')
        print(f'  -> 逐条 {out_path}\n  -> 逐单元 {unit_path}')
        print(f'  硬判据 数据段+壳=DIDX 字节数: 通过 {len(hard)}/{len(units)}'
              f'{"; 例外 " + ", ".join(k for k in units if k not in hard)[:200] if len(hard) != len(units) else ""}')
        for name, bad in soft.items():
            print(f'  {name}: 通过 {len(units) - len(bad)}/{len(units)}'
                  f'{"; 例外 " + ", ".join(bad[:6]) if bad else ""}')
        for cat in ('emotion', 'battle', 'biography', 'street'):
            cs = {k: v for k, v in units.items() if category(k) == cat}
            if not cs:
                continue
            g = {}
            for v in cs.values():
                g[len(v['groups'])] = g.get(len(v['groups']), 0) + 1
            print(f'  {cat:10} 单元 {len(cs):4}  句数 {sum(v["clips"] for v in cs.values()):6,}  '
                  f'估 {sum(v["seconds"] for v in cs.values())/60:6.1f} 分钟  每包语音分组数分布 {sorted(g.items())}')
        sys.exit(0 if units and len(hard) == len(units) else 1)
    if mode == 'slots':
        # 「语音是不是按表情/场景分槽」的可重跑判据: 如果各包共用同一批 id(比如都叫 happy 的那个槽),
        # 这个 id 就会在很多包里出现; 一人一个 id 的话全都只出现 1 次。
        cat = None
        if '--cat' in argv:
            i = argv.index('--cat')
            cat, argv = argv[i + 1], argv[:i] + argv[i + 2:]
        agg = defaultdict(Counter)
        parents = defaultdict(lambda: {'包': set(), '句': 0})
        n = 0
        for p in [q for q in targets(argv) if q.suffix == '.bnk']:
            b = Bank(p)
            if not is_unit(p.stem) or (cat and category(p.stem) != cat):
                continue
            n += 1
            for c in b.clips():
                agg['sound'][c['sound']] += 1
                agg['media'][c['media']] += 1
                parents[c['parent']]['包'].add(p.stem)
                parents[c['parent']]['句'] += 1
            for t, o, _ in b.objs:
                if t == EVENT:
                    agg['event'][o] += 1
        print(f'SLOTS {cat or "全部"}: {n} 个单元包')
        print(f'  {"对象":<8}{"不同 id 数":>12}{"只出现 1 次":>13}{"出现≥5 遍":>11}{"出现最多的两个":>26}')
        for kind, cnt in sorted(agg.items()):
            top = cnt.most_common(2)
            print(f'  {kind:<10}{len(cnt):>12}{sum(1 for v in cnt.values() if v == 1):>13}'
                  f'{sum(1 for v in cnt.values() if v >= 5):>11}'
                  f'{"  ".join(f"{i}:{n2}遍" for i, n2 in top):>26}')
        multi = sorted(parents.items(), key=lambda kv: -len(kv[1]['包']))
        print(f'  父分组 id 共 {len(parents)} 个; 按「几个包共用同一个分组 id」排(共用才可能是通用槽位):')
        for oid, d in multi[:8]:
            print(f'    {oid:>12} 被 {len(d["包"]):3} 个包共用, 合计 {d["句"]:4} 句   例如 {", ".join(sorted(d["包"])[:3])}')
        only1 = sum(1 for d in parents.values() if len(d['包']) == 1)
        print(f'    只出现在 1 个包的分组: {only1}/{len(parents)}')
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
