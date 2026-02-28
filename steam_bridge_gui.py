import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Optional drag-and-drop support
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

CONFIG_FILE = "steam_bridge_config.json"
LOG_FILE = "steam_bridge.log"


# ---------------------------------------------------------------------------
# Steam Flat API wrapper
# ---------------------------------------------------------------------------
class SteamFlatAPI:
    def __init__(self, log, dry_run: bool = False):
        self.log = log
        self.dll = None
        self.user_stats = None
        self.dry_run = dry_run
        self._lock = threading.Lock()

    def init(self) -> bool:
        if self.dry_run:
            self.log("[DRY RUN] SteamAPI_Init skipped")
            return True

        try:
            self.dll = ctypes.WinDLL("steam_api.dll")
        except Exception as e:
            self.log(f"steam_api.dll load failed: {e}")
            return False

        self.dll.SteamAPI_Init.restype = ctypes.c_bool
        if not self.dll.SteamAPI_Init():
            self.log("SteamAPI_Init failed (start from Steam client)")
            return False

        self.dll.SteamAPI_SteamUserStats_v012.restype = ctypes.c_void_p
        self.user_stats = self.dll.SteamAPI_SteamUserStats_v012()
        if not self.user_stats:
            self.log("SteamAPI_SteamUserStats_v012 failed")
            return False

        # --- SetAchievement / ClearAchievement ---
        self.dll.SteamAPI_ISteamUserStats_SetAchievement.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.dll.SteamAPI_ISteamUserStats_SetAchievement.restype = ctypes.c_bool
        self.dll.SteamAPI_ISteamUserStats_ClearAchievement.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.dll.SteamAPI_ISteamUserStats_ClearAchievement.restype = ctypes.c_bool

        # --- StoreStats ---
        self.dll.SteamAPI_ISteamUserStats_StoreStats.argtypes = [ctypes.c_void_p]
        self.dll.SteamAPI_ISteamUserStats_StoreStats.restype = ctypes.c_bool

        # --- RequestCurrentStats ---
        self.dll.SteamAPI_ISteamUserStats_RequestCurrentStats.argtypes = [ctypes.c_void_p]
        self.dll.SteamAPI_ISteamUserStats_RequestCurrentStats.restype = ctypes.c_bool

        # --- GetNumAchievements / GetAchievementName / GetAchievement ---
        self.dll.SteamAPI_ISteamUserStats_GetNumAchievements.argtypes = [ctypes.c_void_p]
        self.dll.SteamAPI_ISteamUserStats_GetNumAchievements.restype = ctypes.c_uint32
        self.dll.SteamAPI_ISteamUserStats_GetAchievementName.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.dll.SteamAPI_ISteamUserStats_GetAchievementName.restype = ctypes.c_char_p
        self.dll.SteamAPI_ISteamUserStats_GetAchievement.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_bool),
        ]
        self.dll.SteamAPI_ISteamUserStats_GetAchievement.restype = ctypes.c_bool

        # --- Stats (Int32 / Float) ---
        self.dll.SteamAPI_ISteamUserStats_SetStatInt32.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32]
        self.dll.SteamAPI_ISteamUserStats_SetStatInt32.restype = ctypes.c_bool
        self.dll.SteamAPI_ISteamUserStats_SetStatFloat.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_float]
        self.dll.SteamAPI_ISteamUserStats_SetStatFloat.restype = ctypes.c_bool
        self.dll.SteamAPI_ISteamUserStats_GetStatInt32.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int32),
        ]
        self.dll.SteamAPI_ISteamUserStats_GetStatInt32.restype = ctypes.c_bool
        self.dll.SteamAPI_ISteamUserStats_GetStatFloat.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_float),
        ]
        self.dll.SteamAPI_ISteamUserStats_GetStatFloat.restype = ctypes.c_bool

        # --- RunCallbacks ---
        self.dll.SteamAPI_RunCallbacks.restype = None

        # Request stats so achievement queries work
        self.dll.SteamAPI_ISteamUserStats_RequestCurrentStats(self.user_stats)

        self.log("SteamAPI_Init ok")
        return True

    def run_callbacks(self):
        with self._lock:
            if self.dll:
                self.dll.SteamAPI_RunCallbacks()

    # -- Achievements --

    def unlock(self, ach_id: str) -> bool:
        if self.dry_run:
            self.log(f"[DRY RUN] unlock: {ach_id}")
            return True
        with self._lock:
            if not self.dll or not self.user_stats:
                return False
            ok = self.dll.SteamAPI_ISteamUserStats_SetAchievement(self.user_stats, ach_id.encode("utf-8"))
            if not ok:
                self.log(f"SetAchievement failed: {ach_id}")
                return False
            ok = self.dll.SteamAPI_ISteamUserStats_StoreStats(self.user_stats)
            if not ok:
                self.log(f"StoreStats failed: {ach_id}")
                return False
        self.log(f"Achievement unlocked: {ach_id}")
        return True

    def clear(self, ach_id: str) -> bool:
        if self.dry_run:
            self.log(f"[DRY RUN] clear: {ach_id}")
            return True
        with self._lock:
            if not self.dll or not self.user_stats:
                return False
            ok = self.dll.SteamAPI_ISteamUserStats_ClearAchievement(self.user_stats, ach_id.encode("utf-8"))
            if not ok:
                self.log(f"ClearAchievement failed: {ach_id}")
                return False
            ok = self.dll.SteamAPI_ISteamUserStats_StoreStats(self.user_stats)
            if not ok:
                self.log(f"StoreStats failed after clear: {ach_id}")
                return False
        self.log(f"Achievement cleared: {ach_id}")
        return True

    def get_all_achievements(self) -> list[tuple[str, bool]]:
        """Return list of (api_name, unlocked)."""
        if self.dry_run:
            self.log("[DRY RUN] get_all_achievements → sample data")
            return [("ACH_SAMPLE_01", False), ("ACH_SAMPLE_02", True)]
        with self._lock:
            if not self.dll or not self.user_stats:
                return []
            n = self.dll.SteamAPI_ISteamUserStats_GetNumAchievements(self.user_stats)
            result = []
            for i in range(n):
                raw = self.dll.SteamAPI_ISteamUserStats_GetAchievementName(self.user_stats, i)
                if not raw:
                    continue
                name = raw.decode("utf-8", errors="replace")
                achieved = ctypes.c_bool(False)
                self.dll.SteamAPI_ISteamUserStats_GetAchievement(
                    self.user_stats, name.encode("utf-8"), ctypes.byref(achieved)
                )
                result.append((name, achieved.value))
        return result

    # -- Stats --

    def set_stat(self, name: str, value, stat_type: str = "int") -> bool:
        if self.dry_run:
            self.log(f"[DRY RUN] set_stat {name}={value} ({stat_type})")
            return True
        with self._lock:
            if not self.dll or not self.user_stats:
                return False
            encoded = name.encode("utf-8")
            if stat_type == "float":
                ok = self.dll.SteamAPI_ISteamUserStats_SetStatFloat(self.user_stats, encoded, ctypes.c_float(float(value)))
            else:
                ok = self.dll.SteamAPI_ISteamUserStats_SetStatInt32(self.user_stats, encoded, ctypes.c_int32(int(value)))
            if not ok:
                self.log(f"SetStat failed: {name}")
                return False
            ok = self.dll.SteamAPI_ISteamUserStats_StoreStats(self.user_stats)
            if not ok:
                self.log(f"StoreStats failed after SetStat: {name}")
                return False
        self.log(f"Stat set: {name}={value} ({stat_type})")
        return True

    def get_stat(self, name: str, stat_type: str = "int"):
        if self.dry_run:
            self.log(f"[DRY RUN] get_stat {name} ({stat_type}) → 0")
            return 0
        with self._lock:
            if not self.dll or not self.user_stats:
                return None
            encoded = name.encode("utf-8")
            if stat_type == "float":
                val = ctypes.c_float(0)
                ok = self.dll.SteamAPI_ISteamUserStats_GetStatFloat(self.user_stats, encoded, ctypes.byref(val))
            else:
                val = ctypes.c_int32(0)
                ok = self.dll.SteamAPI_ISteamUserStats_GetStatInt32(self.user_stats, encoded, ctypes.byref(val))
            if not ok:
                self.log(f"GetStat failed: {name}")
                return None
        self.log(f"Stat get: {name}={val.value} ({stat_type})")
        return val.value

    def shutdown(self):
        if self.dll:
            try:
                self.dll.SteamAPI_Shutdown()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------
