#!/usr/bin/env python3
"""
MC Ping Tracker v1.1.5
Developed by Tedisanxd
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
import os
import socket
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime, timezone

# HiDPI on Windows
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ── Theme Palettes ────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#0d1117", "card": "#161b22", "mid": "#21262d",
        "border": "#30363d", "accent": "#58a6ff", "green": "#3fb950",
        "red": "#f85149", "yellow": "#d29922", "text": "#e6edf3",
        "dim": "#8b949e", "graphbg": "#0a0e14", "graphfill": "#132035",
        "graphline": "#58a6ff", "lagmark": "#f85149",
    },
    "light": {
        "bg": "#f6f8fa", "card": "#ffffff", "mid": "#eaeef2",
        "border": "#d0d7de", "accent": "#0969da", "green": "#1a7f37",
        "red": "#cf222e", "yellow": "#9a6700", "text": "#1f2328",
        "dim": "#656d76", "graphbg": "#eaf0f6", "graphfill": "#cce0ff",
        "graphline": "#0969da", "lagmark": "#cf222e",
    },
    "crimson": {
        "bg": "#0d0608", "card": "#1a0a0e", "mid": "#2d1218",
        "border": "#5a1a24", "accent": "#ff6b81", "green": "#52b788",
        "red": "#ff2d44", "yellow": "#ffd166", "text": "#ffe8ec",
        "dim": "#b08090", "graphbg": "#080305", "graphfill": "#400d18",
        "graphline": "#ff6b81", "lagmark": "#ff2d44",
    },
    "midnight": {
        "bg": "#06040f", "card": "#0d0a1f", "mid": "#1a1535",
        "border": "#312860", "accent": "#a78bfa", "green": "#34d399",
        "red": "#f87171", "yellow": "#fbbf24", "text": "#ede9fe",
        "dim": "#7c6fa4", "graphbg": "#04020c", "graphfill": "#1a1040",
        "graphline": "#a78bfa", "lagmark": "#f87171",
    },
}

SWATCHES = [
    ("dark",     "#1e2a3a", "#58a6ff", "Dark",     "white"),
    ("light",    "#e8f0fe", "#0969da", "Light",    "#0969da"),
    ("system",   "#2a2a3a", "#9ca3af", "System",   "white"),
    ("crimson",  "#2d0a10", "#ff6b81", "Crimson",  "white"),
    ("midnight", "#0d0820", "#a78bfa", "Midnight", "white"),
]


def _detect_system_theme():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if val == 1 else "dark"
    except Exception:
        return "dark"


C = dict(THEMES["dark"])

MAX_POINTS  = 120
VERSION     = "1.1.5"
AUTHOR      = "Tedisanxd"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

try:
    from mcstatus import JavaServer
    MCSTATUS_OK = True
except ImportError:
    MCSTATUS_OK = False

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    TRAY_OK = True
except ImportError:
    TRAY_OK = False


# ══════════════════════════════════════════════════════════════════════════════
#  Config
# ══════════════════════════════════════════════════════════════════════════════
class Config:
    DEFAULTS = {
        "server":            "hypixel.net",
        "port":              25565,
        "ping_interval":     2.0,
        "lag_threshold":     200,
        "spike_delta":       50,
        "notify_threshold":  300,
        "theme":             "dark",
        "window_geometry":   "980x640",
        "webhook_url":       "",
        "webhook_enabled":   False,
        "webhook_spikes":    True,
        "webhook_offline":   True,
        "webhook_online":    True,
        "webhook_cooldown":  15,
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    self.data.update(json.load(f))
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def __getitem__(self, k):    return self.data.get(k, self.DEFAULTS.get(k))
    def __setitem__(self, k, v): self.data[k] = v; self.save()
    def get(self, k, d=None):    return self.data.get(k, d)


# ══════════════════════════════════════════════════════════════════════════════
#  Discord Webhook
# ══════════════════════════════════════════════════════════════════════════════
class DiscordWebhook:
    def __init__(self):
        self.url        = ""
        self.enabled    = False
        self.on_spike   = True
        self.on_offline = True
        self.on_online  = True
        self._cooldown  = 15
        self._last_spike = 0.0

    def configure(self, url, enabled, on_spike, on_offline, on_online, cooldown=15):
        self.url        = url.strip()
        self.enabled    = enabled
        self.on_spike   = on_spike
        self.on_offline = on_offline
        self.on_online  = on_online
        self._cooldown  = max(1, int(cooldown))

    def send_spike(self, server, ms, kind, stats, callback=None):
        if not (self.enabled and self.on_spike and self.url):
            return
        now = time.time()
        if now - self._last_spike < self._cooldown:
            return
        self._last_spike = now

        avg = int(stats["total"] / max(stats["count"], 1))
        color = 0xFF4444 if kind == "high ping" else 0xFF8C00
        embed = {
            "title": "⚡  Lag Spike Detected",
            "color": color,
            "fields": [
                {"name": "🖥️ Server",  "value": server,              "inline": True},
                {"name": "📡 Ping",    "value": f"**{int(ms)}ms**",  "inline": True},
                {"name": "🔖 Type",    "value": kind.title(),        "inline": True},
                {"name": "📊 Session Stats",
                 "value": (f"Min `{int(stats['min'])}ms`  "
                            f"Avg `{avg}ms`  "
                            f"Max `{int(stats['max'])}ms`  "
                            f"Spikes `{stats['spikes']}`"),
                 "inline": False},
            ],
            "footer": {"text": f"MC Ping Tracker v{VERSION} · by {AUTHOR}"},
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        threading.Thread(
            target=self._send, args=({"embeds": [embed]}, callback), daemon=True
        ).start()

    def send_status_change(self, server, online: bool, ping=None, callback=None):
        if not (self.enabled and self.url):
            return
        if online and not self.on_online:
            return
        if not online and not self.on_offline:
            return

        if online:
            embed = {
                "title": "✅  Server Online",
                "color": 0x3FB950,
                "fields": [
                    {"name": "🖥️ Server", "value": server,                      "inline": True},
                    {"name": "📡 Ping",   "value": f"{int(ping)}ms" if ping else "N/A", "inline": True},
                ],
                "footer": {"text": f"MC Ping Tracker v{VERSION} · by {AUTHOR}"},
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        else:
            embed = {
                "title": "❌  Server Offline",
                "color": 0xF85149,
                "fields": [
                    {"name": "🖥️ Server", "value": server, "inline": True},
                ],
                "footer": {"text": f"MC Ping Tracker v{VERSION} · by {AUTHOR}"},
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            }
        threading.Thread(
            target=self._send, args=({"embeds": [embed]}, callback), daemon=True
        ).start()

    def send_test(self, server, callback):
        if not self.url:
            callback(False, "No webhook URL set")
            return
        embed = {
            "title": "🔔  Test Notification",
            "color": 0x58A6FF,
            "description": "MC Ping Tracker webhook is connected and working!",
            "fields": [
                {"name": "🖥️ Server",  "value": server or "Not connected", "inline": True},
                {"name": "📋 Version", "value": f"v{VERSION}",             "inline": True},
                {"name": "👤 Author",  "value": AUTHOR,                    "inline": True},
            ],
            "footer": {"text": f"MC Ping Tracker v{VERSION} · by {AUTHOR}"},
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        threading.Thread(
            target=self._send, args=({"embeds": [embed]}, callback), daemon=True
        ).start()

    def _send(self, payload, callback=None):
        try:
            data = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(
                self.url, data=data,
                headers={"Content-Type": "application/json",
                          "User-Agent": f"MCPingTracker/{VERSION}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10):
                pass
            if callback:
                callback(True, "Sent successfully")
        except urllib.error.HTTPError as e:
            if callback:
                callback(False, f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            if callback:
                callback(False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  Ping Worker
# ══════════════════════════════════════════════════════════════════════════════
class PingWorker(threading.Thread):
    def __init__(self, on_result, on_error):
        super().__init__(daemon=True)
        self.on_result = on_result
        self.on_error  = on_error
        self.host      = None
        self.port      = 25565
        self.interval  = 2.0
        self._stop     = threading.Event()
        self._active   = threading.Event()
        self._srv_obj  = None

    def set_server(self, host, port=25565):
        self.host      = host
        self.port      = port
        self._srv_obj  = None
        self._active.set()

    def set_interval(self, secs):
        self.interval = max(0.5, float(secs))

    def stop(self):
        self._stop.set()
        self._active.set()

    def run(self):
        while not self._stop.is_set():
            self._active.wait()
            if self._stop.is_set():
                break
            if self.host:
                self._ping()
            time.sleep(self.interval)

    def _ping(self):
        if MCSTATUS_OK:
            try:
                if self._srv_obj is None:
                    self._srv_obj = JavaServer.lookup(
                        f"{self.host}:{self.port}", timeout=5)
                srv = self._srv_obj
                try:
                    self.on_result(round(srv.status().latency, 1))
                    return
                except Exception:
                    pass
                try:
                    self.on_result(round(srv.ping(), 1))
                    return
                except Exception as e:
                    self._srv_obj = None
                    self.on_error(str(e))
                    return
            except Exception as e:
                self._srv_obj = None
                self.on_error(str(e))
                return
        try:
            t0 = time.perf_counter()
            s  = socket.create_connection((self.host, self.port), timeout=5)
            ms = (time.perf_counter() - t0) * 1000
            s.close()
            self.on_result(round(ms, 1))
        except Exception as e:
            self.on_error(str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  Ping Graph
# ══════════════════════════════════════════════════════════════════════════════
class PingGraph(tk.Canvas):
    PL, PR, PT, PB = 58, 16, 16, 36

    def __init__(self, parent, cfg, **kw):
        super().__init__(parent, bg=C["bg"], highlightthickness=0, **kw)
        self.cfg    = cfg
        self.points = deque(maxlen=MAX_POINTS)
        self.bind("<Configure>", lambda _: self.redraw())

    def add(self, ms, is_lag):
        self.points.append((ms, is_lag))
        self.redraw()

    def clear(self):
        self.points.clear()
        self.redraw()

    def redraw(self):
        self.configure(bg=C["bg"])
        self.delete("all")
        W, H = self.winfo_width(), self.winfo_height()
        if W < 20 or H < 20:
            return
        pl, pr, pt, pb = self.PL, self.PR, self.PT, self.PB
        gw, gh = W - pl - pr, H - pt - pb

        self.create_rectangle(pl, pt, W-pr, H-pb,
                               fill=C["graphbg"], outline=C["border"])

        if not self.points:
            self.create_text(W//2, H//2, text="Waiting for data…",
                             fill=C["dim"], font=("Consolas", 12))
            return

        vals  = [p[0] for p in self.points]
        max_v = max(max((v for v in vals if v > 0), default=100) * 1.25, 100)
        n     = len(self.points)

        self._draw_grid(pl, pr, pt, W, H, gw, gh, max_v)

        def xy(i, v):
            x = pl + int(i / max(n-1, 1) * gw)
            y = pt + gh - int(max(v, 0) / max_v * gh)
            return x, max(pt, min(pt+gh, y))

        poly = [pl, H-pb]
        for i, (v, _) in enumerate(self.points):
            poly += list(xy(i, v))
        poly += [xy(n-1, vals[-1])[0], H-pb]
        if len(poly) >= 6:
            self.create_polygon(poly, fill=C["graphfill"], outline="", smooth=True)

        lag_th = self.cfg["lag_threshold"]
        for i, (v, flag) in enumerate(self.points):
            if i > 0:
                p1 = xy(i-1, self.points[i-1][0])
                p2 = xy(i, v)
                color = C["lagmark"] if (v > lag_th or flag) else C["graphline"]
                self.create_line(*p1, *p2, fill=color, width=2)
            if v > lag_th or flag:
                x, y = xy(i, v)
                self.create_oval(x-4, y-4, x+4, y+4,
                                 fill=C["lagmark"], outline="#ff9999", width=1)

        lv, lflag = self.points[-1]
        lx, ly = xy(n-1, lv)
        dot_c = (C["lagmark"] if (lv > lag_th or lflag)
                 else C["green"] if lv < 100 else C["yellow"])
        self.create_oval(lx-5, ly-5, lx+5, ly+5,
                         fill=dot_c, outline="white", width=1)

        elapsed = int(n * self.cfg["ping_interval"])
        self.create_text(pl+2, H-8, text=f"−{elapsed}s",
                         fill=C["dim"], anchor="w", font=("Consolas", 8))
        self.create_text(W-pr-2, H-8, text="now",
                         fill=C["dim"], anchor="e", font=("Consolas", 8))

    def _draw_grid(self, pl, pr, pt, W, H, gw, gh, max_v):
        pb = self.PB
        for g in [0, 25, 50, 100, 150, 200, 300, 500, 750, 1000]:
            if g > max_v:
                break
            y = pt + gh - int(g / max_v * gh)
            self.create_line(pl, y, W-pr, y, fill=C["border"], dash=(3, 5))
            self.create_text(pl-4, y, text=str(g),
                             fill=C["dim"], anchor="e", font=("Consolas", 8))
        self.create_line(pl, pt, pl, H-pb, fill=C["border"], width=1)
        self.create_line(pl, H-pb, W-pr, H-pb, fill=C["border"], width=1)
        self.create_text(8, pt+gh//2, text="ms", fill=C["dim"],
                         angle=90, font=("Consolas", 9))
        lag_th = self.cfg["lag_threshold"]
        if lag_th <= max_v:
            ly = pt + gh - int(lag_th / max_v * gh)
            self.create_line(pl, ly, W-pr, ly,
                             fill=C["lagmark"], dash=(6, 4), width=1)
            self.create_text(W-pr-2, ly-6, text=f"lag ≥{lag_th}ms",
                             fill=C["lagmark"], anchor="e", font=("Consolas", 8))


# ══════════════════════════════════════════════════════════════════════════════
#  Notifier
# ══════════════════════════════════════════════════════════════════════════════
class Notifier:
    def __init__(self):
        self._last     = 0.0
        self._cooldown = 12

    def send(self, title, body):
        if time.time() - self._last < self._cooldown:
            return
        self._last = time.time()
        threading.Thread(target=self._dispatch, args=(title, body), daemon=True).start()

    def _dispatch(self, title, body):
        try:
            from plyer import notification
            notification.notify(title=title, message=body,
                                app_name="MC Ping Tracker", timeout=5)
            return
        except Exception:
            pass
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, body, duration=5, threaded=True)
            return
        except Exception:
            pass
        try:
            import subprocess
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f"$n.ShowBalloonTip(5000,'{title}','{body}',"
                "[System.Windows.Forms.ToolTipIcon]::Info)"
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  System Tray
# ══════════════════════════════════════════════════════════════════════════════
class TrayManager:
    def __init__(self, on_show, on_quit):
        self.on_show = on_show
        self.on_quit = on_quit
        self.icon    = None
        self._status = "ok"

    def _make_img(self, rgb):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        d.ellipse([2,  2,  62, 62], fill=(*rgb, 55))
        d.ellipse([6,  6,  58, 58], fill=(*rgb, 255))
        d.ellipse([14, 10, 34, 28], fill=(255, 255, 255, 50))
        return img

    def set_status(self, status):
        if status == self._status or self.icon is None:
            return
        self._status = status
        colors = {"ok": (63,185,80), "lag": (210,153,34), "offline": (248,81,73)}
        try:
            self.icon.icon = self._make_img(colors.get(status, (63,185,80)))
        except Exception:
            pass

    def start(self):
        if not TRAY_OK:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", lambda i, m: self.on_show(), default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit",        lambda i, m: self.on_quit()),
            )
            self.icon = pystray.Icon(
                "MCPingTracker", self._make_img((63,185,80)), "MC Ping Tracker", menu
            )
            self.icon.run()
        except Exception as e:
            print(f"[Tray] {e}")

    def stop(self):
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  Main App
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg      = Config()
        self.worker   = PingWorker(self._on_ping, self._on_error)
        self.notifier = Notifier()
        self.webhook  = DiscordWebhook()
        self.tray     = TrayManager(self._show, self._quit) if TRAY_OK else None

        self._alive              = True
        self._prev_ping          = None
        self._server_was_offline = False
        self._stats              = dict(min=float("inf"), max=0.0,
                                        total=0.0, count=0, spikes=0)
        self._lag_log            = []
        self._wh_log_entries     = []
        self._ping_data          = deque(maxlen=MAX_POINTS)
        self._active_tab_name    = "monitor"

        # ── Persistent StringVars ──────────────────────────────────────────────
        self._ping_var    = tk.StringVar(value="---")
        self._status_var  = tk.StringVar(value="● Disconnected")
        self._bar_var     = tk.StringVar(
            value="Not connected  ·  Close window to minimize to tray")
        self._min_var     = tk.StringVar(value="---")
        self._avg_var     = tk.StringVar(value="---")
        self._max_var     = tk.StringVar(value="---")
        self._spike_var   = tk.StringVar(value="0")
        self._srv_var     = tk.StringVar(value=self.cfg["server"])
        self._port_var    = tk.StringVar(value=str(self.cfg["port"]))
        self._lag_var     = tk.StringVar(value=str(self.cfg["lag_threshold"]))
        self._delta_var   = tk.StringVar(value=str(self.cfg["spike_delta"]))
        self._notify_var  = tk.StringVar(value=str(self.cfg["notify_threshold"]))
        self._ivl_var     = tk.StringVar(value=str(self.cfg["ping_interval"]))
        # Discord
        self._wh_url_var      = tk.StringVar(value=self.cfg.get("webhook_url", ""))
        self._wh_enabled_var  = tk.BooleanVar(value=self.cfg.get("webhook_enabled", False))
        self._wh_spikes_var   = tk.BooleanVar(value=self.cfg.get("webhook_spikes", True))
        self._wh_offline_var  = tk.BooleanVar(value=self.cfg.get("webhook_offline", True))
        self._wh_online_var   = tk.BooleanVar(value=self.cfg.get("webhook_online", True))
        self._wh_cooldown_var = tk.StringVar(value=str(self.cfg.get("webhook_cooldown", 15)))
        self._wh_status_var   = tk.StringVar(value="")

        # Load saved theme
        saved    = self.cfg.get("theme", "dark")
        resolved = _detect_system_theme() if saved == "system" else saved
        C.update(THEMES.get(resolved, THEMES["dark"]))

        # Init webhook from config
        self._apply_webhook_cfg()

        self.title("MC Ping Tracker")
        self.geometry(self.cfg["window_geometry"])
        self.minsize(760, 520)
        self.resizable(True, True)
        self.configure(bg=C["bg"])

        self._set_app_icon()
        self._build_ui()

        self.worker.start()
        if self.tray:
            self.tray.start()

        self.protocol("WM_DELETE_WINDOW", self._hide)
        self._auto_connect()

    # ── App icon ──────────────────────────────────────────────────────────────
    def _set_app_icon(self):
        if not TRAY_OK:
            return
        try:
            sz  = 64
            img = Image.new("RGBA", (sz, sz), (0,0,0,0))
            d   = ImageDraw.Draw(img)
            cx, cy, r = sz//2, sz//2, sz//2 - 4
            pts = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
            acc = tuple(int(C["accent"][i:i+2], 16) for i in (1, 3, 5))
            d.polygon(pts, fill=(*acc, 255))
            hi = [(cx-3, cy-r//2-4), (cx+r//3, cy-6), (cx-3, cy+4), (cx-r//3-3, cy-6)]
            d.polygon(hi, fill=(255, 255, 255, 70))
            photo = ImageTk.PhotoImage(img)
            self.iconphoto(True, photo)
            self._icon_ref = photo
        except Exception:
            pass

    # ── Build / Rebuild ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.configure(bg=C["bg"])
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _rebuild_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=C["bg"])
        self._set_app_icon()
        self._build_ui()
        self.graph.points = self._ping_data
        self.graph.redraw()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=C["card"], height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border"], height=1).pack(side="bottom", fill="x")

        left = tk.Frame(hdr, bg=C["card"])
        left.pack(side="left", padx=18, pady=12)
        tk.Label(left, text="⛏", bg=C["card"], fg=C["accent"],
                 font=("Segoe UI Emoji", 22)).pack(side="left", padx=(0,8))
        tk.Label(left, text="MC Ping Tracker", bg=C["card"], fg=C["text"],
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(left, text=f" v{VERSION}", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9)).pack(side="left", anchor="s", pady=5)
        tk.Label(left, text=" · ", bg=C["card"], fg=C["border"],
                 font=("Segoe UI", 11)).pack(side="left", anchor="s", pady=5)
        tk.Label(left, text=f"developed by {AUTHOR}", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9, "italic")).pack(side="left", anchor="s", pady=5)

        right = tk.Frame(hdr, bg=C["card"])
        right.pack(side="right", padx=18, pady=12)

        tk.Label(right, text="Server", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 10)).pack(side="left", padx=(0,6))

        ekw = dict(bg=C["mid"], fg=C["text"], font=("Consolas", 11),
                   relief="flat", insertbackground=C["text"],
                   highlightthickness=1, highlightbackground=C["border"],
                   highlightcolor=C["accent"])

        e_srv = tk.Entry(right, textvariable=self._srv_var, width=24, **ekw)
        e_srv.pack(side="left", ipady=6, padx=(0,2))
        e_srv.bind("<Return>", lambda _: self._connect())

        tk.Label(right, text=":", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 12)).pack(side="left")

        e_port = tk.Entry(right, textvariable=self._port_var, width=6, **ekw)
        e_port.pack(side="left", ipady=6, padx=(2,10))
        e_port.bind("<Return>", lambda _: self._connect())

        self._conn_btn = tk.Button(
            right, text="Connect", command=self._connect,
            bg=C["accent"], fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=16, pady=6, cursor="hand2",
            activebackground=C["accent"], activeforeground="white"
        )
        self._conn_btn.pack(side="left")

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self):
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(body, bg=C["bg"], width=252)
        left.pack(side="left", fill="y", padx=(0,10))
        left.pack_propagate(False)

        right = tk.Frame(body, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(left)
        self._build_graph_panel(right)

    # ── Left panel with tabs ──────────────────────────────────────────────────
    def _build_left_panel(self, parent):
        # Tab bar
        tab_bar = tk.Frame(parent, bg=C["bg"])
        tab_bar.pack(fill="x", pady=(0, 6))

        self._tab_frames = {}
        self._tab_btns   = {}

        container = tk.Frame(parent, bg=C["bg"])
        container.pack(fill="both", expand=True)

        # Create a frame for each tab
        for name in ("monitor", "settings", "discord"):
            self._tab_frames[name] = tk.Frame(container, bg=C["bg"])

        # Build tab buttons
        tab_defs = [("monitor", "Monitor"), ("settings", "Settings"), ("discord", "Discord")]
        for name, label in tab_defs:
            active = (name == self._active_tab_name)
            btn = tk.Button(
                tab_bar, text=label,
                command=lambda n=name: self._switch_tab(n),
                bg=C["accent"] if active else C["mid"],
                fg="white" if active else C["dim"],
                font=("Segoe UI", 9, "bold"),
                relief="flat", padx=10, pady=5, cursor="hand2",
                activebackground=C["accent"], activeforeground="white"
            )
            btn.pack(side="left", padx=(0, 2))
            self._tab_btns[name] = btn

        # Populate each tab
        self._build_monitor_tab(self._tab_frames["monitor"])
        self._build_settings_tab(self._tab_frames["settings"])
        self._build_discord_tab(self._tab_frames["discord"])

        # Show saved active tab
        self._switch_tab(self._active_tab_name)

    def _switch_tab(self, name):
        self._active_tab_name = name
        for k, f in self._tab_frames.items():
            f.pack_forget()
        self._tab_frames[name].pack(fill="both", expand=True)
        for k, btn in self._tab_btns.items():
            if k == name:
                btn.config(bg=C["accent"], fg="white")
            else:
                btn.config(bg=C["mid"], fg=C["dim"])

    # ── Monitor tab: stats + log ──────────────────────────────────────────────
    def _build_monitor_tab(self, parent):
        self._build_stats_panel(parent)
        self._build_log_panel(parent)

    # ── Stats panel ───────────────────────────────────────────────────────────
    def _build_stats_panel(self, parent):
        card = self._card(parent, "LIVE STATS")

        self._ping_lbl = tk.Label(card, textvariable=self._ping_var,
                                  bg=C["card"], fg=C["accent"],
                                  font=("Consolas", 42, "bold"))
        self._ping_lbl.pack(pady=(6, 0))
        tk.Label(card, text="milliseconds", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9)).pack()

        self._status_lbl = tk.Label(card, textvariable=self._status_var,
                                    bg=C["mid"], fg=C["dim"],
                                    font=("Segoe UI", 9, "bold"), padx=10, pady=3)
        self._status_lbl.pack(pady=8)

        self._divider(card)

        row = tk.Frame(card, bg=C["card"])
        row.pack(fill="x", padx=8, pady=6)
        for lbl, var, col in [("MIN", self._min_var, C["green"]),
                               ("AVG", self._avg_var, C["accent"]),
                               ("MAX", self._max_var, C["red"])]:
            f = tk.Frame(row, bg=C["card"])
            f.pack(side="left", expand=True)
            tk.Label(f, text=lbl, bg=C["card"], fg=C["dim"],
                     font=("Segoe UI", 8)).pack()
            tk.Label(f, textvariable=var, bg=C["card"], fg=col,
                     font=("Consolas", 14, "bold")).pack()

        self._divider(card)

        r2 = tk.Frame(card, bg=C["card"])
        r2.pack(fill="x", padx=12, pady=4)
        tk.Label(r2, text="Lag Spikes", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(r2, textvariable=self._spike_var, bg=C["card"],
                 fg=C["red"], font=("Consolas", 14, "bold")).pack(side="right")

        tk.Button(card, text="Reset Stats", command=self._reset_stats,
                  bg=C["mid"], fg=C["dim"], font=("Segoe UI", 9),
                  relief="flat", padx=8, pady=4, cursor="hand2").pack(pady=(8, 8))

    # ── Spike log ─────────────────────────────────────────────────────────────
    def _build_log_panel(self, parent):
        card = self._card(parent, "SPIKE LOG", expand=True)

        frame = tk.Frame(card, bg=C["card"])
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._log = tk.Text(frame, bg=C["graphbg"], fg=C["text"],
                            font=("Consolas", 8), relief="flat",
                            state="disabled", wrap="none", height=7,
                            selectbackground=C["mid"])
        self._log.tag_config("spike", foreground=C["lagmark"])
        for entry in self._lag_log:
            self._log.config(state="normal")
            self._log.insert("end", entry, "spike")
        self._log.config(state="disabled")
        self._log.see("end")

        sb = tk.Scrollbar(frame, command=self._log.yview,
                          bg=C["mid"], troughcolor=C["bg"])
        self._log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True)

        tk.Button(card, text="Clear Log", command=self._clear_log,
                  bg=C["mid"], fg=C["dim"], font=("Segoe UI", 8),
                  relief="flat", padx=6, pady=3, cursor="hand2").pack(pady=(0, 6))

    # ── Settings tab ──────────────────────────────────────────────────────────
    def _build_settings_tab(self, parent):
        card = self._card(parent, "SETTINGS")

        ekw = dict(bg=C["mid"], fg=C["text"], font=("Consolas", 10),
                   relief="flat", insertbackground=C["text"],
                   highlightthickness=1, highlightbackground=C["border"],
                   highlightcolor=C["accent"])

        for label, var in [("Lag spike ≥ (ms)",  self._lag_var),
                            ("Spike delta (ms)",  self._delta_var),
                            ("Notify ≥ (ms)",     self._notify_var),
                            ("Interval (s)",      self._ivl_var)]:
            row = tk.Frame(card, bg=C["card"])
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=label, bg=C["card"], fg=C["dim"],
                     font=("Segoe UI", 9), width=17, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=var, width=7, **ekw).pack(
                side="right", ipady=4)

        tk.Button(card, text="Apply Settings", command=self._apply_settings,
                  bg=C["accent"], fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=C["accent"], activeforeground="white").pack(
                  pady=(6, 4))

        self._divider(card)

        # Theme picker
        tk.Label(card, text="APPEARANCE", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(4, 4))

        srow = tk.Frame(card, bg=C["card"])
        srow.pack(fill="x", padx=10, pady=(0, 8))
        current = self.cfg.get("theme", "dark")
        for name, bg_p, acc_p, label, fg_l in SWATCHES:
            active = (current == name)
            outer = tk.Frame(srow, bg=acc_p if active else C["border"],
                             padx=1, pady=1, cursor="hand2")
            outer.pack(side="left", padx=2)
            inner = tk.Frame(outer, bg=bg_p, cursor="hand2")
            inner.pack()
            lbl = tk.Label(inner, text=label, bg=bg_p, fg=acc_p,
                           font=("Segoe UI", 7, "bold"), padx=5, pady=3,
                           cursor="hand2")
            lbl.pack()
            for w in (outer, inner, lbl):
                w.bind("<Button-1>", lambda e, n=name: self._apply_theme(n))

    # ── Discord tab ───────────────────────────────────────────────────────────
    def _build_discord_tab(self, parent):
        card = self._card(parent, "DISCORD WEBHOOK")

        ekw = dict(bg=C["mid"], fg=C["text"], font=("Consolas", 9),
                   relief="flat", insertbackground=C["text"],
                   highlightthickness=1, highlightbackground=C["border"],
                   highlightcolor=C["accent"])

        # URL field
        tk.Label(card, text="Webhook URL", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(2, 2))
        tk.Entry(card, textvariable=self._wh_url_var, **ekw).pack(
            fill="x", padx=10, ipady=5, pady=(0, 6))

        # Enable toggle row
        tog_row = tk.Frame(card, bg=C["card"])
        tog_row.pack(fill="x", padx=10, pady=2)
        tk.Label(tog_row, text="Enable", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        enabled = self._wh_enabled_var.get()
        self._toggle_btn = tk.Button(
            tog_row,
            text="ON " if enabled else "OFF",
            bg=C["green"] if enabled else C["mid"],
            fg="white", font=("Consolas", 9, "bold"),
            relief="flat", padx=10, pady=2, cursor="hand2",
            command=self._toggle_webhook
        )
        self._toggle_btn.pack(side="right")

        self._divider(card)

        # Notify options
        tk.Label(card, text="NOTIFY ON", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(4, 3))

        cbkw = dict(bg=C["card"], activebackground=C["card"],
                    selectcolor=C["mid"], font=("Segoe UI", 9),
                    cursor="hand2", command=self._save_webhook_cfg)
        for var, label in [
            (self._wh_spikes_var,  "⚡  Lag spikes"),
            (self._wh_offline_var, "❌  Server goes offline"),
            (self._wh_online_var,  "✅  Server comes online"),
        ]:
            tk.Checkbutton(card, variable=var, text=label,
                           fg=C["text"], **cbkw).pack(anchor="w", padx=10, pady=1)

        self._divider(card)

        # Cooldown
        cd_row = tk.Frame(card, bg=C["card"])
        cd_row.pack(fill="x", padx=10, pady=4)
        tk.Label(cd_row, text="Spike cooldown (s)", bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 9), anchor="w").pack(side="left")
        tk.Entry(cd_row, textvariable=self._wh_cooldown_var, width=5, **ekw).pack(
            side="right", ipady=4)

        # Buttons
        btn_row = tk.Frame(card, bg=C["card"])
        btn_row.pack(fill="x", padx=10, pady=(8, 4))
        tk.Button(btn_row, text="Save & Apply", command=self._save_webhook_cfg,
                  bg=C["accent"], fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  activebackground=C["accent"], activeforeground="white").pack(
                  side="left", padx=(0, 4))
        self._test_btn = tk.Button(
            btn_row, text="Send Test", command=self._test_webhook,
            bg=C["mid"], fg=C["text"], font=("Segoe UI", 9),
            relief="flat", padx=10, pady=4, cursor="hand2"
        )
        self._test_btn.pack(side="left")

        # Status label
        tk.Label(card, textvariable=self._wh_status_var, bg=C["card"],
                 fg=C["dim"], font=("Segoe UI", 8),
                 wraplength=228).pack(padx=10, pady=(2, 8))

        # Webhook log
        log_card = self._card(parent, "WEBHOOK LOG", expand=True)
        frame = tk.Frame(log_card, bg=C["card"])
        frame.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._wh_log = tk.Text(
            frame, bg=C["graphbg"], fg=C["text"],
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word", height=6,
            selectbackground=C["mid"]
        )
        self._wh_log.tag_config("ok",   foreground=C["green"])
        self._wh_log.tag_config("err",  foreground=C["red"])
        self._wh_log.tag_config("info", foreground=C["accent"])
        for entry, tag in self._wh_log_entries:
            self._wh_log.config(state="normal")
            self._wh_log.insert("end", entry, tag)
        self._wh_log.config(state="disabled")
        self._wh_log.see("end")

        sb = tk.Scrollbar(frame, command=self._wh_log.yview,
                          bg=C["mid"], troughcolor=C["bg"])
        self._wh_log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._wh_log.pack(fill="both", expand=True)

        tk.Button(log_card, text="Clear Log",
                  command=self._clear_wh_log,
                  bg=C["mid"], fg=C["dim"], font=("Segoe UI", 8),
                  relief="flat", padx=6, pady=3, cursor="hand2").pack(pady=(0, 6))

    # ── Graph panel ───────────────────────────────────────────────────────────
    def _build_graph_panel(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"])
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="Ping Graph", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        leg = tk.Frame(hdr, bg=C["bg"])
        leg.pack(side="right")
        for col, txt in [(C["graphline"], "Normal"),
                          (C["lagmark"],   "Lag Spike"),
                          (C["yellow"],    "Elevated")]:
            dot = tk.Canvas(leg, bg=C["bg"], width=10, height=10,
                            highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=col, outline="")
            dot.pack(side="left", padx=(10, 3))
            tk.Label(leg, text=txt, bg=C["bg"], fg=C["dim"],
                     font=("Segoe UI", 9)).pack(side="left")

        self.graph = PingGraph(parent, self.cfg)
        self.graph.pack(fill="both", expand=True)

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=C["card"], height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=C["border"], height=1).pack(fill="x", side="top")

        tk.Label(bar, textvariable=self._bar_var, bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 8)).pack(side="left", padx=10)

        warns = []
        if not MCSTATUS_OK:
            warns.append("⚠ mcstatus missing — TCP fallback")
        if not TRAY_OK:
            warns.append("⚠ pystray/Pillow missing — no tray")
        if warns:
            tk.Label(bar, text="  ·  ".join(warns), bg=C["card"], fg=C["yellow"],
                     font=("Segoe UI", 8)).pack(side="right", padx=10)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _card(self, parent, title, expand=False):
        outer = tk.Frame(parent, bg=C["border"], padx=1, pady=1)
        outer.pack(fill="both" if expand else "x", pady=4, expand=expand)
        inner = tk.Frame(outer, bg=C["card"])
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, bg=C["card"], fg=C["dim"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(8, 3))
        return inner

    def _divider(self, parent):
        tk.Frame(parent, bg=C["border"], height=1).pack(fill="x", padx=8, pady=4)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _auto_connect(self):
        if self.cfg["server"]:
            self._connect()

    def _connect(self):
        host = self._srv_var.get().strip()
        try:
            port = int(self._port_var.get().strip())
        except ValueError:
            port = 25565
        if not host:
            return
        self.cfg["server"] = host
        self.cfg["port"]   = port
        self.graph.clear()
        self._ping_data.clear()
        self._reset_stats()
        self._prev_ping          = None
        self._server_was_offline = False
        self._status_var.set("● Connecting…")
        self._status_lbl.config(fg=C["yellow"], bg=C["mid"])
        self._bar_var.set(f"Connecting to {host}:{port}…")
        self.worker.set_server(host, port)

    def _apply_settings(self):
        try:
            lag   = int(self._lag_var.get())
            delta = int(self._delta_var.get())
            nfy   = int(self._notify_var.get())
            ivl   = float(self._ivl_var.get())
            self.cfg["lag_threshold"]    = lag
            self.cfg["spike_delta"]      = delta
            self.cfg["notify_threshold"] = nfy
            self.cfg["ping_interval"]    = ivl
            self.worker.set_interval(ivl)
            self.graph.redraw()
        except ValueError as e:
            messagebox.showerror("Bad Input", str(e))

    def _apply_theme(self, name):
        resolved = _detect_system_theme() if name == "system" else name
        C.update(THEMES.get(resolved, THEMES["dark"]))
        self.cfg["theme"] = name
        self._rebuild_ui()

    def _reset_stats(self):
        self._stats = dict(min=float("inf"), max=0.0, total=0.0, count=0, spikes=0)
        for v in (self._min_var, self._avg_var, self._max_var):
            v.set("---")
        self._spike_var.set("0")
        self._ping_var.set("---")

    def _clear_log(self):
        self._lag_log.clear()
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _clear_wh_log(self):
        self._wh_log_entries.clear()
        self._wh_log.config(state="normal")
        self._wh_log.delete("1.0", "end")
        self._wh_log.config(state="disabled")

    # ── Discord webhook actions ───────────────────────────────────────────────
    def _apply_webhook_cfg(self):
        self.webhook.configure(
            url=self.cfg.get("webhook_url", ""),
            enabled=self.cfg.get("webhook_enabled", False),
            on_spike=self.cfg.get("webhook_spikes", True),
            on_offline=self.cfg.get("webhook_offline", True),
            on_online=self.cfg.get("webhook_online", True),
            cooldown=self.cfg.get("webhook_cooldown", 15),
        )

    def _toggle_webhook(self):
        new_val = not self._wh_enabled_var.get()
        self._wh_enabled_var.set(new_val)
        self._toggle_btn.config(
            text="ON " if new_val else "OFF",
            bg=C["green"] if new_val else C["mid"]
        )
        self._save_webhook_cfg()

    def _save_webhook_cfg(self):
        try:
            cooldown = int(self._wh_cooldown_var.get())
        except ValueError:
            cooldown = 15
        url     = self._wh_url_var.get().strip()
        enabled = self._wh_enabled_var.get()
        spikes  = self._wh_spikes_var.get()
        offline = self._wh_offline_var.get()
        online  = self._wh_online_var.get()

        self.cfg["webhook_url"]      = url
        self.cfg["webhook_enabled"]  = enabled
        self.cfg["webhook_spikes"]   = spikes
        self.cfg["webhook_offline"]  = offline
        self.cfg["webhook_online"]   = online
        self.cfg["webhook_cooldown"] = cooldown

        self.webhook.configure(url, enabled, spikes, offline, online, cooldown)
        self._wh_status_var.set(
            f"Active · cooldown {cooldown}s" if enabled else "Disabled"
        )

    def _test_webhook(self):
        self._save_webhook_cfg()
        if not self.webhook.url:
            self._wh_status_var.set("⚠  Enter a webhook URL first")
            return
        self._wh_status_var.set("Sending test…")
        self._test_btn.config(state="disabled")
        self.webhook.send_test(
            self.cfg["server"],
            lambda ok, msg: self.after(0, self._on_test_result, ok, msg)
        )

    def _on_test_result(self, ok, msg):
        self._wh_status_var.set(("✓  " if ok else "✗  ") + msg)
        self._test_btn.config(state="normal")
        self._wh_append("ok" if ok else "err", f"TEST: {msg}")

    def _wh_append(self, tag, message):
        ts    = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}\n"
        self._wh_log_entries.append((entry, tag))
        try:
            self._wh_log.config(state="normal")
            self._wh_log.insert("end", entry, tag)
            self._wh_log.see("end")
            self._wh_log.config(state="disabled")
        except tk.TclError:
            pass   # widget may not exist if Discord tab was never opened

    # ── Ping callbacks ────────────────────────────────────────────────────────
    def _on_ping(self, ms):   self.after(0, self._handle_ping, ms)
    def _on_error(self, msg): self.after(0, self._handle_error, msg)

    def _handle_ping(self, ms):
        lag_th    = self.cfg["lag_threshold"]
        delta_th  = self.cfg["spike_delta"]
        notify_th = self.cfg["notify_threshold"]

        delta_spike = (self._prev_ping is not None and
                       (ms - self._prev_ping) >= delta_th)
        is_lag      = (ms > lag_th) or delta_spike
        self._prev_ping = ms

        s = self._stats
        s["count"] += 1
        s["total"] += ms
        s["min"]    = min(s["min"], ms)
        s["max"]    = max(s["max"], ms)
        if is_lag:
            s["spikes"] += 1
            self._log_spike(ms, delta_spike)

        # Online transition (was offline → now online)
        if self._server_was_offline:
            self._server_was_offline = False
            self.webhook.send_status_change(
                self.cfg["server"], online=True, ping=ms,
                callback=lambda ok, m: self._wh_append(
                    "ok" if ok else "err",
                    f"Online alert {'sent' if ok else 'failed: ' + m}"
                )
            )
            self._wh_append("ok", f"Server back online: {self.cfg['server']} ({int(ms)}ms)")

        if   ms < 80:        ping_c = C["green"]
        elif ms < 150:       ping_c = C["accent"]
        elif ms < lag_th:    ping_c = C["yellow"]
        else:                ping_c = C["red"]

        self._ping_var.set(str(int(ms)))
        self._ping_lbl.config(fg=ping_c)
        self._min_var.set(str(int(s["min"])))
        self._avg_var.set(str(int(s["total"] / s["count"])))
        self._max_var.set(str(int(s["max"])))
        self._spike_var.set(str(s["spikes"]))
        self._status_var.set("● Online")
        self._status_lbl.config(fg=C["green"], bg=C["mid"])

        ts = datetime.now().strftime("%H:%M:%S")
        self._bar_var.set(
            f"{self.cfg['server']}  ·  {int(ms)}ms  ·  {ts}"
            f"  ·  spikes: {s['spikes']}  ·  close window → tray"
        )

        self._ping_data.append((ms, is_lag))
        self.graph.add(ms, is_lag)

        if ms > notify_th:
            self.notifier.send("High Ping!",
                               f"{self.cfg['server']}: {int(ms)}ms (>{notify_th}ms)")
        if self.tray:
            self.tray.set_status("lag" if is_lag else "ok")

    def _handle_error(self, msg):
        self._ping_var.set("ERR")
        self._ping_lbl.config(fg=C["red"])
        self._status_var.set("● Offline")
        self._status_lbl.config(fg=C["red"], bg=C["mid"])
        self._bar_var.set(f"Error: {msg[:80]}")
        self._ping_data.append((0, False))
        self.graph.add(0, False)

        # Offline transition
        if not self._server_was_offline:
            self._server_was_offline = True
            self.webhook.send_status_change(
                self.cfg["server"], online=False,
                callback=lambda ok, m: self._wh_append(
                    "ok" if ok else "err",
                    f"Offline alert {'sent' if ok else 'failed: ' + m}"
                )
            )
            self._wh_append("err", f"Server offline: {self.cfg['server']}")

        if self.tray:
            self.tray.set_status("offline")

    def _log_spike(self, ms, is_delta=False):
        ts    = datetime.now().strftime("%H:%M:%S")
        kind  = "delta jump" if is_delta else "high ping"
        entry = f"[{ts}] {int(ms)}ms  ▲ {kind}\n"
        self._lag_log.append(entry)
        self._log.config(state="normal")
        self._log.insert("end", entry, "spike")
        self._log.see("end")
        self._log.config(state="disabled")

        # Send Discord webhook for spike
        self.webhook.send_spike(
            self.cfg["server"], ms, kind, self._stats,
            callback=lambda ok, m: self._wh_append(
                "ok" if ok else "err",
                f"Spike alert ({int(ms)}ms {kind}) {'sent' if ok else 'failed: ' + m}"
            )
        )

    # ── Window management ─────────────────────────────────────────────────────
    def _hide(self):
        self.withdraw()
        if self.tray and self.tray.icon:
            try:
                self.tray.icon.notify("MC Ping Tracker is still running.")
            except Exception:
                pass

    def _show(self):
        self.after(0, self._do_show)

    def _do_show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _quit(self):
        self._alive = False
        self.worker.stop()
        if self.tray:
            self.tray.stop()
        self.cfg["window_geometry"] = self.geometry()
        self.after(0, self.destroy)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
