import tkinter as tk
from tkinter import ttk, filedialog
import threading
import time
import psutil
from processor import MidiProcessor
from bridge import KeyboardBridge
from logger import AppLogger
from MidiListener import MidiListener

class AIPianoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PianoAotoPlayer_v0.8F")
        self.root.geometry("850x720")
        
        self.processor = MidiProcessor()
        self.bridge = KeyboardBridge()
        self.logger = AppLogger()
        
        self.current_song = None
        self.is_playing = False
        self.is_paused = False
        self.keys_rects = {}
        
        # UI 變量
        self.speed = tk.DoubleVar(value=1.0)
        self.transpose = tk.IntVar(value=0)
        self.visual_on = tk.BooleanVar(value=True)
        self.countdown_text = tk.StringVar(value="")
        self.midi_listener = MidiListener(self.bridge, self)

        self.setup_ui()
        self.update_cpu_monitor()

    def setup_ui(self):
        # 1. 頂部控制欄
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(pady=10, fill="x", padx=20)
        
        ttk.Button(ctrl_frame, text="導入檔案 (MIDI/XML)", command=self.load_midi).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="播放/繼續", command=self.start_playback).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="暫停", command=self.pause_playback).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="停止", command=self.stop_playback).pack(side="left", padx=5)
        
        self.cpu_lbl = ttk.Label(ctrl_frame, text="CPU: 0%", foreground="green")
        self.cpu_lbl.pack(side="right", padx=10)

        # 2. 狀態顯示與紅字倒數
        self.info_lbl = ttk.Label(self.root, text="[等待中] 請導入歌曲", font=("Microsoft JhengHei", 12), justify="center")
        self.info_lbl.pack(pady=5)
        
        # 紅字大倒數
        self.countdown_lbl = tk.Label(self.root, textvariable=self.countdown_text, font=("Arial", 36, "bold"), fg="red")
        self.countdown_lbl.pack(pady=5)

        # 3. 演奏參數設置區
        set_frame = ttk.LabelFrame(self.root, text="演奏控制")
        set_frame.pack(pady=5, fill="x", padx=20)
        
        # 播放速度：0.1 ~ 5.0，步長 0.1
        ttk.Label(set_frame, text="播放速度 (0.1-5.0):").grid(row=0, column=0, padx=5)
        self.speed_scale = ttk.Scale(set_frame, from_=0.1, to=5.0, variable=self.speed, orient="horizontal", length=200, command=self.update_speed_label)
        self.speed_scale.grid(row=0, column=1)
        self.speed_val_lbl = ttk.Label(set_frame, text="1.0x")
        self.speed_val_lbl.grid(row=0, column=2, padx=5)
        
        # 轉調
        ttk.Label(set_frame, text="轉調:").grid(row=0, column=3, padx=5)
        self.tp_spin = ttk.Spinbox(set_frame, from_=-12, to=12, textvariable=self.transpose, width=5)
        self.tp_spin.grid(row=0, column=4)
        
        ttk.Checkbutton(set_frame, text="開啟視覺化", variable=self.visual_on).grid(row=0, column=5, padx=10)
        # 獲取設備列表
        ports = self.midi_listener.get_available_ports()
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(ctrl_frame, textvariable=self.port_var, values=ports)
        self.port_combo.pack(side="left", padx=5)
        # 添加一個連接按鈕
        ttk.Button(ctrl_frame, text="連接 MIDI 鍵盤", command=self.connect_midi).pack(side="left")
        
        # 4. 88鍵畫布
        self.setup_visual_canvas()

    def connect_midi(self):
        port_name = self.port_var.get()
        if port_name:
            self.midi_listener.start_listening(port_name)
            self.info_lbl.config(text=f"[實時模式] 已連接: {port_name}")

    def setup_visual_canvas(self):
        v_frame = ttk.LabelFrame(self.root, text="視覺化鋼琴 (88鍵)")
        v_frame.pack(fill="x", padx=10, pady=5)
        self.v_canvas = tk.Canvas(v_frame, width=820, height=120, bg="white")
        self.v_canvas.pack(pady=5)
        
        w = 11.0 # 白鍵寬度
        white_idx = 0
        # 繪製白鍵 (MIDI 21 - 108)
        for midi in range(21, 109):
            if midi % 12 not in [1, 3, 6, 8, 10]:
                x0 = white_idx * w
                rect = self.v_canvas.create_rectangle(x0, 0, x0 + w, 120, fill="white", outline="gray")
                self.keys_rects[midi] = rect
                white_idx += 1
        # 重疊繪製黑鍵
        white_idx = 0
        for midi in range(21, 109):
            if midi % 12 in [1, 3, 6, 8, 10]:
                x0 = (white_idx * w) - (w * 0.3)
                rect = self.v_canvas.create_rectangle(x0, 0, x0 + (w * 0.6), 75, fill="black")
                self.keys_rects[midi] = rect
            else:
                white_idx += 1

    def update_speed_label(self, *args):
        # 強制四捨五入到 0.1 單位
        val = round(self.speed.get(), 1)
        self.speed.set(val)
        self.speed_val_lbl.config(text=f"{val}x")
        self.update_info_display()

    def update_info_display(self, elapsed=0):
        if not self.current_song: return
        s_factor = self.speed.get()
        # 直接除以倍速即可
        real_duration = self.current_song['duration'] / s_factor
        
        m, s = divmod(int(elapsed), 60)
        tm, ts = divmod(int(real_duration), 60)
        
        status = "[播放中]" if self.is_playing else "[等待中]"
        if self.is_paused: status = "[暫停中]"
        
        info = f"{status} {self.current_song['title']}\n進度: {m:02d}:{s:02d} / 總長: {tm:02d}:{ts:02d} (速度: {s_factor}x)"
        self.info_lbl.config(text=info)

    def load_midi(self):
        # 支援雙引擎格式
        path = filedialog.askopenfilename(filetypes=[
            ("所有支援格式", "*.mid;*.midi;*.xml;*.mxl"),
            ("MIDI 檔案", "*.mid;*.midi"),
            ("MusicXML 檔案", "*.xml;*.mxl")
        ])
        if path:
            try:
                self.current_song = self.processor.parse(path)
                self.update_info_display(0)
                self.logger.info(f"成功加載檔案: {path}")
            except Exception as e:
                self.logger.error(f"解析檔案失敗: {e}")

    def trigger_key_visual(self, midi_note):
        if not self.visual_on.get() or midi_note not in self.keys_rects: return
        rect = self.keys_rects[midi_note]
        # 判斷原色
        orig_color = "black" if midi_note % 12 in [1, 3, 6, 8, 10] else "white"
        self.v_canvas.itemconfig(rect, fill="cyan")
        self.root.after(120, lambda: self.v_canvas.itemconfig(rect, fill=orig_color))

    def start_playback(self):
        if not self.current_song: return
        if self.is_paused:
            self.is_paused = False
            return
        if not self.is_playing:
            self.is_playing = True
            threading.Thread(target=self.play_engine, daemon=True).start()

    def adjust_pitch(self, midi_pitch):
        """將加上轉調後的音高，限制在 60~95 之間 (自動移八度)"""
        while midi_pitch < 60:
            midi_pitch += 12
        while midi_pitch > 95:
            midi_pitch -= 12
        return midi_pitch
    
    def play_engine(self):
        # 播放前紅字倒數
        for i in range(3, 0, -1):
            if not self.is_playing: 
                self.countdown_text.set("")
                return
            self.countdown_text.set(f"準備演奏: {i}")
            time.sleep(1)
        
        self.countdown_text.set("GO!")
        self.root.after(1000, lambda: self.countdown_text.set(""))

        # 正式演奏邏輯
        start_t = time.time()
        elapsed = 0
        notes = self.current_song['notes']
        #bpm_factor = 60 / self.current_song['bpm']
        i = 0
        
        while i < len(notes) and self.is_playing:
            if self.is_paused:
                time.sleep(0.1)
                start_t = time.time() - elapsed
                continue

            current_speed = self.speed.get()
            n = notes[i]
            # 因為 n['t'] 已經是絕對秒數，直接除以倍速即可
            target_time = n['t'] / current_speed
            
            # 和弦優化：抓取同一時間點的所有音符
            # 先加上 UI 的轉調值，再進行八度修正，確保最終音高在 60~95 內
            base_pitch = n['p'] + self.transpose.get()
            chord_midi = [self.adjust_pitch(base_pitch)]

            j = i + 1
            while j < len(notes) and abs(notes[j]['t'] - n['t']) < 0.005:
                next_pitch = notes[j]['p'] + self.transpose.get()
                chord_midi.append(self.adjust_pitch(next_pitch))
                j += 1

            # 高精準度等待
            while elapsed < target_time:
                if not self.is_playing: return
                elapsed = time.time() - start_t
                time.sleep(0.0005)

            # 透過 bridge 執行按鍵
            self.bridge.execute_chord(chord_midi)
            
            # 更新視覺化與 UI
            for m_note in chord_midi:
                self.root.after(0, self.trigger_key_visual, m_note)
            
            if i % 2 == 0: # 減少 UI 刷頻負擔
                self.root.after(0, self.update_info_display, elapsed)
            
            i = j # 跳至下一組音符
        
        self.is_playing = False
        self.update_info_display(elapsed)

    def stop_playback(self):
        self.is_playing = False
        self.is_paused = False
        self.countdown_text.set("")

    def pause_playback(self):
        if self.is_playing: self.is_paused = True

    def update_cpu_monitor(self):
        usage = psutil.cpu_percent()
        color = "red" if usage > 80 else "orange" if usage > 50 else "green"
        self.cpu_lbl.config(text=f"CPU: {usage}%", foreground=color)
        self.root.after(1000, self.update_cpu_monitor)

if __name__ == "__main__":
    root = tk.Tk()
    app = AIPianoApp(root)
    root.mainloop()