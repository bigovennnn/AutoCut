"""Install the minimum font assets; verify hashes and retain their license."""

import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = [
    ('NotoSansCJKsc-Regular.otf',
     'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
     '2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'),
    ('OFL.txt', 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE',
     '6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2'),
]


def main() -> None:
    """Prepare deterministic, small resource metadata without neural weights."""
    directory = ROOT / 'resource' / 'fonts'
    directory.mkdir(parents=True, exist_ok=True)
    for name, url, expected in ASSETS:
        target = directory / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        response = requests.get(url, timeout=(10, 120))
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != expected:
            raise RuntimeError(f'{name}: hash mismatch; upstream changed, review the new asset before updating the pin')
        target.write_bytes(response.content)
    font_info = directory / 'font_info.json'
    if not font_info.exists():
        font_info.write_text(json.dumps([{'font_name': 'SiYuanHeiTi',
                            'font_path': str(directory / 'NotoSansCJKsc-Regular.otf'),
                            'class': ['Basic'], 'lang': ['zh', 'en'],
                            'description': 'Noto Sans CJK SC Regular, SIL Open Font License 1.1'}], indent=2), encoding='utf-8')
    for relative, content in [('bgms/meta.json', []), ('script_templates/meta.json', []), ('tts/tts_providers.json', {})]:
        target = ROOT / 'resource' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(json.dumps(content), encoding='utf-8')
    print('Chinese font and its license ready; music/template catalogues remain empty when no assets exist.')


if __name__ == '__main__':
    main()
