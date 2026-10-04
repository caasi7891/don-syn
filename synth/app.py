"""Desktop window for DON SYN."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

import numpy as np

from synth.engine import SynthEngine
from synth.keys import LABELS, SEMI_COUNT, is_black, semi_from_event
from synth.params import NOTE_NAMES, PARAMS, midi_name
from synth.paths import RECORDINGS
from synth.presets import (
    FACTORY_BY_NAME,
    FACTORY_NAMES,
    load_user_presets,
    save_user_presets,
)
from synth.wavfile import save_wav

BG = "#14161c"
PANEL = "#1e212b"
BORDER = "#343846"
TEXT = "#ece8e1"
DIM = "#9b968c"
AMBER = "#ffb15a"
TEAL = "#7ee0c8"
RED = "#ff5d5d"
SCOPE = "#8be9ff"
WHITE_KEY = "#f3efe6"
BLACK_KEY = "#2c3140"
PRESSED = "#ffb15a"
TRACK = "#3a3f50"
FONT = "Malgun Gothic"

OSC_WAVES = ["사인", "삼각", "톱니", "사각", "펄스", "노이즈"]
FILTER_TYPES = ["로우", "하이", "밴드", "끄기"]
LFO_WAVES = ["사인", "삼각", "톱니", "사각", "S&H"]
LFO_DEST = ["피치", "필터", "앰프", "폭"]
VOICE_MODES = ["폴리", "모노", "레가토"]
SCALES = ["반음계", "장조", "단조", "펜타", "블루스", "도리안"]
ARP_MODES = ["위", "아래", "왕복", "랜덤"]
ARP_DIVS = ["4분", "8분", "16분", "셋잇", "점8"]


def _enable_dpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class Knob(tk.Canvas):
    def __init__(self, master, label, name, value, command, fmt="num"):
        super().__init__(master, width=64, height=86, bg=PANEL, highlightthickness=0)
        spec = PARAMS[name]
        self.lo = float(spec.lo)
        self.hi = float(spec.hi)
        self.kind = "log" if spec.kind == "log" else ("int" if spec.kind == "int" else "lin")
        self.label = label
        self.fmt = fmt
        self.command = command
        self.default = spec.default
        self.value = self._coerce(value)
        self._origin = None
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Double-Button-1>", self._reset)
        self.bind("<MouseWheel>", self._wheel)
        self._draw()

    def _coerce(self, value):
        value = float(value)
        if self.kind == "log":
            value = min(self.hi, max(self.lo, value))
        else:
            value = min(self.hi, max(self.lo, value))
        if self.kind == "int":
            value = int(round(value))
        return value

    def _t(self):
        if self.kind == "log":
            return (np.log(self.value) - np.log(self.lo)) / (np.log(self.hi) - np.log(self.lo))
        return (float(self.value) - self.lo) / (self.hi - self.lo)

    def _from_t(self, t):
        t = min(1.0, max(0.0, float(t)))
        if self.kind == "log":
            value = float(np.exp(np.log(self.lo) + t * (np.log(self.hi) - np.log(self.lo))))
        else:
            value = self.lo + t * (self.hi - self.lo)
        return self._coerce(value)

    def _text(self):
        value = self.value
        if self.fmt == "hz":
            return "%d" % int(round(value)) if value < 1000 else "%.1fk" % (value / 1000.0)
        if self.fmt == "ms":
            return "%dms" % int(round(value * 1000)) if value < 1 else "%.2fs" % value
        if self.fmt == "pct":
            return "%d%%" % int(round(float(value) * 100))
        if self.fmt == "int":
            return "%d" % int(round(value))
        if self.fmt == "signed":
            return "%+d" % int(round(value))
        if self.fmt == "note":
            return NOTE_NAMES[int(round(value)) % 12]
        if self.fmt == "drive":
            return "%.1f" % float(value)
        return "%.2f" % float(value)

    def _draw(self):
        self.delete("all")
        cx, cy, radius = 32, 30, 18
        t = self._t()
        self.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#262a36", outline=TRACK)
        self.create_arc(
            cx - radius, cy - radius, cx + radius, cy + radius,
            start=225, extent=-270, style="arc", outline=TRACK, width=3,
        )
        self.create_arc(
            cx - radius, cy - radius, cx + radius, cy + radius,
            start=225, extent=-270 * t, style="arc", outline=AMBER, width=3,
        )
        angle = np.deg2rad(225 - 270 * t)
        self.create_line(
            cx, cy,
            cx + np.cos(angle) * (radius - 5),
            cy - np.sin(angle) * (radius - 5),
            fill=TEXT, width=2,
        )
        self.create_text(32, 58, text=self._text(), fill=TEAL, font=(FONT, 8, "bold"))
        self.create_text(32, 74, text=self.label, fill=DIM, font=(FONT, 8))

    def set(self, value, notify=False):
        self.value = self._coerce(value)
        self._draw()
        if notify and self.command:
            self.command(self.value)

    def _emit(self):
        if self.command:
            self.command(self.value)

    def _press(self, event):
        self._origin = (event.y, self._t())

    def _drag(self, event):
        if self._origin is None:
            return
        y0, t0 = self._origin
        fine = 0.25 if event.state & 0x0001 else 1.0
        self.value = self._from_t(t0 + (y0 - event.y) / 130.0 * fine)
        self._draw()
        self._emit()

    def _reset(self, _event):
        self.value = self._coerce(self.default)
        self._draw()
        self._emit()

    def _wheel(self, event):
        step = 0.03 if self.kind != "int" else 1.0 / max(1.0, self.hi - self.lo)
        if event.state & 0x0001:
            step *= 0.25
        if event.delta < 0:
            step = -step
        self.value = self._from_t(self._t() + step)
        self._draw()
        self._emit()


class Choice(tk.Frame):
    def __init__(self, master, options, value, command, cols=0):
        super().__init__(master, bg=PANEL)
        self.command = command
        self.value = int(value)
        self.buttons = []
        for index, name in enumerate(options):
            button = tk.Label(
                self, text=name, bg="#2a2e3a", fg=TEXT, padx=4, pady=2,
                font=(FONT, 8), cursor="hand2",
            )
            button.bind("<Button-1>", lambda _e, i=index: self._pick(i))
            if cols:
                button.grid(row=index // cols, column=index % cols, padx=1, pady=1, sticky="ew")
                self.columnconfigure(index % cols, weight=1)
            else:
                button.pack(side="left", padx=1, pady=1)
            self.buttons.append(button)
        self._paint()

    def _paint(self):
        for index, button in enumerate(self.buttons):
            on = index == self.value
            button.configure(bg=AMBER if on else "#2a2e3a", fg="#241608" if on else TEXT)

    def _pick(self, index):
        self.value = int(index)
        self._paint()
        if self.command:
            self.command(self.value)

    def set(self, value, notify=False):
        self.value = int(round(float(value)))
        self._paint()
        if notify and self.command:
            self.command(self.value)


class Toggle(tk.Canvas):
    def __init__(self, master, text, value, command):
        super().__init__(master, width=78, height=26, bg=PANEL, highlightthickness=0, cursor="hand2")
        self.text = text
        self.value = 1 if value else 0
        self.command = command
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        self.delete("all")
        on = bool(self.value)
        self.create_oval(2, 4, 22, 22, fill=AMBER if on else "#3a3f50", outline="")
        self.create_text(48, 13, text=self.text, fill=TEXT if on else DIM, font=(FONT, 8, "bold"))

    def _toggle(self, _event):
        self.value = 0 if self.value else 1
        self._draw()
        if self.command:
            self.command(self.value)

    def set(self, value, notify=False):
        self.value = 1 if int(round(float(value))) else 0
        self._draw()
        if notify and self.command:
            self.command(self.value)


class Fader(tk.Canvas):
    def __init__(self, master, label, bipolar, command):
        super().__init__(master, width=46, height=200, bg=BG, highlightthickness=0, cursor="hand2")
        self.label = label
        self.bipolar = bipolar
        self.command = command
        self.value = 0.0
        self._held = False
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _span(self):
        top, bottom = 16, 168
        return top, bottom - top

    def _draw(self):
        self.delete("all")
        top, span = self._span()
        self.create_text(23, 186, text=self.label, fill=DIM, font=(FONT, 8))
        self.create_rectangle(18, top, 28, top + span, fill="#2a2e3a", outline="")
        if self.bipolar:
            t = (self.value + 1.0) * 0.5
            center = top + span / 2.0
            y = top + (1.0 - t) * span
            self.create_rectangle(18, min(center, y), 28, max(center, y), fill=AMBER, outline="")
        else:
            y = top + (1.0 - self.value) * span
            self.create_rectangle(18, y, 28, top + span, fill=TEAL, outline="")
        self.create_rectangle(12, y - 4, 34, y + 4, fill=TEXT, outline="")

    def _set(self, event):
        self._held = True
        top, span = self._span()
        t = 1.0 - (event.y - top) / float(span)
        t = min(1.0, max(0.0, t))
        self.value = t * 2.0 - 1.0 if self.bipolar else t
        self._draw()
        if self.command:
            self.command(self.value)

    def _release(self, _event):
        self._held = False
        if self.bipolar:
            self._spring()

    def _spring(self):
        if self._held or not self.bipolar:
            return
        if abs(self.value) < 0.02:
            self.value = 0.0
            self._draw()
            if self.command:
                self.command(0.0)
            return
        self.value *= 0.6
        self._draw()
        if self.command:
            self.command(self.value)
        self.after(16, self._spring)


class DonSynApp(tk.Tk):
    def __init__(self, audio=True):
        _enable_dpi()
        super().__init__()
        self.title("DON SYN — 키보드 신디사이저")
        self.configure(bg=BG)
        self.geometry("1420x900+80+40")
        self.minsize(1360, 780)
        self.engine = SynthEngine()
        self.controls = {}
        self.holds = {}
        self._flags = set()
        self._bend_keys = set()
        self._loading = True
        self._modal = False
        self.preset_name = "기본"
        self.user_presets = load_user_presets()
        self.want_record = False
        self.status_msg = "키보드를 누르거나 건반을 클릭해서 연주하세요"
        self.status_until = 0
        self._key_size = (0, 0)
        self._geom = []
        self._key_ids = {}
        self._scope_line = None
        self._scope_n = 0
        self.stream = None
        self.sd = None
        self.device = None
        self.octave = 0
        self.mouse_down = False
        self._build()
        self._loading = False
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind_all("<KeyPress>", self._key_down)
        self.bind_all("<KeyRelease>", self._key_up)
        self.bind("<FocusOut>", lambda _e: self.after(40, self._check_focus))
        if audio:
            self.after(80, self._start_audio)
        self.after(60, self._draw_keys)
        self.after(33, self._tick)
        self.after(120, self.focus_force)

    def _build(self):
        tk.Frame(self, bg=AMBER, height=3).grid(row=0, column=0, sticky="ew")
        self._build_header().grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 2))
        self._fill_row(self._osc_filter_env).grid(row=2, column=0, sticky="nsew", padx=8, pady=3)
        self._fill_row(self._lfo_voice_arp_fx).grid(row=3, column=0, sticky="nsew", padx=8, pady=3)
        self.scope = tk.Canvas(self, height=64, bg="#10131a", highlightthickness=1, highlightbackground=BORDER)
        self.scope.grid(row=4, column=0, sticky="ew", padx=10, pady=(4, 2))
        keys = tk.Frame(self, bg=BG)
        keys.grid(row=5, column=0, sticky="nsew", padx=10, pady=2)
        self.pitch = Fader(keys, "피치", True, self.engine.set_bend)
        self.mod = Fader(keys, "모드", False, self.engine.set_mod)
        self.pitch.pack(side="left", padx=(0, 4))
        self.mod.pack(side="left", padx=(0, 8))
        self.key_canvas = tk.Canvas(keys, bg="#10131a", height=150, highlightthickness=0)
        self.key_canvas.pack(side="left", fill="both", expand=True)
        self.key_canvas.bind("<Configure>", self._on_key_configure)
        self.key_canvas.bind("<Button-1>", self._mouse_down)
        self.key_canvas.bind("<B1-Motion>", self._mouse_move)
        self.key_canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.status_var = tk.StringVar(value=self.status_msg)
        tk.Label(
            self, textvariable=self.status_var, bg=BG, fg=DIM, anchor="w",
            font=(FONT, 8), padx=12,
        ).grid(row=6, column=0, sticky="ew")
        tk.Label(
            self, bg=BG, fg="#6f6a62", anchor="w", font=(FONT, 8), padx=12, pady=2,
            text="Z줄·Q줄 흰건반   S D G H J / 2 3 5 6 7 9 0 검은건반   ← → 또는 - = 옥타브   Space 서스테인   ↑↓ 피치   Esc 모두 끄기   노브 더블클릭 초기화   Shift+드래그 미세조정",
        ).grid(row=7, column=0, sticky="ew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        tk.Label(header, text="DON SYN", bg=BG, fg=AMBER, font=(FONT, 18, "bold")).pack(side="left")
        tk.Label(header, text="키보드 신디사이저", bg=BG, fg=DIM, font=(FONT, 9)).pack(side="left", padx=(8, 14))
        self.preset_btn = tk.Menubutton(
            header, text=self.preset_name, bg=PANEL, fg=TEXT, activebackground=AMBER,
            activeforeground="#241608", relief="flat", font=(FONT, 9), padx=10, pady=4,
            indicatoron=True, takefocus=0,
        )
        self.preset_menu = tk.Menu(self.preset_btn, tearoff=0, bg=PANEL, fg=TEXT, activebackground=AMBER, activeforeground="#241608", font=(FONT, 9))
        self.preset_btn.configure(menu=self.preset_menu)
        self.preset_btn.pack(side="left")
        self._rebuild_preset_menu()
        tk.Button(
            header, text="저장", command=self._save_preset, bg=PANEL, fg=TEXT,
            activebackground=AMBER, relief="flat", font=(FONT, 8), padx=8, takefocus=0,
        ).pack(side="left", padx=4)
        self.device_btn = tk.Menubutton(
            header, text="시스템 기본 출력", bg=PANEL, fg=DIM, relief="flat",
            font=(FONT, 8), padx=8, pady=4, takefocus=0,
        )
        self.device_menu = tk.Menu(self.device_btn, tearoff=0, bg=PANEL, fg=TEXT, activebackground=AMBER, font=(FONT, 8))
        self.device_btn.configure(menu=self.device_menu)
        self.device_btn.pack(side="left", padx=6)
        self.oct_var = tk.StringVar()
        self._update_oct_label()
        tk.Button(header, text="<", command=lambda: self._shift_octave(-1), bg=PANEL, fg=TEXT, relief="flat", font=(FONT, 10), width=2, takefocus=0).pack(side="left", padx=(8, 2))
        tk.Label(header, textvariable=self.oct_var, bg=BG, fg=TEXT, font=(FONT, 9)).pack(side="left", padx=4)
        tk.Button(header, text=">", command=lambda: self._shift_octave(1), bg=PANEL, fg=TEXT, relief="flat", font=(FONT, 10), width=2, takefocus=0).pack(side="left", padx=(2, 8))
        self.note_var = tk.StringVar(value="—")
        tk.Label(header, textvariable=self.note_var, bg=BG, fg=TEAL, font=(FONT, 14, "bold"), width=16, anchor="w").pack(side="left", padx=6)
        tk.Frame(header, bg=BG).pack(side="left", fill="x", expand=True)
        tk.Button(header, text="미리듣기", command=self._preview, bg=PANEL, fg=TEXT, relief="flat", font=(FONT, 8), padx=8, takefocus=0).pack(side="left", padx=3)
        self.rec_btn = tk.Button(header, text="녹음", command=self._toggle_rec, bg=PANEL, fg=TEXT, relief="flat", font=(FONT, 8), padx=8, takefocus=0)
        self.rec_btn.pack(side="left", padx=3)
        tk.Button(header, text="패닉", command=self._panic, bg="#3a2424", fg="#ffd0d0", relief="flat", font=(FONT, 8), padx=8, takefocus=0).pack(side="left", padx=3)
        tk.Label(header, text="볼륨", bg=BG, fg=DIM, font=(FONT, 8)).pack(side="left", padx=(8, 2))
        self.volume = tk.Scale(
            header, from_=0, to=1, resolution=0.01, orient="horizontal", showvalue=False,
            length=110, bg=BG, fg=TEXT, troughcolor="#2a2e3a", highlightthickness=0,
            activebackground=AMBER, sliderrelief="flat", takefocus=0, command=self._on_volume,
        )
        self.volume.set(self.engine.p["volume"])
        self.volume.pack(side="left")
        self.meter = tk.Canvas(header, width=70, height=22, bg=BG, highlightthickness=0)
        self.meter.pack(side="left", padx=6)
        return header

    def _fill_row(self, builder):
        row = tk.Frame(self, bg=BG)
        panels = builder(row)
        for index, panel in enumerate(panels):
            row.columnconfigure(index, weight=1, uniform="section")
            panel.grid(row=0, column=index, sticky="nsew", padx=3, pady=2)
        row.rowconfigure(0, weight=1)
        return row

    def _panel(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(frame, text=title, bg=PANEL, fg=AMBER, font=(FONT, 9, "bold")).pack(anchor="w", padx=8, pady=(5, 0))
        body = tk.Frame(frame, bg=PANEL)
        body.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        return frame, body

    def _knob_row(self, parent, items):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(anchor="center")
        for label, name, fmt in items:
            knob = Knob(row, label, name, self.engine.p[name], lambda v, n=name: self._set(n, v), fmt)
            knob.pack(side="left", padx=1)
            self.controls[name] = knob
        return row

    def _choice(self, parent, name, options, cols=0):
        choice = Choice(parent, options, self.engine.p[name], lambda v, n=name: self._set(n, v), cols=cols)
        choice.pack(anchor="w", pady=(0, 3))
        self.controls[name] = choice
        return choice

    def _osc_filter_env(self, parent):
        osc1, body = self._panel(parent, "오실레이터 1")
        self._choice(body, "osc1_wave", OSC_WAVES)
        self._knob_row(body, [
            ("옥타브", "osc1_oct", "signed"),
            ("반음", "osc1_semi", "signed"),
            ("디튠", "osc1_detune", "signed"),
            ("음량", "osc1_level", "pct"),
            ("폭", "osc1_pw", "pct"),
        ])
        osc2, body = self._panel(parent, "오실레이터 2")
        self._choice(body, "osc2_wave", OSC_WAVES)
        self._knob_row(body, [
            ("옥타브", "osc2_oct", "signed"),
            ("반음", "osc2_semi", "signed"),
            ("디튠", "osc2_detune", "signed"),
            ("음량", "osc2_level", "pct"),
            ("폭", "osc2_pw", "pct"),
        ])
        filt, body = self._panel(parent, "필터")
        self._choice(body, "filter_type", FILTER_TYPES)
        self._knob_row(body, [
            ("컷오프", "cutoff", "hz"),
            ("레조", "resonance", "pct"),
            ("엔브", "filter_env", "pct"),
            ("트래킹", "filter_track", "pct"),
        ])
        env, body = self._panel(parent, "엔벨롭")
        tk.Label(body, text="앰프", bg=PANEL, fg=DIM, font=(FONT, 8)).pack(anchor="w")
        self._knob_row(body, [
            ("어택", "amp_a", "ms"), ("디케이", "amp_d", "ms"),
            ("서스", "amp_s", "pct"), ("릴리즈", "amp_r", "ms"),
        ])
        tk.Label(body, text="필터", bg=PANEL, fg=DIM, font=(FONT, 8)).pack(anchor="w")
        self._knob_row(body, [
            ("어택", "flt_a", "ms"), ("디케이", "flt_d", "ms"),
            ("서스", "flt_s", "pct"), ("릴리즈", "flt_r", "ms"),
        ])
        return [osc1, osc2, filt, env]

    def _lfo_voice_arp_fx(self, parent):
        lfo, body = self._panel(parent, "LFO")
        self._choice(body, "lfo_wave", LFO_WAVES)
        self._knob_row(body, [
            ("속도", "lfo_rate", "hz"),
            ("깊이", "lfo_depth", "pct"),
        ])
        tk.Label(body, text="대상", bg=PANEL, fg=DIM, font=(FONT, 8)).pack(anchor="w", pady=(4, 0))
        self._choice(body, "lfo_dest", LFO_DEST)
        voice, body = self._panel(parent, "보이스 / 스케일")
        self._choice(body, "voice_mode", VOICE_MODES)
        self._choice(body, "scale", SCALES, cols=3)
        self._knob_row(body, [
            ("글라이드", "glide", "ms"),
            ("보이스", "poly", "int"),
            ("세기", "velocity", "pct"),
            ("튜닝", "tune", "signed"),
            ("조성", "root", "note"),
        ])
        arp, body = self._panel(parent, "아르페지오")
        top = tk.Frame(body, bg=PANEL)
        top.pack(anchor="w", fill="x")
        toggle = Toggle(top, "켜기", self.engine.p["arp_on"], lambda v: self._set("arp_on", v))
        toggle.pack(side="left", padx=(0, 6))
        self.controls["arp_on"] = toggle
        hold = Toggle(top, "홀드", self.engine.p["hold"], lambda v: self._set("hold", v))
        hold.pack(side="left")
        self.controls["hold"] = hold
        self._choice(body, "arp_mode", ARP_MODES)
        self._choice(body, "arp_div", ARP_DIVS)
        self._knob_row(body, [
            ("템포", "arp_bpm", "int"),
            ("옥타브", "arp_oct", "int"),
            ("게이트", "arp_gate", "pct"),
        ])
        fx, body = self._panel(parent, "이펙트")
        self._knob_row(body, [
            ("드라이브", "drive", "drive"),
            ("딜레이", "delay_mix", "pct"),
            ("시간", "delay_time", "ms"),
            ("피드백", "delay_fb", "pct"),
        ])
        self._knob_row(body, [
            ("코러스", "chorus_mix", "pct"),
            ("리버브", "reverb_mix", "pct"),
        ])
        return [lfo, voice, arp, fx]

    def _set(self, name, value):
        self.engine.set_param(name, value)
        if not self._loading:
            self._mark_edited()

    def _on_volume(self, value):
        self.engine.set_param("volume", float(value))
        if not self._loading:
            self._mark_edited()

    def _mark_edited(self):
        if not self.preset_name.endswith(" ●"):
            self.preset_name += " ●"
            self.preset_btn.configure(text=self.preset_name)

    def _rebuild_preset_menu(self):
        menu = self.preset_menu
        menu.delete(0, "end")
        for name in FACTORY_NAMES:
            menu.add_command(label=name, command=lambda n=name: self._select_factory(n))
        if self.user_presets:
            menu.add_separator()
            for name in self.user_presets:
                menu.add_command(label=name, command=lambda n=name: self._select_user(n))

    def _apply_preset(self, name, params):
        self._loading = True
        try:
            self.engine.load(params)
            for key, widget in self.controls.items():
                if key in self.engine.p:
                    widget.set(self.engine.p[key], notify=False)
            self.volume.set(self.engine.p["volume"])
        finally:
            self._loading = False
        self.preset_name = name
        self.preset_btn.configure(text=name)
        self.focus_set()

    def _select_factory(self, name):
        self._apply_preset(name, FACTORY_BY_NAME[name])

    def _select_user(self, name):
        self._apply_preset(name, self.user_presets[name])

    def _save_preset(self):
        self._modal = True
        try:
            name = simpledialog.askstring("프리셋 저장", "프리셋 이름", parent=self)
        finally:
            self._modal = False
            self.focus_set()
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in FACTORY_BY_NAME:
            name = name + " 사용자"
        self.user_presets[name] = self.engine.params_snapshot()
        try:
            save_user_presets(self.user_presets)
        except OSError as exc:
            messagebox.showerror("저장 실패", str(exc), parent=self)
            return
        self._rebuild_preset_menu()
        self.preset_name = name
        self.preset_btn.configure(text=name)
        self._say("프리셋을 저장했습니다: %s" % name)

    def _say(self, text, ms=4000):
        self.status_msg = text
        self.status_until = self._now() + ms

    def _now(self):
        return int(self.tk.call("clock", "milliseconds"))

    def _base(self):
        return 60 + self.octave * 12

    def _update_oct_label(self):
        self.oct_var.set("옥타브 %+d   Z=%s" % (self.octave, midi_name(self._base())))

    def _shift_octave(self, delta):
        new = max(-3, min(3, self.octave + delta))
        if new == self.octave:
            return
        old_base = self._base()
        moved = []
        for midi, bag in list(self.holds.items()):
            for source in list(bag):
                if source == "mouse" or source.startswith("k"):
                    moved.append((source, midi - old_base))
                    self._unpress(midi, source)
        self.octave = new
        self._update_oct_label()
        self._draw_keys()
        base = self._base()
        for source, semi in moved:
            if 0 <= semi < SEMI_COUNT:
                self._press(base + semi, source)

    def _press(self, midi, source):
        midi = int(midi)
        current = None
        for held, bag in self.holds.items():
            if source in bag:
                current = held
                break
        if current == midi:
            return
        if current is not None:
            self._unpress(current, source)
        bag = self.holds.setdefault(midi, set())
        first = not bag
        bag.add(source)
        if first:
            self.engine.note_down(midi)
        self._paint_keys()

    def _unpress(self, midi, source):
        bag = self.holds.get(midi)
        if not bag or source not in bag:
            return
        bag.discard(source)
        if not bag:
            del self.holds[midi]
            self.engine.note_up(midi)
        self._paint_keys()

    def _unpress_source(self, source):
        for midi, bag in list(self.holds.items()):
            if source in bag:
                self._unpress(midi, source)

    def _panic(self):
        self.holds.clear()
        self._flags.discard("sustain")
        self._bend_keys.clear()
        self.engine.set_bend(0.0)
        self.engine.panic()
        self._paint_keys()
        self._say("모든 소리를 껐습니다", 1500)

    def _apply_key_bend(self):
        if "Up" in self._bend_keys and "Down" not in self._bend_keys:
            self.engine.set_bend(1.0)
        elif "Down" in self._bend_keys and "Up" not in self._bend_keys:
            self.engine.set_bend(-1.0)
        else:
            self.engine.set_bend(0.0)

    def _check_focus(self):
        focus = self.focus_get()
        if focus is None:
            self._drop_live_keys()
            return
        try:
            outside = focus.winfo_toplevel() is not self
        except tk.TclError:
            outside = True
        if outside:
            self._drop_live_keys()

    def _drop_live_keys(self):
        if not self.holds and not self._bend_keys and "sustain" not in self._flags:
            return
        self.holds.clear()
        self._flags.clear()
        self._bend_keys.clear()
        self.engine.set_bend(0.0)
        self.engine.release_all()
        self._paint_keys()

    def _key_down(self, event):
        if self._modal:
            return
        focus = self.focus_get()
        if focus is not None:
            try:
                if focus.winfo_toplevel() is not self:
                    return
            except tk.TclError:
                return
        ks = event.keysym
        if ks == "Escape":
            self._panic()
            return "break"
        if ks == "space":
            if "sustain" not in self._flags:
                self._flags.add("sustain")
                self.engine.set_sustain(True)
            return "break"
        if ks in ("Left", "minus"):
            if "oct-" not in self._flags:
                self._flags.add("oct-")
                self._shift_octave(-1)
            return "break"
        if ks in ("Right", "equal"):
            if "oct+" not in self._flags:
                self._flags.add("oct+")
                self._shift_octave(1)
            return "break"
        if ks in ("Up", "Down"):
            self._bend_keys.add(ks)
            self._apply_key_bend()
            return "break"
        semi = semi_from_event(event.keycode, event.keysym)
        if semi is None:
            return
        self._press(self._base() + semi, "k%d" % event.keycode)
        return "break"

    def _key_up(self, event):
        ks = event.keysym
        if ks == "space":
            self._flags.discard("sustain")
            if not self._modal:
                self.engine.set_sustain(False)
            return
        if ks in ("Left", "minus"):
            self._flags.discard("oct-")
            return
        if ks in ("Right", "equal"):
            self._flags.discard("oct+")
            return
        if ks in ("Up", "Down"):
            self._bend_keys.discard(ks)
            self._apply_key_bend()
            return
        self._unpress_source("k%d" % event.keycode)

    def _on_key_configure(self, event):
        size = (event.width, event.height)
        if size == self._key_size or event.width < 80 or event.height < 40:
            return
        self._key_size = size
        self._draw_keys()

    def _draw_keys(self):
        canvas = self.key_canvas
        width = max(canvas.winfo_width(), 400)
        height = max(canvas.winfo_height(), 110)
        canvas.delete("all")
        whites = [semi for semi in range(SEMI_COUNT) if not is_black(semi)]
        ww = (width - 4) / float(len(whites))
        self._geom = []
        white_x = {}
        index = 0
        base = self._base()
        for semi in range(SEMI_COUNT):
            if is_black(semi):
                continue
            x = 2 + index * ww
            rect = canvas.create_rectangle(x + 1, 2, x + ww - 1, height - 2, fill=WHITE_KEY, outline="#c8c2b6")
            canvas.create_text(x + ww / 2, height - 30, text=LABELS[semi], fill="#222", font=(FONT, 9, "bold"))
            canvas.create_text(x + ww / 2, height - 14, text=midi_name(base + semi), fill="#8a847a", font=(FONT, 7))
            if semi % 12 == 0:
                canvas.create_oval(x + ww / 2 - 2, height - 44, x + ww / 2 + 2, height - 40, fill=AMBER, outline="")
            self._geom.append({"semi": semi, "id": rect, "box": (x + 1, 2, x + ww - 1, height - 2)})
            white_x[semi] = x
            index += 1
        for semi in range(SEMI_COUNT):
            if not is_black(semi):
                continue
            x = white_x[semi - 1]
            bw = ww * 0.58
            bh = height * 0.62
            x0 = x + ww - bw / 2
            rect = canvas.create_rectangle(x0, 2, x0 + bw, bh, fill=BLACK_KEY, outline="#111")
            canvas.create_text(x0 + bw / 2, bh - 14, text=LABELS[semi], fill="#eee", font=(FONT, 8, "bold"))
            self._geom.append({"semi": semi, "id": rect, "box": (x0, 2, x0 + bw, bh)})
        self._key_ids = {item["semi"]: item["id"] for item in self._geom}
        self._paint_keys()

    def _semi_at(self, x, y):
        for item in reversed(self._geom):
            x0, y0, x1, y1 = item["box"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return item["semi"]
        return None

    def _paint_keys(self):
        if not self._key_ids:
            return
        base = self._base()
        down = set()
        for midi in self.engine.public_raw:
            semi = int(midi) - base
            if 0 <= semi < SEMI_COUNT:
                down.add(semi)
        for semi, rect in self._key_ids.items():
            if semi in down:
                fill = "#c47a28" if is_black(semi) else PRESSED
            else:
                fill = BLACK_KEY if is_black(semi) else WHITE_KEY
            self.key_canvas.itemconfig(rect, fill=fill)

    def _mouse_down(self, event):
        self.mouse_down = True
        self.focus_set()
        semi = self._semi_at(event.x, event.y)
        if semi is not None:
            self._press(self._base() + semi, "mouse")

    def _mouse_move(self, event):
        if not self.mouse_down:
            return
        semi = self._semi_at(event.x, event.y)
        midi = None if semi is None else self._base() + semi
        current = None
        for held, bag in self.holds.items():
            if "mouse" in bag:
                current = held
                break
        if midi is None:
            if current is not None:
                self._unpress(current, "mouse")
            return
        if current != midi:
            self._press(midi, "mouse")

    def _mouse_up(self, _event):
        self.mouse_down = False
        self._unpress_source("mouse")

    def _preview(self):
        if any(src.startswith("pv") for bag in self.holds.values() for src in bag):
            return
        notes = [self._base() + semi for semi in (0, 4, 7)]
        for index, midi in enumerate(notes):
            self._press(midi, "pv%d" % index)
        self.after(1100, lambda notes=notes: self._preview_off(notes))

    def _preview_off(self, notes):
        for index, midi in enumerate(notes):
            self._unpress(midi, "pv%d" % index)

    def _toggle_rec(self):
        if not self.want_record:
            self.engine.start_recording()
            self.want_record = True
            self.rec_btn.configure(text="정지", bg=RED, fg="white")
            self._say("녹음 중. 정지를 누르면 wav로 저장됩니다.")
            return
        self._save_from_engine()

    def _save_from_engine(self):
        audio, overflow = self.engine.stop_recording()
        self.want_record = False
        self.rec_btn.configure(text="녹음", bg=PANEL, fg=TEXT)
        if audio.size < self.engine.sr // 5:
            self._say("녹음이 너무 짧아서 저장하지 않았습니다.")
            return
        RECORDINGS.mkdir(exist_ok=True)
        stamp = self.tk.call("clock", "format", self.tk.call("clock", "seconds"), "-format", "%Y%m%d-%H%M%S")
        path = RECORDINGS / ("don-syn-%s.wav" % stamp)
        try:
            save_wav(path, audio, self.engine.sr)
        except OSError as exc:
            self._say("저장 실패: %s" % exc)
            return
        extra = " (10분에서 잘렸습니다)" if overflow else ""
        self._say("저장했습니다: %s%s" % (path.name, extra), 6000)

    def _draw_scope(self):
        copied = self.engine.copy_scope()
        if copied is None:
            return
        buf, write = copied
        canvas = self.scope
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 20 or height < 20:
            return
        n = min(len(buf), max(width, 300))
        if write >= n:
            view = buf[write - n:write]
        else:
            view = np.concatenate((buf[-(n - write):], buf[:write])) if write or n else buf[:1]
        if view.size == 0:
            return
        idx = np.linspace(0, view.size - 1, width).astype(int)
        ys = view[idx]
        heard = float(np.max(np.abs(ys))) if ys.size else 0.0
        ys = ys * min(4.0, 0.9 / max(0.22, heard))
        mid = height / 2.0
        amp = height / 2.0 - 4
        coords = []
        for i, sample in enumerate(ys):
            coords.extend((i, mid - float(sample) * amp))
        if self._scope_line is None or self._scope_n != width:
            canvas.delete("all")
            canvas.create_line(0, mid, width, mid, fill="#2a3144")
            self._scope_line = canvas.create_line(*coords, fill=SCOPE, width=1.4)
            self._scope_n = width
        else:
            canvas.coords(self._scope_line, *coords)

    def _paint_meter(self):
        peak = float(self.engine.public_peak)
        width = 70
        filled = int(min(1.0, peak) * width)
        color = RED if peak > 0.95 else AMBER if peak > 0.7 else TEAL
        self.meter.delete("all")
        self.meter.create_rectangle(0, 6, width, 16, fill="#2a2e3a", outline="")
        if filled:
            self.meter.create_rectangle(0, 6, filled, 16, fill=color, outline="")

    def _tick(self):
        try:
            self._paint_keys()
            self._draw_scope()
            self._paint_meter()
            if self.want_record and not self.engine.recording:
                self._save_from_engine()
            notes = " ".join(midi_name(n) for n in self.engine.public_notes[:6])
            cpu = self.engine.public_cpu * 100.0
            msg = self.status_msg
            if self.status_until and self._now() > self.status_until:
                self.status_msg = ""
                self.status_until = 0
                msg = ""
            if self.engine.public_status:
                msg = self.engine.public_status
            elif cpu > 90:
                msg = "부하가 높습니다. 보이스를 줄이거나 리버브를 낮춰 보세요."
            self.note_var.set(notes or "—")
            self.status_var.set("CPU %3.0f%%    %s" % (cpu, msg))
        finally:
            self.after(33, self._tick)

    def _start_audio(self):
        try:
            import sounddevice as sd
        except Exception as exc:
            self.engine.public_status = "오디오 라이브러리를 불러오지 못했습니다. (%s)" % exc
            return
        self.sd = sd
        self._fill_devices()
        self._open_stream(None)

    def _fill_devices(self):
        self.device_menu.delete(0, "end")
        self.device_menu.add_command(label="시스템 기본 출력", command=lambda: self._choose_device(None, "시스템 기본 출력"))
        try:
            devices = self.sd.query_devices()
        except Exception:
            return
        for index, info in enumerate(devices):
            if info["max_output_channels"] <= 0:
                continue
            label = info["name"]
            if len(label) > 42:
                label = label[:40] + "…"
            self.device_menu.add_command(
                label=label,
                command=lambda i=index, text=label: self._choose_device(i, text),
            )

    def _choose_device(self, device, label):
        self.device = device
        self.device_btn.configure(text=label)
        self._open_stream(device)
        self.focus_set()

    def _open_stream(self, device):
        if self.sd is None:
            return
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        try:
            self.stream = self.sd.OutputStream(
                samplerate=self.engine.sr,
                channels=2,
                dtype="float32",
                blocksize=512,
                device=device,
                latency="low",
                callback=self._audio_cb,
            )
            self.stream.start()
            self.engine.public_status = ""
        except Exception as exc:
            self.engine.public_status = "오디오 장치를 열지 못했습니다. %s" % exc

    def _audio_cb(self, outdata, frames, _time_info, status):
        if status:
            text = str(status).lower()
            if "underflow" in text:
                self.engine.public_status = "출력 버퍼가 밀렸습니다. 보이스를 낮춰 보세요."
        try:
            audio = self.engine.render(frames)
        except Exception as exc:
            self.engine.public_status = "엔진 오류: %s" % exc
            audio = np.zeros(frames, dtype=np.float32)
        if audio.shape[0] != frames:
            audio = np.zeros(frames, dtype=np.float32)
        outdata[:, 0] = audio
        outdata[:, 1] = audio

    def _close(self):
        try:
            if self.want_record:
                self._save_from_engine()
        except Exception:
            pass
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass
        self.destroy()


def main():
    app = DonSynApp(audio=True)
    app.mainloop()
