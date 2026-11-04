"""语音文本比对用的规范化 —— voice_emo_map.py 和 voice_probe.py 共用，别让两处判据各说各话。

规范化 = 片假名折成平假名、按 Unicode 类别剔掉标点和符号、再去促音「っ」。

为什么要抹 っ: 表情语音一句才 1 秒上下，笑和惊呼那几类的促音 ASR 写得忽有忽无（同一个笑声两种写法、
「诶」带不带促音也两样），抹掉之后各自归成一条，规则表才不用为每种写法各写一条。
长音「ー」**留着**: 抹了它「答应」那一类会把「沉吟」那一类吃掉，配成一张笑脸 —— 实测就是这么翻车的。
拖音的重复交给规则表的 contains（同一拖音的两种写法，靠短的那一条 contains 就够）。
标点为什么按 Unicode 类别剔: 手抄字符表会漏 —— 第一版就漏了半角 ! 和 …，带感叹号的那整句没命中。

（转写原文是游戏语音，按裁定不进版本库；要对照就查本机未跟踪的 out/voice_lines.tsv。）
"""
import unicodedata


def norm(t):
    a = []
    for ch in t:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:
            ch = chr(o - 0x60)
        if ch.isspace() or unicodedata.category(ch)[0] in 'PS':
            continue
        a.append(ch)
    return ''.join(a).replace('っ', '')
