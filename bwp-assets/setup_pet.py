"""装桌宠: 重编译 → 写配置 → 启动。必须先退出正在运行的 BwpDesktopPet。
用法: python setup_pet.py [skel路径 ...]  不给参数就装名册上那四只
装好后运行中就能换人: 宠物上 Ctrl+滚轮, 或托盘图标右键 →「切换角色」。"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent / "deskspine"
OUT = REPO / "out" / "x64" / "Release" / "net8.0-windows" / "win-x64"
EXE = OUT / "BwpDesktopPet.exe"
CONFIG = Path(os.environ["LOCALAPPDATA"]) / "DeskSpine" / "config.json"  # 目录名跟 ProgramName 走, 改名那轮故意没动(动了丢用户已有配置)
EMOTION = ROOT / "t" / "spine_emotion"

# 槽位 0..9 就是角色名册, 出场哪一只由 ActiveSlot 决定
DEFAULT_PETS = [
    EMOTION / "buzhihuo_1127" / "buzhihuo_1127.skel",                # 不知火
    EMOTION / "maozhanggui_sp_yihua_3754" / "maozhanggui_sp_yihua_3754.skel",  # 猫掌柜焕宴
    EMOTION / "qianji_0552" / "qianji_0552.skel",                     # 千姬(副脸)
    EMOTION / "xieji_0481" / "xieji_0481.skel",                       # 蟹姬
]
SLOT_COUNT = 10

# 名册上的中文名, 和 deskspine/DeskSpine/src/PetNames.cs 保持一致
PET_NAMES = {
    "buzhihuo_1127": "不知火",
    "qianji_0552": "千姬",
    "maozhanggui_sp_yihua_3754": "猫掌柜焕宴",
    "xieji_0481": "蟹姬",
}

V36 = 0x0306          # 百闻牌骨架全是 3.6.52
BWP_HERO = 5          # AnimatorType.BwpHero

skels = [Path(a).resolve() for a in sys.argv[1:]] or DEFAULT_PETS
if len(skels) > SLOT_COUNT:
    sys.exit(f"名册最多 {SLOT_COUNT} 格, 给了 {len(skels)} 只")
for skel in skels:
    if not skel.exists():
        sys.exit(f"找不到骨架 {skel}")
    if not skel.with_suffix(".atlas").exists():
        sys.exit(f"{skel.name} 旁边缺同名 .atlas, 桌宠起不来")

running = subprocess.run(["tasklist", "/FI", "IMAGENAME eq BwpDesktopPet.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
if "BwpDesktopPet.exe" in running:
    sys.exit("BwpDesktopPet 还在运行, 输出文件会被锁住。托盘图标右键退出后再跑一次。")

print("== 编译 Release")
r = subprocess.run(["dotnet", "build", str(REPO / "DeskSpine.sln"), "-c", "Release", "-v", "q", "--nologo"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
bad = [l for l in r.stdout.splitlines() if "error" in l]
if r.returncode != 0:
    print("\n".join(bad[:10]))
    sys.exit(f"编译失败 (exit {r.returncode})")
print(f"   OK  {EXE.name} -> {time.strftime('%H:%M', time.localtime(EXE.stat().st_mtime))}")

print("== 写配置")
cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
shutil.copy2(CONFIG, CONFIG.with_suffix(".json.bak"))
cfg["SpineConfig"]["SpineVersion"] = V36
cfg["SpineConfig"]["InteractMode"] = BWP_HERO
for i in range(SLOT_COUNT):
    cfg["SpineConfig"][f"SkelPath{i}"] = str(skels[i]) if i < len(skels) else None
cfg["SpineConfig"]["ActiveSlot"] = 0
# 头像框接入撤掉后这几键没人读了, 留着只会让人以为还能切框, 顺手清干净
for key in [k for k in cfg["SpineConfig"] if k == "ActiveFrame" or k.startswith("FramePath")]:
    del cfg["SpineConfig"][key]
cfg["BasicConfig"]["SpineUsePMA"] = True
cfg["SystemConfig"]["Visible"] = True
CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
print(f"   版本=3.6.x  模式=阴阳师百闻牌_式神  PMA=开  出场=槽位0")
for i, skel in enumerate(skels):
    folder = skel.parent.name
    name = PET_NAMES.get(folder, folder)
    print(f"   名册[{i}] {name}" + ("" if name == folder else f"  ({folder})"))
print(f"   原配置已备份为 {CONFIG.name}.bak")

print("== 启动")
subprocess.Popen([str(EXE)], cwd=str(OUT))
print("   已启动。判据: 出场那只先播一遍登场动作再回到 idle; 单击/双击/滚轮/拖拽各触发不同动作,")
print("        表情骨架 (happy/sad/surprise/thinking) 会换脸, 式神立绘会换姿态。")
print("        Ctrl+滚轮 或 托盘右键→「切换角色」换一只; 缩放/位置是全局的, 名册上几只共用。")
print("        头像骨架只有百来单位大, 觉得太小就调设置里的 Spine 缩放。")
