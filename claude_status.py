#!/usr/bin/env python3
"""
Claude Usage Monitor - Windows Taskbar Overlay
Muestra el uso de Claude y cuándo se renueva, flotando sobre la barra de tareas.

Cómo ejecutar: python claude_status.py
No necesita compilación - corre directamente como script Python (evita falsos positivos de antivirus).
"""

import tkinter as tk
from tkinter import font as tkfont, messagebox, simpledialog
import json
import os
import threading
import time
from pathlib import Path
import datetime
import webbrowser
import sys
import subprocess

# ── Importaciones opcionales ────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ── Constantes ───────────────────────────────────────────────────────────────
APP_NAME = "Claude Monitor"
VERSION  = "1.0.0"
CONFIG_PATH = Path.home() / ".claude_monitor" / "config.json"

TASKBAR_HEIGHT = 48          # píxeles de la barra de tareas de Windows
WINDOW_WIDTH   = 290
WINDOW_HEIGHT  = 115
MARGIN         = 10

DEFAULT_CONFIG = {
    "always_on_top":          True,
    "alpha":                  0.88,       # 0.0 (invisible) a 1.0 (opaco)
    "auto_refresh_seconds":   60,
    "theme":                  "dark",
    "position_x":             -1,         # -1 = auto (esquina superior derecha)
    "position_y":             -1,
    "anthropic_api_key":      "",
    "plan_type":              "pro",      # "free" | "pro" | "max" | "api"
    "monthly_tokens_limit":   0,          # 0 = desconocido
    "billing_reset_day":      1,          # día del mes en que se renueva
    "show_in_taskbar":        False,
    "compact":                False,
}

THEMES = {
    "dark": {
        "bg":         "#14141e",
        "bg2":        "#1e1e2e",
        "fg":         "#cdd6f4",
        "fg_dim":     "#6c7086",
        "accent":     "#7c4dff",
        "warn":       "#f38ba8",
        "bar_bg":     "#313244",
        "bar_fill":   "#7c4dff",
        "bar_warn":   "#f38ba8",
        "btn_bg":     "#1e1e2e",
        "btn_hover":  "#313244",
        "border":     "#313244",
        "title_fg":   "#89b4fa",
    },
    "light": {
        "bg":         "#eff1f5",
        "bg2":        "#e6e9ef",
        "fg":         "#4c4f69",
        "fg_dim":     "#9ca0b0",
        "accent":     "#7c4dff",
        "warn":       "#d20f39",
        "bar_bg":     "#dce0e8",
        "bar_fill":   "#7c4dff",
        "bar_warn":   "#d20f39",
        "btn_bg":     "#e6e9ef",
        "btn_hover":  "#dce0e8",
        "border":     "#ccd0da",
        "title_fg":   "#1e66f5",
    },
}

