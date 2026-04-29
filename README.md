# AutoCut2 - 智能视频剪辑智能体

多模态社交媒体内容生成智能体，自动识别视频高光片段，生成平台适配文案。

**当前版本：** v2.2.0

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **多高光拼接** | 自动选取 3+ 个精彩片段，智能拼接 |
| **专业转场** | CROSSFADE 交叉淡化，平滑过渡 |
| **自动字幕** | 基于 ASR 时间戳烧录字幕 |
| **花字特效** | 发光、弹跳、脉冲、抖动效果 |
| **多平台文案** | 小红书、抖音、B站、朋友圈适配 |
| **音视频后处理** | 淡入淡出、背景音乐混音 |

---

## 快速开始

### 环境要求

- Python 3.10+
- FFmpeg（添加到系统 PATH）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API Key

```bash
cp config.env.example AutoCut/config.env
# 编辑 AutoCut/config.env，填入 API 密钥
```

### 启动服务

**方式一：独立前端 + API（推荐）**
```bash
# 终端1：启动后端
python api_server.py

# 终端2：启动前端
cd frontend && python -m http.server 3000
```

访问：http://localhost:3000

**方式二：Streamlit 一体化界面**
```bash
streamlit run app.py
```

---

## 项目架构

### 4 层设计

```
┌─────────────────────────────────────┐
│  用户层：Streamlit / HTML 前端        │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  智能体层：AutoCutAgent                │
│  8阶段流水线编排                       │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  媒体层：FFmpeg + OpenCV + MoviePy    │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  AI 层：LLM + ASR + VLM              │
└───────────────────────────────────────┘
```

### 8 阶段处理流水线

```
阶段1: 素材提取 → 音频(16kHz WAV) + 关键帧(1fps)
阶段2: 语音识别 → ASR 转文字，带时间戳
阶段3: 清晰度过滤 → Laplacian 方差滤波，Top 15
阶段4: 画面分析 → VLM 分析关键帧内容
阶段5: 内容评分 → 多维度评分，Top 5
阶段6: 高光选择 → LLM 分析，输出 3+ 片段
阶段7: 视频剪辑 → FFmpeg + MoviePy 转场拼接
阶段8: 文案生成 → 平台适配文案
```

---

## 目录结构

```
AutoCut2/
├── app.py                  # Streamlit Web 界面（可选）
├── api_server.py           # FastAPI 后端服务器
├── frontend/
│   └── index.html          # 独立前端界面
├── autocut_agent.py        # 核心智能体
├── media_processor.py      # FFmpeg/OpenCV 封装
├── video_trimmer.py        # FFmpeg 视频剪辑
├── video_assembler.py       # MoviePy 专业拼接
├── subtitle_generator.py    # 自动字幕生成
├── flower_text_effects.py  # 花字特效
├── audio_processor.py      # 音频后处理
├── moviepy_processor.py    # MoviePy 2.x 封装
├── agentcore.py            # LLM 基础设施
├── asr_processor.py        # 语音识别
├── highlight_scorer.py     # 多维度评分
├── minimax_client.py       # MiniMax LLM 适配器
├── prompt_manager.py       # 提示词管理
├── version.py              # 版本管理
├── CHANGELOG.md           # 开发日志
├── CLAUDE.md              # 开发者指南
├── DEPLOYMENT_GUIDE.md    # 本地部署指南
├── README_FOR_TEAM.md     # 团队共享文档
├── requirements.txt       # Python 依赖
└── config.env.example     # 配置模板
```

---

## 核心模块

### 视频拼接 (video_assembler.py)

| 功能 | 说明 |
|------|------|
| 多片段拼接 | 支持 3+ 高光片段 |
| 转场效果 | CROSSFADE / WIPE / SLIDE |
| 淡入淡出 | 可配置时长 |
| 字幕烧录 | TextClip 渲染 |

### 花字特效 (flower_text_effects.py)

| 效果 | 说明 |
|------|------|
| `create_glow()` | 多层霓虹发光 |
| `create_bounce()` | 正弦弹跳动画 |
| `create_pulse()` | 节律缩放动画 |
| `create_shake()` | 水平抖动 |

### 高光评分 (highlight_scorer.py)

| 维度 | 权重 |
|------|------|
| 清晰度 | 20% |
| 视觉关键词 | 15% |
| 语音能量 | 30% |
| LLM 语义 | 20% |
| 场景转换接近度 | 15% |

---

## AI 模型配置

| 模型 | 用途 | 默认方案 |
|------|------|----------|
| **LLM** | 文案生成 + 高光选择 | DeepSeek / DashScope Qwen |
| **ASR** | 语音识别 | DashScope Paraformer-v2 |
| **VLM** | 画面分析 | DashScope Qwen-VL |

### 本地化方案

| 云端 | 本地替代 |
|------|----------|
| LLM → DeepSeek/Qwen | Ollama + DeepSeek-R1 |
| ASR → DashScope | Whisper |
| VLM → Qwen-VL | LLaVA |

详见 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit + HTML/CSS/JS |
| 后端 | FastAPI |
| 媒体处理 | FFmpeg + OpenCV + MoviePy 2.x |
| LLM 编排 | LangChain (PromptTemplate + JSON Parser) |
| AI 模型 | DeepSeek / DashScope / MiniMax |

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2.2.0 | 2026-04-21 | 多高光拼接、VideoAssembler、转场、字幕、花字 |
| v2.0.0 | 2026-04-20 | 前后端分离架构 |
| v1.2.0 | 2026-04-19 | highlight_scorer 多维评分 |
| v1.1.0 | 2026-04-18 | MiniMax LLM + VLM |
| v1.0.0 | 2026-04-17 | 初始版本，Streamlit 一体化 |

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 团队分工

| 模块 | 优先级 |
|------|--------|
| 核心流水线 | P0 |
| 视频拼接 | P0 |
| 前端界面 | P1 |
| ASR 本地化 | P1 |
| LLM 本地化 | P2 |
| 效果增强 | P2 |

详见 [README_FOR_TEAM.md](README_FOR_TEAM.md)

---

## License

MIT License
