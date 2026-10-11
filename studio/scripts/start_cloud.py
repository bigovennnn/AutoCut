"""Start the lightweight exporter on loopback, without local model downloads."""

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
load_dotenv(ROOT / '.env.cloud')
os.environ['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'src'), str(ROOT)])
os.environ['OPENSTORYLINE_CONFIG'] = str(ROOT / 'config.cloud.toml')
if shutil.which('ffmpeg'):
    os.environ['IMAGEIO_FFMPEG_EXE'] = shutil.which('ffmpeg')
if not shutil.which('ffprobe'):
    raise SystemExit('请先安装FFmpeg（需同时提供ffprobe）')
print('AutoCut轻量出片：http://127.0.0.1:8005，停止服务：Ctrl+C', flush=True)
os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'cloud_app:app', '--host', '127.0.0.1', '--port', '8005'])
