import os
import streamlit as st
from autocut_agent import AutoCutAgent
import time

st.set_page_config(
    page_title="AutoCut",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        * {
            box-sizing: border-box;
        }
        
        .main {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        }
        
        .stApp {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        /* Hide default Streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Typography */
        h1 {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            font-weight: 700;
            font-size: 2.5rem;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }
        
        h2 {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            font-weight: 600;
            font-size: 1.125rem;
            color: #1e293b;
            letter-spacing: -0.01em;
            margin-top: 0;
            margin-bottom: 1.5rem;
        }
        
        h3 {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            font-weight: 600;
            font-size: 1rem;
            color: #334155;
            letter-spacing: -0.01em;
            margin-top: 0;
            margin-bottom: 0.75rem;
        }
        
        .subtitle {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            font-size: 1rem;
            color: #64748b;
            font-weight: 400;
            line-height: 1.6;
        }
        
        /* Card styles */
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 
                0 1px 3px rgba(0, 0, 0, 0.04),
                0 4px 12px rgba(0, 0, 0, 0.06),
                0 16px 48px rgba(0, 0, 0, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.8);
            margin-bottom: 1.5rem;
        }
        
        .result-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 
                0 1px 3px rgba(0, 0, 0, 0.04),
                0 4px 12px rgba(0, 0, 0, 0.06),
                0 16px 48px rgba(0, 0, 0, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.8);
            margin-top: 1.5rem;
        }
        
        /* Progress bar */
        .progress-wrapper {
            margin-bottom: 2rem;
        }
        
        .progress-label-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        
        .progress-label {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.875rem;
            font-weight: 600;
            color: #1e293b;
        }
        
        .progress-percent {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        /* Status text */
        .status-container {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 1.5rem;
            border-left: 4px solid #3b82f6;
        }
        
        .status-text {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.9375rem;
            color: #1e40af;
            font-weight: 500;
            line-height: 1.5;
        }
        
        .status-text.success {
            color: #065f46;
        }
        
        .status-container.success {
            background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
            border-left-color: #10b981;
        }
        
        /* Step items */
        .steps-container {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .step-item {
            display: flex;
            align-items: center;
            padding: 0.875rem 1rem;
            border-radius: 10px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .step-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            border-radius: 3px;
            transition: all 0.3s ease;
        }
        
        .step-item.pending {
            background: #f8fafc;
            opacity: 0.5;
        }
        
        .step-item.pending::before {
            background: #cbd5e1;
        }
        
        .step-item.active {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1), 0 2px 8px rgba(59, 130, 246, 0.08);
        }
        
        .step-item.active::before {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        }
        
        .step-item.completed {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        }
        
        .step-item.completed::before {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }
        
        .step-icon {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.875rem;
            margin-right: 1rem;
            flex-shrink: 0;
            transition: all 0.3s ease;
        }
        
        .step-item.pending .step-icon {
            background: #e2e8f0;
            color: #64748b;
        }
        
        .step-item.active .step-icon {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
            animation: pulse 2s infinite;
        }
        
        .step-item.completed .step-icon {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
        }
        
        @keyframes pulse {
            0%, 100% {
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
            }
            50% {
                box-shadow: 0 4px 20px rgba(59, 130, 246, 0.6);
            }
        }
        
        .step-content {
            flex: 1;
        }
        
        .step-title {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.9375rem;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 0.125rem;
        }
        
        .step-desc {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.8125rem;
            color: #64748b;
        }
        
        /* Button styles */
        .stButton>button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border-radius: 12px;
            padding: 0.875rem 2rem;
            font-weight: 600;
            font-size: 1rem;
            border: none;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
            width: 100%;
            letter-spacing: -0.01em;
        }
        
        .stButton>button:hover {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
            transform: translateY(-1px);
        }
        
        .stButton>button:active {
            transform: translateY(0);
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }
        
        /* Input styles */
        .stSelectbox>div>div>select,
        .stFileUploader>div>div>div>div {
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            padding: 0.75rem 1rem;
            background: white;
            transition: all 0.2s ease;
        }
        
        .stSelectbox>div>div>select:focus,
        .stFileUploader>div>div>div>div:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        /* Section divider */
        .section-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, #e2e8f0 50%, transparent 100%);
            margin: 2rem 0;
        }
        
        /* Info box */
        .info-box {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 12px;
            padding: 1.25rem;
            border: 1px solid #e2e8f0;
        }
        
        .info-box-text {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.875rem;
            color: #475569;
            line-height: 1.6;
        }
        
        /* Result section */
        .result-section {
            margin-bottom: 2rem;
        }
        
        .frame-card {
            background: white;
            border-radius: 16px;
            padding: 1.25rem;
            border: 1px solid #e2e8f0;
            margin-bottom: 1rem;
            transition: all 0.2s ease;
        }
        
        .frame-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
            border-color: #cbd5e1;
        }
        
        .frame-detail-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .frame-detail-label {
            font-size: 0.8125rem;
            color: #64748b;
            font-weight: 500;
        }
        
        .frame-detail-value {
            font-size: 0.875rem;
            color: #1e293b;
            font-weight: 600;
        }
        
        /* Text area */
        .stTextArea>div>div>textarea {
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 1rem;
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            font-size: 0.9375rem;
            line-height: 1.6;
        }
        
        .stTextArea>div>div>textarea:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: #f8fafc;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
            font-weight: 600;
            color: #334155;
        }
        
        /* Top spacing */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
    </style>
