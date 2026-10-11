"""Install two pinned official OFL display fonts; no external sticker packs."""

import hashlib
import io
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ASSETS = [
    ('SmileySans-Oblique.ttf', 'https://github.com/atelier-anchor/smiley-sans/releases/download/v2.0.1/smiley-sans-v2.0.1.zip', 'b447d7e781f08bc95c4c9f23ba71ed2b8ebb639aa7184485c71c4ca5afcd25c4'),
    ('SmileySans-OFL.txt', 'https://raw.githubusercontent.com/atelier-anchor/smiley-sans/v2.0.1/LICENSE', '9401f4050f1b66c26b6ccdc8b0e14a3c1cc37aac122eda84386f25854a9bec72'),
    ('KNMaiyuan-Regular.ttf', 'https://raw.githubusercontent.com/maoken-fonts/KNMaiyuan/580b2bb873828122f7816f1c5c4caf2667cba62f/fonts/TTF/KNMaiyuan-Regular.ttf', '94ea78c51086b1ea58c1744784b2335dea2c5ef1c5193b80e02c7d46b8e0283f'),
    ('KNMaiyuan-OFL.txt', 'https://raw.githubusercontent.com/maoken-fonts/KNMaiyuan/580b2bb873828122f7816f1c5c4caf2667cba62f/OFL.txt', '0d3aa94d1bf406e867659d976fcb67a46e6ec224f6d9490dade350d537def214'),
]


def main() -> None:
    """Verify selected bytes and retain author/license information locally."""
    folder = ROOT / 'resource/fonts/fancy'
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(trust_env=False, follow_redirects=True, timeout=120) as client:
        for name, url, expected in ASSETS:
            target = folder / name
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                continue
            response = client.get(url)
            response.raise_for_status()
            data = response.content
            if url.endswith('.zip'):
                data = zipfile.ZipFile(io.BytesIO(data)).read(name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'{name}: 字体资源SHA-256不符')
            temporary = target.with_suffix(target.suffix + '.part')
            temporary.write_bytes(data)
            temporary.replace(target)
    print('得意黑与荆南麦圆字体、OFL许可已准备并校验。')


if __name__ == '__main__':
    main()
