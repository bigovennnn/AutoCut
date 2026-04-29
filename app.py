import os
import sys
import time
import base64
import tempfile
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

import streamlit as st

st.set_page_config(
    page_title="AutoCut | 智能视频剪辑",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==================== SVG 图标库 ====================
ICONS = {
    "logo": """<svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="8" fill="url(#logoGrad)"/><path d="M8 12l8-4 8 4v8l-8 4-8-4V12z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 8v8l8 4M16 16l-8 4" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>""",
    "upload": """<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 16V4m0 0l-4 4m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg>""",
    "check": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>""",
    "copy": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>""",
    "download": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>""",
    "refresh": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>""",
}

# ==================== 全局 CSS ====================
def inject_global_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {
        --primary: #0EA5E9;
        --primary-light: #38BDF8;
        --primary-dark: #0284C7;
        --secondary: #8B5CF6;
        --accent: #F59E0B;
        --success: #10B981;
        --bg-base: #FAFBFC;
        --bg-elevated: #FFFFFF;
        --bg-subtle: #F1F5F9;
        --text-primary: #0F172A;
        --text-secondary: #475569;
        --text-tertiary: #94A3B8;
        --border-default: #E2E8F0;
        --border-hover: #CBD5E1;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.05);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
        --shadow-xl: 0 16px 48px rgba(0,0,0,0.12);
        --shadow-glow: 0 0 40px rgba(14, 165, 233, 0.15);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 24px;
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    html, body, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: var(--bg-base) !important;
        color: var(--text-primary);
    }
    
    /* Hide Streamlit chrome */
    #MainMenu, footer, header, .stApp > header, .stApp > footer,
    [data-testid="stHeader"], [data-testid="stStatusWidget"], .stDeployButton { display: none !important; }
    
    /* Main container */
    [data-testid="stMainBlockContainer"] {
        background: transparent !important;
        padding: 0 !important;
        max-width: 100% !important;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(0.98); }
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    /* Header */
    .app-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 72px;
        background: rgba(250, 251, 252, 0.9);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 1px solid var(--border-default);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 2rem;
    }
    
    .header-brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .brand-text {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .header-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.375rem 0.875rem;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--success);
    }
    
    .header-badge::before {
        content: '';
        width: 6px;
        height: 6px;
        background: var(--success);
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }
    
    /* Stage container */
    .stage-container {
        min-height: 100vh;
        padding-top: 72px;
    }
    
    /* Upload Stage */
    .upload-stage {
        max-width: 800px;
        margin: 0 auto;
        padding: 3rem 2rem;
        animation: fadeIn 0.6s ease-out;
    }
    
    /* Processing Stage */
    .processing-stage {
        max-width: 1000px;
        margin: 0 auto;
        padding: 3rem 2rem;
        animation: fadeIn 0.6s ease-out;
    }
    
    .processing-layout {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 3rem;
        align-items: center;
    }
    
    @media (max-width: 900px) {
        .processing-layout {
            grid-template-columns: 1fr;
            gap: 2rem;
        }
    }
    
    /* Video preview */
    .video-preview-container {
        position: relative;
        border-radius: var(--radius-xl);
        overflow: hidden;
        background: #000;
        aspect-ratio: 16/9;
        box-shadow: var(--shadow-xl);
    }
    
    .video-preview-container video {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .video-overlay {
        position: absolute;
        inset: 0;
        background: linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 50%);
        display: flex;
        align-items: flex-end;
        padding: 1.5rem;
    }
    
    .video-info {
        color: white;
    }
    
    .video-filename {
        font-weight: 600;
        font-size: 0.875rem;
        margin-bottom: 0.25rem;
    }
    
    .video-meta {
        font-size: 0.75rem;
        opacity: 0.8;
    }
    
    /* Progress section */
    .progress-section {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    
    .progress-ring-wrapper {
        position: relative;
        width: 200px;
        height: 200px;
        margin-bottom: 2rem;
    }
    
    .progress-ring-svg {
        transform: rotate(-90deg);
        width: 100%;
        height: 100%;
    }
    
    .progress-ring-bg {
        fill: none;
        stroke: var(--border-default);
        stroke-width: 8;
    }
    
    .progress-ring-fill {
        fill: none;
        stroke: url(#progressGradient);
        stroke-width: 8;
        stroke-linecap: round;
        stroke-dasharray: 565;
        stroke-dashoffset: 565;
        transition: stroke-dashoffset 0.5s ease;
    }
    
    .progress-text {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    
    .progress-percent {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1;
    }
    
    .progress-label {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    /* Steps list */
    .steps-list {
        width: 100%;
        max-width: 320px;
    }
    
    .step-item {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.875rem 1rem;
        border-radius: var(--radius-md);
        margin-bottom: 0.5rem;
        transition: all 0.3s ease;
    }
    
    .step-item.pending {
        opacity: 0.5;
    }
    
    .step-item.active {
        background: rgba(14, 165, 233, 0.08);
        border: 1px solid rgba(14, 165, 233, 0.2);
    }
    
    .step-item.completed {
        background: rgba(16, 185, 129, 0.08);
    }
    
    .step-icon {
        width: 32px;
        height: 32px;
        border-radius: var(--radius-sm);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.875rem;
        flex-shrink: 0;
    }
    
    .step-item.pending .step-icon {
        background: var(--bg-subtle);
        color: var(--text-tertiary);
    }
    
    .step-item.active .step-icon {
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
        color: white;
        animation: pulse 2s ease-in-out infinite;
    }
    
    .step-item.completed .step-icon {
        background: var(--success);
        color: white;
    }
    
    .step-content {
        flex: 1;
    }
    
    .step-name {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    
    .step-item.pending .step-name {
        color: var(--text-tertiary);
    }
    
    .step-desc {
        font-size: 0.75rem;
        color: var(--text-secondary);
        margin-top: 0.125rem;
    }
    
    /* Result Stage */
    .result-stage {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
        animation: fadeIn 0.6s ease-out;
    }
    
    .result-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2rem;
    }
    
    .result-title {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    
    .result-title .icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, var(--success) 0%, #059669 100%);
        border-radius: var(--radius-md);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
    }
    
    .result-grid {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 2rem;
    }
    
    @media (max-width: 1024px) {
        .result-grid {
            grid-template-columns: 1fr;
        }
    }
    
    /* Video player */
    .video-player-wrapper {
        background: var(--bg-elevated);
        border-radius: var(--radius-xl);
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }
    
    .video-player {
        width: 100%;
        aspect-ratio: 16/9;
        background: #000;
    }
    
    /* Keyframes section */
    .keyframes-section {
        margin-top: 1.5rem;
    }
    
    .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-title::before {
        content: '';
        width: 4px;
        height: 20px;
        background: linear-gradient(180deg, var(--primary) 0%, var(--secondary) 100%);
        border-radius: 2px;
    }
    
    .keyframes-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
    }
    
    @media (max-width: 1200px) {
        .keyframes-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .keyframes-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    .keyframe-card {
        position: relative;
        aspect-ratio: 16/9;
        border-radius: var(--radius-md);
        overflow: hidden;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .keyframe-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-lg);
    }
    
    .keyframe-score {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        padding: 0.25rem 0.5rem;
        background: linear-gradient(135deg, var(--accent) 0%, #F97316 100%);
        border-radius: var(--radius-sm);
        font-size: 0.6875rem;
        font-weight: 700;
        color: white;
    }
    
    .keyframe-time {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 0.5rem;
        background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
        font-size: 0.75rem;
        color: white;
        font-variant-numeric: tabular-nums;
    }
    
    /* Copywriting section */
    .copywriting-section {
        background: var(--bg-elevated);
        border-radius: var(--radius-xl);
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
    }
    
    .copywriting-tabs {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--border-default);
    }
    
    .copy-tab {
        padding: 0.5rem 1rem;
        background: transparent;
        border: none;
        border-radius: var(--radius-md);
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-secondary);
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .copy-tab:hover {
        background: var(--bg-subtle);
        color: var(--text-primary);
    }
    
    .copy-tab.active {
        background: rgba(14, 165, 233, 0.1);
        color: var(--primary);
    }
    
    .copywriting-content {
        min-height: 200px;
    }
    
    .copywriting-text {
        font-size: 1rem;
        line-height: 1.8;
        color: var(--text-primary);
        white-space: pre-wrap;
    }
    
    .copywriting-actions {
        display: flex;
        gap: 0.75rem;
        margin-top: 1.5rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border-default);
    }
    
    .btn-action {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.625rem 1rem;
        border-radius: var(--radius-md);
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        border: none;
    }
    
    .btn-action-primary {
        background: var(--primary);
        color: white;
    }
    
    .btn-action-primary:hover {
        background: var(--primary-dark);
    }
    
    .btn-action-secondary {
        background: var(--bg-subtle);
        color: var(--text-secondary);
        border: 1px solid var(--border-default);
    }
    
    .btn-action-secondary:hover {
        background: var(--border-default);
    }
    </style>
    
    <svg style="position: absolute; width: 0; height: 0;">
        <defs>
            <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#0EA5E9"/>
                <stop offset="100%" stop-color="#8B5CF6"/>
            </linearGradient>
            <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#0EA5E9"/>
                <stop offset="100%" stop-color="#8B5CF6"/>
            </linearGradient>
        </defs>
    </svg>
    """, unsafe_allow_html=True)

# ==================== 组件函数 ====================
def render_header():
    """渲染应用头部"""
    st.markdown(f"""
    <header class="app-header">
        <div class="header-brand">
            {ICONS['logo']}
            <span class="brand-text">AutoCut</span>
        </div>
        <div class="header-badge">系统就绪</div>
    </header>
    """, unsafe_allow_html=True)

def render_upload_stage():
    """渲染上传阶段"""
    platforms = [
        ("xiaohongshu", "小红书"),
        ("douyin", "抖音"),
        ("bilibili", "B站"),
        ("moments", "朋友圈"),
    ]
    
    selected_platform = st.session_state.get("selected_platform", "xiaohongshu")
    uploaded_file = st.session_state.get("uploaded_file")
    
    st.markdown('<div class="upload-stage">', unsafe_allow_html=True)
    
    # 使用 columns 居中
    left_col, center_col, right_col = st.columns([1, 2, 1])
    
    with center_col:
        # 上传区域 - 使用 st.file_uploader 但用 CSS 隐藏原生样式
        st.markdown("""
        <style>
        /* 隐藏原生文件上传器 */
        [data-testid="stFileUploader"] {
            position: relative !important;
            height: auto !important;
        }
        [data-testid="stFileUploadDropzone"] {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }
        [data-testid="stFileUploadDropzone"] > div {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 自定义上传区域
        st.markdown(f"""
        <div style="
            width: 100%;
            aspect-ratio: 16/10;
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.05) 0%, rgba(139, 92, 246, 0.03) 100%);
            border: 2px dashed #E2E8F0;
            border-radius: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1.5rem;
            padding: 2rem;
            text-align: center;
            margin-bottom: 1.5rem;
        ">
            <div style="
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #0EA5E9 0%, #8B5CF6 100%);
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                box-shadow: 0 0 40px rgba(14, 165, 233, 0.3);
            ">
                {ICONS['upload']}
            </div>
            <div>
                <div style="font-size: 1.25rem; font-weight: 600; color: #0F172A; margin-bottom: 0.5rem;">
                    拖入视频或点击上传
                </div>
                <div style="font-size: 0.875rem; color: #64748B;">
                    支持 MP4、MOV、AVI 格式，最大 500MB
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <span style="padding: 0.25rem 0.625rem; background: rgba(14, 165, 233, 0.1); border-radius: 6px; font-size: 0.6875rem; font-weight: 600; color: #0EA5E9;">MP4</span>
                <span style="padding: 0.25rem 0.625rem; background: rgba(14, 165, 233, 0.1); border-radius: 6px; font-size: 0.6875rem; font-weight: 600; color: #0EA5E9;">MOV</span>
                <span style="padding: 0.25rem 0.625rem; background: rgba(14, 165, 233, 0.1); border-radius: 6px; font-size: 0.6875rem; font-weight: 600; color: #0EA5E9;">AVI</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 文件上传器
        uploaded = st.file_uploader("", type=["mp4", "mov", "avi"], label_visibility="collapsed")
        
        if uploaded:
            st.session_state.uploaded_file = uploaded
            os.makedirs("uploads", exist_ok=True)
            video_path = os.path.join("uploads", uploaded.name)
            if not os.path.exists(video_path):
                with open(video_path, "wb") as f:
                    f.write(uploaded.getbuffer())
            st.session_state.video_path = video_path
            st.rerun()
        
        # 显示已上传文件
        if uploaded_file:
            file_size = len(uploaded_file.getvalue()) / 1024 / 1024
            st.success(f"✅ {uploaded_file.name} ({file_size:.2f} MB)")
        
        # 平台选择
        st.markdown("<div style='text-align: center; margin: 1.5rem 0 0.75rem; font-size: 0.875rem; font-weight: 600; color: #64748B;'>选择发布平台</div>", unsafe_allow_html=True)
        
        platform_cols = st.columns(4)
        for i, (platform_id, platform_name) in enumerate(platforms):
            with platform_cols[i]:
                is_active = selected_platform == platform_id
                if st.button(
                    platform_name,
                    key=f"platform_{platform_id}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary"
                ):
                    st.session_state.selected_platform = platform_id
                    st.rerun()
        
        # 开始按钮
        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        can_start = uploaded_file is not None
        
        if st.button(
            "开始智能分析 →" if can_start else "请先上传视频",
            use_container_width=True,
            type="primary",
            disabled=not can_start
        ):
            st.session_state.current_stage = "processing"
            st.session_state.processing_progress = 0
            st.session_state.current_step = 0
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_processing_stage():
    """渲染处理阶段"""
    steps = [
        ("🎵", "音频转录", "提取视频语音内容"),
        ("👁", "帧分析", "识别关键视觉场景"),
        ("✨", "内容评分", "评估片段质量"),
        ("🎯", "高光选取", "筛选最佳片段"),
        ("✂️", "视频剪辑", "生成精简版本"),
        ("📝", "文案生成", "创作平台专属文案"),
    ]
    
    progress = st.session_state.get("processing_progress", 0)
    current_step = st.session_state.get("current_step", 0)
    video_path = st.session_state.get("video_path", "")
    
    st.markdown('<div class="processing-stage">', unsafe_allow_html=True)
    
    # 模拟进度更新
    if progress < 100:
        time.sleep(0.1)
        st.session_state.processing_progress = min(progress + 2, 100)
        new_step = min(int(st.session_state.processing_progress / 100 * len(steps)), len(steps) - 1)
        if new_step != current_step:
            st.session_state.current_step = new_step
        if st.session_state.processing_progress < 100:
            st.rerun()
    else:
        if st.session_state.get("auto_advance", True):
            st.session_state.current_stage = "result"
            st.session_state.auto_advance = False
            st.rerun()
    
    st.markdown('<div class="processing-layout">', unsafe_allow_html=True)
    
    # 左侧：视频预览
    st.markdown('<div>', unsafe_allow_html=True)
    if video_path and os.path.exists(video_path):
        st.markdown(f"""
        <div class="video-preview-container">
            <video src="{video_path}" autoplay muted loop></video>
            <div class="video-overlay">
                <div class="video-info">
                    <div class="video-filename">{os.path.basename(video_path)}</div>
                    <div class="video-meta">正在分析中...</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="video-preview-container" style="display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);">
            <div style="text-align: center; color: #64748B;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🎬</div>
                <div>视频预览</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 右侧：进度和步骤
    st.markdown('<div class="progress-section">', unsafe_allow_html=True)
    
    offset = 565 - (565 * progress / 100)
    st.markdown(f"""
    <div class="progress-ring-wrapper">
        <svg class="progress-ring-svg" viewBox="0 0 200 200">
            <circle class="progress-ring-bg" cx="100" cy="100" r="90"/>
            <circle class="progress-ring-fill" cx="100" cy="100" r="90" style="stroke-dashoffset: {offset}"/>
        </svg>
        <div class="progress-text">
            <div class="progress-percent">{int(progress)}%</div>
            <div class="progress-label">处理中</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="steps-list">', unsafe_allow_html=True)
    for i, (icon, name, desc) in enumerate(steps):
        if i < current_step:
            status_class = "completed"
            icon_display = ICONS['check']
        elif i == current_step:
            status_class = "active"
            icon_display = icon
        else:
            status_class = "pending"
            icon_display = icon
        
        st.markdown(f"""
        <div class="step-item {status_class}">
            <div class="step-icon">{icon_display}</div>
            <div class="step-content">
                <div class="step-name">{name}</div>
                <div class="step-desc">{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_result_stage():
    """渲染结果阶段"""
    platforms = {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "bilibili": "B站",
        "moments": "朋友圈",
    }
    
    selected_platform = st.session_state.get("selected_platform", "xiaohongshu")
    video_path = st.session_state.get("video_path", "")
    
    keyframes = [
        {"time": "00:03", "score": 92},
        {"time": "00:12", "score": 88},
        {"time": "00:18", "score": 85},
        {"time": "00:25", "score": 82},
    ]
    
    copywritings = {
        "xiaohongshu": """✨ 这段视频太治愈了！每一帧都是壁纸级别

🎬 剪辑亮点：
• 开场3秒抓住眼球，画面构图绝绝子
• 中段节奏把控到位，情绪递进自然
• 结尾留白恰到好处，让人意犹未尽

💡 适合搭配轻音乐，氛围感直接拉满！

#治愈系 #生活美学 #视频剪辑 #氛围感""",
        "douyin": """🔥 这视频不火天理难容！

前3秒直接拿捏，完播率稳了✅
节奏卡点精准，每一帧都在拍子上🎵
情绪递进像坐过山车，评论区肯定炸💥

快艾特你的剪辑搭子来学！👇

#剪辑教程 #短视频运营 #爆款视频""",
        "bilibili": """【剪辑分析】这段素材的潜力被我挖出来了

各位观众姥爷好，今天分析一段投稿素材：

📊 技术层面：
• 画面稳定性：优秀
• 色彩还原度：良好
• 音频清晰度：优秀

🎨 艺术层面：
• 叙事节奏：张弛有度
• 情绪曲线：完整闭环
• 视觉焦点：引导清晰

适合做成混剪素材，已标记关键帧时间点。""",
        "moments": """刚剪完一段视频，感觉还不错～

几个高光时刻都抓到了，节奏也调得挺顺。

生活就是要这样，把平凡的日子剪出仪式感 ✨""",
    }
    
    st.markdown('<div class="result-stage">', unsafe_allow_html=True)
    
    # 头部
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"""
        <div class="result-title">
            <div class="icon">{ICONS['check']}</div>
            <span>分析完成</span>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("🔄 重新分析", type="secondary"):
            st.session_state.current_stage = "upload"
            st.session_state.processing_progress = 0
            st.session_state.current_step = 0
            st.session_state.auto_advance = True
            st.rerun()
    
    st.markdown('<div class="result-grid">', unsafe_allow_html=True)
    
    # 左侧：视频和关键帧
    st.markdown('<div>', unsafe_allow_html=True)
    
    # 视频播放器
    if video_path and os.path.exists(video_path):
        st.video(video_path)
    else:
        st.info("视频播放器")
    
    # 关键帧
    st.markdown('<div class="keyframes-section">', unsafe_allow_html=True)
    st.markdown("""
    <div class="section-header">
        <div class="section-title">精选关键帧</div>
        <span style="font-size: 0.875rem; color: #94A3B8;">共 4 帧</span>
    </div>
    """, unsafe_allow_html=True)
    
    frame_cols = st.columns(4)
    for i, frame in enumerate(keyframes):
        with frame_cols[i]:
            st.markdown(f"""
            <div style="
                position: relative;
                aspect-ratio: 16/9;
                border-radius: 12px;
                overflow: hidden;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <span style="font-size: 1.5rem;">🖼️</span>
                <div style="
                    position: absolute;
                    top: 0.5rem;
                    right: 0.5rem;
                    padding: 0.25rem 0.5rem;
                    background: linear-gradient(135deg, #F59E0B 0%, #F97316 100%);
                    border-radius: 6px;
                    font-size: 0.6875rem;
                    font-weight: 700;
                    color: white;
                ">{frame['score']}分</div>
                <div style="
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    padding: 0.5rem;
                    background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
                    font-size: 0.75rem;
                    color: white;
                ">{frame['time']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 右侧：文案
    st.markdown('<div class="copywriting-section">', unsafe_allow_html=True)
    
    # 平台标签
    tab_cols = st.columns(4)
    for i, (pid, pname) in enumerate(platforms.items()):
        with tab_cols[i]:
            if st.button(
                pname,
                key=f"tab_{pid}",
                use_container_width=True,
                type="primary" if pid == selected_platform else "secondary"
            ):
                st.session_state.selected_platform = pid
                st.rerun()
    
    # 文案内容
    current_copy = copywritings.get(selected_platform, copywritings["xiaohongshu"])
    st.text_area("", current_copy, height=200, label_visibility="collapsed")
    
    # 操作按钮
    btn_cols = st.columns(3)
    with btn_cols[0]:
        if st.button("📋 复制文案", use_container_width=True, type="primary"):
            st.success("已复制到剪贴板！")
    with btn_cols[1]:
        if st.button("🔄 换一版", use_container_width=True, type="secondary"):
            pass
    with btn_cols[2]:
        if st.button("📥 导出", use_container_width=True, type="secondary"):
            pass
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== 主应用 ====================
def main():
    """主应用入口"""
    # 初始化 session state
    if "current_stage" not in st.session_state:
        st.session_state.current_stage = "upload"
    if "selected_platform" not in st.session_state:
        st.session_state.selected_platform = "xiaohongshu"
    if "auto_advance" not in st.session_state:
        st.session_state.auto_advance = True
    
    # 注入全局样式
    inject_global_styles()
    
    # 渲染头部
    render_header()
    
    # 渲染当前阶段
    stage = st.session_state.current_stage
    
    st.markdown('<div class="stage-container">', unsafe_allow_html=True)
    
    if stage == "upload":
        render_upload_stage()
    elif stage == "processing":
        render_processing_stage()
    elif stage == "result":
        render_result_stage()
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
