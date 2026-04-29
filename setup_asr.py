#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AutoCut 语音识别快速设置脚本
帮助用户快速配置和启用真实的语音识别功能
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def check_config_file():
    """检查配置文件是否存在"""
    print_header("1. 检查配置文件")
    
    config_path = Path("config.env")
    example_path = Path("config.env.example")
    
    if config_path.exists():
        print("✅ config.env 文件已存在")
        return True
    else:
        print("❌ config.env 文件不存在")
        if example_path.exists():
            print(f"   从 config.env.example 复制中...")
            import shutil
            shutil.copy(example_path, config_path)
            print("✅ config.env 已创建")
            print("⚠️  请编辑 config.env 填入你的 API Key")
            return True
        else:
            print("❌ config.env.example 也不存在")
            return False


def install_whisper():
    """安装本地 Whisper 模型依赖"""
    print_header("2. 安装本地 Whisper 模型")
    
    print("💡 本地 Whisper 模型可以在没有 API Key 的情况下使用")
    print("   首次运行会自动下载模型文件（约1GB）")
    
    choice = input("\n是否安装 Whisper？(y/n): ").strip().lower()
    
    if choice != 'y':
        print("跳过 Whisper 安装")
        return False
    
    print("\n正在安装 openai-whisper 和 torch...")
    print("这可能需要几分钟时间，请耐心等待...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "openai-whisper>=20231117", "torch>=2.0.0"
        ])
        print("✅ Whisper 安装成功！")
        
        config_path = Path("config.env")
        if config_path.exists():
            content = config_path.read_text(encoding='utf-8')
            if 'ASR_DEFAULT_BACKEND' in content:
                content = content.replace(
                    'ASR_DEFAULT_BACKEND=aliyun_paraformer_v2',
                    'ASR_DEFAULT_BACKEND=whisper_local'
                )
            else:
                content += '\nASR_DEFAULT_BACKEND=whisper_local\n'
            config_path.write_text(content, encoding='utf-8')
            print("✅ 已配置默认使用 Whisper 本地模型")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装失败: {e}")
        return False


def setup_aliyun_asr():
    """设置阿里云 ASR"""
    print_header("3. 配置阿里云 ASR (可选，推荐)")
    
    print("💡 阿里云 ASR 识别速度快，准确率高")
    print("   需要先在阿里云控制台获取 API Key")
    
    choice = input("\n是否配置阿里云 ASR？(y/n): ").strip().lower()
    
    if choice != 'y':
        print("跳过阿里云 ASR 配置")
        return False
    
    print("\n请访问以下地址获取 API Key:")
    print("https://bailian.console.aliyun.com/")
    
    api_key = input("\n请输入你的 ASR_API_KEY: ").strip()
    
    if not api_key:
        print("❌ API Key 不能为空")
        return False
    
    config_path = Path("config.env")
    if config_path.exists():
        content = config_path.read_text(encoding='utf-8')
        
        if 'ASR_API_KEY=' in content:
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('ASR_API_KEY='):
                    new_lines.append(f'ASR_API_KEY={api_key}')
                elif line.startswith('ASR_DEFAULT_BACKEND='):
                    new_lines.append('ASR_DEFAULT_BACKEND=aliyun_paraformer_v2')
                else:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
        else:
            content += f'\nASR_API_KEY={api_key}\n'
            content += 'ASR_DEFAULT_BACKEND=aliyun_paraformer_v2\n'
        
        config_path.write_text(content, encoding='utf-8')
        print("✅ 阿里云 ASR 配置成功！")
        return True
    
    return False


def test_asr():
    """测试语音识别功能"""
    print_header("4. 测试语音识别")
    
    print("正在初始化 ASR 处理器...")
    
    try:
        from asr_processor import ASRProcessor
        
        asr = ASRProcessor()
        print("✅ ASR 处理器初始化成功")
        print(f"   默认后端: {asr.default_backend}")
        print(f"   API Key 已配置: {'是' if asr.asr_api_key else '否'}")
        
        if asr.default_backend == 'whisper_local':
            print("\n💡 Whisper 本地模型已配置")
            print("   处理真实视频时会自动下载模型")
        elif asr.asr_api_key:
            print("\n💡 阿里云 ASR 已配置，可以使用")
        else:
            print("\n⚠️  没有配置任何真实 ASR 后端")
            print("   将使用模拟数据")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    print_header("AutoCut 语音识别快速设置")
    print("欢迎使用 AutoCut 语音识别设置向导！")
    
    steps = [
        ("检查配置文件", check_config_file),
        ("安装本地 Whisper", install_whisper),
        ("配置阿里云 ASR", setup_aliyun_asr),
        ("测试语音识别", test_asr),
    ]
    
    results = []
    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
        except Exception as e:
            print(f"❌ {step_name} 出错: {e}")
            results.append((step_name, False))
    
    print_header("设置完成")
    
    print("\n设置结果:")
    for step_name, result in results:
        status = "✅ 完成" if result else "❌ 未完成/跳过"
        print(f"  {step_name}: {status}")
    
    print("\n" + "="*70)
    print("下一步:")
    print("1. 运行 `streamlit run app.py` 启动应用")
    print("2. 上传视频测试语音识别功能")
    print("="*70)
    
    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
