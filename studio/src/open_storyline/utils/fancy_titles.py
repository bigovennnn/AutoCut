"""Editable, licensed display lettering with bounded local pop animation."""

import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from fontTools.ttLib import TTFont
from moviepy import VideoClip
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
STYLE_VERSION = 'fancy_titles_v1'
FONTS = {
    'smiley': ('SmileySans-Oblique.ttf', 'b447d7e781f08bc95c4c9f23ba71ed2b8ebb639aa7184485c71c4ca5afcd25c4'),
    'maiyuan': ('KNMaiyuan-Regular.ttf', '94ea78c51086b1ea58c1744784b2335dea2c5ef1c5193b80e02c7d46b8e0283f'),
}
STYLES: Dict[str, Dict[str, Any]] = {
    'comic_pop': {'label': '橙黄冲击 · 弹入', 'font': 'smiley', 'top': '#FFF4B0', 'bottom': '#FF9A35', 'ink': '#302348', 'shadow': '#F06463', 'accent': '#FFDB61', 'angle': 0},
    'mint_sticker': {'label': '薄荷贴纸 · 弹入', 'font': 'maiyuan', 'top': '#EEFFF3', 'bottom': '#82EBC6', 'ink': '#204A43', 'shadow': '#55BBA8', 'accent': '#FFD96C', 'angle': -2},
    'pink_punch': {'label': '漫画强调 · 弹入', 'font': 'smiley', 'top': '#FFF3F8', 'bottom': '#FF86AA', 'ink': '#442D60', 'shadow': '#9460D9', 'accent': '#FFD364', 'angle': 2},
}


def style_metadata(style: str) -> Dict[str, Any]:
    """Verify font identity and return provenance for the run record."""
    if style not in STYLES:
        raise ValueError('未知花字样式')
    spec = STYLES[style]
    name, expected = FONTS[spec['font']]
    path = ROOT / 'resource/fonts/fancy' / name
    if not path.is_file():
        raise FileNotFoundError('花字字体未安装，请运行 scripts/bootstrap_fancy_fonts.py')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError('花字字体校验失败')
    return {'style_id': style, 'version': STYLE_VERSION, 'label': spec['label'], 'font_file': name,
            'font_sha256': digest, 'license': 'SIL OFL 1.1', 'animation': 'pop_240ms_exit_140ms',
            'generator': 'local_pillow', 'generated_by_image_model': False}


@lru_cache(maxsize=4)
def _glyphs(path: str) -> frozenset:
    with TTFont(path, lazy=True) as font:
        return frozenset(font.getBestCmap())


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> str:
    lines: List[str] = []
    line = ''
    for char in text:
        if line and font.getlength(line + char) > width:
            lines.append(line)
            line = ''
        line += char
    if line:
        lines.append(line)
    return '\n'.join(lines)


def _star(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, color: str) -> None:
    points = []
    for index in range(8):
        angle = math.pi * index / 4
        r = radius if index % 2 == 0 else radius * 0.30
        points.append((x + math.cos(angle) * r, y + math.sin(angle) * r))
    draw.polygon(points, fill=color)


