"""Repair a render using a saved real plan; retain the original run as evidence."""

import asyncio
import copy
import json
import sys
import time
import uuid
from pathlib import Path

from open_storyline.quickcut.pipeline import (
    EditPlan, Provider, QuickcutOptions, RunLedger, inspect_source, make_timeline,
    now, render_recorded_timeline,
)
from open_storyline.quickcut.speech import write_srt

ROOT = Path(__file__).resolve().parents[1]


async def main(run_id: str) -> None:
    """Create a new render record with explicit provider-result reuse and hashes."""
    source_dir = ROOT / 'runtime-local/runs' / str(uuid.UUID(run_id))
    original = json.loads((source_dir / 'run.json').read_text(encoding='utf-8'))
    plan = EditPlan.model_validate(original['plan'])
    # These options were validated when the original run was accepted. A render
    # needs no credentials; model_construct retains public configuration only.
    options = QuickcutOptions.model_construct(**original['options'],
        llm=Provider.model_validate(original['providers']['llm']),
        vlm=Provider.model_validate(original['providers']['vlm']))
    new_id = str(uuid.uuid4())
    ledger = RunLedger(source_dir.parent / new_id, new_id, options)
    ledger.data.update({'workflow': 'visual_quickcut_rerender_v1',
                        'provider_results_reused_from': original['run_id'],
                        'reused_provider_calls': original['calls'],
                        'descriptions': original.get('descriptions', []), 'candidates': original.get('candidates', []),
                        'plan': plan.model_dump(),
                        'cost': {'currency': 'CNY', 'actual_amount': None,
                                 'reason': '本次未调用模型；原调用用量见引用运行记录'}})
    try:
        ledger.stage('inspecting')
        sources = [inspect_source(Path(item['path'])) for item in original['sources']]
        if any(a['sha256'] != b['sha256'] for a, b in zip(sources, original['sources'])):
            raise ValueError('原素材已变化，不能复用剪辑计划')
        ledger.data['sources'] = sources
        if original.get('transcripts'):
            ledger.data['transcripts'] = original['transcripts']
            ledger.data['providers'] = original['providers']
            ledger.data['capabilities'] = original['capabilities']
            ledger.data['timeline'] = copy.deepcopy(original['timeline'])
            speech = [item for item in ledger.data['timeline']['tracks']['subtitles'] if item.get('kind') == 'speech']
            ledger.data['speech_subtitle_count'] = len(speech)
            ledger.data['warnings'] = original.get('warnings', [])
            write_srt(speech, ledger.directory / 'subtitles.srt')
        else:
            ledger.data['timeline'] = make_timeline(plan, original['candidates'], options)
        ledger.stage('rendering')
        ledger.data['output'] = await render_recorded_timeline(options, ledger, ROOT / 'resource/fonts/font_info.json')
        ledger.data['status'] = 'success'
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
        print(json.dumps({'run_id': new_id, 'status': ledger.data['status'], 'output': ledger.data.get('output')}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
