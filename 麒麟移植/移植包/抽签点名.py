#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽签点名 —— 窗口版

· 字号固定不变（所有名字同一字号，不做任何缩放）
· 窗口化运行，可自由缩放；双击画面可最大化
· 老虎机式滚轮：点一下开始滚动，再点一下减速停在中奖者身上

名单：同目录 num.txt，每行一个名字（UTF-8 / GBK 均可）
      也可把 txt 拖到本程序上打开
记录：抽中者追加写入同目录 result_linux.txt（不动原版 result.txt）

操作：空格 / 回车 / 点击「开始抽签」→ 滚动；再按一次 → 停止
      双击画面 → 最大化/还原     Esc → 退出
"""

import math
import os
import random
import sys
import time

import tkinter as tk
from tkinter import font as tkfont

# ---------------- 主题 ----------------
BG_TOP = "#12141C"      # 窗口底色（上）
BG_BOT = "#0B0C12"      # 窗口底色（下）
PANEL = "#1A1D28"       # 滚轮面板底色
PANEL_EDGE = "#2A2F42"  # 面板描边
BAND = "#232839"        # 中奖高亮带
BAND_EDGE = "#C9A227"   # 高亮带描边（金）
NAME_FG = "#F2F4F8"     # 名字颜色
NAME_SHADOW = "#0A0B10" # 名字投影
GHOST_FG = "#4A5063"    # 非中奖行的名字
ACCENT = "#C9A227"      # 主色（金）
ACCENT_HI = "#E8C55A"
TEXT_DIM = "#7C8398"

ROLL_TICK_MS = 16       # 动画帧间隔（约 60fps）
ROLL_DURATION = 850     # 减速停止耗时（毫秒）：越小停得越快
SLOW_TURNS = 2          # 停止前再多转几圈，越小停得越快

FONT_CANDIDATES = (
    "Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑",
    "SimHei", "黑体", "Noto Sans CJK SC", "WenQuanYi Micro Hei",
    "PingFang SC", "Heiti SC", "SimSun", "宋体",
)
FONT_FAMILY = FONT_CANDIDATES[0]
NAME_SIZE = 46          # ★ 固定字号，永不改变
UI_SIZE = 11

LOG_NAME = "result_linux.txt"
ROSTER_NAME = "num.txt"
TITLE = "抽签点名"


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def pick_font(root):
    try:
        available = {f.lower() for f in tkfont.families(root)}
    except tk.TclError:
        return FONT_CANDIDATES[0]
    for fam in FONT_CANDIDATES:
        if fam.lower() in available:
            return fam
    return ""


def read_names(path):
    data = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if data is None:
        with open(path, "r", encoding="gb18030", errors="ignore") as f:
            data = f.read()
    names, seen = [], set()
    for line in data.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        name = line.strip().strip("\ufeff").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def find_roster():
    for arg in sys.argv[1:]:
        if arg.lower().endswith(".txt") and os.path.isfile(arg):
            return arg
    here = base_dir()
    for cand in (ROSTER_NAME, "名单.txt", "namelist.txt", "names.txt"):
        p = os.path.join(here, cand)
        if os.path.isfile(p):
            return p
    return None


def append_log(winner):
    try:
        path = os.path.join(base_dir(), LOG_NAME)
        with open(path, "a", encoding="utf-8") as f:
            f.write("** 抽签点名 - 结果 **\n")
            f.write("项目名称：" + TITLE + "\n")
            f.write("抽签时间：" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(winner + "\n\n")
    except OSError:
        pass


def rounded_rect(cv, x1, y1, x2, y2, r, **kw):
    """在 Canvas 上画圆角矩形（tkinter 没有原生圆角，用扇形+矩形拼）。"""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


def vertical_gradient(cv, x1, y1, x2, y2, c_top, c_bot):
    """用若干横向色带模拟竖向渐变。"""
    top = cv.winfo_toplevel().winfo_rgb(c_top)
    bot = cv.winfo_toplevel().winfo_rgb(c_bot)
    steps = 64
    h = (y2 - y1) / steps
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0
        col = "#%02x%02x%02x" % tuple(
            int(top[k] / 256 + (bot[k] - top[k]) / 256 * t) for k in range(3)
        )
        cv.create_rectangle(x1, y1 + i * h, x2, y1 + (i + 1) * h + 1,
                            fill=col, outline="")


class App:
    def __init__(self, root, names, roster, family):
        self.root = root
        self.names = names
        self.roster = roster
        self.family = family
        self.n = len(names)

        self.rolling = False
        self.job = None
        self.state = "idle"          # idle | rolling | stopping
        self.spin_count = 0
        self.scroll = 0.0            # 滚轮位置（单位：行）
        self.list_scroll = 0.0       # 横向长名滚动（像素）
        self.roll_start = 0.0
        self.roll_target = 0.0
        self.roll_t0 = 0.0
        self.prev_spin_count = 0

        root.title("%s — %d 人" % (TITLE, self.n))
        root.configure(bg=BG_BOT)
        root.minsize(720, 480)
        root.geometry("1180x740")

        self.name_font = tkfont.Font(root=root, family=family or "TkDefaultFont",
                                     size=NAME_SIZE)
        self.ui_font = tkfont.Font(root=root, family=family or "TkDefaultFont",
                                   size=UI_SIZE)
        self.count_font = tkfont.Font(root=root, family=family or "TkDefaultFont",
                                      size=13, weight="bold")

        self.build_ui()

        for seq in ("<space>", "<Return>", "<KP_Enter>"):
            root.bind(seq, self.toggle)
        root.bind("<Escape>", lambda e: root.destroy())
        root.bind("<F11>", self.toggle_zoom)
        root.bind("<Configure>", self.on_resize)

        self.layout(self.root.winfo_width(), self.root.winfo_height())
        self.draw_reel()

    # ---------------- 界面 ----------------
    def build_ui(self):
        r = self.root
        self.header = tk.Frame(r, bg=BG_TOP, height=58)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        self.title_lbl = tk.Label(self.header, text=TITLE, bg=BG_TOP, fg=NAME_FG,
                                  font=tkfont.Font(root=r, family=self.family or "TkDefaultFont",
                                                   size=15, weight="bold"))
        self.title_lbl.pack(side="left", padx=(22, 0))

        self.roster_lbl = tk.Label(self.header,
                                   text="%s · %d 人" % (os.path.basename(self.roster), self.n),
                                   bg=BG_TOP, fg=TEXT_DIM, font=self.ui_font)
        self.roster_lbl.pack(side="right", padx=(0, 22))

        self.canvas = tk.Canvas(r, bg=BG_TOP, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.toggle)
        self.canvas.bind("<Double-Button-1>", self.toggle_zoom)

        self.footer = tk.Frame(r, bg=BG_BOT, height=104)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

        self.btn = tk.Button(self.footer, text="开始抽签", command=self.toggle,
                             font=tkfont.Font(root=r, family=self.family or "TkDefaultFont",
                                              size=13, weight="bold"),
                             bg=ACCENT, fg="#1A1200", activebackground=ACCENT_HI,
                             activeforeground="#1A1200", relief="flat", bd=0,
                             highlightthickness=0, cursor="hand2", width=12, pady=7)
        self.btn.pack(side="left", padx=(22, 0), pady=22)

        self.hint_lbl = tk.Label(self.footer,
                                 text="空格 / 点击画面 也可以开始", bg=BG_BOT,
                                 fg=TEXT_DIM, font=self.ui_font)
        self.hint_lbl.pack(side="left", padx=(16, 0))

        self.count_lbl = tk.Label(self.footer, text="已抽 0 次", bg=BG_BOT,
                                  fg=TEXT_DIM, font=self.ui_font)
        self.count_lbl.pack(side="right", padx=(0, 22))

    def on_resize(self, event):
        if event.widget is self.root:
            self.layout(event.width, event.height)
            self.draw_reel()

    def layout(self, w, h):
        """按窗口尺寸摆放滚轮面板：字号固定，面板高度由可见行数反推。

        注意 DPI 缩放：tkfont 的 linespace 是物理像素。若行高小于字号，
        名字就会溢出面板；若面板高度不是行高的整数倍，最外侧名字会被切一半。
        所以先定行高，再由行数算出面板高度，保证面板边界正好落在两行之间。
        """
        w = max(w, 720)
        h = max(h, 480)
        self.reel_w = min(940, int(w * 0.86))

        text_h = self.name_font.metrics("linespace")
        self.line_h = float(text_h) + max(18.0, text_h * 0.26)   # 行高必须大于字高

        avail_h = h - 58 - 104 - 34          # 减去页头、页脚和上下留白
        slots = int(avail_h / self.line_h)
        if slots % 2 == 0:
            slots -= 1                        # 保证有正中行
        self.slots = max(3, slots)
        self.center_slot = self.slots // 2
        self.reel_h = int(round(self.slots * self.line_h))

        self.reel_x = (w - self.reel_w) // 2
        # 面板在剩余空间里居中，但顶部至少留 16px，避免贴住页头
        free = h - 58 - 104 - self.reel_h
        self.reel_y = 58 + max(16, free // 2)

    # ---------------- 绘制 ----------------
    def draw_reel(self):
        cv = self.canvas
        cv.delete("all")
        w = cv.winfo_width() or self.root.winfo_width()
        h = cv.winfo_height() or 300

        vertical_gradient(cv, 0, 0, w, h, BG_TOP, BG_BOT)

        x1, y1 = self.reel_x, self.reel_y
        x2, y2 = x1 + self.reel_w, y1 + self.reel_h

        # 面板底 + 描边
        rounded_rect(cv, x1 - 2, y1 - 2, x2 + 2, y2 + 2, 18,
                     fill=PANEL_EDGE, outline="")
        rounded_rect(cv, x1, y1, x2, y2, 16, fill=PANEL, outline="")

        # 中奖高亮带
        band_y1 = y1 + self.center_slot * self.line_h
        band_y2 = band_y1 + self.line_h
        cv.create_rectangle(x1 + 3, band_y1, x2 - 3, band_y2,
                            fill=BAND, outline="")
        cv.create_line(x1 + 6, band_y1, x2 - 6, band_y1, fill=BAND_EDGE, width=1)
        cv.create_line(x1 + 6, band_y2, x2 - 6, band_y2, fill=BAND_EDGE, width=1)
        # 左右小三角指示
        for sx, sgn in ((x1 + 10, 1), (x2 - 10, -1)):
            cy = (band_y1 + band_y2) / 2
            cv.create_polygon(sx, cy - 7, sx, cy + 7, sx + sgn * 9, cy,
                              fill=BAND_EDGE, outline="")

        self.draw_names()

    def _fade_color(self, fg, t):
        """按 t（0=透明，1=完全可见）把名字颜色混向面板底色，靠近边缘就变暗。"""
        if t >= 0.999:
            return fg
        if t <= 0.001:
            return PANEL
        a = self.root.winfo_rgb(fg)
        b = self.root.winfo_rgb(PANEL)
        return "#%02x%02x%02x" % tuple(
            int((a[k] + (b[k] - a[k]) * (1 - t)) / 256) for k in range(3))

    def draw_names(self):
        """把名字画到滚轮里。scroll 每 +1 = 上移一行。

        只画面板内部的行；越靠近上下边缘越暗，到边界正好消失，
        这样不会有名字露在面板外面。
        """
        cv = self.canvas
        cv.delete("name")
        base = math.floor(self.scroll)
        frac = self.scroll - base
        cx = self.reel_x + self.reel_w / 2 + self.list_scroll
        text_w = self.reel_w - 52
        y1 = float(self.reel_y)
        y2 = y1 + self.reel_h
        center_y = y1 + self.center_slot * self.line_h + self.line_h / 2
        fade_rows = 1.15                     # 边缘多少行内开始变暗

        for j in range(self.slots + 1):
            idx = (base + j) % self.n
            cy = center_y + (j - self.center_slot - frac) * self.line_h
            if cy < y1 - self.line_h or cy > y2 + self.line_h:
                continue
            # 距离边缘的可见度
            if cy < y1:
                t = 0.0
            elif cy < y1 + fade_rows * self.line_h:
                t = (cy - y1) / (fade_rows * self.line_h)
            elif cy > y2:
                t = 0.0
            elif cy > y2 - fade_rows * self.line_h:
                t = (y2 - cy) / (fade_rows * self.line_h)
            else:
                t = 1.0
            if t <= 0.02:
                continue
            is_center = (j == self.center_slot) and not self.rolling
            base_fg = NAME_FG if is_center else GHOST_FG
            name = self.names[idx]
            cv.create_text(cx + 2, cy + 2, text=name, font=self.name_font,
                           fill=self._fade_color(NAME_SHADOW, t * 0.85),
                           anchor="center", tags="name", width=text_w)
            cv.create_text(cx, cy, text=name, font=self.name_font,
                           fill=self._fade_color(base_fg, t), anchor="center",
                           tags="name", width=text_w)

    # ---------------- 交互 ----------------
    def toggle(self, event=None):
        if self.state == "idle":
            self.start()
        elif self.state == "rolling":
            self.stop()

    def toggle_zoom(self, event=None):
        """最大化 / 还原。

        "zoomed" 是 Windows 专属的窗口状态，银河麒麟等 Linux 上会直接报错，
        所以按平台分别处理，并且全程容错——绝不能因为最大化失败把程序弄崩。
        """
        r = self.root
        try:
            if sys.platform.startswith("win"):
                r.state("normal" if r.state() == "zoomed" else "zoomed")
                return
            if sys.platform == "darwin":
                if r.attributes("-fullscreen"):
                    r.attributes("-fullscreen", False)
                else:
                    r.attributes("-fullscreen", True)
                return
            # Linux（银河麒麟）：先试窗口管理器最大化，失败就退回全屏，再失败就手动铺满
            try:
                r.attributes("-zoomed", not r.attributes("-zoomed"))
                return
            except tk.TclError:
                pass
            try:
                r.attributes("-fullscreen", not r.attributes("-fullscreen"))
                return
            except tk.TclError:
                pass
            self._manual_max(r)
        except tk.TclError:
            self._manual_max(r)

    def _manual_max(self, r):
        """窗口管理器不支持任何最大化协议时，自己把窗口铺到整个屏幕。"""
        if getattr(self, "_saved_geom", None) is None:
            self._saved_geom = r.geometry()
            r.geometry("%dx%d+0+0" % (r.winfo_screenwidth(), r.winfo_screenheight()))
        else:
            r.geometry(self._saved_geom)
            self._saved_geom = None

    def start(self):
        self.state = "rolling"
        self.spin_count = 0
        self.rolling = True
        self.btn.configure(text="停 止", bg="#E05252", activebackground="#F06A6A",
                           fg="#FFFFFF", activeforeground="#FFFFFF")
        self.hint_lbl.configure(text="再按一次空格 / 点击画面即可停止", fg=TEXT_DIM)
        self.prev_spin_count = int(self.scroll // self.n)
        self.job = self.root.after(ROLL_TICK_MS, self.tick_roll)

    def tick_roll(self):
        if self.state != "rolling":
            return
        self.spin_count += 1
        self.scroll += max(1, int(self.n / 26))     # 每帧约 1/26 圈
        self.draw_names()
        self.job = self.root.after(ROLL_TICK_MS, self.tick_roll)

    def stop(self):
        if self.state != "rolling":
            return
        self.state = "stopping"
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None

        winner_idx = random.randrange(self.n)
        self.winner = self.names[winner_idx]

        # 目标位置：让 winner 恰好停在正中行
        cur = self.scroll
        base_target = math.floor(cur / self.n) * self.n + winner_idx
        while base_target < cur + self.n * SLOW_TURNS:
            base_target += self.n
        self.roll_start = cur
        self.roll_target = base_target
        self.roll_t0 = time.monotonic()
        self.btn.configure(text="停止中…", bg="#5A6070",
                           activebackground="#5A6070", state="disabled",
                           fg="#C8CCD8")
        self.hint_lbl.configure(text="减速中……", fg=TEXT_DIM)
        self.job = self.root.after(ROLL_TICK_MS, self.tick_stop)

    def tick_stop(self):
        t = (time.monotonic() - self.roll_t0) * 1000.0 / ROLL_DURATION
        if t >= 1.0:
            self.scroll = self.roll_target
            self.finish()
            return
        eased = 1 - (1 - t) ** 3                    # easeOutCubic
        self.scroll = self.roll_start + (self.roll_target - self.roll_start) * eased
        self.draw_names()
        self.job = self.root.after(ROLL_TICK_MS, self.tick_stop)

    def finish(self):
        self.state = "idle"
        self.rolling = False
        self.draw_reel()
        self.btn.configure(text="再抽一次", bg=ACCENT, activebackground=ACCENT_HI,
                           fg="#1A1200", activeforeground="#1A1200", state="normal")
        self.hint_lbl.configure(text="空格 / 点击画面 继续", fg=TEXT_DIM)
        self.draws = getattr(self, "draws", 0) + 1
        self.count_lbl.configure(text="已抽 %d 次" % self.draws)
        append_log(self.winner)


def message_window(root, text):
    root.geometry("620x300")
    root.configure(bg=BG_TOP)
    root.title(TITLE)
    tk.Label(root, text=text, bg=BG_TOP, fg=NAME_FG, font=(FONT_FAMILY, 14),
             justify="center").pack(expand=True, fill="both", padx=30)
    root.bind("<Escape>", lambda e: root.destroy())
    root.mainloop()


def main():
    root = tk.Tk()
    root.withdraw()
    global FONT_FAMILY
    FONT_FAMILY = pick_font(root)

    roster = find_roster()
    if not roster:
        root.deiconify()
        message_window(root,
            "没找到名单文件。\n\n请把名单保存为与本程序放在一起的 %s\n（每行一个名字）后重新打开。\n\n"
            "也可以把名单 txt 直接拖到本程序上。" % ROSTER_NAME)
        return
    names = read_names(roster)
    if not names:
        root.deiconify()
        message_window(root, "名单文件里没有名字：\n%s\n\n请填入名字（每行一个）后重新打开。" % roster)
        return

    root.deiconify()
    App(root, names, roster, FONT_FAMILY)
    root.mainloop()


if __name__ == "__main__":
    main()
