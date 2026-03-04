#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速安装支持CUDA的PyTorch
"""

import subprocess
import sys

print("="*70)
print("  安装支持CUDA的PyTorch")
print("="*70)

print("\n💡 这个脚本会尝试安装适合你系统的CUDA版PyTorch")
print("   如果失败，请访问 https://pytorch.org/get-started/locally/")
print("   选择适合你的CUDA版本的安装命令")

# 尝试多个常见的CUDA版本
cuda_versions = [
    ("11.8", "cu118"),
    ("12.1", "cu121"),
    ("12.4", "cu124"),
]

success = False

for cuda_ver, cu_tag in cuda_versions:
    print(f"\n{'='*70}")
    print(f"  尝试安装 CUDA {cuda_ver} 版本...")
    print(f"{'='*70}")
    
    try:
        cmd = [
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", 
            f"https://download.pytorch.org/whl/{cu_tag}"
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        print("\n这可能需要几分钟时间，请耐心等待...\n")
        
        subprocess.check_call(cmd)
        
        print(f"\n✅ PyTorch with CUDA {cuda_ver} 安装成功！")
        success = True
        break
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ CUDA {cuda_ver} 版本安装失败: {e}")
        print("   尝试下一个版本...")
        continue
    except Exception as e:
        print(f"\n❌ 安装出错: {e}")
        continue

if not success:
    print("\n" + "="*70)
    print("  所有CUDA版本安装失败")
    print("="*70)
    print("\n💡 请手动访问: https://pytorch.org/get-started/locally/")
    print("   1. 选择你的操作系统: Windows")
    print("   2. 选择Package: Pip")
    print("   3. 选择Language: Python")
    print("   4. 选择Compute Platform: 你的CUDA版本")
    print("   5. 复制并运行给出的命令")
    print("\n或者继续使用CPU版本（速度稍慢，但功能完整）")
    
    print("\n安装CPU版本作为备选...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio"
        ])
        print("\n✅ CPU版本PyTorch安装成功！")
    except Exception as e:
        print(f"\n❌ CPU版本也安装失败: {e}")
        sys.exit(1)

print("\n" + "="*70)
print("  安装完成！")
print("="*70)

print("\n现在可以运行检查脚本:")
print("  python check_gpu.py")
print("\n然后启动应用:")
print("  streamlit run app.py")
print("="*70)