def _config_path() -> str:
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, CONFIG_FILE)


def load_config() -> dict:
    path = _config_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data: dict):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auto-detect Game.exe next to this script / exe
# ---------------------------------------------------------------------------
def auto_detect_game_exe() -> str | None:
    base = os.path.dirname(os.path.abspath(sys.argv[0]))
    candidate = os.path.join(base, "Game.exe")
    if os.path.isfile(candidate):
        return candidate
    return None


# ---------------------------------------------------------------------------
# Toast notification (Steam-style popup)
# ---------------------------------------------------------------------------
class Toast:
    """Lightweight Toplevel that fades out after *duration* ms."""

    def __init__(self, parent: tk.Tk, message: str, duration: int = 3000):
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#1b2838")

        frm = tk.Frame(self.win, bg="#1b2838", padx=16, pady=10)
        frm.pack()
        tk.Label(frm, text="\u2705", font=("Segoe UI", 16), bg="#1b2838", fg="#66c0f4").pack(side="left", padx=(0, 8))
        tk.Label(frm, text=message, font=("Segoe UI", 11), bg="#1b2838", fg="#c7d5e0", wraplength=280).pack(side="left")

        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sx = parent.winfo_screenwidth()
        sy = parent.winfo_screenheight()
        self.win.geometry(f"+{sx - w - 20}+{sy - h - 60}")

        self.win.after(duration, self._close)

    def _close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class App:
    MINI_LOG_LINES = 5

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WOLF Steam Bridge GUI")
        self.root.geometry("860x580")

        # --- Variables ---
        cfg = load_config()
        detected = auto_detect_game_exe()
        self.game_exe = tk.StringVar(value=cfg.get("game_exe", detected or "Game.exe"))
        self.cmd_dir = tk.StringVar(value=cfg.get("cmd_dir", "steam_cmd"))
        self.dry_run = tk.BooleanVar(value=cfg.get("dry_run", False))

        self.running = False
        self._closing = False
        self.worker = None
        self.steam = None  # created at start

        # --- Notebook ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_main_tab()
        self._build_achievements_tab()
        self._build_stats_tab()
        self._build_log_tab()

        # --- Drag & Drop ---
        if HAS_WINDND:
            windnd.hook_dropfiles(self.root, self._on_drop)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ tabs

    def _build_main_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Main")

        # Game EXE row
        ttk.Label(tab, text="Game EXE:").grid(row=0, column=0, sticky="w")
        ttk.Entry(tab, textvariable=self.game_exe, width=80).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(tab, text="Browse", command=self._pick_exe).grid(row=0, column=2)

        # Command dir row
        ttk.Label(tab, text="Command Dir:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(tab, textvariable=self.cmd_dir, width=80).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(tab, text="Browse", command=self._pick_dir).grid(row=1, column=2, pady=(8, 0))

        # Dry-run + buttons row
        ctrl = ttk.Frame(tab)
        ctrl.grid(row=2, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Checkbutton(ctrl, text="Dry Run (no Steam, no Game launch)", variable=self.dry_run).pack(side="left")
        ttk.Button(ctrl, text="Start", command=self._start).pack(side="left", padx=(16, 0))
        ttk.Button(ctrl, text="Stop", command=self._stop).pack(side="left", padx=8)

        # Help label
        ttk.Label(
            tab,
            text="Commands: unlock ACH_ID | clear ACH_ID | clear_all | set_stat NAME TYPE VALUE | get_stat NAME TYPE",
        ).grid(row=3, column=0, columnspan=3, sticky="w")

        # Mini log
        self.mini_log = tk.Text(tab, height=self.MINI_LOG_LINES, state="disabled", bg="#f5f5f5")
        self.mini_log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_achievements_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Achievements")

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Refresh", command=self._ach_refresh).pack(side="left")
        ttk.Button(toolbar, text="Clear All", command=self._ach_clear_all).pack(side="left", padx=8)

        sep = ttk.Separator(toolbar, orient="vertical")
        sep.pack(side="left", fill="y", padx=8, pady=2)

        ttk.Label(toolbar, text="ACH ID:").pack(side="left")
        self.ach_id_entry = ttk.Entry(toolbar, width=30)
        self.ach_id_entry.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Unlock", command=self._ach_manual_unlock).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Clear", command=self._ach_manual_clear).pack(side="left", padx=2)

        # Treeview
        cols = ("api_name", "status")
        self.ach_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self.ach_tree.heading("api_name", text="API Name")
        self.ach_tree.heading("status", text="Status")
        self.ach_tree.column("api_name", width=350)
        self.ach_tree.column("status", width=120)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.ach_tree.yview)
        self.ach_tree.configure(yscrollcommand=vsb.set)

        self.ach_tree.pack(side="left", fill="both", expand=True, pady=(8, 0))
        vsb.pack(side="right", fill="y", pady=(8, 0))

    def _build_stats_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Stats")

        row = ttk.Frame(tab)
        row.pack(fill="x")

        ttk.Label(row, text="Stat Name:").pack(side="left")
        self.stat_name = ttk.Entry(row, width=30)
        self.stat_name.pack(side="left", padx=4)

        ttk.Label(row, text="Type:").pack(side="left", padx=(12, 0))
        self.stat_type = ttk.Combobox(row, values=["Int", "Float"], state="readonly", width=8)
        self.stat_type.set("Int")
        self.stat_type.pack(side="left", padx=4)

        ttk.Label(row, text="Value:").pack(side="left", padx=(12, 0))
        self.stat_value = ttk.Entry(row, width=16)
        self.stat_value.pack(side="left", padx=4)

        ttk.Button(row, text="Set", command=self._stat_set).pack(side="left", padx=(12, 2))
        ttk.Button(row, text="Get", command=self._stat_get).pack(side="left", padx=2)

        # Result display
        self.stat_result = ttk.Label(tab, text="", font=("Consolas", 11))
        self.stat_result.pack(anchor="w", pady=(16, 0))

    def _build_log_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Log")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Clear Log", command=self._log_clear).pack(side="left")
        ttk.Button(toolbar, text="Export Log", command=self._log_export).pack(side="left", padx=8)

        self.log_text = tk.Text(tab, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

        # Tag colours
        self.log_text.tag_configure("success", foreground="#228B22")
        self.log_text.tag_configure("error", foreground="#CC0000")
        self.log_text.tag_configure("dryrun", foreground="#0066CC")
        self.log_text.tag_configure("normal", foreground="#000000")

    # -------------------------------------------------------- thread-safe GUI helpers

    def _safe_after(self, callback, *args):
        """Schedule callback on the main thread, silently ignored during shutdown."""
        if self._closing:
            return
        try:
            self.root.after(0, callback, *args)
        except tk.TclError:
            pass

    # -------------------------------------------------------- logging (thread-safe)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        # File log (always)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        # GUI update via main thread
        self._safe_after(self._append_log, line, msg)

    def _append_log(self, line: str, raw_msg: str):
        # Determine tag
        tag = "normal"
        low = raw_msg.lower()
        if "fail" in low or "error" in low:
            tag = "error"
        elif "dry run" in low:
            tag = "dryrun"
        elif "unlocked" in low or "cleared" in low or "set:" in low or " ok" in low:
            tag = "success"

        # Full log tab
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line, tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

        # Mini log (keep last N lines)
        self.mini_log.configure(state="normal")
        self.mini_log.insert("end", line)
        # Trim to MINI_LOG_LINES
        count = int(self.mini_log.index("end-1c").split(".")[0])
        if count > self.MINI_LOG_LINES:
            self.mini_log.delete("1.0", f"{count - self.MINI_LOG_LINES}.0")
        self.mini_log.see("end")
        self.mini_log.configure(state="disabled")

    # -------------------------------------------------------- file pickers

    def _pick_exe(self):
        p = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if p:
            self.game_exe.set(p)

    def _pick_dir(self):
        p = filedialog.askdirectory()
        if p:
            self.cmd_dir.set(p)

    # -------------------------------------------------------- drag & drop

    def _on_drop(self, files):
        for raw in files:
            path = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            if path.lower().endswith(".exe"):
                self.game_exe.set(path)
                self.log(f"Game EXE set via drag & drop: {path}")
                return

    # -------------------------------------------------------- start / stop

    def _start(self):
        if self.running:
            return
        exe = self.game_exe.get().strip()
        cmd_dir = self.cmd_dir.get().strip()
        dry = self.dry_run.get()

        if not dry and (not exe or not os.path.exists(exe)):
            messagebox.showerror("Error", "Game EXE not found")
            return
        os.makedirs(cmd_dir, exist_ok=True)

        self.steam = SteamFlatAPI(self.log, dry_run=dry)
        if not self.steam.init():
            messagebox.showerror(
                "Steam",
                "Steam API init failed.\n\n"
                "1. steam_api.dll (32bit/win32) をこの exe と同じフォルダに置いてください\n"
                "2. Steam クライアントにログインした状態で起動してください\n"
                "3. 開発中は steam_appid.txt (中身=App ID) も必要です",
            )
            return

        # Save config
        save_config({
            "game_exe": exe,
            "cmd_dir": cmd_dir,
            "dry_run": dry,
        })

        self.running = True
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    def _stop(self):
        self.running = False

    def _loop(self):
        exe = self.game_exe.get().strip()
        cmd_dir = self.cmd_dir.get().strip()
        dry = self.dry_run.get()

        proc = None
        if not dry:
            self.log(f"Launch game: {exe}")
            try:
                proc = subprocess.Popen([exe])
            except Exception as e:
                self.log(f"Game launch failed: {e}")
                self.running = False
                if self.steam:
                    self.steam.shutdown()
                return
        else:
            self.log("[DRY RUN] Game launch skipped — file watcher only")

        def game_alive():
            if dry:
                return True  # keep running until manual stop
            return proc is not None and proc.poll() is None

        while self.running and game_alive():
            if self.steam:
                self.steam.run_callbacks()
            try:
                entries = os.listdir(cmd_dir)
            except FileNotFoundError:
                entries = []
            for name in entries:
                path = os.path.join(cmd_dir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        line = f.readline().strip()
                    self._dispatch_command(line)
                except Exception as e:
                    self.log(f"Command read error: {e}")
                finally:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            time.sleep(0.1)

        self.running = False
        if self.steam:
            self.steam.shutdown()
        self.log("Bridge stopped")

    # -------------------------------------------------------- command dispatch

    def _dispatch_command(self, line: str):
        if not line:
            return
        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "unlock" and len(parts) >= 2:
            ach_id = parts[1]
            ok = self.steam.unlock(ach_id)
            if ok:
                self._safe_after(lambda: Toast(self.root, f"Achievement unlocked!\n{ach_id}"))

        elif cmd == "clear" and len(parts) >= 2:
            self.steam.clear(parts[1])

        elif cmd == "clear_all":
            self._do_clear_all()

        elif cmd == "set_stat" and len(parts) >= 4:
            # set_stat NAME TYPE VALUE
            stat_name = parts[1]
            stat_type = "float" if parts[2].lower() == "float" else "int"
            self.steam.set_stat(stat_name, parts[3], stat_type)

        elif cmd == "get_stat" and len(parts) >= 3:
            # get_stat NAME TYPE
            stat_name = parts[1]
            stat_type = "float" if parts[2].lower() == "float" else "int"
            self.steam.get_stat(stat_name, stat_type)

        else:
            self.log(f"Unknown command: {line}")

    # -------------------------------------------------------- achievements tab actions

    def _ach_refresh(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started. Press Start first.")
            return

        def _do():
            achs = self.steam.get_all_achievements()
            self._safe_after(self._ach_populate, achs)

        threading.Thread(target=_do, daemon=True).start()

    def _ach_populate(self, achs: list[tuple[str, bool]]):
        for item in self.ach_tree.get_children():
            self.ach_tree.delete(item)
        for name, unlocked in achs:
            status = "Unlocked" if unlocked else "Locked"
            self.ach_tree.insert("", "end", values=(name, status))
        self.log(f"Achievements loaded: {len(achs)} items")

    def _ach_clear_all(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started.")
            return
        if not messagebox.askyesno("Confirm", "Clear ALL achievements? This cannot be undone."):
            return

        def _do():
            achs = self.steam.get_all_achievements()
            count = 0
            for name, unlocked in achs:
                if unlocked:
                    if self.steam.clear(name):
                        count += 1
            self.log(f"Clear All done: {count} achievements cleared")
            self._safe_after(self._ach_refresh)

        threading.Thread(target=_do, daemon=True).start()

    def _do_clear_all(self):
        """Clear all achievements (called from command dispatch, already on worker thread)."""
        achs = self.steam.get_all_achievements()
        count = 0
        for name, unlocked in achs:
            if unlocked:
                if self.steam.clear(name):
                    count += 1
        self.log(f"clear_all: {count} achievements cleared")

    def _ach_manual_unlock(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started.")
            return
        ach_id = self.ach_id_entry.get().strip()
        if not ach_id:
            return

        def _do():
            ok = self.steam.unlock(ach_id)
            if ok:
                self._safe_after(lambda: Toast(self.root, f"Achievement unlocked!\n{ach_id}"))

        threading.Thread(target=_do, daemon=True).start()

    def _ach_manual_clear(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started.")
            return
        ach_id = self.ach_id_entry.get().strip()
        if not ach_id:
            return
        threading.Thread(target=lambda: self.steam.clear(ach_id), daemon=True).start()

    # -------------------------------------------------------- stats tab actions

    def _stat_set(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started.")
            return
        name = self.stat_name.get().strip()
        stype = self.stat_type.get().lower()
        val = self.stat_value.get().strip()
        if not name or not val:
            return
        # Validate numeric value before spawning thread
        try:
            float(val) if stype == "float" else int(val)
        except ValueError:
            messagebox.showerror("Input Error", f"'{val}' is not a valid {stype} value.")
            return

        def _do():
            self.steam.set_stat(name, val, stype)

        threading.Thread(target=_do, daemon=True).start()

    def _stat_get(self):
        if not self.steam:
            messagebox.showinfo("Info", "Bridge not started.")
            return
        name = self.stat_name.get().strip()
        stype = self.stat_type.get().lower()
        if not name:
            return

        def _do():
            v = self.steam.get_stat(name, stype)
            self._safe_after(lambda: self.stat_result.configure(text=f"{name} = {v}"))

        threading.Thread(target=_do, daemon=True).start()

    # -------------------------------------------------------- log tab actions

    def _log_clear(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _log_export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All", "*.*")],
            initialfile="steam_bridge_export.log",
        )
        if not path:
            return
        try:
            content = self.log_text.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log(f"Log exported to {path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # -------------------------------------------------------- lifecycle

    def _on_close(self):
        # Save config on exit
        save_config({
            "game_exe": self.game_exe.get(),
            "cmd_dir": self.cmd_dir.get(),
            "dry_run": self.dry_run.get(),
        })
        self._closing = True
        self._stop()
        # Wait for worker thread to finish (up to 1s) before destroying UI
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=1.0)
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    App(root)
    root.mainloop()
