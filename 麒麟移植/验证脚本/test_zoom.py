# -*- coding: utf-8 -*-
"""用真实 App 实例测试 toggle_zoom 的三条平台分支（给 Tk 方法打桩）。"""
import importlib.util
import sys
import tkinter as tk
import traceback

spec = importlib.util.spec_from_file_location("cq", r"E:\harness\03-抽签点名\Windows版\抽签点名.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

root = tk.Tk()
root.withdraw()
m.FONT_FAMILY = m.pick_font(root)
root.deiconify()
root.geometry("1180x740+80+60")
root.update()
names = m.read_names(m.find_roster())
a = m.App(root, names, m.find_roster(), m.FONT_FAMILY)
root.update()

REAL_PLATFORM = sys.platform
stub = {}

# ---- 给 root 打桩，模拟不同窗口管理器的能力 ----
def make_stub(support_state, support_zoomed, support_fs):
    state = {"fs": False, "zoomed": False, "calls": []}

    def state_method(*args):
        state["calls"].append("state")
        if not support_state or not args:
            raise tk.TclError('bad argument "zoomed": must be normal, iconic, or withdrawn')
        return "normal" if args[0] == "normal" else "zoomed"

    def attributes(*args):
        state["calls"].append("attributes")
        if len(args) == 2:
            if args[0] == "-fullscreen":
                if not support_fs:
                    raise tk.TclError("-fullscreen not supported")
                state["fs"] = bool(args[1]); return ""
            if args[0] == "-zoomed":
                if not support_zoomed:
                    raise tk.TclError("-zoomed not supported")
                state["zoomed"] = bool(args[1]); return ""
        if args[0] == "-fullscreen":
            return state["fs"]
        if args[0] == "-zoomed":
            return state["zoomed"]
        return ""
    return state_method, attributes, state


cases = [
    ("win32 / 支持 zoomed",      "win32",  (True,  False, True)),
    ("darwin / 支持 fullscreen", "darwin", (False, False, True)),
    ("linux / 支持 -zoomed",     "linux",  (False, True,  True)),
    ("linux / 只有 -fullscreen", "linux",  (False, False, True)),
    ("linux / 完全受限(Wayland)", "linux",  (False, False, False)),
]

fails = 0
for label, plat, caps in cases:
    sys.platform = plat
    sm, at, st = make_stub(*caps)
    root.state = sm
    root.attributes = at
    geom_before = root.geometry()
    a._saved_geom = None
    try:
        for _ in range(3):                 # 最大化 → 还原 → 最大化
            a.toggle_zoom()
            root.update()
        alive = root.winfo_exists()
        print("%-26s OK  调用=%s  窗口仍在=%s" % (label, [c for c in st["calls"]], bool(alive)))
    except Exception as e:
        fails += 1
        print("%-26s ★ 失败: %s: %s" % (label, type(e).__name__, e))
        traceback.print_exc()

sys.platform = REAL_PLATFORM
root.destroy()

# ---- 额外：真实窗口上确认 Windows 分支仍然工作 ----
print("\n--- 真实窗口（平台 %s）---" % REAL_PLATFORM)
root2 = tk.Tk()
root2.withdraw()
root2.deiconify()
root2.geometry("1180x740+80+60")
root2.update()
a2 = m.App(root2, names, m.find_roster(), m.FONT_FAMILY)
root2.update()
try:
    g0 = root2.geometry()
    a2.toggle_zoom(); root2.update()
    g1 = root2.geometry()
    a2.toggle_zoom(); root2.update()
    g2 = root2.geometry()
    print("原状 %s → 最大化 %s → 还原 %s  OK" % (g0, g1, g2))
    if g0.split("+")[0] != g2.split("+")[0]:
        print("  ★ 还原后尺寸与原来不一致")
        fails += 1
except Exception as e:
    fails += 1
    print("★ 真实窗口失败:", e)
root2.destroy()

print("\n总判定: %s" % ("全部通过" if fails == 0 else "有 %d 项失败" % fails))
