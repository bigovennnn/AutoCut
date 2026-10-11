"""Subtitle contracts: real offsets, cut coverage, display layers and failures."""

from pathlib import Path

import pytest

from open_storyline.quickcut.pipeline import EditPlan, QuickcutOptions, make_timeline
from open_storyline.quickcut.speech import normalize_whisper, project_speech, write_srt


def test_invalid_asr_times_and_low_probability_are_retained_as_rejected() -> None:
    raw = {'transcription': [
        {'text': '真话', 'offsets': {'from': 100, 'to': 500}, 'tokens': [{'text': '真话', 'p': 0.8}]},
        {'text': '越界', 'offsets': {'from': 0, 'to': 9000}},
        {'text': '可疑', 'offsets': {'from': 600, 'to': 800}, 'tokens': [{'text': '可疑', 'p': 0.1}]},
    ]}
    accepted, rejected = normalize_whisper(raw, 1000)
    assert [s['text'] for s in accepted] == ['真话']
    assert {s['reason'] for s in rejected} == {'invalid_timestamp', 'low_token_probability'}
    with pytest.raises(ValueError):
        normalize_whisper({'template_text': '伪造结果'}, 1000)


def test_speech_reorders_with_clips_and_excludes_partial_units(tmp_path: Path) -> None:
    transcript = [{'source_path': '/a', 'segments': [
        {'text': '完整句', 'start_ms': 1500, 'end_ms': 2000, 'tokens': []},
        {'text': '不能整句复制', 'start_ms': 2500, 'end_ms': 4000, 'tokens': [
            {'text': '前半', 'offsets': {'from': 2500, 'to': 3000}},
            {'text': '后半', 'offsets': {'from': 3000, 'to': 4000}}]},
    ]}]
    timeline = {'tracks': {'video': [
        {'candidate_id': 'later', 'source_path': '/a', 'source_window': {'start': 2600, 'end': 4000}, 'timeline_window': {'start': 0, 'end': 1400}},
        {'candidate_id': 'earlier', 'source_path': '/a', 'source_window': {'start': 1000, 'end': 2200}, 'timeline_window': {'start': 1400, 'end': 2600}},
    ]}}
    items = project_speech(transcript, timeline)
    assert [i['text'] for i in items] == ['后半', '完整句']
    assert items[0]['timeline_window'] == {'start': 400, 'end': 1400}
    assert items[1]['timeline_window'] == {'start': 1900, 'end': 2400}
    write_srt(items, tmp_path / 'speech.srt')
    text = (tmp_path / 'speech.srt').read_text()
    assert '00:00:00,400 --> 00:00:01,400' in text and '不能整句复制' not in text


def test_party_plan_offsets_and_phrase_boundary() -> None:
    provider = {'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}
    options = QuickcutOptions(mode='local', llm=provider, vlm=provider, edit_style='party', target_seconds=5)
    candidates = [{'candidate_id': 'a', 'source_path': '/a', 'start_s': 0, 'end_s': 6}]
    plan = EditPlan(title='party', clips=[{'candidate_id': 'a', 'caption': '一起玩', 'offset_start_s': 1, 'duration_s': 2}])
    speech = [{'source_path': '/a', 'segments': [{'start_ms': 2600, 'end_ms': 3250, 'text': '一句话', 'tokens': []}]}]
    timeline = make_timeline(plan, candidates, options, speech)
    assert timeline['tracks']['video'][0]['source_window'] == {'start': 1000, 'end': 3250}
    assert {item['kind'] for item in timeline['tracks']['subtitles']} == {'title', 'speech'}
    with pytest.raises(ValueError):
        make_timeline(EditPlan(title='x', clips=[{'candidate_id': 'a', 'offset_start_s': 7}]), candidates, options)
