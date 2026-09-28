#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽签点名程序（简约版）
- 读取 num.txt 名单与 award.ini 配置，随机抽签点名
- 防重复、速度调节、背景自由更换、结果自动保存（兼容原版 result.txt）
"""

import os
import sys
import time
import random
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# ---------------- 配色 ----------------
COL_BG_TOP = "#0f1722"
COL_BG_BOT = "#182940"
COL_TEXT = "#f2f6fa"
COL_SUB = "#93a9c2"
COL_DIM = "#5c7189"
COL_GOLD = "#ffcf5c"
COL_GOLD_DARK = "#2a1f0a"
COL_GOLD_HOVER = "#ffd97a"
COL_GOLD_PRESS = "#e8b64c"
COL_BTN = "#233449"
COL_BTN_HOVER = "#2e4560"
COL_BTN_PRESS = "#1b2a3c"
COL_LINE = "#33465e"
COL_PANEL = "#101c2b"
COL_INPUT = "#16233a"
COL_HIT_TEXT = "#7fd3a8"

FONT = "Microsoft YaHei UI"


def resolve_font(root):
    """按平台选择可用中文字体：Windows 用微软雅黑，Linux/麒麟用系统中文字体。"""
    global FONT
    if sys.platform == "win32":
        FONT = "Microsoft YaHei UI"
        return
    try:
        import tkinter.font as tkfont
        fams = set(tkfont.families(root))
        for name in ("Noto Sans CJK SC", "WenQuanYi Zen Hei",
                     "WenQuanYi Micro Hei", "AR PL UMing CN", "DejaVu Sans"):
            if name in fams:
                FONT = name
                return
    except Exception:
        pass
    FONT = "TkDefaultFont"


def open_text_editor(path):
    """跨平台打开文本文件：Windows 用记事本，Linux/麒麟用系统默认编辑器。"""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["notepad.exe", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        return False
    return True


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    d = os.path.dirname(os.path.abspath(__file__))
    if (not os.path.exists(os.path.join(d, "num.txt"))
            and os.path.exists(os.path.join(d, "..", "num.txt"))):
        return os.path.dirname(d)
    return d


BASE_DIR = app_dir()
NUM_FILE = os.path.join(BASE_DIR, "num.txt")
INI_FILE = os.path.join(BASE_DIR, "award.ini")
RESULT_FILE = os.path.join(BASE_DIR, "result.txt")

DEFAULT_INI = """[Form]
Title=抽签点名
Tip=SJTU-Hush出品，2026年
Number=
Picture=back0.JPG
ShowCopyright=True

