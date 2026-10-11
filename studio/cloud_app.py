"""Loopback-only direct-export UI; upstream advanced Agent remains separate."""

import asyncio
import copy
import json
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from open_storyline.quickcut.pipeline import (
    Provider, QuickcutOptions, RunLedger, inspect_source, now, render_recorded_timeline, run_quickcut,
)
from open_storyline.quickcut.speech import local_asr_available, write_srt

ROOT = Path(__file__).resolve().parent
RUN_ROOT = ROOT / 'runtime-local' / 'runs'
UPLOAD_ROOT = Path(os.getenv('AUTOCUT_UPLOADS', str(ROOT / 'uploads'))).resolve()
MAX_BYTES = 500 * 1024 * 1024
ALLOWED_SUFFIXES = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
tasks: Dict[str, asyncio.Task] = {}
render_slot = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(application: FastAPI) -> Any:
    """An interrupted process cannot resume with lost in-memory credentials."""
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    for path in RUN_ROOT.glob('*/run.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('status') == 'running':
                record['status'] = 'failed'
                record['errors'].append({'stage': record['stage'], 'type': 'ProcessInterrupted',
                                         'message': '上次服务中断，任务未完成；请重新提交'})
                record['stage'] = 'failed'
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary.replace(path)
        except (OSError, ValueError):
            continue
    yield
    for task in list(tasks.values()):
        task.cancel()


app = FastAPI(title='AutoCut 云端轻量出片', docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware('http')
async def require_local_origin(request: Request, call_next: Any) -> Any:
    """Keep credential-bearing actions on the local UI's own origin."""
    origin = request.headers.get('origin')
    if request.method == 'POST' and origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        return JSONResponse({'detail': '请从本机出片页面提交请求'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Never echo request bodies containing secrets in validation responses."""
    return JSONResponse({'detail': '请求参数格式不正确'}, status_code=422)


@app.get('/')
async def index() -> FileResponse:
    """Show the direct-export interface."""
    return FileResponse(ROOT / 'web' / 'cloud' / 'index.html')


@app.get('/api/health')
async def health() -> Dict[str, Any]:
    """Report installed infrastructure, without implying provider readiness."""
    font = ROOT / 'resource' / 'fonts' / 'font_info.json'
    return {'status': 'ready', 'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')),
            'font': font.is_file(), 'cloud_credentials': {'llm': bool(os.getenv('DEEPSEEK_API_KEY')),
                                                        'vlm': bool(os.getenv('DASHSCOPE_API_KEY'))},
            'local_model_deployed': False, 'local_asr_available': local_asr_available()}


@app.get('/examples')
async def sample_gallery() -> FileResponse:
    """Show the local verification gallery without publishing private footage."""
    path = ROOT / 'runtime-local' / 'verification' / 'auto-quality-20261011' / 'gallery.html'
    if not path.is_file():
        raise HTTPException(404, '样片对照页尚未生成')
    return FileResponse(path)


@app.get('/api/materials')
async def materials() -> Dict[str, Any]:
    """List only the user-authorized uploads folder, excluding symlinks."""
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    values = [{'name': path.name, 'size_bytes': path.stat().st_size}
              for path in sorted(UPLOAD_ROOT.iterdir())
              if path.is_file() and not path.is_symlink() and path.suffix.lower() in ALLOWED_SUFFIXES]
    return {'files': values, 'folder': str(UPLOAD_ROOT)}


def read_run(run_id: str) -> Dict[str, Any]:
    """Read an atomic persisted record; UUID prevents arbitrary path access."""
    try:
        if str(uuid.UUID(run_id)) != run_id:
            raise ValueError('Invalid UUID')
        return json.loads((RUN_ROOT / run_id / 'run.json').read_text(encoding='utf-8'))
    except (ValueError, FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(404, '找不到这个运行记录') from None


async def execute(run_id: str, paths: List[Path], options: QuickcutOptions, ledger: RunLedger) -> None:
    """Serialize jobs to bound render memory; retain their terminal records."""
    try:
        async with render_slot:
            await run_quickcut(paths, options, ledger, ROOT / 'resource' / 'fonts' / 'font_info.json')
    finally:
        tasks.pop(run_id, None)


def fill_cloud_credentials(config: Dict[str, Any]) -> None:
    """Resolve environment keys by destination service, not by model role."""
    if config.get('mode', 'cloud') != 'cloud':
        return
    for role in ['llm', 'vlm']:
        provider = config.setdefault(role, {})
        if provider.get('api_key'):
            continue
        host = urlparse(provider.get('base_url', '')).hostname or ''
        if host == 'api.deepseek.com':
            provider['api_key'] = os.getenv('DEEPSEEK_API_KEY', '')
        elif host in ['dashscope.aliyuncs.com', 'dashscope-intl.aliyuncs.com', 'dashscope-us.aliyuncs.com',
                       'cn-hongkong.dashscope.aliyuncs.com'] or host.endswith('.maas.aliyuncs.com'):
            provider['api_key'] = os.getenv('DASHSCOPE_API_KEY', '')


@app.post('/api/runs')
async def create_run(config: str = Form(...), existing: str = Form('[]'),
                     files: Optional[List[UploadFile]] = File(None)) -> Dict[str, str]:
    """Accept media and real providers; credentials stay in task memory only."""
    if len(tasks) >= 2:
        raise HTTPException(429, '已有两个任务，请等当前任务完成')
    try:
        raw = json.loads(config)
        fill_cloud_credentials(raw)
        options = QuickcutOptions.model_validate(raw)
        names = json.loads(existing)
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError('文件列表格式不正确')
    except (ValueError, ValidationError, TypeError, AttributeError):
        raise HTTPException(422, '检查API地址、模型、Key及目标时长。云端Key不能为空，本地模式须连接本机服务。') from None
    incoming = files or []
    if not 1 <= len(incoming) + len(names) <= 5:
        raise HTTPException(422, '请选择1—5个视频文件')
    paths = []
    for name in names:
        path = UPLOAD_ROOT / name
        if Path(name).name != name or path.is_symlink() or not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise HTTPException(422, '素材文件不存在或格式不支持')
        paths.append(path)
    run_id = str(uuid.uuid4())
    ledger = RunLedger(RUN_ROOT / run_id, run_id, options)
    input_dir = ledger.directory / 'inputs'
    input_dir.mkdir()
    total = sum(path.stat().st_size for path in paths)
    try:
        if total > MAX_BYTES:
            raise ValueError('素材总大小超过500MB')
        for index, upload in enumerate(incoming):
            suffix = Path(upload.filename or '').suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise ValueError('仅支持常见视频格式')
            target = input_dir / f'input_{index + 1:02d}{suffix}'
            with target.open('wb') as output:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError('素材总大小超过500MB')
                    output.write(chunk)
            paths.append(target)
        # Snapshot authorized folder inputs so later edits cannot change a queued run.
        for index in range(len(names)):
            target = input_dir / f'folder_{index + 1:02d}{paths[index].suffix.lower()}'
            await asyncio.to_thread(shutil.copyfile, paths[index], target)
            paths[index] = target
    except (ValueError, OSError) as exc:
        ledger.data['status'] = 'failed'
        ledger.data['errors'].append({'stage': 'uploading', 'type': type(exc).__name__, 'message': str(exc)})
        ledger.stage('failed')
        shutil.rmtree(input_dir, ignore_errors=True)
        raise HTTPException(422, str(exc)) from None
    finally:
        for upload in incoming:
            await upload.close()
    tasks[run_id] = asyncio.create_task(execute(run_id, paths, options, ledger))
    return {'run_id': run_id}


@app.get('/api/runs/{run_id}')
async def run_status(run_id: str) -> Dict[str, Any]:
    """Return real stages, measured counters and terminal validation."""
    return read_run(run_id)


@app.get('/api/runs/{run_id}/record')
async def run_record(run_id: str) -> FileResponse:
    """Download the complete record; no keys are stored in it."""
    read_run(run_id)
    return FileResponse(RUN_ROOT / run_id / 'run.json', filename=f'autocut-{run_id}.json')


@app.get('/api/runs/{run_id}/preview')
async def sample_preview(run_id: str) -> FileResponse:
    """Serve a previously inspected output frame for the local sample gallery."""
    read_run(run_id)
    path = RUN_ROOT / run_id / 'inspection' / '00_0.jpg'
    if not path.is_file():
        raise HTTPException(404, '该样片尚未生成预览帧')
    return FileResponse(path, media_type='image/jpeg')


@app.get('/api/runs/{run_id}/video')
async def run_video(run_id: str) -> FileResponse:
    """Serve only a successfully validated output from this run's directory."""
    record = read_run(run_id)
    if record['status'] not in ['success', 'degraded']:
        raise HTTPException(409, '任务尚未成功导出有效成片')
    path = Path(record['output']['output_path']).resolve()
    if not path.is_relative_to((RUN_ROOT / run_id).resolve()) or not path.is_file():
        raise HTTPException(404, '成片文件不存在')
    return FileResponse(path, media_type='video/mp4', filename='autocut.mp4')


@app.get('/api/runs/{run_id}/subtitles')
async def speech_subtitles_file(run_id: str) -> FileResponse:
    """Download genuine mapped speech subtitles, never visual titles as ASR."""
    record = read_run(run_id)
    path = RUN_ROOT / run_id / 'subtitles.srt'
    if record['status'] not in ['success', 'degraded'] or not path.is_file():
        raise HTTPException(404, '这个运行没有语音字幕文件')
    return FileResponse(path, media_type='text/plain; charset=utf-8', filename='autocut-speech.srt')


class SubtitleEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subtitle_index: int = Field(ge=0)
    text: str = Field(max_length=100)


class SubtitleEdits(BaseModel):
    model_config = ConfigDict(extra='forbid')
    edits: List[SubtitleEdit] = Field(min_length=1, max_length=120)


class TitleStyleSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title_style: Literal['plain', 'comic_pop', 'mint_sticker', 'pink_punch']


@app.post('/api/runs/{parent_id}/title-style')
async def revise_title_style(parent_id: str, selection: TitleStyleSelection) -> Dict[str, str]:
    """Create an independently validated export with changed display lettering."""
    parent = read_run(parent_id)
    if parent['status'] not in ['success', 'degraded']:
        raise HTTPException(409, '请等成片完成后再换花字')
    if len(tasks) >= 2:
        raise HTTPException(429, '已有两个任务，请等当前任务完成')
    if selection.title_style != 'plain':
        from open_storyline.utils.fancy_titles import style_metadata
        try:
            style_metadata(selection.title_style)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(422, str(exc)) from exc
    timeline = copy.deepcopy(parent['timeline'])
    titles = [item for item in timeline['tracks']['subtitles'] if item.get('kind') == 'title']
    if not titles:
        raise HTTPException(422, '这条成片没有主题标题')
    if all(item.get('title_style', 'plain') == selection.title_style for item in titles):
        raise HTTPException(422, '已经是这个花字样式')
    for item in titles:
        item['title_style'] = selection.title_style
    public_options = {**parent['options'], 'title_style': selection.title_style}
    options = QuickcutOptions.model_construct(**public_options,
        llm=Provider.model_validate(parent['providers']['llm']), vlm=Provider.model_validate(parent['providers']['vlm']))
    run_id = str(uuid.uuid4())
    ledger = RunLedger(RUN_ROOT / run_id, run_id, options)
    ledger.data.update({'workflow': 'title_style_revision_v1', 'parent_run_id': parent_id,
                        'revision_parent_status': parent['status'],
                        'provider_results_reused_from': parent_id, 'providers': parent['providers'],
                        'sources': parent['sources'], 'plan': parent['plan'], 'timeline': timeline,
                        'transcripts': parent.get('transcripts', []), 'capabilities': parent['capabilities'],
                        'warnings': parent.get('warnings', []),
                        'title_style_change': {'new_style': selection.title_style, 'changed_title_count': len(titles)},
                        'cost': {'currency': 'CNY', 'actual_amount': None, 'reason': '本次只在本机更换花字并渲染；未重新调用模型'}})
    tasks[run_id] = asyncio.create_task(execute_subtitle_revision(run_id, ledger, options))
    return {'run_id': run_id}


async def execute_subtitle_revision(run_id: str, ledger: RunLedger, options: QuickcutOptions) -> None:
    """Re-render edited wording with no repeated recognition or cloud requests."""
    try:
        async with render_slot:
            ledger.stage('inspecting')
            for source in ledger.data['sources']:
                if inspect_source(Path(source['path']))['sha256'] != source['sha256']:
                    raise ValueError('源素材已改变，不能直接改字重导出')
            speech = [i for i in ledger.data['timeline']['tracks']['subtitles'] if i.get('kind') == 'speech']
            write_srt(speech, ledger.directory / 'subtitles.srt')
            ledger.data['speech_subtitle_count'] = len(speech)
            ledger.stage('rendering')
            ledger.data['output'] = await render_recorded_timeline(options, ledger, ROOT / 'resource/fonts/font_info.json')
            ledger.data['status'] = 'degraded' if ledger.data.get('revision_parent_status') == 'degraded' else 'success'
            ledger.stage('complete')
    except Exception as exc:
        ledger.data['status'] = 'failed'
        ledger.data['errors'].append({'stage': ledger.data['stage'], 'type': type(exc).__name__, 'message': str(exc)})
        ledger.stage('failed')
    finally:
        ledger.data['finished_at'] = now()
        ledger.data['elapsed_s'] = round(time.monotonic() - ledger.started_monotonic, 3)
        ledger.save()
        tasks.pop(run_id, None)


@app.post('/api/runs/{parent_id}/subtitle-edits')
async def revise_subtitles(parent_id: str, changes: SubtitleEdits) -> Dict[str, str]:
    """Preserve original recognition and edit history in a separate run."""
    parent = read_run(parent_id)
    if parent['status'] not in ['success', 'degraded']:
        raise HTTPException(409, '请等成片完成后再改字幕')
    if len(tasks) >= 2:
        raise HTTPException(429, '已有两个任务，请等当前任务完成')
    timeline = copy.deepcopy(parent['timeline'])
    subtitles = timeline['tracks']['subtitles']
    indices = [e.subtitle_index for e in changes.edits]
    if len(set(indices)) != len(indices) or any(i >= len(subtitles) or subtitles[i].get('kind') != 'speech' for i in indices):
        raise HTTPException(422, '语音字幕索引无效或重复')
    history = []
    for edit in changes.edits:
        item = subtitles[edit.subtitle_index]
        if item['text'] != edit.text.strip():
            history.append({'subtitle_index': edit.subtitle_index, 'original_text': item['text'], 'edited_text': edit.text.strip()})
            item['text'] = edit.text.strip()
            item['review_status'] = 'edited_in_local_ui'
    if not history:
        raise HTTPException(422, '尚未改动字幕文字')
    timeline['tracks']['subtitles'] = [item for item in subtitles if item['text']]
    options = QuickcutOptions.model_construct(**parent['options'],
        llm=Provider.model_validate(parent['providers']['llm']), vlm=Provider.model_validate(parent['providers']['vlm']))
    run_id = str(uuid.uuid4())
    ledger = RunLedger(RUN_ROOT / run_id, run_id, options)
    ledger.data.update({'workflow': 'subtitle_revision_v1', 'parent_run_id': parent_id,
                        'revision_parent_status': parent['status'],
                        'provider_results_reused_from': parent_id, 'providers': parent['providers'],
                        'sources': parent['sources'], 'plan': parent['plan'], 'timeline': timeline,
                        'transcripts': parent.get('transcripts', []), 'subtitle_edits': history,
                        'warnings': [*parent.get('warnings', []), '字幕包含本地改字；原始识别结果保存在父运行记录。'],
                        'cost': {'currency': 'CNY', 'actual_amount': None, 'reason': '本次只在本机重渲染；未重新调用模型'}})
    ledger.data['capabilities'] = parent['capabilities']
    tasks[run_id] = asyncio.create_task(execute_subtitle_revision(run_id, ledger, options))
    return {'run_id': run_id}
