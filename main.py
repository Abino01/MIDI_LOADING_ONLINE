import tkinter as tk
from tkinter import ttk, filedialog
import threading
import time
import psutil
import win32gui
import win32con
import win32api
import win32com.client
import pythoncom
import webbrowser
import os
from processor import MidiProcessor
from bridge import KeyboardBridge
from logger import AppLogger
from MidiListener import MidiListener

class AIPianoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PianoAutoPlayer_v0.9.4")
        self.root.geometry("800x550")
        
        self.processor = MidiProcessor()
        self.bridge = KeyboardBridge()
        self.logger = AppLogger()
        
        self.current_song = None
        self.is_playing = False
        self.keys_rects = {}
        
        self.speed = tk.DoubleVar(value=1.0)
        self.transpose = tk.IntVar(value=0)
        self.countdown_text = tk.StringVar(value="")
        self.midi_listener = MidiListener(self.bridge, self)

        self.setup_ui()
        self.update_sys_monitor()

    def setup_ui(self):
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(pady=10, fill="x", padx=20)
        ttk.Button(ctrl_frame, text="導入檔案", command=self.load_midi).pack(side="left", padx=5)
        self.play_btn = ttk.Button(ctrl_frame, text="播放並鎖定視窗", command=self.start_playback)
        self.play_btn.pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="暫停", command=self.pause_playback).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="停止播放", command=self.stop_playback).pack(side="left", padx=5)

        info_frame = ttk.LabelFrame(self.root, text="當前曲目")
        info_frame.pack(fill="x", padx=20, pady=5)
        self.info_lbl = ttk.Label(info_frame, text="等待導入檔案...", font=("Microsoft JhengHei", 10))
        self.info_lbl.pack(pady=10)
        
        self.countdown_lbl = tk.Label(self.root, textvariable=self.countdown_text, font=("Microsoft JhengHei", 14, "bold"), fg="#e74c3c")
        self.countdown_lbl.pack()

        set_frame = ttk.LabelFrame(self.root, text="參數設定")
        set_frame.pack(fill="x", padx=20, pady=5)
        tk.Scale(set_frame, from_=0.5, to=1.5, resolution=0.1, orient="horizontal", variable=self.speed, label="播放速度").pack(side="left", fill="x", expand=True, padx=10)
        ttk.Label(set_frame, text="轉調:").pack(side="left")
        ttk.Spinbox(set_frame, from_=-12, to=12, textvariable=self.transpose, width=5).pack(side="left", padx=5)

        self.canvas = tk.Canvas(self.root, width=810, height=120, bg="#2c3e50", highlightthickness=0)
        self.canvas.pack(pady=10)
        self.setup_visual_canvas()

        footer = ttk.Frame(self.root)
        footer.pack(side="bottom", fill="x", padx=10, pady=5)
        git_lbl = tk.Label(footer, text="GitHub: Abino01/MIDI_LOADING_ONLINE", font=("Microsoft JhengHei", 9), fg="gray", cursor="hand2")
        git_lbl.pack(side="left")
        git_lbl.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/Abino01/MIDI_LOADING_ONLINE"))
        self.sys_status_lbl = tk.Label(footer, text="資源讀取中...", font=("Consolas", 10), fg="#27ae60")
        self.sys_status_lbl.pack(side="right")

    def load_midi(self):
        path = filedialog.askopenfilename(filetypes=[("音樂檔案", "*.mid;*.midi;*.xml;*.mxl")])
        if path:
            try:
                self.current_song = self.processor.parse(path)
                fname = os.path.basename(path)
                dur = int(self.current_song.get('duration', 0))
                self.info_lbl.config(text=f"已成功載入：{fname} | 長度：{dur}秒")
                self.countdown_text.set("導入成功！點擊播放並切換至遊戲")
            except Exception as e:
                self.info_lbl.config(text=f"解析失敗：{str(e)}")

    def setup_visual_canvas(self):
        self.canvas.delete("all")
        w = 810 / 52
        white_idx = 0
        for midi in range(21, 109):
            if midi % 12 not in [1, 3, 6, 8, 10]:
                x0 = white_idx * w
                self.keys_rects[midi] = self.canvas.create_rectangle(x0, 0, x0+w, 120, fill="white", outline="gray")
                white_idx += 1
        white_idx = 0
        for midi in range(21, 109):
            if midi % 12 in [1, 3, 6, 8, 10]:
                x0 = (white_idx * w) - (w * 0.3)
                self.keys_rects[midi] = self.canvas.create_rectangle(x0, 0, x0+(w*0.6), 75, fill="black", outline="white")
            else:
                white_idx += 1

    def trigger_key_visual(self, midi_note):
        if midi_note not in self.keys_rects: return
        rect = self.keys_rects[midi_note]
        color = "black" if midi_note % 12 in [1, 3, 6, 8, 10] else "white"
        self.canvas.itemconfig(rect, fill="#3498db")
        self.root.after(150, lambda: self.canvas.itemconfig(rect, fill=color))

    def adjust_pitch(self, p):
        while p < 48: p += 12
        while p > 95: p -= 12
        return p

    def start_playback(self):
        if not self.current_song: return
        def countdown():
            for i in range(3, 0, -1):
                self.countdown_text.set(f"請在 {i} 秒內點擊遊戲視窗...")
                time.sleep(1)
            hwnd = win32gui.GetAncestor(win32gui.WindowFromPoint(win32api.GetCursorPos()), win32con.GA_ROOT)
            self.bridge.set_target_hwnd(hwnd)
            self.is_playing = True
            threading.Thread(target=self.play_engine, daemon=True).start()
        threading.Thread(target=countdown, daemon=True).start()

    def play_engine(self):
        self.countdown_text.set("演奏中 (後臺擷取鎖定中)")
        start_t = time.time()
        notes = self.current_song['notes']
        i = 0
        while i < len(notes) and self.is_playing:
            target = notes[i]['t'] / self.speed.get()
            while (time.time() - start_t) < target:
                if not self.is_playing: return
                time.sleep(0.001)
            chord = []
            cur_t = notes[i]['t']
            while i < len(notes) and abs(notes[i]['t'] - cur_t) < 0.005:
                p = self.adjust_pitch(notes[i]['p'] + self.transpose.get())
                chord.append(p)
                self.root.after(0, self.trigger_key_visual, p)
                i += 1
            self.bridge.execute_chord(chord)
        self.is_playing = False
        self.countdown_text.set("演奏結束")
    # 按鍵UI反饋與播放邏輯
    def pause_playback(self):
        self.is_paused = True

    def stop_playback(self):
        self.is_playing = False
        self.is_paused = False
        
    def get_gpu(self):
        try:
            pythoncom.CoInitialize()
            wmi = win32com.client.GetObject(r"winmgmts:root\cimv2")
            items = wmi.ExecQuery("SELECT UtilizationPercentage FROM Win32_PerfFormattedData_GPUPerformanceAnalyzer_GPUEngine")
            usages = [int(i.UtilizationPercentage) for i in items]
            return f"{max(usages)}%" if usages else "0%"
        except: return "N/A"

    def update_sys_monitor(self):
        try:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            gpu = self.get_gpu()
            self.sys_status_lbl.config(text=f"CPU: {cpu}% | RAM: {ram}% | GPU: {gpu}")
        except: pass
        self.root.after(1000, self.update_sys_monitor)

if __name__ == "__main__":
    root = tk.Tk()
    app = AIPianoApp(root)
    root.mainloop()