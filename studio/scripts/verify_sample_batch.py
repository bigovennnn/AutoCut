"""Summarize real attempts, including failures, without overwriting raw records."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict

from open_storyline.quickcut.pipeline import timeline_quality

ROOT = Path(__file__).resolve().parents[1]


def verify(manifest_path: Path) -> Dict:
    """Write a measured ledger summary, keeping retrospective checks separate."""
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for item in manifest['attempts']:
        d = json.loads((ROOT / 'runtime-local/runs' / item['run_id'] / 'run.json').read_text())
        rows.append({**item, 'status': d['status'], 'stage': d['stage'], 'elapsed_s': d.get('elapsed_s'),
                     'calls': len(d['calls']), 'tokens': sum(c['usage']['total_tokens'] for c in d['calls'] if c.get('usage')),
                     'output_validation': d.get('output', {}).get('validation'), 'recorded_quality_checks': d.get('quality_checks'),
                     'retrospective_structure_checks': timeline_quality(d['timeline'], d.get('transcripts')) if 'timeline' in d else None,
                     'errors': d['errors'], 'code_sha256': d['code_sha256'],
                     'review_status': d.get('automatic_review', {}).get('status')})
    report = {'date': manifest['date'], 'scope': '产品开发素材，非冻结研究测试集；未手填自动切点，所有尝试均保留',
              'attempts': rows, 'attempt_count': len(rows),
              'status_counts': {s: sum(r['status'] == s for r in rows) for s in ['success', 'degraded', 'failed']},
              'actual_total_tokens': sum(r['tokens'] for r in rows), 'billing_cny': None,
              'tests': manifest['tests'], 'measurement_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    baseline = manifest_path.parent / 'baseline-code/pipeline.py'
    report['baseline_code_record_matches_copy'] = hashlib.sha256(baseline.read_bytes()).hexdigest() == rows[0]['code_sha256']['src/open_storyline/quickcut/pipeline.py']
    (manifest_path.parent / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return {k: report[k] for k in ['attempt_count', 'status_counts', 'actual_total_tokens', 'baseline_code_record_matches_copy']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), ensure_ascii=False))
