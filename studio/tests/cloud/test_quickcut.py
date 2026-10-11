"""Engineering fixtures only: provider contracts, media correctness, failures."""

import asyncio
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
from fastapi.testclient import TestClient
from moviepy import AudioClip

from open_storyline.nodes.core_nodes.render_video import AudioTrackComposer, RenderVideoPipeline, validate_rendered_media
from open_storyline.nodes.node_state import NodeState
from open_storyline.nodes.node_summary import NodeSummary
from open_storyline.quickcut.pipeline import (
    EditPlan, QuickcutOptions, RenderProgress, RunLedger, inspect_source,
    make_timeline, parse_json_content, run_quickcut, sample_candidates,
)
from open_storyline.utils.recall import StorylineRecall

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def options() -> QuickcutOptions:
    return QuickcutOptions(mode='local', llm={'model': 'test', 'base_url': 'http://127.0.0.1:1/v1'},
                           vlm={'model': 'test', 'base_url': 'http://127.0.0.1:1/v1'},
                           target_seconds=5, input_kind='engineering_fixture')


@pytest.fixture
def media(tmp_path: Path) -> list[Path]:
    result = []
    for color, tone in [('blue', 440), ('red', 880)]:
        path = tmp_path / f'{color}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={color}:s=320x180:r=25:d=4',
                        '-f', 'lavfi', '-i', f'sine=frequency={tone}:sample_rate=44100:duration=4',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(path)],
                       capture_output=True, check=True, timeout=30)
        result.append(path)
    return result


def test_cloud_requires_keys_and_local_requires_loopback() -> None:
    with pytest.raises(ValueError):
        QuickcutOptions(llm={'model': 'x', 'base_url': 'https://api.deepseek.com'},
                        vlm={'model': 'x', 'base_url': 'https://dashscope.aliyuncs.com'})
    with pytest.raises(ValueError):
        QuickcutOptions(mode='local', llm={'model': 'x', 'base_url': 'http://example.com'},
                        vlm={'model': 'x', 'base_url': 'http://127.0.0.1'})


def test_one_deepseek_key_resolves_both_roles_without_cross_provider_leak(monkeypatch: Any) -> None:
    from cloud_app import fill_cloud_credentials
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'injected-deepseek-key')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'injected-dashscope-key')
    config = {'llm': {'model': 'deepseek-flash', 'base_url': 'https://api.deepseek.com'},
              'vlm': {'model': 'deepseek-flash', 'base_url': 'https://api.deepseek.com'}}
    fill_cloud_credentials(config)
    assert QuickcutOptions.model_validate(config).vlm.api_key.get_secret_value() == 'injected-deepseek-key'
    mixed = {'llm': {'base_url': 'https://api.deepseek.com'},
             'vlm': {'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'}}
    fill_cloud_credentials(mixed)
    assert mixed['vlm']['api_key'] == 'injected-dashscope-key'
    unknown = {'llm': {'base_url': 'https://other.example'}, 'vlm': {'base_url': 'https://other.example'}}
    fill_cloud_credentials(unknown)
    assert 'api_key' not in unknown['llm'] and 'api_key' not in unknown['vlm']


def test_parse_rejects_invalid_and_supports_fenced_json() -> None:
    assert parse_json_content('```json\n{"clips": []}\n```') == {'clips': []}
    with pytest.raises(ValueError):
        parse_json_content('[]')
    with pytest.raises(ValueError):
        parse_json_content('Almost JSON {clips: []}')


def test_timeline_no_duplicate_ids_no_overlap_and_budget(options: QuickcutOptions) -> None:
    options.captions = False
    candidates = [{'candidate_id': 'a', 'source_path': '/a.mp4', 'start_s': 2, 'end_s': 6},
                  {'candidate_id': 'b', 'source_path': '/b.mp4', 'start_s': 1, 'end_s': 5}]
    plan = EditPlan(title='test', clips=[{'candidate_id': 'a'}, {'candidate_id': 'b'}])
    items = make_timeline(plan, candidates, options)['tracks']['video']
    assert [item['timeline_window'] for item in items] == [{'start': 0, 'end': 4000}, {'start': 4000, 'end': 5000}]
    assert items[1]['source_window'] == {'start': 1000, 'end': 2000}
    for ids in [['a', 'a'], ['unknown']]:
        with pytest.raises(ValueError):
            make_timeline(EditPlan(title='x', clips=[{'candidate_id': i} for i in ids]), candidates, options)