[Award]
Repeat=False
Speed= 30
"""


# ---------------- 文件工具 ----------------
def read_text_file(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def write_text_file(path, text):
    try:
        with open(path, "w", encoding="gbk", errors="replace", newline="") as f:
            f.write(text)
        return "gbk"
    except Exception:
        with open(path, "w", encoding="utf-8", errors="replace", newline="") as f:
            f.write(text)
        return "utf-8"


def load_names():
    text = read_text_file(NUM_FILE)
    if not text:
        return []
    names = []
    for line in text.splitlines():
        name = line.strip()
        if name:
            names.append(name)
    return names


def parse_ini(text):
    cfg = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            cfg[section + "." + k.strip()] = v.strip()
    return cfg


def load_config():
    if not os.path.exists(INI_FILE):
        write_text_file(INI_FILE, DEFAULT_INI)
    text = read_text_file(INI_FILE)
    if text is None:
        text = DEFAULT_INI
    cfg = parse_ini(text)
    return {
        "title": cfg.get("Form.Title", "抽签点名"),
        "tip": cfg.get("Form.Tip", ""),
        "number": cfg.get("Form.Number", ""),
        "picture": cfg.get("Form.Picture", "back0.JPG"),
        "show_copyright": cfg.get("Form.ShowCopyright", "True") != "False",
        "repeat": cfg.get("Award.Repeat", "False") == "True",
        "speed": int(float(cfg.get("Award.Speed", 30) or 30)),
    }


def save_config(cfg):
    text = (
        "[Form]\r\n"
        "Title={title}\r\n"
        "Tip={tip}\r\n"
        "Number={number}\r\n"
        "Picture={picture}\r\n"
        "ShowCopyright={show_copyright}\r\n"
        "\r\n"
        "[Award]\r\n"
        "Repeat={repeat}\r\n"
        "Speed= {speed}\r\n"
    ).format(
        title=cfg["title"], tip=cfg["tip"], number=cfg["number"],
        picture=cfg["picture"],
        show_copyright="True" if cfg["show_copyright"] else "False",
        repeat="True" if cfg["repeat"] else "False",
        speed=cfg["speed"],
    )
    write_text_file(INI_FILE, text)


def builtin_backgrounds():
    """返回 (显示名, 绝对路径) 列表。"""
    found = []
    for i in range(4):
        for ext in (".JPG", ".jpg", ".png", ".PNG"):
            p = os.path.join(BASE_DIR, "back%d%s" % (i, ext))
            if os.path.exists(p):
                found.append(("背景 %d" % (i + 1), p))
                break
    return found


# ---------------- CanvasButton 圆角按钮 ----------------
class CanvasButton:
    def __init__(self, canvas, tag, text, command, x=0, y=0, w=120, h=40,
                 kind="secondary", font_size=13, anchor="center"):
        self.canvas = canvas
        self.tag = tag
        self.command = command
        self.x, self.y = x, y
        self.w, self.h = w, h
        self.kind = kind
        self.font_size = font_size
        self.anchor = anchor
        self.state = "normal"
        self.items = []
        self.text_cache = text
        self._set_colors()
        self._draw()
        self._bind()

    def _set_colors(self):
        if self.kind == "primary":
            self.fg = COL_GOLD_DARK
            self.bg = COL_GOLD
            self.hover = COL_GOLD_HOVER
            self.press = COL_GOLD_PRESS
            self.outline = ""
        else:
            self.fg = COL_TEXT
            self.bg = ""
            self.hover = COL_BTN_HOVER
            self.press = COL_BTN_PRESS
            self.outline = COL_LINE

    def _draw(self):
        self.delete()
        x, y, w, h = self.x, self.y, self.w, self.h
        r = h / 2
        if self.anchor == "center":
            x1, y1 = x - w / 2, y - h / 2
        elif self.anchor == "w":
            x1, y1 = x, y - h / 2
        else:
            x1, y1 = x - w, y - h / 2
        x2, y2 = x1 + w, y1 + h
        fill = self.bg
        outline = self.outline
        if self.state == "hover":
            fill = self.hover
        elif self.state == "press":
            fill = self.press
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        kw = {"fill": fill, "smooth": True}
        if outline:
            kw["outline"] = outline
        else:
            kw["outline"] = ""
        self.items.append(self.canvas.create_polygon(pts, tags=self.tag, **kw))
        self.items.append(self.canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2, text=self.text_cache,
            fill=self.fg, tags=self.tag, font=(FONT, self.font_size, "bold")))

    def set_text(self, text):
        self.text_cache = text
        for it in self.items:
            if self.canvas.type(it) == "text":
                self.canvas.itemconfig(it, text=text)

    def delete(self):
        for it in self.items:
            self.canvas.delete(it)
        self.items = []

    def place(self, x, y, anchor=None):
        self.x, self.y = x, y
        if anchor:
            self.anchor = anchor
        if self.items and self.canvas.type(self.items[0]):
            self._move()
        else:
            self._draw()

    def _move(self):
        x, y, w, h = self.x, self.y, self.w, self.h
        r = h / 2
        if self.anchor == "center":
            x1, y1 = x - w / 2, y - h / 2
        elif self.anchor == "w":
            x1, y1 = x, y - h / 2
        else:
            x1, y1 = x - w, y - h / 2
        x2, y2 = x1 + w, y1 + h
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        for it in self.items:
            if self.canvas.type(it) == "polygon":
                self.canvas.coords(it, *pts)
            elif self.canvas.type(it) == "text":
                self.canvas.coords(it, (x1 + x2) / 2, (y1 + y2) / 2)

    def _bind(self):
        self.canvas.tag_bind(self.tag, "<Enter>", lambda e: self._set("hover"))
        self.canvas.tag_bind(self.tag, "<Leave>", lambda e: self._set("normal"))
        self.canvas.tag_bind(self.tag, "<ButtonPress-1>", lambda e: self._set("press"))
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", lambda e: self._release())

    def _set(self, state):
        self.state = state
        fill = self.bg
        if state == "hover":
            fill = self.hover
        elif state == "press":
            fill = self.press
        for it in self.items:
            try:
                if self.canvas.type(it) == "polygon":
                    self.canvas.itemconfig(it, fill=fill, outline=self.outline)
                elif self.canvas.type(it) == "text":
                    self.canvas.itemconfig(it, fill=self.fg)
            except tk.TclError:
                pass

    def _release(self):
        self.state = "normal"
        self._set("normal")
        if self.command:
            self.command()


# ---------------- 主程序 ----------------
class AwardApp:
    def __init__(self, root):
        self.root = root
        resolve_font(root)
        self.cfg = load_config()
        self.names = load_names()
        self.drawn = []
        self.pool = list(self.names)
        self.rolling = False
        self.timer = None
        self.interval = self._interval_from_speed(self.cfg["speed"])
        self.current_name = ""
        self.bg_base = None
        self.bg_img_tk = None
        self._bg_cache = {}
        self._last_bg_key = None
        self._last_bg_time = 0.0
        self._relayout_running = False
        self.fullscreen = False

        self.root.title(self.cfg["title"])
        self.root.minsize(960, 600)
        sw = self.root.winfo_screenwidth() or 1280
        sh = self.root.winfo_screenheight() or 800
        w = max(960, min(1280, sw - 80))
        h = max(600, min(800, sh - 140))
        self.root.geometry("%dx%d" % (w, h))
        self._resize_job = None

        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg=COL_BG_TOP)
        self.canvas.pack(fill="both", expand=True)

        self._build_buttons()
        self._load_background()
        self._draw()
        self._show_ready()
        self._bind_keys()
        self.root.report_callback_exception = self._on_callback_error

    def _on_callback_error(self, exc, val, tb):
        try:
            messagebox.showerror("程序出错", "%s: %s" % (exc.__name__, val))
        except Exception:
            pass

    # ---------- 工具 ----------
    def _interval_from_speed(self, speed):
        return max(12, int(140 - (speed - 1) * 1.3))

    def _cv_size(self):
        """画布尺寸；未映射时 winfo 返回 1，兜底为默认分辨率。"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50:
            w = 1280
        if h < 50:
            h = 800
        return w, h

    def _name_font_size(self, w):
        return 100

    def _fit_font_size(self, w, text):
        return self._name_font_size(w)

    # ---------- 背景 ----------
    def _load_background(self):
        """加载背景，并一次性完成预缩放与暗色叠加，避免缩放窗口时反复重算。"""
        self.bg_base = None
        self._bg_cache = {}
        self._last_bg_key = None
        pic = self.cfg["picture"]
        candidates = []
        if os.path.isabs(pic):
            candidates.append(pic)
        else:
            candidates.append(os.path.join(BASE_DIR, pic))
            for name, path in builtin_backgrounds():
                candidates.append(path)
        for p in candidates:
            if os.path.exists(p):
                try:
                    if HAS_PIL:
                        img = Image.open(p).convert("RGB")
                        w, h = img.size
                        scale = min(1.0, 1920.0 / max(w, h))
                        if scale < 1.0:
                            img = img.resize(
                                (max(1, int(w * scale)), max(1, int(h * scale))),
                                Image.LANCZOS)
                        dark = Image.new("RGB", img.size, (9, 16, 28))
                        self.bg_base = Image.blend(img, dark, 0.38)
                    else:
                        from tkinter import PhotoImage
                        self.bg_base = PhotoImage(file=p)
                    return
                except Exception:
                    continue
        self.bg_base = None

    def _bg_key_for(self, w, h):
        """向上取整到 40px 网格，缩放抖动时复用缓存。"""
        if w % 40:
            w = w + 40 - w % 40
        if h % 40:
            h = h + 40 - h % 40
        return w, h

    def _bg_photo_for(self, w, h):
        """按尺寸取缓存照片；没有则快速渲染并最多保留 2 张，防止内存膨胀。"""
        if self.bg_base is None:
            return None
        if isinstance(self.bg_base, Image.Image):
            bw, bh = self._bg_key_for(w, h)
            key = (bw, bh)
            photo = self._bg_cache.get(key)
            if photo is None:
                photo = ImageTk.PhotoImage(
                    self.bg_base.resize((bw, bh), Image.BILINEAR))
                self._bg_cache[key] = photo
                if len(self._bg_cache) > 2:
                    self._bg_cache.pop(next(iter(self._bg_cache)))
            self.bg_img_tk = photo
            return photo
        return self.bg_base

    # ---------- 按钮 ----------
    def _build_buttons(self):
        self.btn_main = CanvasButton(self.canvas, "btn_main", "开始抽签",
                                     self.toggle_roll, kind="primary", w=240, h=64,
                                     font_size=21)
        self.btn_list = CanvasButton(self.canvas, "btn_list", "名单",
                                     self.edit_names, kind="secondary", w=88, h=36)
        self.btn_set = CanvasButton(self.canvas, "btn_set", "设置",
                                    self.open_settings, kind="secondary", w=88, h=36)
        self.btn_reset = CanvasButton(self.canvas, "btn_reset", "重新点名",
                                      self.reset_round, kind="secondary", w=104, h=36)
        self.btn_fs = CanvasButton(self.canvas, "btn_fs", "全屏",
                                   self.toggle_fullscreen, kind="secondary", w=64, h=30,
                                   font_size=11)
        self.var_mode = tk.BooleanVar(value=not self.cfg["repeat"])
        self.chk_mode = tk.Checkbutton(
            self.canvas, text="不重复点名", variable=self.var_mode,
            bg=COL_BG_BOT, fg=COL_SUB, selectcolor=COL_INPUT,
            activebackground=COL_BG_BOT, activeforeground=COL_TEXT,
            highlightthickness=0, bd=0, cursor="hand2",
            font=(FONT, 11))
        self.var_speed = tk.IntVar(value=self.cfg["speed"])
        self.speed_scale = tk.Scale(
            self.canvas, from_=1, to=100, orient="horizontal", variable=self.var_speed,
            command=self._on_speed, bg=COL_BG_BOT, fg=COL_SUB, troughcolor=COL_INPUT,
            highlightthickness=0, bd=0, length=150, showvalue=False,
            font=(FONT, 9))
        self.chk_mode.place(relx=0.03, rely=0.935, anchor="w")
        self.speed_scale.place(relx=0.03, rely=0.885, anchor="w")

    def _place_buttons(self):
        w, h = self._cv_size()
        cx = w / 2
        self.btn_main.place(cx, h * 0.90)
        self.btn_fs.place(w - 42, 40, anchor="e")
        self.btn_list.place(w - 150, h * 0.885, anchor="e")
        self.btn_set.place(w - 46, h * 0.885, anchor="e")
        self.btn_reset.place(w - 150, h * 0.935, anchor="e")

    # ---------- 静态绘制 ----------
    def _draw_bg(self, w, h):
        """重绘背景层（跟随窗口缩放），置于所有内容之下。"""
        self.canvas.delete("bglayer")
        photo = self._bg_photo_for(w, h)
        if photo is not None:
            self.canvas.create_image(0, 0, image=photo, anchor="nw", tags="bglayer")
        else:
            self.canvas.create_rectangle(0, 0, w, h, fill=COL_BG_TOP, tags="bglayer")
            self.canvas.create_rectangle(0, h * 0.5, w, h, fill=COL_BG_BOT, tags="bglayer")
        self.canvas.tag_lower("bglayer")
        self._last_bg_key = self._bg_key_for(w, h)
        self._last_bg_time = time.monotonic()

    def _draw(self):
        # 只清理静态层（背景+文字），保留按钮画布项
        self.canvas.delete("static")
        w, h = self._cv_size()
        self._draw_bg(w, h)

        # 标题（居中，简约）
        self.title_id = self.canvas.create_text(
            w / 2, h * 0.075, text=self.cfg["title"], fill=COL_TEXT,
            font=(FONT, 26, "bold"), tags="static")
        tip = self.cfg["tip"] or "随机抽选 · 公平公正"
        self.tip_id = self.canvas.create_text(
            w / 2, h * 0.075 + 38, text=tip, fill=COL_SUB, font=(FONT, 12),
            tags="static")

        # 中央名字区（字号固定，不随内容变化）
        self.name_id = self.canvas.create_text(
            w / 2, h * 0.38, text="", fill=COL_TEXT,
            font=(FONT, 100, "bold"), tags="static")
        self.status_id = self.canvas.create_text(
            w / 2, h * 0.38 + 104, text="", fill=COL_SUB, font=(FONT, 14),
            tags="static")

        # 已抽中列表（右下角）
        self.drawn_label_id = self.canvas.create_text(
            w - 30, h * 0.70, text="", fill=COL_SUB, anchor="se",
            font=(FONT, 11, "bold"), tags="static")
        self.drawn_id = self.canvas.create_text(
            w - 30, h * 0.70 + 26, text="", fill=COL_TEXT, anchor="se",
            font=(FONT, 13), tags="static")

        # 底部版权
        if self.cfg["show_copyright"]:
            self.canvas.create_text(
                w / 2, h - 16, text=self.cfg["tip"] or "",
                fill=COL_DIM, font=(FONT, 9), tags="static")

        self._place_buttons()
        self._layout_texts()

    def _layout_texts(self):
        w = self.canvas.winfo_width() or 1280
        h = self.canvas.winfo_height() or 800
        size = self._name_font_size(w)
        self.canvas.coords(self.title_id, w / 2, h * 0.075)
        self.canvas.coords(self.tip_id, w / 2, h * 0.075 + 38)
        self.canvas.itemconfig(self.name_id, font=(FONT, size, "bold"))
        self.canvas.coords(self.name_id, w / 2, h * 0.38)
        self.canvas.coords(self.status_id, w / 2, h * 0.38 + 104)
        self.canvas.coords(self.drawn_label_id, w - 30, h * 0.70)
        self.canvas.coords(self.drawn_id, w - 30, h * 0.70 + 26)

    # ---------- 状态显示 ----------
    def _show_ready(self):
        self.canvas.itemconfig(self.name_id, text="", fill=COL_TEXT)
        w = self.canvas.winfo_width() or 1280
        if not self.names:
            self.canvas.itemconfig(
                self.name_id, text="名单为空",
                font=(FONT, self._fit_font_size(w, "名单为空"), "bold"))
            self.canvas.itemconfig(self.status_id,
                                   text="点击右下角「名单」按钮添加学生姓名", fill=COL_SUB)
        else:
            hint = "点击「开始抽签」"
            self.canvas.itemconfig(self.name_id, text=hint, fill=COL_DIM,
                                   font=(FONT, self._fit_font_size(w, hint), "bold"))
            self.canvas.itemconfig(
                self.status_id,
                text="共 %d 人 · 按空格键或点击按钮开始" % len(self.names), fill=COL_SUB)
        self._sync_main_button()
        self._update_drawn_list()

    def _sync_main_button(self):
        if self.rolling:
            self.btn_main.set_text("停　止")
        elif self.drawn:
            self.btn_main.set_text("再抽一位")
        else:
            self.btn_main.set_text("开始抽签")

    def _update_drawn_list(self):
        n = len(self.drawn)
        total = len(self.names)
        self.canvas.itemconfig(self.drawn_label_id, text="已抽中  %d / %d" % (n, total))
        shown = "　".join(self.drawn[-10:])
        if n > 10:
            shown = "… " + shown
        self.canvas.itemconfig(self.drawn_id, text=shown)

    # ---------- 抽签逻辑 ----------
    def toggle_roll(self):
        if self.rolling:
            self.stop_roll()
        else:
            self.start_roll()

    def start_roll(self):
        if not self.names:
            messagebox.showinfo("提示", "名单为空。点击「名单」按钮添加学生姓名后即可抽签。")
            return
        if self.var_mode.get() and not self.pool:
            messagebox.showinfo("提示", "所有人都已抽过，点击「重新点名」可再次抽取。")
            return
        self.rolling = True
        self.canvas.itemconfig(self.name_id, text="", fill=COL_TEXT)
        self.canvas.itemconfig(self.status_id, text="正在抽签…", fill=COL_SUB)
        self._sync_main_button()
        self._roll_step()

    def _roll_step(self):
        if not self.rolling:
            return
        pool = self.pool if (self.var_mode.get() and self.pool) else self.names
        self.current_name = random.choice(pool)
        self.canvas.itemconfig(self.name_id, text=self.current_name)
        self.timer = self.root.after(self.interval, self._roll_step)

    def stop_roll(self):
        self.rolling = False
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        if not self.current_name:
            return
        name = self.current_name
        self.drawn.append(name)
        if self.var_mode.get() and name in self.pool:
            self.pool.remove(name)
        self.canvas.itemconfig(self.name_id, text=name, fill=COL_GOLD)
        remain_txt = ""
        if self.var_mode.get():
            remain_txt = "  ·  还剩 %d 人可抽" % len(self.pool)
        self.canvas.itemconfig(self.status_id,
                               text="抽中！结果已保存到 result.txt" + remain_txt,
                               fill=COL_HIT_TEXT)
        self._update_drawn_list()
        self._save_result([name])
        self._flash()
        self._sync_main_button()

    def _flash(self):
        # 抽中反馈：金色亮度脉冲，字号保持不变
        colors = (COL_GOLD, "#ffe28a", COL_GOLD, "#ffedb3", COL_GOLD)

        def step(n):
            if n >= len(colors):
                return
            self.canvas.itemconfig(self.name_id, fill=colors[n])
            self.root.after(70, lambda: step(n + 1))

        step(0)

    def reset_round(self):
        if self.rolling:
            self.rolling = False
            if self.timer:
                self.root.after_cancel(self.timer)
                self.timer = None
        self.drawn = []
        self.pool = list(self.names)
        self.current_name = ""
        self._show_ready()

    def _on_speed(self, val):
        self.cfg["speed"] = int(float(val))
        self.interval = self._interval_from_speed(self.cfg["speed"])

    # ---------- 结果保存 ----------
    def _save_result(self, names):
        block = (
            "\r\n** 抽签点名程序 结果 **\r\n"
            "项目名称：{title}\r\n"
            "抽奖时间：{time}\r\n"
            "{names}\r\n"
        ).format(
            title=self.cfg["title"],
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            names="\r\n".join(names),
        )
        try:
            with open(RESULT_FILE, "a", encoding="gbk", errors="replace", newline="") as f:
                f.write(block)
        except Exception:
            with open(RESULT_FILE, "a", encoding="utf-8", errors="replace", newline="") as f:
                f.write(block)

    # ---------- 动作 ----------
    def open_settings(self):
        SettingsDialog(self.root, self.cfg, self._apply_settings)

    def _apply_settings(self, cfg):
        self.cfg = cfg
        self.var_speed.set(cfg["speed"])
        self.var_mode.set(not cfg["repeat"])
        self.interval = self._interval_from_speed(cfg["speed"])
        self.root.title(cfg["title"])
        self._load_background()
        self._draw()
        self._show_ready()

    def edit_names(self):
        if self.rolling:
            self.rolling = False
            if self.timer:
                self.root.after_cancel(self.timer)
                self.timer = None
        if not open_text_editor(NUM_FILE):
            messagebox.showerror("错误", "无法打开 num.txt，请手动编辑。")
        if messagebox.askyesno("重新加载", "编辑完成后是否立即重新加载名单？"):
            self.reload_names()

    def reload_names(self):
        self.names = load_names()
        self.reset_round()

    def toggle_fullscreen(self):
        now = time.monotonic()
        if now - getattr(self, "_fs_last", 0.0) < 0.35:
            return
        self._fs_last = now
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            # 用 overrideredirect 实现全屏，绕开 Tk 在 Windows 上
            # "-fullscreen" 属性与外部窗口缩放冲突导致的 C 层死循环
            self._saved_geom = self.root.geometry()
            self.root.overrideredirect(True)
            self.root.geometry("%dx%d+0+0" % (
                self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        else:
            self.root.overrideredirect(False)
            self.root.geometry(getattr(self, "_saved_geom", "1280x800"))
        self.btn_fs.set_text("退出全屏" if self.fullscreen else "全屏")
        self._relayout()
        self.root.focus_force()

    # ---------- 事件 ----------
    def _bind_keys(self):
        self.root.bind("<space>", lambda e: self.toggle_roll())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self._try_exit_fullscreen())
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget != self.root:
            return
        # 轻量：立即跟随窗口调整文字/按钮位置，保持手感
        self._relayout_light()
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        # 重量（背景渲染）：等缩放停止后再执行，且内部有限流
        self._resize_job = self.root.after(120, self._relayout)

    def _relayout_light(self):
        try:
            self._layout_texts()
            self._place_buttons()
        except Exception:
            pass

    def _relayout(self):
        self._resize_job = None
        if self._relayout_running:
            return
        self._relayout_running = True
        try:
            w, h = self._cv_size()
            if self.canvas.winfo_viewable():
                key = self._bg_key_for(w, h)
                if key != self._last_bg_key and \
                        time.monotonic() - self._last_bg_time >= 0.15:
                    self._draw_bg(w, h)
            self._relayout_light()
        finally:
            self._relayout_running = False

    def _try_exit_fullscreen(self):
        if self.fullscreen:
            self.toggle_fullscreen()


# ---------------- 设置对话框 ----------------
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg, on_save):
        super().__init__(master)
        self.cfg = dict(cfg)
        self.on_save = on_save
        self.title("设置")
        self.configure(bg=COL_PANEL)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.thumb_photos = []
        self.bg_choice = self.cfg["picture"]
        self.builtin = builtin_backgrounds()
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - w) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - h) // 2
        self.geometry("+%d+%d" % (x, y))
        self.bind("<Escape>", lambda e: self.destroy())

    def _make_entry(self, parent, var):
        return tk.Entry(parent, textvariable=var, width=34, bg=COL_INPUT, fg=COL_TEXT,
                        insertbackground=COL_TEXT, relief="flat",
                        font=(FONT, 11))

    def _build(self):
        body = tk.Frame(self, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        # 标题
        tk.Label(body, text="项目标题", bg=COL_PANEL, fg=COL_SUB, font=(FONT, 10)
                 ).grid(row=0, column=0, sticky="w", padx=4, pady=5)
        self.var_title = tk.StringVar(value=self.cfg["title"])
        self._make_entry(body, self.var_title).grid(row=0, column=1, sticky="w", padx=4, pady=5)

        # 副标题（出品信息）
        tk.Label(body, text="副标题 / 出品信息", bg=COL_PANEL, fg=COL_SUB, font=(FONT, 10)
                 ).grid(row=1, column=0, sticky="w", padx=4, pady=5)
        self.var_tip = tk.StringVar(value=self.cfg["tip"])
        self._make_entry(body, self.var_tip).grid(row=1, column=1, sticky="w", padx=4, pady=5)

        # 背景选择
        tk.Label(body, text="背景", bg=COL_PANEL, fg=COL_SUB, font=(FONT, 10)
                 ).grid(row=2, column=0, sticky="nw", padx=4, pady=(8, 4))
        bgbox = tk.Frame(body, bg=COL_PANEL)
        bgbox.grid(row=2, column=1, sticky="w", padx=4, pady=(8, 4))
        self._build_bg_thumbs(bgbox)

        # 速度
        tk.Label(body, text="抽签速度", bg=COL_PANEL, fg=COL_SUB, font=(FONT, 10)
                 ).grid(row=3, column=0, sticky="w", padx=4, pady=5)
        spbox = tk.Frame(body, bg=COL_PANEL)
        spbox.grid(row=3, column=1, sticky="w", padx=4, pady=5)
        self.var_speed = tk.IntVar(value=max(1, min(100, self.cfg["speed"])))
        tk.Scale(spbox, from_=1, to=100, orient="horizontal", variable=self.var_speed,
                 bg=COL_PANEL, fg=COL_TEXT, troughcolor=COL_INPUT, highlightthickness=0,
                 length=220, font=(FONT, 9)).pack(side="left")
        tk.Label(spbox, text="慢 ← → 快", bg=COL_PANEL, fg=COL_DIM, font=(FONT, 9)
                 ).pack(side="left", padx=8)

        # 模式
        tk.Label(body, text="抽签模式", bg=COL_PANEL, fg=COL_SUB, font=(FONT, 10)
                 ).grid(row=4, column=0, sticky="w", padx=4, pady=5)
        self.var_repeat = tk.BooleanVar(value=self.cfg["repeat"])
        tk.Checkbutton(body, text="允许重复抽到同一人", variable=self.var_repeat,
                       bg=COL_PANEL, fg=COL_TEXT, selectcolor=COL_INPUT,
                       activebackground=COL_PANEL, activeforeground=COL_TEXT,
                       font=(FONT, 10)).grid(row=4, column=1, sticky="w", padx=4, pady=5)

        # 按钮
        btns = tk.Frame(self, bg=COL_PANEL)
        btns.pack(fill="x", pady=(0, 14))
        tk.Button(btns, text="保存", command=self._save, bg="#2f8a5b", fg="white",
                  activebackground="#3aa56d", activeforeground="white", relief="flat",
                  font=(FONT, 10), padx=26, pady=4).pack(side="right", padx=14)
        tk.Button(btns, text="取消", command=self.destroy, bg="#33465e", fg=COL_TEXT,
                  activebackground="#41546e", activeforeground="white", relief="flat",
                  font=(FONT, 10), padx=26, pady=4).pack(side="right")

    def _build_bg_thumbs(self, box):
        row = tk.Frame(box, bg=COL_PANEL)
        row.pack(side="top", anchor="w")
        self.bg_buttons = []
        self.bg_map = []  # (显示名, 路径)
        for name, path in self.builtin:
            self.bg_map.append((name, path))
            self.bg_buttons.append(self._make_thumb(row, name, path))
        self.custom_btn = tk.Button(row, text="＋ 自定义图片…", command=self._pick_custom,
                                    bg=COL_INPUT, fg=COL_SUB, relief="flat",
                                    activebackground=COL_BTN_HOVER, activeforeground=COL_TEXT,
                                    font=(FONT, 10), padx=10, pady=8)
        self.custom_btn.pack(side="left", padx=(8, 0))
        self.none_btn = tk.Button(row, text="无背景", command=lambda: self._select_bg("", ""),
                                  bg=COL_INPUT, fg=COL_SUB, relief="flat",
                                  activebackground=COL_BTN_HOVER, activeforeground=COL_TEXT,
                                  font=(FONT, 10), padx=10, pady=8)
        self.none_btn.pack(side="left", padx=6)
        self._refresh_highlight()

    def _make_thumb(self, parent, name, path):
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((116, 74), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.thumb_photos.append(photo)
        except Exception:
            photo = None
        btn = tk.Button(parent, image=photo, text=name, compound="top",
                        relief="flat", bd=3, bg=COL_INPUT,
                        activebackground=COL_BTN_HOVER, cursor="hand2",
                        font=(FONT, 9), fg=COL_SUB, activeforeground=COL_TEXT,
                        command=lambda: self._select_bg(name, path))
        btn.photo = photo
        btn.pack(side="left", padx=4)
        return btn

    def _select_bg(self, name, path):
        self.bg_choice = path if path else ""
        self._refresh_highlight()

    def _pick_custom(self):
        f = filedialog.askopenfilename(
            parent=self, initialdir=BASE_DIR,
            title="选择背景图片",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")])
        if not f:
            return
        self.bg_choice = f
        self._refresh_highlight()

    def _refresh_highlight(self):
        for i, (name, path) in enumerate(self.bg_map):
            selected = (self.bg_choice == path)
            self.bg_buttons[i].config(bg=COL_GOLD if selected else COL_INPUT,
                                      fg=COL_GOLD_DARK if selected else COL_SUB)
        custom = self.bg_choice and self.bg_choice not in [p for _, p in self.bg_map]
        self.custom_btn.config(bg=COL_GOLD if custom else COL_INPUT,
                               fg=COL_GOLD_DARK if custom else COL_SUB)
        self.none_btn.config(bg=COL_GOLD if not self.bg_choice else COL_INPUT,
                             fg=COL_GOLD_DARK if not self.bg_choice else COL_SUB)

    def _save(self):
        self.cfg["title"] = self.var_title.get().strip() or "抽签点名"
        self.cfg["tip"] = self.var_tip.get().strip()
        self.cfg["speed"] = max(1, min(100, self.var_speed.get()))
        self.cfg["repeat"] = self.var_repeat.get()
        pic = self.bg_choice
        if pic and os.path.isabs(pic) and os.path.dirname(pic) == BASE_DIR:
            pic = os.path.basename(pic)
        self.cfg["picture"] = pic
        save_config(self.cfg)
        self.on_save(self.cfg)
        self.destroy()


def main():
    root = tk.Tk()
    AwardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
