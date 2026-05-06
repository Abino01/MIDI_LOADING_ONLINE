import os
import mido
from music21 import converter, note, chord

class MidiProcessor:
    def parse(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        
        # 根據副檔名選擇解析引擎
        if ext in ['.mid', '.midi']:
            return self._parse_midi_with_mido(file_path)
        elif ext in ['.xml', '.mxl']:
            return self._parse_xml_with_music21(file_path)
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")

    def _parse_midi_with_mido(self, file_path):
        """使用 mido 解析 MIDI 檔案 (節奏最精準，支援變速，並過濾鼓組)"""
        mid = mido.MidiFile(file_path)
        notes = []
        current_time_sec = 0.0 
        
        for msg in mid:
            current_time_sec += msg.time
            
            # 捕捉按下音符的瞬間 (有些 MIDI 用 velocity=0 代表鬆開)
            if msg.type == 'note_on' and msg.velocity > 0:
                
                # 【新增的過濾邏輯】：如果是第 10 通道 (索引為 9) 的鼓組，就跳過不處理
                if msg.channel == 9:
                    continue
                    
                notes.append({
                    't': current_time_sec, # 絕對秒數
                    'p': msg.note
                })
        
        notes.sort(key=lambda x: x['t'])
        
        return {
            'title': os.path.basename(file_path),
            'author': 'Unknown',
            'bpm': 120, # 僅供顯示
            'duration': mid.length, # 總時長(秒)
            'key': 'Unknown',
            'notes': notes
        }


    def _parse_xml_with_music21(self, file_path):
        """使用 music21 解析 XML 檔案 ( fallback 方案 )"""
        score = converter.parse(file_path)
        bpm = self._get_bpm(score)
        bpm_factor = 60.0 / bpm
        notes = []
        
        for element in score.flat.notes:
            # 提前在這裡把「拍數」轉換為「絕對秒數」
            t_sec = float(element.offset) * bpm_factor
            
            if isinstance(element, note.Note):
                notes.append({'t': t_sec, 'p': element.pitch.midi})
            elif isinstance(element, chord.Chord):
                for n in element.notes:
                    notes.append({'t': t_sec, 'p': n.pitch.midi})
        
        notes.sort(key=lambda x: x['t'])
        total_duration_sec = float(score.duration.quarterLength) * bpm_factor
        
        return {
            'title': os.path.basename(file_path),
            'author': 'Unknown',
            'bpm': bpm,
            'duration': total_duration_sec,
            'key': str(score.analyze('key')),
            'notes': notes
        }

    def _get_bpm(self, score):
        temp = score.metronomeMarkBoundaries()
        return temp[0][2].number if temp else 120
