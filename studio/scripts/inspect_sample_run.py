"""Produce contact sheets of actual exported clips, with recorded source ranges."""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def inspect(run_id: str) -> Dict:
    """Inspect every cut at three output times; retain frames beside its record."""
    directory = ROOT / 'runtime-local/runs' / run_id
    record = json.loads((directory / 'run.json').read_text())
    output = Path(record['output']['output_path'])
    clips = record['timeline']['tracks']['video']
    dest = directory / 'inspection'
    dest.mkdir(exist_ok=True)
    sheet = Image.new('RGB', (760, len(clips) * 202 + 40), '#f3f4ef')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
    draw.text((12, 10), f"{run_id} | {record['status']} | {record['output']['validation']['duration_s']:.2f}s", font=font, fill='#163532')
    frames = []
    for i, clip in enumerate(clips):
        a, b = clip['timeline_window']['start'] / 1000, clip['timeline_window']['end'] / 1000
        src = clip['source_window']
        draw.text((12, 40 + i * 202), f"{clip['candidate_id']} | {Path(clip['source_path']).name} {src['start']/1000:.2f}-{src['end']/1000:.2f}s | output {a:.2f}-{b:.2f}s", font=font, fill='#163532')
        for j, t in enumerate([a + min(.3, (b-a)/5), (a+b)/2, b-min(.15, (b-a)/5)]):
            frame = dest / f'{i:02d}_{j}.jpg'
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(t), '-i', str(output),
                            '-frames:v', '1', '-vf', 'scale=240:160:force_original_aspect_ratio=decrease',
                            str(frame)], check=True, capture_output=True, timeout=30)
            with Image.open(frame) as image:
                sheet.paste(image, (12+j*250+(240-image.width)//2, 64+i*202))
            frames.append({'output_time_s': t, 'path': str(frame)})
    sheet_path = dest / 'contact_sheet.jpg'
    sheet.save(sheet_path, quality=90)
    report = {'run_id': run_id, 'contact_sheet': str(sheet_path), 'frames': frames,
              'inspection_scope': '实际导出帧与切点；不代替实时观看、听音或盲评'}
    (dest / 'inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    print(json.dumps(inspect(args.run_id), ensure_ascii=False))
