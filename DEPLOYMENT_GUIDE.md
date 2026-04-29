# AutoCut2 本地部署指南

## 方案一：快速开始（使用云端API）

### 1. 环境准备
```bash
# Python 3.10+
python --version

# FFmpeg
ffmpeg -version
# 若未安装：https://ffmpeg.org/download.html
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置API密钥
```bash
# 复制配置模板
cp config.env.example AutoCut/config.env

# 编辑配置（根据需要选择服务商）
nano AutoCut/config.env
```

配置项说明：
```env
# LLM配置（文案生成+高光选择）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com  # 或 DashScope/MiniMax

# ASR配置（语音识别，可选）
ASR_API_KEY=your_asr_key
ASR_BASE_URL=https://dashscope.aliyuncs.com

# VLM配置（图画分析，可选）
VLM_API_KEY=your_vlm_key
VLM_BASE_URL=https://dashscope.aliyuncs.com
```

### 4. 启动服务
```bash
# 后端API服务
python api_server.py

# 前端（另一个终端）
cd frontend && python -m http.server 3000
```

访问：http://localhost:3000

---

## 方案二：完全本地化部署（无API费用）

### 2.1 安装 Whisper（ASR本地化）
```bash
pip install openai-whisper
python install_whisper.py  # 下载模型
```

### 2.2 安装 Ollama（LLM本地化）
```bash
# 下载 Ollama：https://ollama.ai/download
ollama pull deepseek-r1:7b      # 下载模型（约6GB）
ollama pull qwen2.5:7b          # 或使用通义千问
```

### 2.3 修改配置
```bash
nano AutoCut/config.env
```

```env
# 切换到本地模式
USE_MINIMAX_LLM=false
USE_WHISPER=true
USE_LOCAL_LLM=true

# Ollama配置
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=deepseek-r1:7b

# Whisper配置
ASR_MODEL=base
```

### 2.4 启动
```bash
# 确保 Ollama 服务运行
ollama serve

# 启动 AutoCut
python api_server.py
```

---

## 方案三：GPU加速部署（推荐）

适用于有NVIDIA显卡的机器

### 3.1 安装 CUDA + PyTorch
```bash
python install_cuda_torch.py
```

### 3.2 启用GPU支持
```bash
python check_gpu.py
# 应输出 GPU 信息
```

### 3.3 修改配置
```env
# 启用GPU加速
USE_GPU=true
DEVICE=cuda

# Whisper使用GPU
ASR_MODEL=medium  # 更大的模型，但更快
```

---

## Docker 部署（可选）

### Dockerfile
```dockerfile
FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y ffmpeg

# 复制代码
COPY . /app
WORKDIR /app

# 安装Python依赖
RUN pip install -r requirements.txt

# 暴露端口
EXPOSE 8000 3000

# 启动
CMD ["python", "api_server.py"]
```

### 构建运行
```bash
docker build -t autocut2 .
docker run -p 8000:8000 -p 3000:3000 autocut2
```

---

## 环境变量速查表

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_MINIMAX_LLM` | `false` | 使用MiniMax后端 |
| `USE_WHISPER` | `false` | 使用Whisper ASR |
| `USE_LOCAL_LLM` | `false` | 使用Ollama本地LLM |
| `USE_GPU` | `false` | 启用GPU加速 |
| `DEVICE` | `cuda` | 设备类型：cuda/cpu |
| `LLM_MODEL` | `deepseek-chat` | LLM模型名称 |
| `ASR_MODEL` | `base` | Whisper模型：tiny/base/small/medium/large |

---

## 性能对比

| 配置 | 处理10分钟视频 | 月成本 |
|------|----------------|--------|
| 全云端API | ~5分钟 | ~¥50 |
| Whisper本地+云LLM | ~8分钟 | ~¥30 |
| 全本地（CPU） | ~15分钟 | ¥0 |
| 全本地（GPU） | ~3分钟 | ¥0 |
