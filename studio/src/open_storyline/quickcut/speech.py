"""Local real ASR, source-to-edit subtitle mapping, and SRT export."""

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
MODEL_HASHES = {
    'base': '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe',
    'small-q5_1': 'ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb',
}
VENDORED_CLI = ROOT / 'runtime-local/vendor/whisper.cpp/build/bin/whisper-cli'


def local_asr_available() -> bool:
    """Report installation presence, without claiming recognition accuracy."""
    return any((ROOT / f'resource/models/whisper/ggml-{name}.bin').is_file() for name in MODEL_HASHES) and bool(VENDORED_CLI.is_file() or shutil.which('whisper-cli'))


def normalize_whisper(raw: Dict[str, Any], duration_ms: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validate genuine offsets and retain rejected segments with reasons."""
    if not isinstance(raw.get('transcription'), list):
        raise ValueError('Whisper没有返回合法转录结果')
    accepted, rejected = [], []
    for index, segment in enumerate(raw['transcription']):
        text = segment.get('text', '').strip()
        offsets = segment.get('offsets', {})
        start, end = offsets.get('from'), offsets.get('to')
        tokens = [t for t in segment.get('tokens', []) if not str(t.get('text', '')).startswith('[_')]
        probabilities = [float(t['p']) for t in tokens if isinstance(t.get('p'), (int, float)) and math.isfinite(t['p'])]
        mean_probability = sum(probabilities) / len(probabilities) if probabilities else None
        reason = None
        if not text or re.fullmatch(r'[\s\[\]（）()♪♫音乐掌声笑声]+', text):
            reason = 'non_speech_marker'
        elif not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= duration_ms + 250:
            reason = 'invalid_timestamp'
        elif mean_probability is not None and mean_probability < 0.35:
            reason = 'low_token_probability'
        elif len(text) > 120 or re.search(r'(.{2,8})\1{3,}', text):
            reason = 'repetition_or_excessive_length'
        record = {'segment_id': index, 'start_ms': start, 'end_ms': min(end, duration_ms) if isinstance(end, int) else end,
                  'text': text, 'token_probability_mean': mean_probability,
                  'tokens': tokens, 'review_status': 'unreviewed'}
        if reason:
            rejected.append({**record, 'reason': reason})
        else:
            accepted.append(record)
    return accepted, rejected


def transcribe_local(sources: List[Dict[str, Any]], ledger: Any, model_name: str = 'small-q5_1') -> List[Dict[str, Any]]:
    """Transcribe actual source audio using a bounded local lightweight-model process."""
    binary = str(VENDORED_CLI) if VENDORED_CLI.is_file() else shutil.which('whisper-cli')
    if model_name not in MODEL_HASHES:
        raise ValueError('本地语音模型不支持')
    model_path = ROOT / f'resource/models/whisper/ggml-{model_name}.bin'
    if not binary or not model_path.is_file():
        raise FileNotFoundError(f'本地语音识别尚未安装，请先安装Whisper.cpp和{model_name}模型')
    with model_path.open('rb') as model:
        model_hash = hashlib.file_digest(model, 'sha256').hexdigest()
    if model_hash != MODEL_HASHES[model_name]:
        raise ValueError('本地Whisper模型校验失败')
    folder = ledger.directory / 'speech'
    folder.mkdir(exist_ok=True)
    result = []
    ledger.data['providers']['asr'] = {'name': 'whisper.cpp', 'model': model_name,
                                     'model_sha256': model_hash, 'location': 'local',
                                     'timestamp_method': 'whisper_token_timestamps_approximate'}
    ledger.data['asr_calls'] = []
    ledger.data['capabilities']['speech_transcription'] = True
    for index, source in enumerate(sources):
        if not source['has_audio']:
            result.append({'source_path': source['path'], 'segments': [], 'rejected_segments': [], 'status': 'no_audio'})
            continue
        wav = folder / f'source_{index + 1:02d}.wav'
        prefix = folder / f'source_{index + 1:02d}'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', source['path'], '-vn',
                        '-af', 'aresample=async=1:first_pts=0', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(wav)],
                       capture_output=True, check=True, timeout=60)
        started = time.monotonic()
        command = [binary, '-m', str(model_path), '-f', str(wav), '-l', 'zh', '-t', '4',
                   '-ojf', '-osrt', '-of', str(prefix), '-ml', '24', '-sow', '-mc', '0', '-sns']
        # No domain prompt: the edit theme must not become invented spoken words.
        measured_command = ['/usr/bin/time', '-l', *command] if sys.platform == 'darwin' else command
        process = subprocess.run(measured_command, capture_output=True, text=True, timeout=300)
        (folder / f'source_{index + 1:02d}.log').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise RuntimeError(f'本地语音识别失败，退出码{process.returncode}；原始诊断保存在speech目录')
        raw = json.loads(prefix.with_suffix('.json').read_text(encoding='utf-8'))
        segments, rejected = normalize_whisper(raw, round(source['duration_s'] * 1000))
        result.append({'source_path': source['path'], 'segments': segments, 'rejected_segments': rejected,
                       'status': 'transcribed' if segments else 'no_accepted_speech', 'raw_path': str(prefix.with_suffix('.json'))})
        peak = re.search(r'(\d+)\s+maximum resident set size', process.stderr)
        ledger.data['asr_calls'].append({'source_path': source['path'], 'model': model_name,
                                         'elapsed_s': round(time.monotonic() - started, 3),
                                         'process_peak_rss_bytes': int(peak.group(1)) if peak else None,
                                         'status': 'success', 'accepted_segments': len(segments),
                                         'rejected_segments': len(rejected)})
        ledger.data['transcripts'] = result
        ledger.stage('transcribing', completed_sources=index + 1, total_sources=len(sources))
    ledger.data['warnings'].append('本地语音字幕为自动识别初稿；餐厅噪声、背景音乐和多人讲话可能造成错字，需人工核对。')
    ledger.data['transcripts'] = result
    ledger.save()
    return result


def project_speech(transcripts: List[Dict[str, Any]], timeline: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map complete recognized units into edited time; never label cut-off text as complete speech."""
    mapping = {item['source_path']: item for item in transcripts}
    output = []
    for clip in timeline['tracks']['video']:
        start, end = clip['source_window']['start'], clip['source_window']['end']
        timeline_start = clip['timeline_window']['start']
        for segment in mapping.get(clip['source_path'], {}).get('segments', []):
            if start <= segment['start_ms'] and segment['end_ms'] <= end:
                units = [{'text': segment['text'], 'start_ms': segment['start_ms'], 'end_ms': segment['end_ms']}]
            else:
                units = []
                # Preserve only complete timed tokens when a sentence is trimmed.
                for token in segment.get('tokens', []):
                    offset = token.get('offsets', {})
                    a, b = offset.get('from'), offset.get('to')
                    if isinstance(a, int) and isinstance(b, int) and start <= a < b <= end:
                        units.append({'text': token['text'], 'start_ms': a, 'end_ms': b})
            for unit in units:
                text = unit['text'].strip()
                if not text or text.startswith('[_'):
                    continue
                a, b = unit['start_ms'], unit['end_ms']
                if output and output[-1]['source_path'] == clip['source_path'] and output[-1]['candidate_id'] == clip['candidate_id'] and output[-1]['segment_id'] == segment.get('segment_id') and a - output[-1]['source_end_ms'] <= 200 and len(output[-1]['text']) + len(text) <= 14:
                    output[-1]['text'] += text
                    output[-1]['source_end_ms'] = b
                    output[-1]['timeline_window']['end'] = timeline_start + b - start
                else:
                    output.append({'kind': 'speech', 'text': text, 'source_path': clip['source_path'],
                                   'candidate_id': clip['candidate_id'], 'source_start_ms': a, 'source_end_ms': b,
                                   'segment_id': segment.get('segment_id'),
                                   'timeline_window': {'start': timeline_start + a - start, 'end': timeline_start + b - start},
                                   'review_status': 'unreviewed'})
    return output


def write_srt(items: List[Dict[str, Any]], path: Path) -> None:
    """Export only speech subtitles with millisecond timecodes."""
    def stamp(ms: int) -> str:
        hours, ms = divmod(ms, 3600000)
        minutes, ms = divmod(ms, 60000)
        seconds, ms = divmod(ms, 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}'
    blocks = [f"{index}\n{stamp(item['timeline_window']['start'])} --> {stamp(item['timeline_window']['end'])}\n{item['text']}\n"
              for index, item in enumerate(items, 1)]
    path.write_text('\n'.join(blocks), encoding='utf-8')
