import ctypes
import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class SteamFlatAPI:
    def __init__(self, log):
        self.log = log
        self.dll = None
        self.user_stats = None

    def init(self) -> bool:
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

        self.dll.SteamAPI_ISteamUserStats_SetAchievement.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.dll.SteamAPI_ISteamUserStats_SetAchievement.restype = ctypes.c_bool
        self.dll.SteamAPI_ISteamUserStats_StoreStats.argtypes = [ctypes.c_void_p]
        self.dll.SteamAPI_ISteamUserStats_StoreStats.restype = ctypes.c_bool
        self.dll.SteamAPI_RunCallbacks.restype = None
        self.log("SteamAPI_Init ok")
        return True

    def run_callbacks(self):
        if self.dll:
            self.dll.SteamAPI_RunCallbacks()

    def unlock(self, ach_id: str) -> bool:
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

    def shutdown(self):
        if self.dll:
            try:
                self.dll.SteamAPI_Shutdown()
            except Exception:
                pass


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("WOLF Steam Bridge GUI")
        self.root.geometry("760x480")

        self.game_exe = tk.StringVar(value="Game.exe")
        self.cmd_dir = tk.StringVar(value="steam_cmd")
        self.running = False
        self.worker = None
        self.steam = SteamFlatAPI(self.log)

        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Game EXE:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.game_exe, width=70).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frm, text="Browse", command=self.pick_exe).grid(row=0, column=2)

        ttk.Label(frm, text="Command Dir:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frm, textvariable=self.cmd_dir, width=70).grid(row=1, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(frm, text="Browse", command=self.pick_dir).grid(row=1, column=2, pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Button(btns, text="Start", command=self.start).pack(side="left")
        ttk.Button(btns, text="Stop", command=self.stop).pack(side="left", padx=8)

        ttk.Label(frm, text="WOLF command format: unlock ACH_ID").grid(row=3, column=0, columnspan=3, sticky="w")

        self.text = tk.Text(frm, height=18)
        self.text.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        if hasattr(self, "text"):
            self.text.insert("end", line)
            self.text.see("end")
        try:
            with open("steam_bridge.log", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def pick_exe(self):
        p = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if p:
            self.game_exe.set(p)

    def pick_dir(self):
        p = filedialog.askdirectory()
        if p:
            self.cmd_dir.set(p)

    def start(self):
        if self.running:
            return
        exe = self.game_exe.get().strip()
        cmd_dir = self.cmd_dir.get().strip()
        if not exe or not os.path.exists(exe):
            messagebox.showerror("Error", "Game EXE not found")
            return
        os.makedirs(cmd_dir, exist_ok=True)

        if not self.steam.init():
            messagebox.showerror("Steam", "Steam API init failed. Launch from Steam and place steam_api.dll next to this app.")
            return

        self.running = True
        self.worker = threading.Thread(target=self.loop, daemon=True)
        self.worker.start()

    def stop(self):
        self.running = False

    def loop(self):
        exe = self.game_exe.get().strip()
        cmd_dir = self.cmd_dir.get().strip()

        self.log(f"Launch game: {exe}")
        proc = subprocess.Popen([exe])

        while self.running and proc.poll() is None:
            self.steam.run_callbacks()
            for name in os.listdir(cmd_dir):
                path = os.path.join(cmd_dir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        line = f.readline().strip()
                    parts = line.split(maxsplit=1)
                    if len(parts) == 2 and parts[0].lower() == "unlock":
                        self.steam.unlock(parts[1])
                    else:
                        self.log(f"Unknown command: {line}")
                except Exception as e:
                    self.log(f"Command read error: {e}")
                finally:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            time.sleep(0.1)

        self.running = False
        self.steam.shutdown()
        self.log("Bridge stopped")

    def on_close(self):
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    App(root)
    root.mainloop()
