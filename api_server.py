"""
AutoCut API Server - FastAPI Backend
提供视频处理和文案生成的 RESTful API
"""

import os
import sys
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 导入现有的 AutoCut 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from autocut_agent import AutoCutAgent
from media_processor import MediaProcessor

# 创建 FastAPI 应用
app = FastAPI(
    title="AutoCut API",
    description="智能视频剪辑 API",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
UPLOAD_DIR = Path("temp/uploads")
OUTPUT_DIR = Path("temp/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 存储任务状态
tasks: Dict[str, Dict[str, Any]] = {}


# ============ 数据模型 ============

class ProcessingStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    current_step: str
    message: str
    result: Optional[Dict[str, Any]] = None


class CopywritingRequest(BaseModel):
    task_id: str
    platform: str  # xiaohongshu, douyin, bilibili, moments


class CopywritingResponse(BaseModel):
    platform: str
    content: str
    tags: List[str]


# ============ 辅助函数 ============

def generate_task_id() -> str:
    """生成唯一任务ID"""
    return f"task_{uuid.uuid4().hex[:12]}"


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    return tasks.get(task_id)


def update_task_status(task_id: str, **kwargs):
    """更新任务状态"""
    if task_id in tasks:
        tasks[task_id].update(kwargs)
        tasks[task_id]["updated_at"] = datetime.now().isoformat()


# ============ API 路由 ============

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "AutoCut API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    platform: str = "xiaohongshu"
):
    """
    上传视频并创建处理任务
    
    - **file**: 视频文件
    - **platform**: 目标平台 (xiaohongshu, douyin, bilibili, moments)
    """
    task_id = generate_task_id()
    
    # 保存上传的文件
    file_ext = Path(file.filename).suffix
    upload_path = UPLOAD_DIR / f"{task_id}{file_ext}"
    
    try:
        content = await file.read()
        with open(upload_path, "wb") as f:
            f.write(content)
        
        # 创建任务记录
        tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "current_step": "等待处理",
            "message": "视频上传成功，等待处理",
            "platform": platform,
            "upload_path": str(upload_path),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None
        }
        
        # 后台启动处理任务
        background_tasks.add_task(process_video_task, task_id, str(upload_path), platform)
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "视频上传成功，开始处理"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """获取任务处理状态"""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "message": task["message"]
    }


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """获取处理结果"""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task["status"] != "completed":
        return {
            "task_id": task_id,
            "status": task["status"],
            "message": "处理尚未完成"
        }
    
    return {
        "task_id": task_id,
        "status": "completed",
        "result": task.get("result", {})
    }