def test_lexical_recall_without_neural_packages() -> None:
    data = [{'description': '校园社团活动'}, {'description': '海边日落'}]
    index = StorylineRecall.build_vectorstore(data, backend='lexical')
    assert StorylineRecall.query_top_n(index, '海边', 1) == [data[1]]
    assert StorylineRecall.query_top_n(None, 'test') == []
    assert 'torch' not in sys.modules


def test_zero_volume_really_mutes() -> None:
    clip = AudioClip(lambda t: np.sin(440 * 2 * np.pi * t), duration=1, fps=44100)
    mixed = AudioTrackComposer(cache=None).compose(voiceover_items=[], bgm_items=[], video_audio_clip=clip,
                                                   final_duration_s=1, video_volume_scale=0)
    assert np.max(np.abs(mixed.get_frame(np.array([0.1, 0.2, 0.3])))) == 0
    mixed.close()
    clip.close()


def test_sampling_actual_frames_bounded(media: list[Path], tmp_path: Path) -> None:
    sources = [inspect_source(path) for path in media]
    candidates = sample_candidates(sources, tmp_path / 'frames')
    assert len(candidates) == 2
    assert all(Path(frame['path']).stat().st_size > 0 for item in candidates for frame in item['frames'])
    assert sources[0]['duration_s'] == pytest.approx(4, abs=0.1)
    assert sources[0]['has_audio'] and len(sources[0]['sha256']) == 64


def test_render_real_mp4_source_order_caption_audio(media: list[Path], tmp_path: Path, options: QuickcutOptions) -> None:
    ledger = RunLedger(tmp_path / 'ledger', 'fixture', options)
    state = NodeState(session_id='fixture', artifact_id='render', lang='zh', node_summary=NodeSummary(auto_console=False),
                      llm=None, mcp_ctx=RenderProgress(ledger))
    inputs: Dict[str, Any] = {'load_media': {'videos': []}, 'plan_timeline': {'tracks': {
        'video': [{'source_path': str(path), 'source_window': {'start': 500, 'end': 2500},
                   'timeline_window': {'start': i * 2000, 'end': (i + 1) * 2000}, 'fps': 25}
                  for i, path in enumerate(media)],
        'subtitles': [{'text': '工程测试：中文标题', 'timeline_window': {'start': 0, 'end': 2000}}],
    }}, 'text_rec': [{'font_name': 'SiYuanHeiTi'}], 'transition_rec': [], 'output_max_dimension_px': 720,
        'aspect_ratio': '16:9', 'include_video_audio': True, 'clip_compose_mode': 'padding',
        'font_color': (255, 237, 130, 255), 'stroke_color': (0, 0, 0, 255), 'margin_bottom': 140}
    pipeline = RenderVideoPipeline(server_cache_dir=tmp_path, font_info_path=ROOT / 'resource/fonts/font_info.json')
    result = asyncio.run(pipeline.render(node_state=state, inputs=inputs))
    assert result['validation']['decoded'] and result['validation']['has_audio']
    assert result['duration_s'] == pytest.approx(4, abs=0.1)
    assert result['validation']['width'] == 720
    for time_s, channel in [(1, 2), (3, 0)]:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(time_s), '-i', result['output_path'], '-frames:v', '1',
                              '-vf', 'scale=72:40', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                             capture_output=True, check=True, timeout=30).stdout
        mean = np.frombuffer(raw, dtype=np.uint8).reshape(40, 72, 3)[5:15].mean(axis=(0, 1))
        assert mean[channel] > 200
    audio = subprocess.run(['ffmpeg', '-v', 'error', '-i', result['output_path'], '-f', 'f32le', '-ac', '1', '-ar', '8000', '-'],
                           capture_output=True, check=True, timeout=30).stdout
    signal = np.frombuffer(audio, dtype=np.float32)
    for second, expected_tone in [(0, 440), (2, 880)]:
        segment = signal[int((second + 0.1) * 8000):int((second + 1.1) * 8000)]
        dominant = np.fft.rfftfreq(len(segment), d=1/8000)[np.abs(np.fft.rfft(segment)).argmax()]
        assert abs(dominant - expected_tone) < 10
    # Verify Chinese caption raster has colored glyphs, rather than silent omission.
    from PIL import Image
    from open_storyline.nodes.core_nodes.render_video import PillowSubtitleRenderer
    font = json.loads((ROOT / 'resource/fonts/font_info.json').read_text())[0]['font_path']
    layers = PillowSubtitleRenderer(font).render(inputs['plan_timeline']['tracks']['subtitles'], video_size=(720, 406),
                                                font_color=(255, 237, 130, 255))
    assert layers and np.count_nonzero(layers[0].mask.get_frame(0)) > 100
    for layer in layers:
        layer.close()


