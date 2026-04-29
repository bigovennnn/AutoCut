# 🚀 NVIDIA GPU 快速设置指南

## ✅ 好消息！你的配置已经正确！

你的 `config.env` 已经设置好了：
```env
WHISPER_DEVICE=cuda
```

---

## 📋 三步启用GPU加速

### 第1步：检查GPU状态

运行检查脚本：
```bash
python check_gpu.py
```

这个脚本会告诉你：
- PyTorch是否安装
- CUDA是否可用
- 你的GPU型号
- Whisper是否正常

---

### 第2步：如果需要，安装CUDA版PyTorch

如果 `check_gpu.py` 显示CUDA不可用，运行：

```bash
python install_cuda_torch.py
```

这个脚本会自动尝试安装适合你系统的CUDA版PyTorch。

如果自动安装失败，可以：
1. 访问 https://pytorch.org/get-started/locally/
2. 选择：
   - OS: Windows
   - Package: Pip
   - Language: Python
   - Compute Platform: 你的CUDA版本（比如 11.8 或 12.1）
3. 复制并运行给出的命令

---

### 第3步：享受GPU加速！

重新运行应用：
```bash
streamlit run app.py
```

处理视频时你会看到：
```
✅ 使用GPU: NVIDIA GeForce RTX xxxx
🔧 加载 Whisper 模型: base (设备: cuda)
```

---

## ⚡ 性能对比

| 设备 | 处理速度 | 适用场景 |
|------|---------|---------|
| **CPU** | 基准速度 | 没有GPU时 |
| **GPU** | 快5-10倍 ⚡ | 推荐！ |

---

## 🎛️ 模型大小选择

根据你的GPU显存选择合适的模型：

| 模型 | 显存需求 | 速度 | 准确率 |
|------|---------|------|--------|
| `tiny` | ~1GB | 最快 | ⭐⭐ |
| `base` | ~1GB | 快 | ⭐⭐⭐ |
| `small` | ~2GB | 中等 | ⭐⭐⭐⭐ |
| `medium` | ~5GB | 较慢 | ⭐⭐⭐⭐⭐ |
| `large` | ~10GB | 最慢 | ⭐⭐⭐⭐⭐⭐ |

修改 `config.env` 中的：
```env
WHISPER_MODEL_SIZE=base   # 或 small, medium, large
```

---

## 🔍 常见问题

### Q: 还是显示用CPU？
A: 运行 `python check_gpu.py` 检查：
1. 是否安装了CUDA版PyTorch？
2. NVIDIA驱动是否最新？
3. CUDA版本是否匹配？

### Q: 显存不足怎么办？
A: 改用更小的模型：
```env
WHISPER_MODEL_SIZE=tiny   # 或 base
```

### Q: 想知道GPU用了多少？
A: 打开另一个PowerShell运行：
```bash
nvidia-smi
```

---

## 📁 相关文件

- `check_gpu.py` - 检查GPU状态
- `install_cuda_torch.py` - 安装CUDA版PyTorch
- `config.env` - 配置文件（已设置为cuda）

---

## 🎉 开始使用

现在就试试吧！
```bash
# 1. 检查GPU
python check_gpu.py

# 2. 启动应用
streamlit run app.py

# 3. 上传视频，享受GPU加速！
```
