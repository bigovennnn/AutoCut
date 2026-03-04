#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的ASR初始化测试
"""

from asr_processor import ASRProcessor

print("="*70)
print("  测试ASR处理器初始化")
print("="*70)

try:
    asr = ASRProcessor()
    print("✅ ASR初始化成功！")
    print(f"   默认后端: {asr.default_backend}")
    print(f"   API Key配置: {bool(asr.asr_api_key and asr.asr_api_key.strip())}")
    print(f"   超时设置: {asr.timeout}秒")
    print(f"   最大重试: {asr.max_retries}次")
    
    if asr.default_backend == 'whisper_local':
        print("\n💡 已配置为使用本地 Whisper 模型")
        print("   请先安装依赖: pip install openai-whisper torch")
    elif asr.asr_api_key:
        print("\n💡 已配置阿里云 ASR，可以使用")
    else:
        print("\n⚠️  未配置真实 ASR 后端")
        print("   将使用模拟数据")
        
except Exception as e:
    print(f"❌ ASR初始化失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
