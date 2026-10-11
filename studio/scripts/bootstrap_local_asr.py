"""Download a lightweight multilingual Whisper model, with pinned SHA-256."""

import argparse
import hashlib
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    'base': '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe',
    'small-q5_1': 'ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb',
}


def retain_licenses(folder: Path) -> None:
    """Keep official runtime and model licenses alongside downloaded weights."""
    sources = {
        'LICENSE.whisper.cpp': 'https://raw.githubusercontent.com/ggml-org/whisper.cpp/v1.9.4/LICENSE',
        'LICENSE.whisper': 'https://raw.githubusercontent.com/openai/whisper/main/LICENSE',
    }
    for name, url in sources.items():
        target = folder / name
        if not target.is_file():
            response = httpx.get(url, timeout=30, trust_env=False)
            response.raise_for_status()
            target.write_text(response.text, encoding='utf-8')


def main() -> None:
    """Install the selected model into ignored resources with its license."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=list(MODELS), default='base')
    model = parser.parse_args().model
    expected = MODELS[model]
    url = f'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model}.bin'
    target = ROOT / f'resource/models/whisper/ggml-{model}.bin'
    target.parent.mkdir(parents=True, exist_ok=True)
    retain_licenses(target.parent)
    if target.is_file():
        with target.open('rb') as existing:
            if hashlib.file_digest(existing, 'sha256').hexdigest() == expected:
                print(f'Whisper {model} model already verified')
                return
    temporary = target.with_suffix('.part')
    digest = hashlib.sha256()
    with httpx.Client(trust_env=False, follow_redirects=True, timeout=120) as client:
        with client.stream('GET', url) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_bytes(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError('Whisper model checksum mismatch; partial file retained for diagnosis')
    temporary.replace(target)
    print(f'Whisper {model} installed and verified: {target.stat().st_size} bytes')


if __name__ == '__main__':
    main()