def build_title_rgba(text: str, style: str, video_size: Tuple[int, int]) -> Image.Image:
    """Produce a transparent title with two outlines, depth, and original accents."""
    metadata = style_metadata(style)
    spec = STYLES[style]
    text = ' '.join(text.split())
    if not text or len(text) > 30:
        raise ValueError('花字需要1—30个字符，推荐4—10个字')
    path = ROOT / 'resource/fonts/fancy' / metadata['font_file']
    missing = [char for char in text if not char.isspace() and ord(char) not in _glyphs(str(path))]
    if missing:
        raise ValueError('花字字体不支持字符：' + ''.join(sorted(set(missing))))
    width, height = video_size
    max_width = int(width * 0.76)
    size = max(22, min(56, round(height * 0.064), round(width * 0.115)))
    while True:
        font = ImageFont.truetype(str(path), size=size)
        wrapped = _wrap(text, font, max_width)
        if wrapped.count('\n') < 2 or size <= 20:
            break
        size -= 2
    if wrapped.count('\n') >= 2:
        raise ValueError('花字超过两行，请精简标题')
    stroke = max(2, round(size * 0.10))
    outer = stroke + max(2, round(size * 0.08))
    pad = max(22, outer * 3)
    measure = ImageDraw.Draw(Image.new('L', (1, 1)))
    bbox = measure.multiline_textbbox((0, 0), wrapped, font=font, spacing=3, align='center', stroke_width=outer)
    w, h = math.ceil(bbox[2] - bbox[0] + pad * 2), math.ceil(bbox[3] - bbox[1] + pad * 2)
    origin = (pad - bbox[0], pad - bbox[1])
    rgba = Image.new('RGBA', (w, h))
    draw = ImageDraw.Draw(rgba)
    depth = max(3, round(size * 0.12))
    draw.multiline_text((origin[0] + depth, origin[1] + depth), wrapped, font=font, spacing=3,
                        align='center', fill=spec['shadow'], stroke_width=outer + 1, stroke_fill=spec['ink'])
    draw.multiline_text(origin, wrapped, font=font, spacing=3, align='center', fill='white', stroke_width=outer, stroke_fill='white')
    draw.multiline_text(origin, wrapped, font=font, spacing=3, align='center', fill=spec['ink'], stroke_width=stroke, stroke_fill=spec['ink'])
    mask = Image.new('L', (w, h))
    ImageDraw.Draw(mask).multiline_text(origin, wrapped, font=font, spacing=3, align='center', fill=255)
    top = np.array(tuple(bytes.fromhex(spec['top'][1:])), dtype=float)
    bottom = np.array(tuple(bytes.fromhex(spec['bottom'][1:])), dtype=float)
    blend = np.clip((np.arange(h) - pad) / max(1, h - pad * 2), 0, 1)[:, None]
    colors = top + (bottom - top) * blend
    gradient = np.repeat(colors[:, None, :], w, axis=1).astype('uint8')
    fill = Image.fromarray(gradient).convert('RGBA')
    fill.putalpha(mask)
    rgba.alpha_composite(fill)
    draw = ImageDraw.Draw(rgba)
    _star(draw, pad * 0.48, h * 0.36, max(6, size * 0.18), spec['accent'])
    _star(draw, w - pad * 0.48, h * 0.66, max(5, size * 0.14), spec['accent'])
    for offset in [-1, 1]:
        draw.line([(w - pad * 0.48, h * 0.28), (w - pad * 0.48 + 6, h * 0.28 + offset * 6)], fill=spec['ink'], width=2)
    if spec['angle']:
        rgba = rgba.rotate(spec['angle'], resample=Image.Resampling.BICUBIC, expand=True)
    # Leave room for overshoot so the dynamic graphic never leaves the frame.
    safe_width = max(1, int(width * 0.88 / 1.10))
    if rgba.width > safe_width:
        rgba = rgba.resize((safe_width, round(rgba.height * safe_width / rgba.width)), Image.Resampling.LANCZOS)
    return rgba


def make_title_clip(text: str, style: str, start_s: float, duration_s: float, video_size: Tuple[int, int]) -> VideoClip:
    """Cache eight entrance frames on a small fixed canvas; keep speech untouched."""
    asset = build_title_rgba(text, style, video_size)
    canvas_size = (math.ceil(asset.width * 1.10) + 4, math.ceil(asset.height * 1.10) + 4)
    scales = [0.74, 0.89, 1.02, 1.10, 1.07, 1.03, 1.01, 1.0]
    frames = []
    for scale in scales:
        frame = Image.new('RGBA', canvas_size)
        resized = asset.resize((max(1, round(asset.width * scale)), max(1, round(asset.height * scale))), Image.Resampling.LANCZOS)
        frame.alpha_composite(resized, ((frame.width - resized.width) // 2, (frame.height - resized.height) // 2))
        frames.append(np.asarray(frame))
    def frame_index(t: float) -> int:
        return min(7, max(0, int(t / 0.24 * 8)))
    clip = VideoClip(frame_function=lambda t: frames[frame_index(t)][:, :, :3], duration=duration_s)
    def mask_at(t: float) -> np.ndarray:
        fade = min(1.0, max(0.0, (duration_s - t) / min(0.14, duration_s / 2)))
        return frames[frame_index(t)][:, :, 3].astype(np.float32) / 255 * fade
    mask = VideoClip(frame_function=mask_at, is_mask=True, duration=duration_s)
    y = max(14, round(video_size[1] * 0.055))
    return clip.with_mask(mask).with_start(start_s).with_position(('center', y))
