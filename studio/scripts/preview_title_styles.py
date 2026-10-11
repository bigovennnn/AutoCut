"""Generate transparent lettering samples and a review sheet from real fonts."""

import hashlib
import json
import zipfile

from PIL import Image, ImageDraw, ImageFont

from open_storyline.utils.fancy_titles import ROOT, STYLES, STYLE_VERSION, build_title_rgba, style_metadata


def main() -> None:
    """Export reusable alpha assets plus a readable three-style comparison."""
    folder = ROOT / 'runtime-local/verification/fancy-titles'
    folder.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1080, 660), '#F4F0E8')
    font = ImageFont.truetype(str(ROOT / 'resource/fonts/NotoSansCJKsc-Regular.otf'), 24)
    draw = ImageDraw.Draw(sheet)
    assets = []
    draw.text((28, 18), 'AutoCut / 可编辑花字 · 开源字体 + 本地动画', font=font, fill='#243C37')
    for index, (style, spec) in enumerate(STYLES.items()):
        x = index * 360
        draw.rounded_rectangle((x + 12, 70, x + 348, 645), radius=22, fill=['#2D383A', '#405B50', '#382E4B'][index])
        for row, text in enumerate(['海底捞拉面局', '千万别拉断', '快乐越拉越长']):
            asset = build_title_rgba(text, style, (404, 720))
            path = folder / f'{style}_{row + 1}.png'
            asset.save(path)
            assets.append({'file': path.name, 'style_id': style, 'text': text,
                           'size': list(asset.size), 'mode': 'RGBA',
                           'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            sheet.paste(asset, (x + (360 - asset.width) // 2, 155 + row * 142), asset)
        draw.text((x + 28, 90), spec['label'], font=font, fill='#FFFFFF')
    sheet.save(folder / 'style-sheet.png')
    manifest = {'version': STYLE_VERSION, 'source_video_size': [404, 720],
                'styles': [{**style_metadata(style), 'parameters': spec} for style, spec in STYLES.items()],
                'assets': assets, 'decoration_origin': 'original geometric accents drawn locally'}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(folder / 'fancy-title-pack.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in [folder / 'manifest.json', folder / 'style-sheet.png', *[folder / a['file'] for a in assets]]:
            bundle.write(path, path.name)
        for name in ['SmileySans-OFL.txt', 'KNMaiyuan-OFL.txt']:
            bundle.write(ROOT / 'resource/fonts/fancy' / name, 'licenses/' + name)
    print(folder / 'style-sheet.png')


if __name__ == '__main__':
    main()
