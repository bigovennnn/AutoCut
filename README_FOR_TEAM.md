# AutoCut2 团队共享文档

## 项目概述

AutoCut2 是一个多模态社交媒体内容生成智能体，能自动从视频中识别高光片段并生成平台适配文案。

**当前版本：** v2.2.0

---

## 项目结构

```
AutoCut2/
├── app.py                 # Streamlit Web界面（可选旧版）
├── api_server.py          # FastAPI 后端服务器（新版推荐）
├── autocut_agent.py       # 核心智能体，8阶段处理流水线
├── media_processor.py      # 音视频处理（FFmpeg/OpenCV）
├── agentcore.py           # LLM 初始化与提示词模板
├── asr_processor.py       # 语音识别（ASR）
├── video_trimmer.py       # 视频剪辑
├── video_assembler.py     # 视频拼接（多片段+转场+字幕）
├── subtitle_generator.py  # 自动字幕生成
├── flower_text_effects.py # 花字特效（发光/弹跳/脉冲/抖动）
├── audio_processor.py     # 音频后处理
├── moviepy_processor.py   # MoviePy 2.x 封装
├── prompt_manager.py      # 提示词管理
├── highlight_scorer.py    # 多维度高光评分
├── minimax_client.py      # MiniMax LLM 适配器
├── version.py             # 版本管理
│
├── frontend/
│   └── index.html         # 独立前端界面
│
├── AutoCut/               # 旧版本目录（保留兼容）
│   └── config.env         # API密钥配置
│
├── requirements.txt       # Python 依赖
├── config.env.example     # 配置模板
├── CLAUDE.md             # 开发者指南
├── CHANGELOG.md          # 开发日志
└── README.md             # 项目主文档
```

---

## 核心文件说明

### 核心处理模块

| 文件 | 用途 | 关键类/函数 |
|------|------|-------------|
| `autocut_agent.py` | 8阶段流水线编排 | `AutoCutAgent.process_video()` |
| `media_processor.py` | 音视频处理 | `MediaProcessor.extract_audio()`, `extract_frames()` |
| `video_assembler.py` | 专业视频拼接 | `VideoAssembler.assemble()` |
| `asr_processor.py` | 语音转文字 | `ASRProcessor.transcribe()` |

### AI 能力模块

| 文件 | 用途 | 依赖 |
|------|------|------|
| `agentcore.py` | LLM 调用（DeepSeek/Qwen/MiniMax） | API Key |
| `asr_processor.py` | 语音识别 | DashScope ASR / Whisper |
| `minimax_client.py` | MiniMax LLM 适配 | MiniMax API |

### 视觉效果模块

| 文件 | 用途 | 效果 |
|------|------|------|
| `subtitle_generator.py` | 烧录字幕 | 基于 transcription 时间戳 |
| `flower_text_effects.py` | 花字特效 | 发光/弹跳/脉冲/抖动 |
| `video_assembler.py` | 转场效果 | CROSSFADE / WIPE / SLIDE |

---

## 工作原理

### 8阶段处理流水线

```
1. 材料提取 → 2. 语音识别 → 3. 清晰度过滤
     ↓
4. 画面分析 → 5. 内容评分 → 6. 高光选择
     ↓
7. 视频剪辑 → 8. 文案生成
```

1. **材料提取**：提取音频(16kHz WAV) + 关键帧(1fps)
2. **语音识别**：ASR 转文字，带时间戳
3. **清晰度过滤**：Laplacian 方差滤波，保留 Top 15
4. **画面分析**：VLM 分析关键帧内容
5. **内容评分**：多维度评分（清晰度20% + 视觉15% + 语音30% + LLM20% + 场景15%）
6. **高光选择**：LLM 综合分析，输出高光片段（最少3个）
7. **视频剪辑**：FFmpeg 快速剪辑 + MoviePy 转场拼接 + 字幕烧录
8. **文案生成**：LLM 生成平台适配文案

### 视频拼接流程

```
输入视频 → 提取高光片段 → 应用转场 → 添加字幕 → 添加花字 → 输出
```

转场类型：`CROSSFADE`（默认）/ `WIPE_LEFT` / `WIPE_RIGHT` / `SLIDE_UP` / `SLIDE_DOWN`

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
# 编辑 config.env，填入 API 密钥
```

### 启动服务

**方式一：独立前端 + API（推荐）**
```bash
# 终端1：启动后端
python api_server.py

