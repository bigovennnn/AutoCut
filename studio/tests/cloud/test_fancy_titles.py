"""Meaningful lettering gates: glyph coverage, safe area, alpha and timing."""

import numpy as np
import pytest

from open_storyline.utils.fancy_titles import STYLES, build_title_rgba, make_title_clip


@pytest.mark.parametrize('style', list(STYLES))
def test_pop_alpha_stays_in_safe_area_and_exits(style: str) -> None:
    clip = make_title_clip('海底捞拉面局', style, 2, 2, (404, 720))
    assert clip.start == 2 and clip.end == 4
    assert clip.w <= 404 * 0.9
    for t in [0, 0.09, 0.24, 1.8, 2]:
        mask = clip.mask.get_frame(t)
        assert mask.shape == clip.get_frame(t).shape[:2]
        assert not np.any(mask[0]) and not np.any(mask[-1])
        assert not np.any(mask[:, 0]) and not np.any(mask[:, -1])
    assert np.any(clip.mask.get_frame(0.24))
    assert not np.any(clip.mask.get_frame(2))
    clip.close()


def test_missing_glyph_and_invalid_style_fail_instead_of_tofu() -> None:
    with pytest.raises(ValueError, match='不支持字符'):
        build_title_rgba('拉面🦄', 'comic_pop', (404, 720))
    with pytest.raises(ValueError, match='未知'):
        build_title_rgba('拉面', 'unknown', (404, 720))
