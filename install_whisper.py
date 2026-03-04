
import subprocess
import sys
import subprocess

print("="*70)
print("  正在安装 Whisper 语音识别依赖...")
print("="*70)

try:
    print("\n步骤 1/2: 安装 torch...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "torch", "-f", 
        "https://download.pytorch.org/whl/torch_stable.html"
    ])
    print("✅ torch 安装成功！")
except Exception as e:
    print(f"⚠️  torch 安装失败: {e}")
    print("正在尝试标准安装方式...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "torch"])
        print("✅ torch 安装成功！")
    except Exception as e2:
        print(f"❌ torch 安装失败: {e2}")
        sys.exit(1)

try:
    print("\n步骤 2/2: 安装 openai-whisper...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "openai-whisper"])
    print("✅ openai-whisper 安装成功！")
except Exception as e:
    print(f"❌ openai-whisper 安装失败: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("  Whisper 安装完成！")
print("="*70)
print("\n现在你可以:")
print("1. 运行 'streamlit run app.py' 启动应用")
print("2. 上传视频，首次运行会自动下载模型")
print("="*70)

