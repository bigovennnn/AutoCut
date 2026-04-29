
# AutoCut - 多模态内容生成智能体

专为社交媒体内容创作定制的端到端全链路自动化 Web 应用。

## ✨ 功能特性

- 🎬 **智能视频剪辑**：基于完整音画分析自动识别高光片段，精准裁剪
- 📸 **关键帧提取**：无帧数限制，每秒1帧精确提取，结合内容精彩度智能筛选
- 🎤 **语音识别**：ASR 自动转录，带时间戳的分段字幕
- 🤖 **多模态理解**：视觉语言模型（VLM）分析画面，音画联合对齐
- 🎯 **内容评分机制**：清晰度（30%）+ 画面精彩度 + 语音内容综合评分
- ✍️ **文案生成**：一键生成小红书/朋友圈/抖音/B站风格文案

---

## 🏗️ 项目架构详解

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层 (Web UI)                          │
│                     Streamlit (app.py)                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      智能体层 (AutoCutAgent)                    │
│                   autocut_agent.py                               │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐    │
│  │ 语音识别   │→ │ 关键帧分析 │→ │ 高光选择 & 文案生成 │    │
│  │ (ASR API)  │  │ (VLM API)  │  │ (LLM + LangChain)   │    │
│  └────────────┘  └────────────┘  └──────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    媒体处理层 (MediaProcessor)                    │
│                    media_processor.py                             │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │  音频提取      │  │  关键帧抽取    │  │  图片质量筛选   │  │
│  │  (FFmpeg)      │  │  (FFmpeg)      │  │  (OpenCV)       │  │
│  └────────────────┘  └────────────────┘  └─────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      AI 模型层 (云端 API)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐                  │
│  │   LLM    │  │   ASR    │  │     VLM      │                  │
│  │(DeepSeek)│  │(Paraformer│  │(Qwen-VL)     │                  │
│  └──────────┘  └──────────┘  └──────────────┘                  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 📁 核心模块详解

### 1. app.py - Web 交互层

**职责**：Streamlit 前端界面，用户交互入口

**主要功能**：
- 视频文件上传（支持 MP4、MOV、AVI、MKV）
- 参数配置（发布平台、文案风格）
- 处理进度实时展示
- 结果可视化（高光视频、关键帧、文案）

**关键组件**：
```
- 文件上传器
- 参数选择器（平台/风格）
- 进度条 + 状态文本
- 结果展示区（视频/图片/文案）
```

---

### 2. autocut_agent.py - 智能体核心层

**职责**：业务逻辑编排，AI 能力整合

**核心类**：`AutoCutAgent`

#### 8 阶段处理流水线

```
阶段 1: 📥 素材提取
   ├─ extract_audio()       → 提取音频为 16kHz WAV
   └─ extract_keyframes()   → 无限制每秒1帧提取

阶段 2: 🎤 语音识别
   └─ transcribe_audio()    → ASR API 转录 + 时间戳

阶段 3: 🔍 清晰度预筛选
   └─ filter_best_images()  → Top 15 清晰帧（控制 API 成本）

阶段 4: 🎨 候选帧分析
   └─ analyze_frames_with_timestamps()
      ├─ 时间对齐 → align_frame_with_transcription()
      ├─ 音画联合 → VLM API 分析
      └─ 生成描述 + 时间区间标注

阶段 5: 🎯 内容精彩度筛选
   └─ select_best_frames_by_content()
      ├─ 评分维度：
      │  ├─ 清晰度 (30%)
      │  ├─ 画面精彩关键词
      │  └─ 语音内容精彩度
      └─ 输出 Top 5 精彩帧

阶段 6: ✨ 高光选择（基于完整分析）
   └─ find_highlight_with_full_analysis()
      ├─ 输入：所有候选帧分析 + 语音转录
      ├─ LLM 综合判断
      └─ 输出：start/end 时间 + 选择理由

阶段 7: ✂️ 视频裁剪
   └─ trim_video()
      ├─ FFmpeg 流复制 (c='copy')
      └─ 无重编码，速度快，画质无损

阶段 8: 📝 文案生成
   └─ generate_copywriting()
      ├─ 输入：画面分析 + 语音内容
      ├─ 平台/风格定制
      └─ 输出：可直接发布的文案
```

#### 关键算法

**1. 时间对齐算法** (`align_frame_with_transcription`)
```python
输入：帧时间戳 + 语音片段列表
逻辑：
  - 精确匹配：帧在语音片段时间区间内 → 直接返回
  - 最近邻：计算帧到各语音片段的距离 → 返回最近
输出：最相关的语音片段
```

**2. 内容精彩度评分** (`select_best_frames_by_content`)
```
评分公式：
  总分 = 清晰度分×0.3 + 画面精彩分 + 语音精彩分

- 清晰度分：min(清晰度/200, 1.0)
- 画面精彩分：检测关键词（精彩/激动/燃/震撼等）→ +0.2
- 语音精彩分：检测关键词（太棒了/厉害/完美等）→ +0.3
```

**3. 音画联合高光选择** (`find_highlight_with_full_analysis`)
```
Prompt 输入：
  ├─ 完整语音转录（带时间戳）
  └─ 所有候选帧分析（时间+画面描述）

要求：
  ├─ 结合语音和画面综合判断
  ├─ 时长 3-10 秒
  └─ JSON 格式输出
```

---

### 3. media_processor.py - 媒体处理层

**职责**：本地媒体文件处理，FFmpeg + OpenCV 封装

**核心类**：`MediaProcessor`

| 方法 | 功能 | 技术栈 |
|------|------|--------|
| `extract_audio()` | 提取音频为 16kHz 单声道 WAV | FFmpeg |
| `extract_keyframes()` | 无限制每秒1帧抽帧 | FFmpeg |
| `filter_best_images()` | 拉普拉斯方差筛选清晰度 | OpenCV |

#### 关键技术细节

**音频提取参数**：
```
acodec='pcm_s16le'  # PCM 16位编码（ASR 最佳格式）
ac=1                 # 单声道
ar='16k'             # 16kHz 采样率
```

**关键帧提取**：
```
fps=1                # 每秒1帧
vframes=无限制       # 移除原 50 帧限制
q:v=2                # JPG 高质量
```

**清晰度评估**：
```python
# 拉普拉斯方差算法
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
fm = cv2.Laplacian(gray, cv2.CV_64F).var()
# 方差越大 → 边缘越丰富 → 图片越清晰
```

---

### 4. agentcore.py - LLM 基础设施

**职责**：统一 LLM 接口，Prompt 模板管理

**核心函数**：
- `get_llm()` - 初始化 ChatOpenAI 客户端（兼容各类 OpenAI 格式 API）
- `get_copywriting_prompt()` - 文案生成 Prompt 模板

**LLM 配置**：
```
model: qwen-turbo (可配置)
temperature: 0.8
max_tokens: 1024
```

---

## 📂 完整项目结构

```
AutoCut/
├── app.py                          # Streamlit Web 界面
├── autocut_agent.py                # 智能体核心逻辑（8阶段流水线）
│   ├── AutoCutAgent
│   │   ├── transcribe_audio()      # ASR 语音识别
│   │   ├── align_frame_with_transcription()  # 时间对齐
│   │   ├── analyze_frames_with_timestamps() # 关键帧分析
│   │   ├── select_best_frames_by_content()  # 内容评分筛选
│   │   ├── find_highlight_with_full_analysis() # 高光选择
│   │   ├── trim_video()            # 视频裁剪
│   │   ├── generate_copywriting()   # 文案生成
│   │   └── process_video()         # 主流程编排
├── media_processor.py               # 媒体处理引擎
│   └── MediaProcessor
│       ├── extract_audio()         # 音频提取
│       ├── extract_keyframes()     # 关键帧提取
│       └── filter_best_images()    # 清晰度筛选
├── agentcore.py                     # LLM 基础设施
│   ├── get_llm()
│   └── get_copywriting_prompt()
├── config.env.example               # 配置文件模板
├── requirements.txt                 # Python 依赖
├── test_scheme3.py                  # 方案3功能测试脚本
├── temp_workspace/                  # 临时工作目录（自动创建）
│   ├── *.wav                        # 提取的音频
│   └── frames/                      # 提取的关键帧
└── uploads/                         # 上传文件目录（自动创建）
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 FFmpeg

- **Windows**: 下载 FFmpeg 并添加到系统 PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`

### 3. 配置 API Key

复制 `config.env.example` 为 `config.env`，填入 API Key：

```env
# LLM 配置（文案生成/高光选择）
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.deepseek.com/v1

# ASR 配置（语音识别，可选）
ASR_API_KEY=your_asr_api_key
ASR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions

# VLM 配置（画面分析，可选，默认复用 LLM）
VLM_API_KEY=your_vlm_api_key
VLM_BASE_URL=your_vlm_base_url
```

### 4. 运行应用

```bash
streamlit run app.py
```

然后在浏览器中打开显示的地址（通常是 http://localhost:8501）

---

## 📊 数据流图

```
输入视频
   │
   ├─→ [MediaProcessor.extract_audio] → 音频文件
   │                                  ↓
   │                          [ASR API] → 转录文本 + 时间戳
   │
   └─→ [MediaProcessor.extract_keyframes] → 所有关键帧（无限制）
                                          ↓
                                  [MediaProcessor.filter_best_images]
                                          ↓
                                  Top 15 清晰帧（预筛选）
                                          ↓
                          [AutoCutAgent.analyze_frames_with_timestamps]
                                          ↓
                    音画联合分析 → 候选帧（带描述+时间）
                                          ↓
                          [AutoCutAgent.select_best_frames_by_content]
                                          ↓
                          Top 5 精彩帧（基于内容评分）
                                          ↓
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ↓                                 ↓                                 ↓
[VLM 整体画面分析]          [LLM 高光选择（完整分析）]          [LLM 文案生成]
        ↓                                 ↓                                 ↓
   画面描述                        高光时间区间                        平台定制文案
        ↓                                 ↓                                 ↓
        └─────────────────────────────────┼─────────────────────────────────┘
                                          ↓
                              最终输出结果
                              ├─ 高光视频
                              ├─ 5 张精彩关键帧（带时间+描述+评分）
                              └─ 可直接发布的文案
```

---

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Streamlit | 本地 Web UI，快速原型 |
| **编排** | LangChain | LLM 应用框架，LCEL 语法 |
| **媒体处理** | FFmpeg | 音视频处理，流复制裁剪 |
| **图像处理** | OpenCV | 拉普拉斯方差清晰度评估 |
| **LLM** | ChatOpenAI 兼容 | 支持 DeepSeek/Qwen/豆包等 |
| **ASR** | Paraformer-v2 | 阿里云语音识别（可选） |
| **VLM** | Qwen-VL / GPT-4V | 视觉语言模型（可选） |

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | 是 | 大语言模型 API Key |
| `LLM_BASE_URL` | 是 | API 基础 URL |
| `ASR_API_KEY` | 否 | 语音识别 API Key（无则用模拟数据） |
| `ASR_BASE_URL` | 否 | ASR API URL |
| `VLM_API_KEY` | 否 | 视觉模型 API Key（默认复用 LLM） |
| `VLM_BASE_URL` | 否 | VLM API URL |

---

## 📝 使用说明

1. 上传视频文件（支持 MP4、MOV、AVI、MKV 格式）
2. 选择目标发布平台（小红书/朋友圈/抖音/B站）
3. 选择文案风格（温馨治愈/活泼俏皮/专业严谨等）
4. 点击「一键生成」
5. 查看生成的高光视频、关键帧（带时间标注+精彩度评分）和文案
6. 复制文案，直接发布！

---

## ⚠️ 注意事项

- 视频处理在本地完成，不会上传到云端（仅 API 调用上传文本/编码图片）
- 首次运行需要配置 API Key
- 建议使用较短的视频进行测试（长视频会增加 API 成本）
- 关键帧提取无帧数限制，但预筛选为 Top 15 以控制 API 调用量

---

## 🧪 测试

运行方案3功能测试：

```bash
python test_scheme3.py
```

---

## 📄 许可证

本项目仅供学习和研究使用。

