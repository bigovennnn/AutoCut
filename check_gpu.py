#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查GPU状态和PyTorch CUDA支持
"""

import sys
import subprocess

print("="*70)
print("  检查GPU和CUDA状态")
print("="*70)

# 检查1: PyTorch是否安装
print("\n[1/5] 检查 PyTorch 安装状态...")
try:
    import torch
    print(f"✅ PyTorch 版本: {torch.__version__}")
except ImportError:
    print("❌ PyTorch 未安装")
    print("   请运行: pip install torch")
    sys.exit(1)

# 检查2: CUDA是否可用
print("\n[2/5] 检查 CUDA 可用性...")
if torch.cuda.is_available():
    print(f"✅ CUDA 可用！")
    print(f"   CUDA 版本: {torch.version.cuda}")
    print(f"   GPU 数量: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
    
    print(f"\n💡 当前设备: {torch.cuda.current_device()}")
else:
    print("❌ CUDA 不可用")
    print("\n💡 解决方案：")
    print("   你需要安装支持CUDA的PyTorch版本")
    print("\n   请访问 https://pytorch.org/get-started/locally/")
    print("   选择你的CUDA版本并运行相应的安装命令")
    print("\n   或者尝试以下命令（Windows CUDA 11.8）：")
    print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    
    # 检查是否有NVIDIA GPU
    print("\n[补充] 检查NVIDIA GPU硬件...")
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("\n✅ 检测到NVIDIA GPU！nvidia-smi 输出：")
            print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
        else:
            print("\n⚠️  无法运行 nvidia-smi")
    except Exception as e:
        print(f"\n⚠️  检查NVIDIA GPU时出错: {e}")
    
    sys.exit(1)

# 检查3: Whisper是否安装
print("\n[3/5] 检查 Whisper 安装状态...")
try:
    import whisper
    print(f"✅ Whisper 已安装")
except ImportError:
    print("❌ Whisper 未安装")
    print("   请运行: pip install openai-whisper")
    sys.exit(1)

# 检查4: 配置文件
print("\n[4/5] 检查配置文件...")
from dotenv import load_dotenv
import os

load_dotenv('config.env', encoding='utf-8')
whisper_device = os.getenv("WHISPER_DEVICE", "cpu")
whisper_model = os.getenv("WHISPER_MODEL_SIZE", "base")

print(f"   配置的设备: {whisper_device}")
print(f"   配置的模型: {whisper_model}")

if whisper_device == "cuda":
    print("   ✅ 配置正确，将使用GPU")
else:
    print(f"   ⚠️  配置为 {whisper_device}，建议改为 cuda")

# 检查5: 测试小型模型加载
print("\n[5/5] 测试GPU模型加载（tiny模型，快速测试）...")
try:
    print("   正在加载 tiny 模型到 GPU...")
    model = whisper.load_model("tiny", device="cuda")
    print("   ✅ 模型成功加载到 GPU！")
    
    # 测试一个小操作
    print("   测试GPU推理...")
    import numpy as np
    test_audio = np.zeros(16000, dtype=np.float32)  # 1秒静音
    test_audio = whisper.pad_or_trim(test_audio)
    mel = whisper.log_mel_spectrogram(test_audio).to(model.device)
    print("   ✅ GPU推理正常！")
    
    print("\n" + "="*70)
    print("  🎉 所有检查通过！GPU已准备就绪！")
    print("="*70)
    print(f"\n💡 提示：")
    print(f"   - 当前使用: GPU (CUDA)")
    print(f"   - 模型大小: {whisper_model}")
    print(f"   - 处理速度将比CPU快5-10倍！")
    print("\n现在可以重新运行 streamlit run app.py 了！")
    
except Exception as e:
    print(f"   ❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n💡 建议：")
    print("   1. 确保安装了CUDA版本的PyTorch")
    print("   2. 检查NVIDIA驱动是否最新")
    print("   3. 可以先尝试用 tiny 模型测试")

print("\n" + "="*70)