@app.post("/copywriting/{task_id}")
async def generate_copywriting(task_id: str, platform: str):
    """
    为指定平台生成文案
    
    - **task_id**: 任务ID
    - **platform**: 目标平台
    """
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="视频处理尚未完成")
    
    try:
        # 使用现有的 AutoCutAgent 生成文案
        agent = AutoCutAgent()
        
        # 获取视频分析结果
        result = task.get("result", {})
        transcription = result.get("transcription", {})
        frames_info = result.get("frames_info", [])
        
        # 生成文案
        copywriting = agent.generate_copywriting(
            transcription=transcription,
            frames_info=frames_info,
            platform=platform
        )
        
        return {
            "platform": platform,
            "content": copywriting.get("content", ""),
            "tags": copywriting.get("tags", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文案生成失败: {str(e)}")


@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """下载处理后的视频"""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = task.get("result", {})
    output_path = result.get("output_video")

    # 如果裁剪后的视频不存在，尝试使用原始视频
    if not output_path or not os.path.exists(output_path):
        output_path = result.get("original_video")

    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"autocut_{task_id}.mp4"
    )


# ============ 后台处理任务 ============

def _progress_callback_factory(task_id: str):
    """创建进度回调函数"""
    # 步骤映射 - 与 autocut_agent.py process_video 中的 _update_progress 调用匹配
    # 也与前端 stepMap 对应:
    # 'extract': 1, 'transcribe': 2, 'analyze': 3, 'score': 4,
    # 'concat': 5, 'export': 6, 'copywriting': 7, 'done': 8
    step_mapping = {
        1: ("extract", "提取音频与关键帧"),
        2: ("transcribe", "语音识别转文字"),
        3: ("analyze", "画面质量分析"),
        4: ("score", "精彩片段评分"),
        5: ("concat", "智能拼接片段"),
        6: ("export", "导出视频文件"),
        7: ("copywriting", "生成平台文案"),
        8: ("done", "处理完成"),
    }

    def callback(step: int, message: str, progress: int):
        step_info = step_mapping.get(step, ("processing", message))
        update_task_status(
            task_id,
            progress=progress,
            current_step=step_info[0],
            message=message
        )
    return callback


async def process_video_task(task_id: str, video_path: str, platform: str):
    """
    后台处理视频任务 - 调用真实的 AutoCutAgent
    """
    # 确保输出目录存在，使用绝对路径
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 转换为绝对路径确保一致性
    video_path = str(Path(video_path).resolve())
    output_dir = str(OUTPUT_DIR.resolve())

    try:
        update_task_status(
            task_id,
            status="processing",
            progress=1,
            current_step="init",
            message="初始化处理模块"
        )

        # 初始化处理器，使用 api_server 的输出目录
        agent = AutoCutAgent()
        agent.media_processor.output_dir = output_dir
        # 更新所有新组件的输出目录
        agent.video_trimmer.output_dir = Path(output_dir)
        agent.moviepy_processor.output_dir = Path(output_dir)
        agent.set_progress_callback(_progress_callback_factory(task_id))

        print(f"📁 视频路径: {video_path}")
        print(f"📁 输出目录: {output_dir}")

        # 在线程池中运行同步的 process_video 方法
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: agent.process_video(video_path, platform)
        )

        # 提取结果
        output_video = result.get("trimmed_video")

        # 如果裁剪失败，使用原始视频作为后备
        if not output_video or not os.path.exists(output_video):
            print(f"⚠️  视频裁剪失败，使用原始视频: {video_path}")
            output_video = video_path
        else:
            # 确保裁剪后的视频路径也是绝对路径
            output_video = str(Path(output_video).resolve())

        transcription = result.get("transcription", {})
        best_frames_info = result.get("best_frames_info", [])
        highlights = result.get("highlights", [])  # 新的多高光格式
        copywriting = result.get("copywriting", "")

        # 获取关键帧数据用于返回
        frames_data = []
        for frame in best_frames_info[:5]:
            frame_data = {
                "timestamp": frame.get("timestamp", 0),
                "description": frame.get("description", ""),
                "clarity": frame.get("clarity", 0),
            }
            # 如果有路径，读取为 base64
            frame_path = frame.get("path")
            if frame_path and os.path.exists(frame_path):
                try:
                    with open(frame_path, "rb") as f:
                        import base64
                        frame_data["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
                except Exception:
                    pass
            frames_data.append(frame_data)

        # 格式化高光片段
        formatted_highlights = []
        for i, h in enumerate(highlights):
            formatted_highlights.append({
                "rank": i + 1,
                "start": h.get("start", 0),
                "end": h.get("end", 0),
                "duration": h.get("end", 0) - h.get("start", 0),
                "score": h.get("total_score", 0),
                "reason": h.get("reason", ""),
                "scores": h.get("scores", {})
            })

        # 计算总时长
        total_duration = sum(h.get("end", 0) - h.get("start", 0) for h in highlights)

        # 完成任务
        update_task_status(
            task_id,
            status="completed",
            progress=100,
            current_step="done",
            message="处理完成",
            result={
                "output_video": output_video,
                "original_video": video_path,
                "transcription": transcription,
                "frames_info": frames_data,
                "highlights": formatted_highlights,
                "total_duration": total_duration,
                "copywriting": copywriting
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_task_status(
            task_id,
            status="failed",
            message=f"处理失败: {str(e)}"
        )


# ============ 主入口 ============

if __name__ == "__main__":
    print("🚀 启动 AutoCut API 服务器...")
    print("📡 API 地址: http://localhost:8000")
    print("📖 API 文档: http://localhost:8000/docs")
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
