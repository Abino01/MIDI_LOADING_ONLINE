import time
import win32gui
import win32con
import win32api

class KeyboardBridge:
    def __init__(self):
        self.hwnd = None
        # MIDI虛擬鍵映射
        self.mapping = {
            # 低音區域
            60: (0x5A, None), 61: (0x5A, 'shift'), 62: (0x58, None), 63: (0x43, 'ctrl'), 64: (0x43, None),
            65: (0x56, None), 66: (0x56, 'shift'), 67: (0x42, None), 68: (0x42, 'shift'), 69: (0x4E, None),
            70: (0x4D, 'ctrl'), 71: (0x4D, None),
            # 中音區域
            72: (0x41, None), 73: (0x41, 'shift'), 74: (0x53, None), 75: (0x44, 'ctrl'), 76: (0x44, None),
            77: (0x46, None), 78: (0x46, 'shift'), 79: (0x47, None), 80: (0x47, 'shift'), 81: (0x48, None),
            82: (0x4A, 'ctrl'), 83: (0x4A, None),
            # 高音區域
            84: (0x51, None), 85: (0x51, 'shift'), 86: (0x57, None), 87: (0x45, 'ctrl'), 88: (0x45, None),
            89: (0x52, None), 90: (0x52, 'shift'), 91: (0x54, None), 92: (0x54, 'shift'), 93: (0x59, None),
            94: (0x55, 'ctrl'), 95: (0x55, None)
        }

    def set_target_hwnd(self, hwnd):
        """鎖定目標遊戲視窗句柄"""
        self.hwnd = hwnd

    def _force_send_key(self, vk_code, is_down):

        # 強制發送SendMessage to WM_ACTIVATE 構造精確LParam跟ScanCode

        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            return

        # 獲取硬體掃描碼 (Scan Code)
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        
        #強制視窗訊息隊列
        win32gui.SendMessage(self.hwnd, win32con.WM_ACTIVATE, win32con.WA_CLICKACTIVE, 0)
        
        if is_down:
            # 建立按下訊息LParam
            lparam = 1 | (scan_code << 16)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk_code, lparam)
        else:
            # 建立反饋訊息LParam(bit 30, 31 eor= 1)
            lparam = 1 | (scan_code << 16) | (0xC0000000)
            win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, vk_code, lparam)

    def execute_chord(self, midi_notes):
        """執行和弦演奏"""
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            return

        for note in midi_notes:
            if note in self.mapping:
                vk_code, mod = self.mapping[note]
                
                # 1. 處理修飾鍵按下
                if mod == 'shift': self._force_send_key(win32con.VK_SHIFT, True)
                if mod == 'ctrl': self._force_send_key(win32con.VK_CONTROL, True)

                # 2. 發送主按鍵按下
                self._force_send_key(vk_code, True)
                
                # 3. 模擬物理按壓延遲 (10ms)
                # 這是讓 DirectInput 引擎有足夠時間在下一幀採樣到按鍵狀態的關鍵
                time.sleep(0.01) 
                
                # 4. 發送主按鍵彈起
                self._force_send_key(vk_code, False)

                # 5. 釋放修飾鍵
                if mod == 'shift': self._force_send_key(win32con.VK_SHIFT, False)
                if mod == 'ctrl': self._force_send_key(win32con.VK_CONTROL, False)