def test_render_rejects_corrupt_output(tmp_path: Path) -> None:
    path = tmp_path / 'broken.mp4'
    path.write_bytes(b'not a video')
    with pytest.raises(subprocess.CalledProcessError):
        validate_rendered_media(path, 4)


def test_missing_provider_stops_without_success(media: list[Path], tmp_path: Path, options: QuickcutOptions, monkeypatch: Any) -> None:
    from open_storyline.quickcut import pipeline
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError('injected provider failure')
    monkeypatch.setattr(pipeline, 'provider_call', fail)
    ledger = RunLedger(tmp_path / 'failed', 'fixture', options)
    asyncio.run(run_quickcut(media, options, ledger, ROOT / 'resource/fonts/font_info.json'))
    record = json.loads((ledger.directory / 'run.json').read_text())
    assert record['status'] == 'failed' and record['errors'][0]['stage'] == 'understanding'
    assert 'output' not in record and 'api_key' not in json.dumps(record)


def test_api_no_key_rejects_without_echoing_secrets_and_bad_origin() -> None:
    from cloud_app import app
    client = TestClient(app)
    assert client.get('/api/health').json()['ffmpeg']
    invalid = {'llm': {'model': 'x', 'base_url': 'http://bad', 'api_key': 'secret-fixture'},
               'vlm': {'model': 'x', 'base_url': 'https://api.example.com', 'api_key': ''}}
    response = client.post('/api/runs', data={'config': json.dumps(invalid)})
    assert response.status_code == 422 and 'secret-fixture' not in response.text
    assert client.post('/api/runs', headers={'origin': 'https://elsewhere.example'}, data={'config': '{}'}).status_code == 403
    assert client.get('/api/runs/../../etc/passwd').status_code == 404


def test_required_local_asr_failure_stops_before_cloud_or_render(media: list[Path], options: QuickcutOptions, tmp_path: Path, monkeypatch: Any) -> None:
    """An explicitly requested ASR stage cannot silently become title-only success."""
    import open_storyline.quickcut.pipeline as pipeline
    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError('injected missing ASR model')
    monkeypatch.setattr(pipeline, 'transcribe_local', unavailable)
    options.speech_subtitles = True
    ledger = RunLedger(tmp_path / 'asr-failed', 'asr-failed-fixture', options)
    asyncio.run(run_quickcut(media, options, ledger, ROOT / 'resource/fonts/font_info.json'))
    assert ledger.data['status'] == 'failed'
    assert ledger.data['calls'] == [] and not ledger.data.get('output')
    assert ledger.data['errors'][0]['stage'] == 'transcribing'


