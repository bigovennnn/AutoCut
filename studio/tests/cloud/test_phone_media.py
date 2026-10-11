"""Phone-like rotated media and absent audio are concrete first-run risks."""

import asyncio
import json
import subprocess
from pathlib import Path

import numpy as np

from open_storyline.nodes.core_nodes.render_video import RenderVideoPipeline
from open_storyline.nodes.node_state import NodeState
from open_storyline.nodes.node_summary import NodeSummary
from open_storyline.quickcut.pipeline import QuickcutOptions, RenderProgress, RunLedger

ROOT = Path(__file__).resolve().parents[2]


def test_rotated_phone_video_without_audio(tmp_path: Path) -> None:
    original = tmp_path / 'landscape.mp4'
    rotated = tmp_path / 'phone.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'color=red:s=320x180:r=25:d=2,drawbox=x=160:y=0:w=160:h=180:color=blue:t=fill',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(original)], check=True, timeout=30)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-display_rotation:v:0', '90', '-i', str(original),
                    '-c', 'copy', str(rotated)], check=True, timeout=30)
    metadata = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(rotated)],
                                        check=True, capture_output=True, text=True, timeout=30).stdout)
    assert any(abs(item.get('rotation', 0)) == 90 for item in metadata['streams'][0].get('side_data_list', []))
    options = QuickcutOptions(mode='local', llm={'model': 'fixture', 'base_url': 'http://127.0.0.1:1'},
                             vlm={'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}, input_kind='engineering_fixture')
    ledger = RunLedger(tmp_path / 'ledger', 'phone-fixture', options)
    state = NodeState(session_id='phone', artifact_id='render', lang='zh', node_summary=NodeSummary(auto_console=False),
                      llm=None, mcp_ctx=RenderProgress(ledger))
    pipeline = RenderVideoPipeline(server_cache_dir=tmp_path, font_info_path=ROOT / 'resource/fonts/font_info.json')
    result = asyncio.run(pipeline.render(node_state=state, inputs={
        'load_media': {'videos': []}, 'plan_timeline': {'tracks': {'video': [{
            'source_path': str(rotated), 'source_window': {'start': 0, 'end': 2000},
            'timeline_window': {'start': 0, 'end': 2000}, 'fps': 25}]}},
        'output_max_dimension_px': 720, 'aspect_ratio': '9:16', 'include_video_audio': True,
        'clip_compose_mode': 'padding',
    }))
    assert result['validation']['height'] == 720
    assert abs(result['validation']['width'] - 720 * 9 / 16) <= 2
    assert result['validation']['width'] % 2 == 0
    assert not result['validation']['has_audio']
    values = []
    images = []
    for path in [str(rotated), result['output_path']]:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0.5', '-i', path, '-frames:v', '1',
                              '-vf', 'scale=18:32', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                             check=True, capture_output=True, timeout=30).stdout
        image = np.frombuffer(raw, dtype=np.uint8).reshape(32, 18, 3)
        images.append(image)
        values.append([image[5, 9].argmax(), image[26, 9].argmax()])
    assert values[0] == values[1] and values[0][0] != values[0][1]
    # Check coverage and geometry, not only two color samples in the canvas.
    assert np.abs(images[0].astype(float) - images[1].astype(float)).mean() < 20