# 终端2：启动前端服务器
python -m http.server 3000 --directory frontend
```

**方式二：Streamlit 一体化界面**
```bash
streamlit run app.py
```

---

## 未来改进方向

### 1. 本地部署（高优先级）

**目标：** 脱离云端API，纯本地运行

**方案：**
- [ ] **ASR本地化**：集成 Whisper（`pip install openai-whisper`）
  - 文件：`install_whisper.py`（已有）
  - 优势：离线可用，无API费用
- [ ] **VLM本地化**：使用 Qwen-VL 本地模型 或 LLaVA
- [ ] **LLM本地化**：Ollama + DeepSeek/Qwen 本地模型
  - 配置：`USE_OLLAMA=true`, `OLLAMA_BASE_URL=http://localhost:11434`

**难度：** ⭐⭐⭐（中等）

---

### 2. 效果增强

**目标：** 提升视频质量和观感

| 改进项 | 方案 | 难度 |
|--------|------|------|
| 智能字幕样式 | 根据内容自动选择颜色/位置 | ⭐ |
| 动态花字 | 基于语音能量自动触发动画 | ⭐⭐ |
| 背景音乐 | 智能匹配视频氛围选BGM | ⭐⭐⭐ |
| 封面生成 | 选取最精彩帧+标题字幕 | ⭐⭐ |
| 运镜效果 | 关键帧间平滑缩放/平移 | ⭐⭐ |

**相关文件：**
- `flower_text_effects.py` - 扩展花字类型
- `audio_processor.py` - 扩展BGM功能
- `video_assembler.py` - 扩展转场和特效

---

### 3. 多平台优化

**目标：** 支持更多平台，精准适配

- [ ] 微信视频号适配
- [ ] YouTube Shorts 适配
- [ ] TikTok 国际版
- [ ] Instagram Reels

**相关文件：**
- `agentcore.py` - 扩展 prompt 模板
- `prompt_manager.py` - 平台配置管理

---

### 4. 自动化流水线

**目标：** 减少人工干预

- [ ] Webhook 回调通知
- [ ] 批量处理队列
- [ ] 定时自动剪辑
- [ ] 社交平台直连发布（API集成）

**相关文件：**
- `api_server.py` - 扩展 Webhook 端点
- `frontend_server.py` - 批量处理界面

---

### 5. 性能优化

**目标：** 提升处理速度

| 优化项 | 方案 | 预期提升 |
|--------|------|----------|
| 帧提取 | GPU加速（OpenCV CUDA） | 5-10x |
| ASR | Whisper GPU推理 | 3-5x |
| 并行处理 | 多片段并行剪辑 | 2-3x |
| 缓存 | 复用已处理帧 | 按场景 |

**相关文件：**
- `check_gpu.py` - GPU 检测
- `install_cuda_torch.py` - CUDA 环境配置

---

### 6. 用户体验优化

**目标：** 降低使用门槛

- [ ] 拖拽上传
- [ ] 实时预览剪辑效果
- [ ] 进度条 + 预计剩余时间
- [ ] 历史记录管理
- [ ] 一键分享

**相关文件：**
- `frontend/index.html` - 前端界面
- `app.py` - Streamlit 界面

---

## 文件归属（团队分工参考）

| 模块 | 负责人 | 优先级 |
|------|--------|--------|
| 核心流水线（autocut_agent.py） | @bigovennnn | P0 |
| 视频拼接（video_assembler.py） | @bigovennnn | P0 |
| 前端界面（frontend/） | 待定 | P1 |
| ASR本地化（Whisper集成） | 待定 | P1 |
| LLM适配（Ollama/本地模型） | 待定 | P2 |
| 效果增强（花字/BGM） | 待定 | P2 |
| 文档完善（README/DEPLOYMENT） | @bigovennnn | P1 |

---

## 常见问题

**Q: 视频处理失败？**
- 检查 FFmpeg 是否安装：`ffmpeg -version`
- 检查 API Key 是否配置正确
- 查看终端错误日志

**Q: 如何查看处理进度？**
- API 模式：访问 `http://localhost:8000/status/{task_id}`
- Streamlit 模式：查看侧边栏进度条

**Q: 如何添加新的转场效果？**
- 编辑 `video_assembler.py` 中的 `TransitionType` 枚举
- 在对应方法中实现 `apply_*_transition()`

---

## 联系方式

- 项目负责人：bigovennnn
- GitHub：https://github.com/bigovennnn/AutoCut
- 文档：`CLAUDE.md`（开发者详细指南）