""", unsafe_allow_html=True)

st.title("AutoCut")
st.markdown('<p class="subtitle">上传原始视频，智能生成社交媒体内容</p>', unsafe_allow_html=True)

if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'current_status' not in st.session_state:
    st.session_state.current_status = '等待上传视频'
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'step_states' not in st.session_state:
    st.session_state.step_states = ['pending'] * 8
if 'step_messages' not in st.session_state:
    st.session_state.step_messages = [
        '提取音频和关键帧',
        '识别视频语音内容',
        '预筛选高质量关键帧',
        '分析关键帧内容信息',
        '选择最精彩的关键帧',
        '确定最佳高光时间段',
        '裁剪生成高光视频',
        '生成社交媒体文案'
    ]
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'result_data' not in st.session_state:
    st.session_state.result_data = None

@st.cache_resource
def get_agent():
    return AutoCutAgent()

agent = get_agent()

steps = [
    {"title": "素材提取", "desc": "提取音频和关键帧"},
    {"title": "语音识别", "desc": "识别视频语音内容"},
    {"title": "关键帧筛选", "desc": "预筛选高质量关键帧"},
    {"title": "帧内容分析", "desc": "分析关键帧内容信息"},
    {"title": "精彩帧选择", "desc": "选择最精彩的关键帧"},
    {"title": "高光片段确定", "desc": "确定最佳高光时间段"},
    {"title": "视频裁剪", "desc": "裁剪生成高光视频"},
    {"title": "文案生成", "desc": "生成社交媒体文案"}
]

col1, col2 = st.columns([11, 13])

with col1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h2>素材上传与设置</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "选择视频文件",
        type=["mp4", "mov", "avi", "mkv"],
        label_visibility="collapsed"
    )
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    st.markdown('<h3>发布平台</h3>', unsafe_allow_html=True)
    platform = st.selectbox(
        "",
        ["小红书", "朋友圈", "抖音", "B站"],
        index=0,
        label_visibility="collapsed"
    )
    
    st.markdown('<h3>文案风格</h3>', unsafe_allow_html=True)
    style = st.selectbox(
        "",
        ["温馨治愈", "活泼俏皮", "专业严谨", "文艺复古", "潮流时尚"],
        index=0,
        label_visibility="collapsed"
    )
    
    st.markdown('<div style="height: 1.5rem;"></div>', unsafe_allow_html=True)
    generate_btn = st.button("开始处理")
    
    if not uploaded_file:
        st.markdown('''
            <div class="info-box" style="margin-top: 1.5rem;">
                <p class="info-box-text">支持 MP4、MOV、AVI、MKV 格式的视频文件。上传后选择目标平台和文案风格，即可一键生成社交媒体内容。</p>
            </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<h2>处理进度</h2>', unsafe_allow_html=True)
    
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    steps_placeholder = st.empty()
    
    def render_progress():
        with progress_placeholder.container():
            st.markdown(f'''
                <div class="progress-wrapper">
                    <div class="progress-label-row">
                        <span class="progress-label">整体进度</span>
                        <span class="progress-percent">{st.session_state.progress}%</span>
                    </div>
                </div>
            ''', unsafe_allow_html=True)
            st.progress(st.session_state.progress / 100)
    
    def render_status():
        status_class = 'success' if st.session_state.processing_complete else ''
        with status_placeholder.container():
            st.markdown(f'''
                <div class="status-container {status_class}">
                    <p class="status-text {status_class}">{st.session_state.current_status}</p>
                </div>
            ''', unsafe_allow_html=True)
    
    def render_steps():
        steps_html = '<div class="steps-container">'
        for i, step in enumerate(steps):
            state = st.session_state.step_states[i]
            icon = str(i + 1)
            if state == 'completed':
                icon = '✓'
            
            desc = st.session_state.step_messages[i]
            
            steps_html += f'''
                <div class="step-item {state}">
                    <div class="step-icon">{icon}</div>
                    <div class="step-content">
                        <div class="step-title">{step["title"]}</div>
                        <div class="step-desc">{desc}</div>
                    </div>
                </div>
            '''
        steps_html += '</div>'
        
        with steps_placeholder.container():
            st.markdown(steps_html, unsafe_allow_html=True)
    
    render_progress()
    render_status()
    render_steps()
    
    st.markdown('</div>', unsafe_allow_html=True)

def update_progress(step_num, message, progress):
    st.session_state.progress = progress
    st.session_state.current_step = step_num
    st.session_state.current_status = message
    
    for i in range(8):
        if i < step_num - 1:
            st.session_state.step_states[i] = 'completed'
        elif i == step_num - 1:
            st.session_state.step_states[i] = 'active'
        else:
            st.session_state.step_states[i] = 'pending'
    
    st.session_state.step_messages[step_num - 1] = message
    
    render_progress()
    render_status()
    render_steps()

if uploaded_file is not None and generate_btn:
    try:
        for i in range(8):
            st.session_state.step_states[i] = 'pending'
            st.session_state.step_messages[i] = steps[i]['desc']
        st.session_state.processing_complete = False
        st.session_state.progress = 0
        
        os.makedirs("uploads", exist_ok=True)
        video_path = os.path.join("uploads", uploaded_file.name)
        
        with open(video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        agent.set_progress_callback(update_progress)
        result = agent.process_video(video_path, platform, style)
        
        st.session_state.current_status = '处理完成！所有步骤已成功执行'
        st.session_state.processing_complete = True
        st.session_state.progress = 100
        st.session_state.result_data = result
        
        for i in range(8):
            st.session_state.step_states[i] = 'completed'
        
        render_progress()
        render_status()
        render_steps()
        
    except Exception as e:
        st.session_state.current_status = f'处理出错: {str(e)}'
        render_status()
        st.exception(e)

if st.session_state.processing_complete and st.session_state.result_data:
    result = st.session_state.result_data
    
    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    st.markdown('<h2>处理结果</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="result-section">', unsafe_allow_html=True)
    st.markdown('<h3>高光视频</h3>', unsafe_allow_html=True)
    if result['trimmed_video'] and os.path.exists(result['trimmed_video']):
        st.video(result['trimmed_video'])
    else:
        st.warning("视频裁剪失败，请检查 FFmpeg 配置")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="result-section">', unsafe_allow_html=True)
    st.markdown('<h3>精选关键帧</h3>', unsafe_allow_html=True)
    if 'frames_with_analysis' in result and result['frames_with_analysis']:
        for idx, frame_data in enumerate(result['frames_with_analysis']):
            img_path = frame_data['path']
            if os.path.exists(img_path):
                st.markdown('<div class="frame-card">', unsafe_allow_html=True)
                frame_col1, frame_col2 = st.columns([1, 2])
                with frame_col1:
                    st.image(img_path, caption=f"关键帧 {idx+1}", use_column_width=True)
                with frame_col2:
                    st.markdown(f'''
                        <div class="frame-detail-row">
                            <span class="frame-detail-label">时间区间</span>
                            <span class="frame-detail-value">{frame_data["time_interval"]["start"]:.1f}s - {frame_data["time_interval"]["end"]:.1f}s</span>
                        </div>
                    ''', unsafe_allow_html=True)
                    if 'content_score' in frame_data:
                        st.markdown(f'''
                            <div class="frame-detail-row">
                                <span class="frame-detail-label">精彩度评分</span>
                                <span class="frame-detail-value">{frame_data["content_score"]:.2f}</span>
                            </div>
                        ''', unsafe_allow_html=True)
                    st.markdown(f'''
                        <div class="frame-detail-row">
                            <span class="frame-detail-label">清晰度</span>
                            <span class="frame-detail-value">{frame_data["clarity"]:.2f}</span>
                        </div>
                    ''', unsafe_allow_html=True)
                    st.markdown(f'''
                        <div style="margin-top: 0.75rem;">
                            <span class="frame-detail-label">内容描述</span>
                            <p style="font-size: 0.875rem; color: #334155; margin-top: 0.25rem; line-height: 1.5;">{frame_data["description"]}</p>
                        </div>
                    ''', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    elif result['best_frames']:
        img_cols = st.columns(len(result['best_frames']))
        for idx, img_path in enumerate(result['best_frames']):
            if os.path.exists(img_path):
                img_cols[idx].image(img_path, caption=f"关键帧 {idx+1}", use_column_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="result-section">', unsafe_allow_html=True)
    st.markdown('<h3>生成文案</h3>', unsafe_allow_html=True)
    st.text_area(
        "",
        result['copywriting'],
        height=200,
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="result-section">', unsafe_allow_html=True)
    with st.expander("查看详细处理信息"):
        st.write(f"**高光时间段：** {result['highlight']['start']}s - {result['highlight']['end']}s")
        st.write(f"**选择理由：** {result['highlight'].get('reason', 'N/A')}")
        st.write(f"**画面分析：** {result['image_analysis']}")
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h3>系统状态</h3>', unsafe_allow_html=True)
        
        api_key = os.getenv("LLM_API_KEY", "")
        has_valid_api = api_key and api_key != "your_api_key_here"
        
        if not has_valid_api:
            st.info("""
            语音识别已正常工作（使用本地Whisper模型）

            如需更好的画面分析和智能文案，请配置API Key：
            1. 编辑 `config.env`
            2. 填入你的 `LLM_API_KEY` 和 `VLM_API_KEY`
            3. 重启应用即可
            """)
        else:
            st.success("所有功能正常")
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown('<h3>语音内容</h3>', unsafe_allow_html=True)
        st.write(result['transcription']['full_text'])
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