# ── Carga / guardado de configuración ────────────────────────────────────────
def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ── Lectura de datos de uso ───────────────────────────────────────────────────
def get_claude_data_dir() -> Path | None:
    """Busca la carpeta de datos de Claude Code en el sistema."""
    candidates = [
        Path.home() / ".claude",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Claude",
        Path(os.environ.get("APPDATA", ""))       / "Claude",
        Path(os.environ.get("USERPROFILE", ""))   / ".claude",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def parse_session_tokens_from_projects(claude_dir: Path) -> int:
    """
    Lee los archivos de proyecto de Claude Code para estimar tokens usados
    en el período actual.
    """
    total = 0
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return total

    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for proj_dir in projects_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        for jsonl_file in proj_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            # Filtrar por período actual
                            ts_str = entry.get("timestamp", "")
                            if ts_str:
                                try:
                                    ts = datetime.datetime.fromisoformat(
                                        ts_str.replace("Z", "+00:00")
                                    ).replace(tzinfo=None)
                                    if ts < month_start:
                                        continue
                                except Exception:
                                    pass
                            # Sumar tokens si existen
                            usage = entry.get("usage", {})
                            if usage:
                                total += usage.get("input_tokens", 0)
                                total += usage.get("output_tokens", 0)
                            # También en message.usage
                            msg = entry.get("message", {})
                            if msg:
                                mu = msg.get("usage", {})
                                total += mu.get("input_tokens", 0)
                                total += mu.get("output_tokens", 0)
                        except (json.JSONDecodeError, KeyError):
                            continue
            except (IOError, PermissionError):
                continue
    return total

def fetch_api_usage(api_key: str) -> dict:
    """
    Intenta obtener el uso desde la API de Anthropic.
    Devuelve dict con claves: tokens_used, tokens_limit, period_start, period_end, ok, error
    """
    result = {"ok": False, "error": "requests no instalado", "tokens_used": 0,
              "tokens_limit": 0, "period_start": None, "period_end": None}
    if not HAS_REQUESTS:
        return result
    if not api_key:
        result["error"] = "API key no configurada"
        return result

    now = datetime.datetime.utcnow()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end   = now

    url = "https://api.anthropic.com/v1/usage"
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }
    params = {
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            used = 0
            for item in data.get("data", []):
                used += item.get("input_tokens", 0)
                used += item.get("output_tokens", 0)
            result.update({
                "ok":           True,
                "tokens_used":  used,
                "period_start": start,
                "period_end":   end,
            })
        else:
            result["error"] = f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        result["error"] = str(e)[:120]
    return result

def days_until_reset(reset_day: int) -> int:
    """Calcula cuántos días faltan hasta el día de renovación del plan."""
    today = datetime.date.today()
    this_month_reset = today.replace(day=reset_day)
    if today >= this_month_reset:
        # Ya pasó este mes, el próximo reset es el mes siguiente
        if today.month == 12:
            next_reset = this_month_reset.replace(year=today.year + 1, month=1)
        else:
            next_reset = this_month_reset.replace(month=today.month + 1)
    else:
        next_reset = this_month_reset
    return (next_reset - today).days

def reset_date_str(reset_day: int) -> str:
    """Devuelve la fecha del próximo reset como string legible."""
    today = datetime.date.today()
    this_month_reset = today.replace(day=reset_day)
    if today >= this_month_reset:
        if today.month == 12:
            next_reset = this_month_reset.replace(year=today.year + 1, month=1)
        else:
            next_reset = this_month_reset.replace(month=today.month + 1)
    else:
        next_reset = this_month_reset
    MONTHS_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    return f"{next_reset.day} {MONTHS_ES[next_reset.month - 1]}"

# ── Ventana de configuración ─────────────────────────────────────────────────
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self.cfg    = cfg.copy()
        self.on_save = on_save
        t = THEMES[cfg.get("theme", "dark")]

        self.title("Configuración - Claude Monitor")
        self.configure(bg=t["bg"])
        self.resizable(False, False)
        self.grab_set()

        pad = {"padx": 12, "pady": 4}

        def label(text, row, col=0, **kw):
            tk.Label(self, text=text, bg=t["bg"], fg=t["fg"],
                     font=("Segoe UI", 9)).grid(row=row, column=col,
                                                sticky="w", **pad)

        # --- Plan ---
        label("Plan:", 0)
        self.plan_var = tk.StringVar(value=cfg.get("plan_type", "pro"))
        plan_menu = tk.OptionMenu(self, self.plan_var, "free", "pro", "max", "api")
        plan_menu.configure(bg=t["btn_bg"], fg=t["fg"], activebackground=t["btn_hover"],
                            relief="flat", borderwidth=1)
        plan_menu["menu"].configure(bg=t["btn_bg"], fg=t["fg"])
        plan_menu.grid(row=0, column=1, sticky="ew", **pad)

        # --- API Key ---
        label("API Key (opcional):", 1)
        self.api_var = tk.StringVar(value=cfg.get("anthropic_api_key", ""))
        api_entry = tk.Entry(self, textvariable=self.api_var, show="*",
                             bg=t["btn_bg"], fg=t["fg"], insertbackground=t["fg"],
                             relief="flat", width=32)
        api_entry.grid(row=1, column=1, sticky="ew", **pad)

        # --- Día de renovación ---
        label("Día de renovación:", 2)
        self.reset_day_var = tk.IntVar(value=cfg.get("billing_reset_day", 1))
        spin = tk.Spinbox(self, from_=1, to=28, textvariable=self.reset_day_var,
                          width=5, bg=t["btn_bg"], fg=t["fg"],
                          buttonbackground=t["btn_bg"], relief="flat")
        spin.grid(row=2, column=1, sticky="w", **pad)

        # --- Límite de tokens (0 = desconocido) ---
        label("Límite tokens/mes (0=auto):", 3)
        self.limit_var = tk.IntVar(value=cfg.get("monthly_tokens_limit", 0))
        tk.Entry(self, textvariable=self.limit_var, width=12,
                 bg=t["btn_bg"], fg=t["fg"], insertbackground=t["fg"],
                 relief="flat").grid(row=3, column=1, sticky="w", **pad)

        # --- Transparencia ---
        label("Transparencia (0.3–1.0):", 4)
        self.alpha_var = tk.DoubleVar(value=cfg.get("alpha", 0.88))
        tk.Scale(self, from_=0.3, to=1.0, resolution=0.05,
                 variable=self.alpha_var, orient="horizontal", length=180,
                 bg=t["bg"], fg=t["fg"], troughcolor=t["bar_bg"],
                 highlightthickness=0).grid(row=4, column=1, sticky="w", **pad)

        # --- Auto-refresh ---
        label("Refresco auto (segundos):", 5)
        self.refresh_var = tk.IntVar(value=cfg.get("auto_refresh_seconds", 60))
        tk.Spinbox(self, from_=10, to=3600, textvariable=self.refresh_var,
                   width=6, bg=t["btn_bg"], fg=t["fg"],
                   buttonbackground=t["btn_bg"], relief="flat").grid(
                       row=5, column=1, sticky="w", **pad)

        # --- Tema ---
        label("Tema:", 6)
        self.theme_var = tk.StringVar(value=cfg.get("theme", "dark"))
        tk.OptionMenu(self, self.theme_var, "dark", "light").grid(
            row=6, column=1, sticky="w", **pad)

        # --- Botones ---
        frame_btns = tk.Frame(self, bg=t["bg"])
        frame_btns.grid(row=7, column=0, columnspan=2, pady=12)

        tk.Button(frame_btns, text="Guardar", command=self._save,
                  bg=t["accent"], fg="#ffffff", relief="flat",
                  padx=16, pady=4,
                  font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)
        tk.Button(frame_btns, text="Cancelar", command=self.destroy,
                  bg=t["btn_bg"], fg=t["fg"], relief="flat",
                  padx=16, pady=4).pack(side="left", padx=6)

        # Centrar sobre la ventana padre
        self.update_idletasks()
        pw = parent.winfo_x() + parent.winfo_width()  // 2
        ph = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"+{pw - self.winfo_width()//2}+{ph - self.winfo_height()//2}")

    def _save(self):
        self.cfg["plan_type"]             = self.plan_var.get()
        self.cfg["anthropic_api_key"]     = self.api_var.get().strip()
        self.cfg["billing_reset_day"]     = int(self.reset_day_var.get())
        self.cfg["monthly_tokens_limit"]  = int(self.limit_var.get())
        self.cfg["alpha"]                 = round(float(self.alpha_var.get()), 2)
        self.cfg["auto_refresh_seconds"]  = int(self.refresh_var.get())
        self.cfg["theme"]                 = self.theme_var.get()
        self.on_save(self.cfg)
        self.destroy()

