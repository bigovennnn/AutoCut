"""Automatic review contracts and retained baselines, using explicit fixtures."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from open_storyline.quickcut import pipeline


def test_candidate_clocks_include_spanning_speech() -> None:
    candidates = [{'candidate_id': 'a', 'source_path': '/a', 'start_s': 6, 'end_s': 12}]
    speech = [{'source_path': '/a', 'segments': [{'text': '跨窗真句', 'start_ms': 5500, 'end_ms': 8000}]}]
    item = pipeline.planning_candidates(candidates, [{'candidate_id': 'a', 'description': 'fixture'}], speech)[0]
    assert item['source_start_s'] == 6 and item['source_id'] == 'source_01'
    assert item['speech'][0]['offset_start_s'] == -0.5
    assert item['speech'][0]['offset_end_s'] == 2 and not item['speech'][0]['fully_contained']


def test_candidates_keep_longer_phrases_and_cover_source_without_overlap() -> None:
    phrases = [{'start_ms': 0, 'end_ms': 8000}, {'start_ms': 8000, 'end_ms': 11000},
               {'start_ms': 11000, 'end_ms': 16000}]
    boundaries = pipeline.candidate_boundaries(16.62, 3, phrases)
    assert boundaries == [0, 8, 11, 16.62]
    assert all(b > a for a, b in zip(boundaries, boundaries[1:]))
    birthday = pipeline.candidate_boundaries(28.727, 5, [{'start_ms': 0, 'end_ms': 8000}])
    assert birthday[1] == 8 and birthday[0] == 0 and birthday[-1] == pytest.approx(28.727, abs=1e-9)


def test_finite_times_and_skip_short_tail() -> None:
    provider = {'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}
    options = pipeline.QuickcutOptions(mode='local', llm=provider, vlm=provider, target_seconds=5, captions=False)
    with pytest.raises(ValueError):
        pipeline.SelectedClip(candidate_id='a', offset_start_s=float('inf'))
    candidates = [{'candidate_id': 'a', 'source_path': '/a', 'start_s': 0, 'end_s': 6},
                  {'candidate_id': 'b', 'source_path': '/b', 'start_s': 0, 'end_s': 6}]
    plan = pipeline.EditPlan(title='fixture', clips=[{'candidate_id': 'a', 'duration_s': 4.6},
                                                    {'candidate_id': 'b', 'duration_s': 3}])
    video = pipeline.make_timeline(plan, candidates, options)['tracks']['video']
    assert len(video) == 1 and video[0]['timeline_window']['end'] == 4600


def test_visual_title_filter_does_not_rewrite_speech() -> None:
    speech = {'kind': 'speech', 'text': '圆图啊', 'timeline_window': {'start': 0, 'end': 2000}}
    titles = [{'kind': 'title', 'text': text, 'timeline_window': {'start': i * 5000, 'end': i * 5000 + 2000}}
              for i, text in enumerate(['一起拉面', '圆图啊', '笑声不断', '继续试试', '聚会日常'])]
    timeline = {'tracks': {'subtitles': [*titles, speech]}}
    decisions = pipeline.filter_visual_titles(timeline, [{'segments': [{'text': '圆图啊'}]}], '朋友聚餐拉面')
    assert speech in timeline['tracks']['subtitles'] and speech['text'] == '圆图啊'
    assert len([s for s in timeline['tracks']['subtitles'] if s['kind'] == 'title']) == 3
    assert any(d['text'] == '圆图啊' and d['reason'] == 'verbatim_unreviewed_asr' for d in decisions)


def test_keep_mostly_complete_phrase_within_candidate() -> None:
    provider = {'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}
    options = pipeline.QuickcutOptions(mode='local', llm=provider, vlm=provider, target_seconds=5, captions=False)
    candidates = [{'candidate_id': 'a', 'source_path': '/a', 'start_s': 0, 'end_s': 4.32}]
    speech = [{'source_path': '/a', 'segments': [{'text': '完整真句', 'start_ms': 0, 'end_ms': 4320, 'tokens': []}]}]
    plan = pipeline.EditPlan(title='fixture', clips=[{'candidate_id': 'a', 'duration_s': 3}])
    timeline = pipeline.make_timeline(plan, candidates, options, speech)
    assert timeline['tracks']['video'][0]['source_window'] == {'start': 0, 'end': 4320}
    assert not pipeline.timeline_quality(timeline, speech)['recognized_phrase_boundary_cuts']


def test_opening_only_uses_real_plan_title_and_rejects_empty_provider_titles() -> None:
    provider = {'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}
    options = pipeline.QuickcutOptions(mode='local', llm=provider, vlm=provider, target_seconds=5)
    candidates = [{'candidate_id': 'a', 'source_path': '/a', 'start_s': 0, 'end_s': 4}]
    plan = pipeline.EditPlan(title='雨天校园', clips=[{'candidate_id': 'a', 'caption': '', 'duration_s': 4}])
    titles = pipeline.make_timeline(plan, candidates, options)['tracks']['subtitles']
    assert titles[0]['text'] == plan.title and titles[0]['source_field'] == 'plan.title'
    plan.title = ''
    with pytest.raises(ValueError, match='标题'):
        pipeline.make_timeline(plan, candidates, options)


@pytest.mark.parametrize('review_kind', ['valid', 'out_of_range', 'provider_failed', 'backtrack'])
def test_automatic_review_preserves_initial_and_rejects_bad_proposals(tmp_path: Path, monkeypatch: Any,
                                                                    review_kind: str) -> None:
    provider = {'model': 'fixture', 'base_url': 'http://127.0.0.1:1'}
    options = pipeline.QuickcutOptions(mode='local', llm=provider, vlm=provider, target_seconds=5,
                                       captions=False, input_kind='engineering_fixture')
    source = {'path': '/fixture', 'duration_s': 12, 'has_audio': False}
    candidates = [{'candidate_id': 'a', 'source_path': '/fixture', 'start_s': 0, 'end_s': 6},
                  {'candidate_id': 'b', 'source_path': '/fixture', 'start_s': 6, 'end_s': 12}]
    initial = {'title': 'fixture', 'clips': [{'candidate_id': 'a', 'duration_s': 4}]}
    monkeypatch.setattr(pipeline, 'inspect_source', lambda path: source)
    monkeypatch.setattr(pipeline, 'sample_candidates', lambda *args: candidates)
    monkeypatch.setattr(pipeline, 'describe_candidates', lambda *args: [
        {'candidate_id': c['candidate_id'], 'description': 'injected fixture'} for c in candidates])
    monkeypatch.setattr(pipeline, 'provider_call', lambda *args: initial)

    def review(*args: Any) -> Any:
        if review_kind == 'provider_failed':
            raise RuntimeError('injected timeout')
        clips = ([{'candidate_id': 'b', 'duration_s': 2}, {'candidate_id': 'a', 'duration_s': 2}]
                 if review_kind == 'backtrack' else [{'candidate_id': 'a', 'offset_start_s': 1,
                                                    'duration_s': 8 if review_kind == 'out_of_range' else 3}])
        return {'observations': ['injected observation'], 'plan': {'title': 'fixture', 'clips': clips}}

    async def render(*args: Any) -> Any:
        return {'validation': {'decoded': True}}

    monkeypatch.setattr(pipeline, 'review_edit', review)
    monkeypatch.setattr(pipeline, 'render_recorded_timeline', render)
    ledger = pipeline.RunLedger(tmp_path / review_kind, review_kind, options)
    asyncio.run(pipeline.run_quickcut([Path('/fixture')], options, ledger, Path('/font')))
    record = ledger.data
    assert record['initial_plan']['clips'][0]['duration_s'] == 4
    assert record['initial_timeline']['tracks']['video'][0]['source_window'] == {'start': 0, 'end': 4000}
    if review_kind == 'valid':
        assert record['status'] == 'success' and record['automatic_review']['status'] == 'accepted'
        assert record['timeline']['tracks']['video'][0]['source_window'] == {'start': 1000, 'end': 4000}
    else:
        assert record['status'] == 'degraded' and record['automatic_review']['status'] == 'rejected_or_failed'
        assert record['timeline'] == record['initial_timeline'] and record['warnings']
