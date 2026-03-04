#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速系统检查 - 确定应该安装哪个PyTorch版本
"""

import subprocess
import sys

print("="*70)
print("  AutoCut - 快速系统检查")
print("="*70)

# 1. 检查NVIDIA GPU
print("\n[1/3] 检查NVIDIA GPU...")
has_nvidia_gpu = False
try:
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("✅ 检测到NVIDIA GPU！")
        has_nvidia_gpu = True
        print("\nnvidia-smi 输出摘要:")
        lines = result.stdout.split('\n')
        for line in lines[:15]:
            if line.strip():
                print(f"  {line}")
    else:
        print("❌ 未检测到NVIDIA GPU（nvidia-smi失败）")
except FileNotFoundError:
    print("❌ 未检测到NVIDIA GPU（nvidia-smi未找到）")
except Exception as e:
    print(f"⚠️  检查NVIDIA GPU时出错: {e}")

# 2. 检查PyTorch
print("\n[2/3] 检查PyTorch...")
try:
    import torch
    print(f"✅ PyTorch已安装: {torch.__version__}")
    
    if torch.cuda.is_available():
        print(f"✅ CUDA可用！")
        print(f"   CUDA版本: {torch.version.cuda}")
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print("\n🎉 太好了！你已经有CUDA版PyTorch了！")
        print("   直接运行 streamlit run app.py 即可！")
    else:
        print("⚠️  CUDA不可用")
        if has_nvidia_gpu:
            print("\n💡 你有NVIDIA GPU，但PyTorch没有CUDA支持")
            print("   建议安装CUDA版PyTorch以获得5-10倍速度提升！")
        else:
            print("\n💡 你没有NVIDIA GPU，使用CPU版本即可")
            print("   CPU版本功能完整，只是速度稍慢")
            
except ImportError:
    print("❌ PyTorch未安装")

# 3. 给出建议
print("\n" + "="*70)
print("  📋 建议")
print("="*70)

try:
    import torch
    if torch.cuda.is_available():
        print("\n✅ 一切就绪！直接使用即可！")
        print("   运行: streamlit run app.py")
    else:
        if has_nvidia_gpu:
            print("\n💡 建议安装CUDA版PyTorch:")
            print("   运行: python install_cuda_torch.py")
            print("\n或者访问 https://pytorch.org/get-started/locally/ 手动选择")
        else:
            print("\n💡 安装CPU版PyTorch:")
            print("   运行: pip install torch torchvision torchaudio")
except ImportError:
    if has_nvidia_gpu:
        print("\n💡 你有NVIDIA GPU！建议安装CUDA版PyTorch:")
        print("   运行: python install_cuda_torch.py")
    else:
        print("\n💡 安装CPU版PyTorch:")
        print("   运行: pip install torch torchvision torchaudio")

print("\n" + "="*70)
