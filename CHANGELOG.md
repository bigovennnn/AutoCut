# AutoCut2 开发日志 (Changelog)

## [2.2.0] - 2026-04-21

### 新增
- **video_assembler.py** - 专业视频拼接器，支持多高光片段、转场、字幕、花字
- **subtitle_generator.py** - 自动字幕生成模块
- **flower_text_effects.py** - 花字特效（发光、弹跳、脉冲、抖动）
- **audio_processor.py** - 音频后处理模块
- **video_trimmer.py** - 增强型视频剪辑器
- **prompt_manager.py** - 提示词模板管理
- **version.py** - 版本管理模块
- **MoviePy 2.x** 集成，支持专业视频拼接和转场效果

### 改进
- 重构自动剪辑为核心功能，支持多高光片段拼接
- 强制最小3个高光片段（_fill_missing_highlights）
- 阶段7使用VideoAssembler替代简单拼接
- CROSSFADE转场（0.5s）实现片段间平滑过渡
- 音频淡入淡出效果
- 8阶段流水线完善

### 修复
- MoviePy 2.1.2 API兼容性问题（CrossFadeOut/CrossFadeIn等）
- audio_processor.py 语法错误（return type annotations）

---

## [2.0.0] - 2026-04-20

### 架构变更
- **前后端分离** - 从Streamlit一体化方案迁移到独立前端+API服务器架构
- **api_server.py** - FastAPI后端服务器
- **frontend/index.html** - 独立前端界面

### 新增
- RESTful API端点（/upload, /status, /result, /download）
- 任务队列和进度追踪
- 异步后台任务处理
- CORS跨域支持

---

## [1.2.0] - 2026-04-19

### 新增
- highlight_scorer.py - 多维度评分系统
- 清晰度20%、视觉关键词15%、语音能量30%、LLM语义20%、场景转换15%

### 改进
- 改进AutoCut pipeline可靠性
- 优化高光选择算法

---

## [1.1.0] - 2026-04-18

### 新增
- minimax_client.py - MiniMax LLM适配器
- VLM帧分析能力
- 多平台文案生成（小红书、抖音、B站、朋友圈）

---

## [1.0.0] - 2026-04-17

### 初始版本
- Streamlit Web UI
- 8阶段处理流水线
- FFmpeg音视频处理
- ASR语音识别
- LLM文案生成