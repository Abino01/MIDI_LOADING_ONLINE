import mido
from music21 import converter, note, chord
import os

class MidiProcessor:
    def parse(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        
        # 根據副檔名自動分流
        if ext in ['.mid', '.midi']:
            return self._parse_with_mido(file_path)
        elif ext in ['.xml', '.mxl']:
            return self._parse_with_music21(file_path)
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")

    def _parse_with_mido(self, file_path):
        """引擎 A: mido (極速處理 MIDI)"""
        mid = mido.MidiFile(file_path)
        notes = []
        tpb = mid.ticks_per_beat
        
        for track in mid.tracks:
            track_time = 0
            for msg in track:
                track_time += msg.time
                # 僅抓取按下音符且力度大於 0 的事件
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes.append({
                        't': track_time / tpb, # 換算為 Quarter Length 以相容 main.py
                        'p': msg.note
                    })
        
        notes.sort(key=lambda x: x['t'])
        
        return {
            'title': os.path.basename(file_path) + " (Fast Mode)",
            'bpm': self._get_bpm_mido(mid),
            'duration': max([n['t'] for n in notes]) if notes else 0,
            'notes': notes
        }

    def _parse_with_music21(self, file_path):
        """引擎 B: music21 (處理複雜 XML)"""
        score = converter.parse(file_path)
        notes = []
        
        for element in score.flat.notes:
            if isinstance(element, note.Note):
                notes.append({'t': float(element.offset), 'p': element.pitch.midi})
            elif isinstance(element, chord.Chord):
                for n in element.notes:
                    notes.append({'t': float(element.offset), 'p': n.pitch.midi})
        
        notes.sort(key=lambda x: x['t'])
        
        return {
            'title': os.path.basename(file_path) + " (High Compatibility Mode)",
            'bpm': self._get_bpm_music21(score),
            'duration': float(score.duration.quarterLength),
            'notes': notes
        }

    def _get_bpm_mido(self, mid):
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    return mido.tempo2bpm(msg.tempo)
        return 120

    def _get_bpm_music21(self, score):
        temp = score.metronomeMarkBoundaries()
        return temp[0][2].number if temp else 120