def test_http_upload_to_mp4_with_explicit_provider_fixtures(media: list[Path], tmp_path: Path, monkeypatch: Any) -> None:
    """Real HTTP/SDK/media path; model responses are explicitly injected fixtures."""
    import cloud_app
    monkeypatch.setattr(cloud_app, 'RUN_ROOT', tmp_path / 'runs')
    # A stopped proxy inherited from the desktop must not block provider calls.
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('HTTPS_PROXY', 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', '')
    monkeypatch.delenv('AUTOCUT_TRUST_ENV_PROXY', raising=False)
    class FixtureHandler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def do_POST(self) -> None:
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if len(request['messages']) == 1:
                text = {'clips': [{'candidate_id': 'clip_001', 'description': 'injected blue fixture'},
                                  {'candidate_id': 'clip_002', 'description': 'injected red fixture'}]}
                assert any(item['type'] == 'image_url' for item in request['messages'][0]['content'])
            else:
                text = {'title': 'engineering fixture', 'clips': [
                    {'candidate_id': 'clip_001', 'caption': '蓝色工程测试'},
                    {'candidate_id': 'clip_002', 'caption': '红色工程测试'}]}
            response = {'id': 'injected-fixture', 'object': 'chat.completion', 'created': 0, 'model': 'injected-fixture',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(text)}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}
            body = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = {'model': 'injected-fixture', 'base_url': f'http://127.0.0.1:{server.server_port}/v1'}
        config = {'mode': 'local', 'llm': provider, 'vlm': provider, 'target_seconds': 5, 'input_kind': 'engineering_fixture', 'auto_polish': False}
        with TestClient(cloud_app.app) as client:
            response = client.post('/api/runs', data={'config': json.dumps(config)},
                                   files=[('files', (path.name, path.read_bytes(), 'video/mp4')) for path in media])
            assert response.status_code == 200
            run_id = response.json()['run_id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                record = client.get(f'/api/runs/{run_id}').json()
                if record['status'] != 'running':
                    break
                time.sleep(0.1)
            assert record['status'] == 'success', record.get('errors')
            assert record['input_kind'] == 'engineering_fixture'
            assert len(record['calls']) == 2
            assert all(call['transport'] == 'direct' for call in record['calls'])
            assert record['output']['validation']['decoded']
            assert 'api_key' not in json.dumps(record)
            assert client.get(f'/api/runs/{run_id}/video').headers['content-type'] == 'video/mp4'
            assert client.get(f'/api/runs/{run_id}/record').json()['run_id'] == run_id
            # Explicit speech fixture exercises editing without another provider
            # call, while the immutable parent and original offsets survive.
            parent_path = cloud_app.RUN_ROOT / run_id / 'run.json'
            record['timeline']['tracks']['subtitles'].append({
                'kind': 'speech', 'text': '测试原句', 'review_status': 'unreviewed',
                'timeline_window': {'start': 100, 'end': 900}})
            parent_path.write_text(json.dumps(record), encoding='utf-8')
            parent_bytes = parent_path.read_bytes()
            index = len(record['timeline']['tracks']['subtitles']) - 1
            assert client.post(f'/api/runs/{run_id}/subtitle-edits', json={'edits': [
                {'subtitle_index': 0, 'text': '不能改标题'}]}).status_code == 422
            response = client.post(f'/api/runs/{run_id}/subtitle-edits', json={'edits': [
                {'subtitle_index': index, 'text': '测试改字！'}]})
            assert response.status_code == 200
            revision_id = response.json()['run_id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                revision = client.get(f'/api/runs/{revision_id}').json()
                if revision['status'] != 'running':
                    break
                time.sleep(0.1)
            assert revision['status'] == 'success', revision.get('errors')
            assert parent_path.read_bytes() == parent_bytes
            assert revision['calls'] == [] and revision['parent_run_id'] == run_id
            assert revision['output']['validation']['has_audio']
            assert revision['output']['validation']['duration_s'] == record['output']['validation']['duration_s']
            srt = client.get(f'/api/runs/{revision_id}/subtitles').text
            assert '00:00:00,100 --> 00:00:00,900' in srt and '测试改字！' in srt
            assert revision['subtitle_edits'][0]['original_text'] == '测试原句'
            revision_path = cloud_app.RUN_ROOT / revision_id / 'run.json'
            before_style = revision_path.read_bytes()
            response = client.post(f'/api/runs/{revision_id}/title-style', json={'title_style': 'comic_pop'})
            assert response.status_code == 200
            styled_id = response.json()['run_id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                styled = client.get(f'/api/runs/{styled_id}').json()
                if styled['status'] != 'running':
                    break
                time.sleep(0.1)
            assert styled['status'] == 'success', styled.get('errors')
            assert revision_path.read_bytes() == before_style
            assert styled['calls'] == [] and styled['timeline']['tracks']['video'] == revision['timeline']['tracks']['video']
            assert styled['output']['validation']['decoded'] and styled['output']['validation']['has_audio']
            assert client.get(f'/api/runs/{styled_id}/subtitles').text == srt
            assert styled['title_rendering']['styles'][0]['font_sha256']
    finally:
        server.shutdown()
        server.server_close()
