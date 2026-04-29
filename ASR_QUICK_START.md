# 🔊 AutoCut 语音识别 - 快速开始指南

## 🎯 问题解决

之前系统总是返回预设的假文字（"今天天气真的很好..."），现在已经修复！

---

## 💡 两种使用方式

### 方式一：本地 Whisper 模型（推荐，免费）

**无需 API Key！** 首次运行会自动下载模型。

#### 步骤：

1. **安装依赖**
   ```bash
   pip install openai-whisper torch
   ```

2. **已配置好！** 
   - `config.env` 已默认设置 `ASR_DEFAULT_BACKEND=whisper_local`
   - 模型大小：`base` (74MB，平衡速度和准确率)

3. **启动应用**
   ```bash
   streamlit run app.py
   ```

4. **上传视频**
   - 首次处理视频时会自动下载模型
   - 后续处理会快很多

---

### 方式二：阿里云 ASR（更快更准）

如果需要更快的识别速度和更高的准确率，可以使用阿里云 ASR。

#### 步骤：

1. **获取 API Key**
   - 访问：https://bailian.console.aliyun.com/
   - 注册并开通 "百炼" 服务
   - 获取 API Key

2. **配置 API Key**
   编辑 `config.env` 文件：
   ```env
   ASR_API_KEY=sk-你的实际API密钥
   ASR_DEFAULT_BACKEND=aliyun_paraformer_v2
   ```

3. **启动应用**
   ```bash
   streamlit run app.py
   ```

---

## 🚀 快速设置脚本

也可以使用交互式设置脚本：

```bash
python setup_asr.py
```

这个脚本会帮助你：
- ✅ 创建 config.env 文件
- ✅ 安装 Whisper 本地模型
- ✅ 配置阿里云 ASR
- ✅ 测试语音识别功能

---

## 🔍 如何知道是否在使用真实ASR？

1. **查看界面提示**
   - 在 "处理详情" 中，如果使用了模拟数据，会显示黄色警告
   - 警告会告诉你如何启用真实ASR

2. **查看控制台输出**
   运行时会看到：
   ```
   🔊 尝试使用 whisper_local 进行语音识别...
   ✅ 语音识别完成，使用后端: whisper_local
   ```

---

## ⚙️ 配置选项说明

在 `config.env` 中可以调整：

### Whisper 模型大小
```env
# 更小更快
WHISPER_MODEL_SIZE=tiny    # 39MB

# 平衡（推荐）
WHISPER_MODEL_SIZE=base    # 74MB

# 更准确
WHISPER_MODEL_SIZE=small   # 244MB
WHISPER_MODEL_SIZE=medium  # 769MB
WHISPER_MODEL_SIZE=large   # 1550MB
```

### 设备选择
```env
# CPU（默认，兼容性好）
WHISPER_DEVICE=cpu

# NVIDIA GPU（更快，需要CUDA）
WHISPER_DEVICE=cuda
```

---

## 📊 性能对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **本地 Whisper** | 免费、无需网络、隐私好 | 首次需下载模型、速度中等 | 个人使用、隐私敏感 |
| **阿里云 ASR** | 速度快、准确率高 | 需要API Key、有费用 | 商业使用、大批量处理 |

---

## ❓ 常见问题

### Q: 为什么还是显示模拟数据？
A: 检查：
1. 是否安装了 `openai-whisper` 和 `torch`？
2. `config.env` 中的 `ASR_DEFAULT_BACKEND` 是否设置正确？
3. 查看控制台的错误信息

### Q: Whisper 下载太慢怎么办？
A: 
- 可以手动下载模型放到 `~/.cache/whisper/`
- 或者先使用 `tiny` 模型测试

### Q: 可以同时配置两种方式吗？
A: 可以！系统会自动降级：
- 优先使用配置的后端
- 失败后自动尝试其他后端
- 最后才使用模拟数据

---

## 🎉 开始使用

现在你可以：

```bash
# 1. 安装 Whisper（如果还没安装）
pip install openai-whisper torch

# 2. 启动应用
streamlit run app.py

# 3. 上传你的奥运会颁奖视频
# 4. 享受真实的语音识别！
```

有问题？查看 `ASR_IMPROVEMENT_REPORT.md` 了解更多技术细节！
