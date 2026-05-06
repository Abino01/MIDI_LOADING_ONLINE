import mido
import threading

class MidiListener:
    def __init__(self, bridge_instance, app_instance):
        self.bridge = bridge_instance
        self.app = app_instance
        self.is_listening = False
        self.listen_thread = None
        self.current_port = None

      # 【新增】：和弦緩衝池
        self.chord_buffer = []
        self.buffer_timer = None
    def _flush_buffer(self):
        """定時器觸發：把緩衝池裡的音符當作一個和弦一次性彈出"""
        if not self.chord_buffer: return
        
        # 複製當前緩衝池的音，然後清空緩衝池
        notes_to_play = self.chord_buffer.copy()
        self.chord_buffer.clear()
        self.buffer_timer = None
        
        # 一次性發送給鍵盤橋接器（完美實現多鍵齊按）
        self.bridge.execute_chord(notes_to_play)
        
        # 觸發 UI 視覺化
        for pitch in notes_to_play:
            self.app.root.after(0, self.app.trigger_key_visual, pitch)

    def get_available_ports(self):
        """獲取當前電腦上所有的 MIDI 輸入設備名稱"""
        return mido.get_input_names()

    def start_listening(self, port_name):
        """開始監聽指定的 MIDI 端口"""
        if self.is_listening:
            self.stop_listening()

        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop, args=(port_name,), daemon=True)
        self.listen_thread.start()
        print(f"開始監聽 MIDI 端口: {port_name}")

    def stop_listening(self):
        """停止監聽"""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=1)
        if self.current_port:
            self.current_port.close()
            self.current_port = None
        print("停止監聽 MIDI 端口")

    def _listen_loop(self, port_name):
        """後台監聽循環"""
        try:
            # 打開 MIDI 輸入端口
            with mido.open_input(port_name) as inport:
                self.current_port = inport
                
                # 持續接收實時 MIDI 訊號
                for msg in inport:
                    if not self.is_listening:
                        break
                        
                    # 當按下琴鍵時 (note_on 且力度大於 0)
                    if msg.type == 'note_on' and msg.velocity > 0:
                        
                        # 【過濾鼓組】：如果是第 10 通道 (索引為 9) 的鼓點，直接忽略！
                        if msg.channel == 9:
                            continue
                            
                        base_pitch = msg.note + self.app.transpose.get()
                        adjusted_pitch = self.app.adjust_pitch(base_pitch)
                        
                        # 【修改】：不直接彈，而是放進緩衝池
                        self.chord_buffer.append(adjusted_pitch)
                        
                        # 如果定時器還沒啟動，就啟動一個 0.01 秒的倒數計時
                        if self.buffer_timer is None:
                            self.buffer_timer = threading.Timer(0.01, self._flush_buffer)
                            self.buffer_timer.start()
                        
        except Exception as e:
            print(f"MIDI 監聽發生錯誤: {e}")
            self.is_listening = False