# ── Barra de progreso personalizada ──────────────────────────────────────────
class ProgressBar(tk.Canvas):
    def __init__(self, parent, t: dict, **kw):
        kw.setdefault("height", 8)
        kw.setdefault("bd", 0)
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, bg=t["bg"], **kw)
        self._t = t
        self._pct = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct: float):
        self._pct = max(0.0, min(1.0, pct))
        self._draw()

    def _draw(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2:
            return
        t  = self._t
        r  = h // 2   # radio de las esquinas redondeadas
        self.delete("all")
        # Fondo
        self._rounded_rect(2, 2, w - 2, h - 2, r, t["bar_bg"])
        # Relleno
        fill_w = max(0, int((w - 4) * self._pct))
        if fill_w > 0:
            color = t["bar_warn"] if self._pct > 0.85 else t["bar_fill"]
            self._rounded_rect(2, 2, 2 + fill_w, h - 2, r, color)

    def _rounded_rect(self, x1, y1, x2, y2, r, color):
        self.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90,  extent=90,  fill=color, outline="")
        self.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0,   extent=90,  fill=color, outline="")
        self.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90,  fill=color, outline="")
        self.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90,  fill=color, outline="")
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline="")

# ── Ventana principal ─────────────────────────────────────────────────────────
class ClaudeMonitor:
    def __init__(self):
        self.cfg   = load_config()
        self.data  = {}          # últimos datos recuperados
        self._drag_x = 0
        self._drag_y = 0
        self._refresh_timer = None
        self._spinning  = False
        self._spin_frame = 0

        self.root = tk.Tk()
        self._build_window()
        self._build_ui()
        self._position_window()
        self._start_auto_refresh()
        self.refresh()           # primera carga inmediata
        self.root.mainloop()

    # ── Construcción de ventana ───────────────────────────────────────────────
    def _build_window(self):
        r = self.root
        t = self._theme()

        r.title(APP_NAME)
        r.configure(bg=t["bg"])
        r.overrideredirect(True)          # sin bordes del sistema operativo
        r.attributes("-topmost",  self.cfg["always_on_top"])
        r.attributes("-alpha",    self.cfg["alpha"])

        # Ocultar/mostrar de la barra de tareas de Windows
        if not self.cfg.get("show_in_taskbar", False):
            r.attributes("-toolwindow", True)

        r.resizable(False, False)

        # Arrastrar ventana con clic izquierdo
        r.bind("<ButtonPress-1>",   self._drag_start)
        r.bind("<B1-Motion>",       self._drag_move)
        r.bind("<ButtonRelease-1>", self._drag_end)

        # Menú contextual con clic derecho
        r.bind("<Button-3>", self._show_context_menu)

    def _build_ui(self):
        t = self._theme()
        r = self.root
        W = WINDOW_WIDTH

        # Contenedor con borde
        self.frame = tk.Frame(r, bg=t["bg"], bd=1, relief="flat",
                              highlightbackground=t["border"],
                              highlightthickness=1)
        self.frame.pack(fill="both", expand=True)
        self.frame.bind("<ButtonPress-1>",   self._drag_start)
        self.frame.bind("<B1-Motion>",       self._drag_move)
        self.frame.bind("<Button-3>",        self._show_context_menu)

        # ── Barra de título ───────────────────────────────────────────────────
        title_frame = tk.Frame(self.frame, bg=t["bg2"])
        title_frame.pack(fill="x")
        title_frame.bind("<ButtonPress-1>",   self._drag_start)
        title_frame.bind("<B1-Motion>",       self._drag_move)
        title_frame.bind("<Button-3>",        self._show_context_menu)

        self.lbl_title = tk.Label(
            title_frame, text="● Claude Monitor",
            bg=t["bg2"], fg=t["title_fg"],
            font=("Segoe UI", 8, "bold"), anchor="w", padx=8)
        self.lbl_title.pack(side="left", fill="x", expand=True, pady=3)
        self.lbl_title.bind("<ButtonPress-1>", self._drag_start)
        self.lbl_title.bind("<B1-Motion>",     self._drag_move)

        # Botón ⚙
        self.btn_cfg = tk.Label(title_frame, text="⚙", bg=t["bg2"],
                                fg=t["fg_dim"], font=("Segoe UI", 10),
                                cursor="hand2", padx=4)
        self.btn_cfg.pack(side="right", pady=2, padx=2)
        self.btn_cfg.bind("<Button-1>", lambda e: self._open_settings())
        self.btn_cfg.bind("<Enter>",    lambda e: self.btn_cfg.config(fg=t["fg"]))
        self.btn_cfg.bind("<Leave>",    lambda e: self.btn_cfg.config(fg=t["fg_dim"]))

        # Botón ⟳
        self.btn_refresh = tk.Label(title_frame, text="⟳", bg=t["bg2"],
                                    fg=t["fg_dim"], font=("Segoe UI", 11),
                                    cursor="hand2", padx=4)
        self.btn_refresh.pack(side="right", pady=2)
        self.btn_refresh.bind("<Button-1>", lambda e: self.refresh())
        self.btn_refresh.bind("<Enter>",    lambda e: self.btn_refresh.config(fg=t["fg"]))
        self.btn_refresh.bind("<Leave>",    lambda e: self.btn_refresh.config(fg=t["fg_dim"]))

        # ── Cuerpo ────────────────────────────────────────────────────────────
        body = tk.Frame(self.frame, bg=t["bg"], padx=10, pady=6)
        body.pack(fill="both", expand=True)

        # Fila 1 – uso en tokens
        row1 = tk.Frame(body, bg=t["bg"])
        row1.pack(fill="x")
        self.lbl_usage = tk.Label(row1, text="Cargando...",
                                  bg=t["bg"], fg=t["fg"],
                                  font=("Segoe UI", 9, "bold"), anchor="w")
        self.lbl_usage.pack(side="left")
        self.lbl_pct = tk.Label(row1, text="",
                                bg=t["bg"], fg=t["accent"],
                                font=("Consolas", 9, "bold"), anchor="e")
        self.lbl_pct.pack(side="right")

        # Barra de progreso
        self.bar = ProgressBar(body, t, width=W - 24)
        self.bar.pack(fill="x", pady=(3, 6))

        # Fila 2 – renovación
        row2 = tk.Frame(body, bg=t["bg"])
        row2.pack(fill="x")
        self.lbl_renew = tk.Label(row2, text="",
                                  bg=t["bg"], fg=t["fg_dim"],
                                  font=("Segoe UI", 8), anchor="w")
        self.lbl_renew.pack(side="left")

        # Fila 3 – estado / timestamp
        self.lbl_status = tk.Label(body, text="",
                                   bg=t["bg"], fg=t["fg_dim"],
                                   font=("Segoe UI", 7), anchor="w")
        self.lbl_status.pack(fill="x", pady=(2, 0))

    # ── Posicionamiento ───────────────────────────────────────────────────────
    def _position_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = self.cfg.get("position_x", -1)
        y  = self.cfg.get("position_y", -1)
        if x < 0 or y < 0:
            x = sw - WINDOW_WIDTH  - MARGIN
            y = MARGIN
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    # ── Tema ──────────────────────────────────────────────────────────────────
    def _theme(self) -> dict:
        return THEMES.get(self.cfg.get("theme", "dark"), THEMES["dark"])

    # ── Refrescado de datos ───────────────────────────────────────────────────
    def refresh(self):
        """Lanza el refresco de datos en un hilo separado para no bloquear la UI."""
        self._start_spin()
        thread = threading.Thread(target=self._fetch_and_update, daemon=True)
        thread.start()

    def _fetch_and_update(self):
        data = self._collect_data()
        # Actualizar UI en el hilo principal
        self.root.after(0, lambda: self._update_ui(data))

    def _collect_data(self) -> dict:
        """Recopila datos de uso desde todas las fuentes disponibles."""
        result = {
            "tokens_used":   0,
            "tokens_limit":  self.cfg.get("monthly_tokens_limit", 0),
            "reset_day":     self.cfg.get("billing_reset_day", 1),
            "plan":          self.cfg.get("plan_type", "pro"),
            "source":        "local",
            "error":         None,
            "last_updated":  datetime.datetime.now(),
        }

        api_key = self.cfg.get("anthropic_api_key", "").strip()

        # ── Fuente 1: Anthropic API (si hay API key) ──────────────────────────
        if api_key and HAS_REQUESTS:
            api_data = fetch_api_usage(api_key)
            if api_data["ok"]:
                result["tokens_used"]  = api_data["tokens_used"]
                result["tokens_limit"] = api_data.get("tokens_limit", 0) or result["tokens_limit"]
                result["source"]       = "api"
                return result
            else:
                result["error"] = api_data["error"]

        # ── Fuente 2: Archivos locales de Claude Code ─────────────────────────
        claude_dir = get_claude_data_dir()
        if claude_dir:
            tokens = parse_session_tokens_from_projects(claude_dir)
            if tokens > 0:
                result["tokens_used"] = tokens
                result["source"]      = "local"

        return result

    def _update_ui(self, data: dict):
        self._stop_spin()
        t     = self._theme()
        used  = data.get("tokens_used",  0)
        limit = data.get("tokens_limit", 0)
        plan  = data.get("plan",         "pro").upper()
        reset_day   = data.get("reset_day", 1)
        days_left   = days_until_reset(reset_day)
        reset_date  = reset_date_str(reset_day)
        last_update = data["last_updated"].strftime("%H:%M:%S")

        # Texto de uso
        if limit > 0:
            pct = used / limit
            used_k  = _fmt_tokens(used)
            limit_k = _fmt_tokens(limit)
            self.lbl_usage.config(text=f"Tokens: {used_k} / {limit_k}")
            self.lbl_pct.config(text=f"{pct*100:.1f}%",
                                fg=t["warn"] if pct > 0.85 else t["accent"])
            self.bar.set(pct)
        else:
            used_k = _fmt_tokens(used)
            self.lbl_usage.config(text=f"Tokens este mes: {used_k}")
            self.lbl_pct.config(text="")
            self.bar.set(0)

        # Renovación
        self.lbl_renew.config(
            text=f"Plan {plan}  ·  Renueva {reset_date}  ({days_left}d)")

        # Estado / fuente
        src   = data.get("source", "local")
        error = data.get("error")
        if error:
            status = f"⚠ {error[:45]}"
            self.lbl_status.config(fg=t["warn"])
        else:
            src_icon = "☁" if src == "api" else "📁"
            status   = f"{src_icon} {src}  ·  {last_update}"
            self.lbl_status.config(fg=t["fg_dim"])
        self.lbl_status.config(text=status)

    # ── Animación de refresco ─────────────────────────────────────────────────
    _SPIN_FRAMES = ["⟳", "↻", "↺", "⟳"]

    def _start_spin(self):
        self._spinning   = True
        self._spin_frame = 0
        self._animate_spin()

    def _stop_spin(self):
        self._spinning = False
        self.btn_refresh.config(text="⟳")

    def _animate_spin(self):
        if not self._spinning:
            return
        frames = ["◐", "◓", "◑", "◒"]
        self.btn_refresh.config(text=frames[self._spin_frame % len(frames)])
        self._spin_frame += 1
        self.root.after(150, self._animate_spin)

    # ── Auto-refresco ─────────────────────────────────────────────────────────
    def _start_auto_refresh(self):
        secs = max(10, self.cfg.get("auto_refresh_seconds", 60))
        self._refresh_timer = self.root.after(secs * 1000, self._auto_tick)

    def _auto_tick(self):
        self.refresh()
        self._start_auto_refresh()

    # ── Arrastre de ventana ───────────────────────────────────────────────────
    def _drag_start(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, event):
        # Guardar posición final
        self.cfg["position_x"] = self.root.winfo_x()
        self.cfg["position_y"] = self.root.winfo_y()
        save_config(self.cfg)

    # ── Menú contextual ───────────────────────────────────────────────────────
    def _show_context_menu(self, event):
        t   = self._theme()
        menu = tk.Menu(self.root, tearoff=False,
                       bg=t["bg2"], fg=t["fg"],
                       activebackground=t["btn_hover"],
                       activeforeground=t["fg"],
                       relief="flat", bd=1)

        on_top = self.cfg.get("always_on_top", True)
        menu.add_command(
            label=f"{'✓ ' if on_top else ''}Siempre visible",
            command=self._toggle_always_on_top)
        menu.add_command(
            label="↺ Refrescar ahora",
            command=self.refresh)
        menu.add_separator()
        menu.add_command(
            label="⚙ Configuración",
            command=self._open_settings)
        menu.add_command(
            label="🌐 Abrir consola Anthropic",
            command=lambda: webbrowser.open("https://console.anthropic.com/settings/usage"))
        menu.add_separator()
        menu.add_command(
            label="⬛ Esquina superior derecha",
            command=self._snap_top_right)
        menu.add_command(
            label="⬜ Esquina superior izquierda",
            command=self._snap_top_left)
        menu.add_separator()
        menu.add_command(label="✕ Cerrar", command=self._quit)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _toggle_always_on_top(self):
        val = not self.cfg.get("always_on_top", True)
        self.cfg["always_on_top"] = val
        self.root.attributes("-topmost", val)
        save_config(self.cfg)

    def _open_settings(self):
        def on_save(new_cfg):
            self.cfg = new_cfg
            save_config(self.cfg)
            # Aplicar cambios inmediatos
            self.root.attributes("-alpha",   self.cfg["alpha"])
            self.root.attributes("-topmost", self.cfg["always_on_top"])
            self._rebuild_ui()
            self.refresh()

        SettingsWindow(self.root, self.cfg, on_save)

    def _rebuild_ui(self):
        """Reconstruye la UI completa (para cambio de tema)."""
        for w in self.root.winfo_children():
            w.destroy()
        self._build_window()
        self._build_ui()

    def _snap_top_right(self):
        sw = self.root.winfo_screenwidth()
        x  = sw - WINDOW_WIDTH - MARGIN
        y  = MARGIN
        self.root.geometry(f"+{x}+{y}")
        self.cfg["position_x"] = x
        self.cfg["position_y"] = y
        save_config(self.cfg)

    def _snap_top_left(self):
        self.root.geometry(f"+{MARGIN}+{MARGIN}")
        self.cfg["position_x"] = MARGIN
        self.cfg["position_y"] = MARGIN
        save_config(self.cfg)

    def _quit(self):
        self.root.quit()

# ── Utilidades ────────────────────────────────────────────────────────────────
def _fmt_tokens(n: int) -> str:
    """Formatea un número de tokens de forma legible."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)

# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Verificar Python 3.8+
    if sys.version_info < (3, 8):
        print("Requiere Python 3.8 o superior.")
        sys.exit(1)

    # Verificar tkinter disponible
    try:
        import tkinter
    except ImportError:
        print("tkinter no está disponible. Instala Python con soporte Tk.")
        sys.exit(1)

    print(f"{APP_NAME} v{VERSION}")
    print(f"Config: {CONFIG_PATH}")
    print("Haz clic derecho sobre la ventana para opciones.")
    print("Arrastra la ventana con clic izquierdo.")
    print()

    try:
        ClaudeMonitor()
    except KeyboardInterrupt:
        print("\nCerrado.")
