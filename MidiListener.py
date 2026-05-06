import mido
import threading

class MidiListener:
    def __init__(self, bridge_instance, app_instance):
        self.bridge = bridge_instance
        self.app = app_instance
        self.is_listening = False
        self.listen_thread = None
        self.current_port = None

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
                            
                        # 1. 獲取音高並加上 UI 的轉調
                        base_pitch = msg.note + self.app.transpose.get()
                        
                        # 3. 呼叫 KeyboardBridge 彈奏 (包裝成列表傳入)
                        self.bridge.execute_chord([base_pitch])
                        
                        # 4. 觸發 UI 上的鋼琴按鍵發光 (可選)
                        self.app.root.after(0, self.app.trigger_key_visual, base_pitch)
                        
        except Exception as e:
            print(f"MIDI 監聽發生錯誤: {e}")
            self.is_listening = False

