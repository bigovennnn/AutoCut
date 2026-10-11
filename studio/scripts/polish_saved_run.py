"""Render a reviewed editorial plan with genuine local ASR results."""

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

from open_storyline.quickcut.pipeline import (
    EditPlan, Provider, QuickcutOptions, RunLedger, inspect_source, make_timeline,
    now, render_recorded_timeline,
)
from open_storyline.quickcut.speech import write_srt

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    """Retain model provenance, review annotations and a fresh render record."""
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--edit-plan', type=Path, required=True)
    args = parser.parse_args()
    original = json.loads((ROOT / 'runtime-local/runs' / str(uuid.UUID(args.run_id)) / 'run.json').read_text())
    analysis = json.loads(args.analysis.read_text())
    editorial = json.loads(args.edit_plan.read_text())
    if analysis['status'] != 'analysis_complete':
        raise ValueError('语音分析尚未完成')
    if [s['sha256'] for s in original['sources']] != [s['sha256'] for s in analysis['sources']]:
        raise ValueError('语音分析与视频素材不匹配')
    public_options = {**original['options'], 'request': editorial['context'], 'target_seconds': editorial['target_seconds'],
                      'edit_style': 'party', 'speech_subtitles': True, 'asr_model': analysis['providers']['asr']['model']}
    # Rendering reuses already validated media and public provider configuration.
    options = QuickcutOptions.model_construct(**public_options,
        llm=Provider.model_validate(original['providers']['llm']), vlm=Provider.model_validate(original['providers']['vlm']))
    run_id = str(uuid.uuid4())
    ledger = RunLedger(ROOT / 'runtime-local/runs' / run_id, run_id, options)
    ledger.data.update({'workflow': 'editorial_polish_v1', 'provider_results_reused_from': original['run_id'],
                        'reused_provider_calls': original['calls'], 'asr_analysis_origin': str(args.analysis.resolve()),
                        'asr_calls': [], 'reused_asr_calls': analysis['asr_calls'], 'transcripts': analysis['transcripts'],
                        'editorial_plan': editorial, 'editorial_origin': 'assistant_source_frame_review_and_user_brief',
                        'warnings': analysis['warnings'][:], 'cost': {'currency': 'CNY', 'actual_amount': None,
                            'reason': '本次复用真实分析并在本机重新渲染；原云端费用仍未知'}})
    ledger.data['providers']['asr'] = analysis['providers']['asr']
    ledger.data['capabilities']['speech_transcription'] = True
    for exclusion in editorial.get('excluded_asr_segments', []):
        transcript = ledger.data['transcripts'][exclusion['source_index'] - 1]
        keep = []
        for segment in transcript['segments']:
            if segment['segment_id'] == exclusion['segment_id']:
                transcript['rejected_segments'].append({**segment, 'reason': exclusion['reason'],
                                                        'review_status': 'excluded_by_editorial_review'})
            else:
                keep.append(segment)
        transcript['segments'] = keep
    try:
        ledger.stage('inspecting')
        sources = [inspect_source(Path(item['path'])) for item in original['sources']]
        if any(a['sha256'] != b['sha256'] for a, b in zip(sources, original['sources'])):
            raise ValueError('源素材已经变化')
        ledger.data['sources'] = sources
        candidates, clips = [], []
        for index, edit in enumerate(editorial['clips'], 1):
            source = sources[edit['source_index'] - 1]
            a, b = edit['start_s'], edit['end_s']
            if not 0 <= a < b <= source['duration_s']:
                raise ValueError('人工复核区间超出源视频范围')
            for previous in candidates:
                if previous['source_path'] == source['path'] and max(a, previous['start_s']) < min(b, previous['end_s']):
                    raise ValueError('人工复核计划包含重复源区间')
            candidate_id = f'review_{index:03d}'
            candidates.append({'candidate_id': candidate_id, 'source_path': source['path'], 'start_s': a, 'end_s': b,
                               'selection_reason': edit['reason'], 'selection_origin': 'editorial_review'})
            clips.append({'candidate_id': candidate_id, 'caption': edit['caption'], 'duration_s': b - a})
        plan = EditPlan(title=editorial['title'], clips=clips)
        ledger.data['candidates'], ledger.data['plan'] = candidates, plan.model_dump()
        # Explicitly reviewed ranges stay fixed. Mapping excludes cut-off ASR units.
        timeline = make_timeline(plan, candidates, options)
        from open_storyline.quickcut.speech import project_speech
        speech = project_speech(analysis['transcripts'], timeline)
        timeline['tracks']['subtitles'].extend(speech)
        ledger.data['speech_subtitle_count'] = len(speech)
        ledger.data['timeline'] = timeline
        write_srt(speech, ledger.directory / 'subtitles.srt')
        ledger.stage('rendering')
        ledger.data['output'] = await render_recorded_timeline(options, ledger, ROOT / 'resource/fonts/font_info.json')
        ledger.data['status'] = 'success' if speech else 'degraded'
        if not speech:
            ledger.data['warnings'].append('这组素材没有得到可用语音字幕；没有编造对白。')
        ledger.stage('complete')
    except Exception as exc:
        ledger.data['status'] = 'failed'
        ledger.data['errors'].append({'stage': ledger.data['stage'], 'type': type(exc).__name__, 'message': str(exc)})
        ledger.stage('failed')
        raise
    finally:
        ledger.data['finished_at'] = now()
        ledger.data['elapsed_s'] = round(time.monotonic() - ledger.started_monotonic, 3)
        ledger.save()
        print(json.dumps({'run_id': run_id, 'status': ledger.data['status'], 'output': ledger.data.get('output'),
                          'speech_subtitle_count': ledger.data.get('speech_subtitle_count')}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
