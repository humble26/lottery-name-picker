#!/bin/bash
# 抽签点名 —— 环境探测（无需 root，什么都不装，只读检测）
# 用法：在终端执行  bash 检查环境.sh
# 然后把全部输出复制发给我

line() { echo "----------------------------------------"; }

echo "========================================"
echo "  抽签点名 · 环境探测"
echo "  生成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo

line; echo "【1】系统版本"; line
[ -f /etc/os-release ] && cat /etc/os-release
for f in /etc/kylin-release /etc/.kyinfo /etc/kylin-build; do
    [ -f "$f" ] && { echo "--- $f ---"; cat "$f"; }
done
echo "架构(CPU)  : $(uname -m)"
echo "CPU 型号   : $(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ *//')"
echo "内核       : $(uname -r)"
echo "桌面环境   : ${XDG_CURRENT_DESKTOP:-（空）}"
echo "DISPLAY    : ${DISPLAY:-（空）}"
echo "WAYLAND    : ${WAYLAND_DISPLAY:-（空）}"
echo

line; echo "【2】Python 解释器"; line
PY=""
for c in python3 /usr/bin/python3 python /usr/local/bin/python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
    echo "★ 没有找到 python3"
else
    echo "路径 : $(command -v "$PY")"
    echo "版本 : $($PY --version 2>&1)"
    "$PY" - <<'PYEOF'
import sys, sysconfig
print("     详细 :", sys.version.replace("\n", " "))
print("     前缀 :", sys.prefix)
print("     纯lib:", sysconfig.get_paths().get("purelib"))
PYEOF
fi
echo

line; echo "【3】★ 图形界面能力（最关键）★"; line
if [ -n "$PY" ]; then
    "$PY" - <<'PYEOF'
import importlib

def probe(mod, label):
    try:
        m = importlib.import_module(mod)
        return True, "%s  可用  版本=%s" % (label, getattr(m, "__version__", "?"))
    except Exception as e:
        return False, "%s  不可用 (%s: %s)" % (label, type(e).__name__, e)

# tkinter —— 本方案当前依赖它
ok, msg = probe("tkinter", "tkinter")
print(("[有] " if ok else "[无] ") + msg)
if ok:
    try:
        import tkinter as tk, tkinter.font as tf
        r = tk.Tk(); r.withdraw()
        print("       Tk 版本   :", tk.TkVersion)
        print("       屏幕      : %dx%d" % (r.winfo_screenwidth(), r.winfo_screenheight()))
        print("       Tk scaling:", r.tk.call("tk", "scaling"))
        fams = set(tf.families(r))
        want = ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
                "Noto Sans SC", "Source Han Sans SC", "Source Han Sans CN",
                "Microsoft YaHei", "SimHei", "AR PL UMing CN", "AR PL UKai CN",
                "Droid Sans Fallback", "Ubuntu", "DejaVu Sans"]
        print("       中文字体  :")
        hit = [w for w in want if w in fams]
        if hit:
            for w in hit: print("           有", w)
        else:
            print("           ★ 一个候选中文字体都没有（可能显示方块）")
        print("       字体总数  :", len(fams))
        r.destroy()
    except Exception as e:
        print("       ★ 能 import 但创建窗口失败:", type(e).__name__, e)

# 备选：GTK3（麒麟是 GNOME 系，常自带）
for mod, label in (("gi", "PyGObject(gi)"),
                   ("gi.repository.Gtk", "GTK3 (gi.repository.Gtk)"),
                   ("curses", "curses(终端)")):
    ok, msg = probe(mod, label)
    print(("[有] " if ok else "[无] ") + msg)
PYEOF
else
    echo "跳过（没有 python3）"
fi
echo

line; echo "【4】其它可能用到的"; line
command -v pip3 >/dev/null 2>&1 && echo "[有] pip3  $(pip3 --version 2>&1)" || echo "[无] pip3"
for b in firefox chromium chromium-browser google-chrome falkon; do
    command -v "$b" >/dev/null 2>&1 && echo "[有] 浏览器: $b"
done
command -v zenity >/dev/null 2>&1 && echo "[有] zenity" || echo "[无] zenity"
echo "用户 : $(id -un)  (uid=$(id -u))"
echo "家目录: $HOME"
line; echo "【5】探测结束 —— 请把以上全部内容复制发给我"; line
