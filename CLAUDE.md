# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## GitHub Repository
**URL**: https://github.com/bigovennnn/AutoCut

## Project Overview

AutoCut is a multi-modal content generation agent for social media content creation. It automatically identifies highlight segments from videos and generates platform-specific copy (Xiaohongshu, Moments, Douyin, Bilibili).

## Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
streamlit run AutoCut/app.py
```

### Testing
```bash
python AutoCut/test_scheme3.py
```

### Prerequisites
- FFmpeg must be installed and added to system PATH
- Python 3.10+

### Configuration
Copy `AutoCut/config.env.example` to `AutoCut/config.env` and fill in API keys:
- `LLM_API_KEY` / `LLM_BASE_URL` - LLM for copywriting and highlight selection (default: DashScope/Qwen)
- `ASR_API_KEY` / `ASR_BASE_URL` - ASR for speech recognition (optional, falls back to mock)
- `VLM_API_KEY` / `VLM_BASE_URL` - VLM for frame analysis (optional, falls back to mock)

Set `USE_MINIMAX_LLM=true` to switch to MiniMax LLM backend.

## Architecture

### 4-Layer Design

```
┌─────────────────────────────────────┐
│  User Layer: Streamlit (app.py)     │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  Agent Layer: AutoCutAgent          │
│  (autocut_agent.py)                │
│  8-stage pipeline orchestration     │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  Media Layer: MediaProcessor        │
│  (media_processor.py)              │
│  FFmpeg + OpenCV                   │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│  AI Layer: Cloud APIs              │
│  LLM (DeepSeek/Qwen)              │
│  ASR (Paraformer-v2)              │
│  VLM (Qwen-VL)                    │
└─────────────────────────────────────┘
```

### Core Components

| File | Responsibility |
|------|---------------|
| `app.py` | Streamlit web UI, user interaction |
| `autocut_agent.py` | Main agent: 8-stage pipeline (extract → transcribe → filter → analyze → score → select highlight → trim → generate copy) |
| `media_processor.py` | Audio extraction (FFmpeg), keyframe extraction (FFmpeg), clarity filtering (OpenCV Laplacian), scene change detection |
| `agentcore.py` | LLM initialization, copywriting prompt templates |
| `asr_processor.py` | Speech-to-text with multiple backend support |
| `video_trimmer.py` | FFmpeg-based video cutting |
| `highlight_scorer.py` | Multi-dimensional scoring (clarity 20%, visual keywords 15%, speech energy 30%, LLM semantics 20%, scene change proximity 15%) |

### 8-Stage Processing Pipeline (in `autocut_agent.py`)

1. **Material Extraction**: Audio (16kHz WAV) + keyframes (1fps, unlimited)
2. **Speech Recognition**: ASR transcription with timestamps
3. **Clarity Pre-filtering**: Laplacian variance filtering, keep Top 15
4. **Frame Analysis**: VLM analyzes frames aligned with speech
5. **Content Scoring**: Multi-dimensional scoring, select Top 5
6. **Highlight Selection**: LLM analyzes full audio-visual data, outputs segments
7. **Video Trimming**: FFmpeg stream copy (fast, lossless)
8. **Copywriting Generation**: LLM generates platform-specific content

### Fallback Behavior
When API keys are not configured, the system uses mock data to allow local testing without API costs.

## Directory Structure

```
AutoCut/
├── app.py                 # Web UI entry point
├── autocut_agent.py       # Main agent logic
├── media_processor.py     # FFmpeg/OpenCV wrapper
├── agentcore.py           # LLM infrastructure
├── asr_processor.py       # Speech recognition
├── video_trimmer.py       # Video cutting
├── highlight_scorer.py     # Frame scoring
├── minimax_client.py      # MiniMax LLM adapter
├── video_assembler.py     # Video assembly with transitions
├── subtitle_generator.py  # Auto subtitle generation
├── flower_text_effects.py # Stylized text effects
├── audio_processor.py     # Audio post-processing
├── version.py             # Version management
├── config.env.example     # API configuration template
├── requirements.txt       # Dependencies
├── uploads/               # Uploaded videos (auto-created)
└── temp_workspace/        # Intermediate files (auto-created)
    └── frames/            # Extracted keyframes
```

## Version Management

版本: `2.2.0`

遵循语义化版本 (Semantic Versioning):
- **MAJOR** (x.0.0): 破坏性变更，不兼容的API/架构调整
- **MINOR** (1.x.0): 新增功能，向后兼容
- **PATCH** (1.2.x): 问题修复，向后兼容

当前版本定义在 `version.py`，修改版本号后自动生效。提交时需在commit message中标注版本变化。
