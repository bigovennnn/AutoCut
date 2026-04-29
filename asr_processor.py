import os
import time
import json
import subprocess
import tempfile
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from dotenv import load_dotenv
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union


class ASRBackend(Enum):
    ALIYUN_PARAFORMER = "aliyun_paraformer"
    ALIYUN_PARAFORMER_V2 = "aliyun_paraformer_v2"
    WHISPER_LOCAL = "whisper_local"
    MOCK = "mock"


class ASRProcessor:
    _whisper_model_cache: Dict[str, object] = {}
    _whisper_device_cache: Optional[str] = None

    def __init__(self, config_env_path: str = "config.env"):
        load_dotenv(config_env_path, encoding="utf-8")

        self.asr_api_key = os.getenv("ASR_API_KEY", "")
        self.asr_base_url = os.getenv(
            "ASR_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions",
        )

        self.default_backend = os.getenv(
            "ASR_DEFAULT_BACKEND", ASRBackend.ALIYUN_PARAFORMER_V2.value
        )

        self.whisper_model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        self.whisper_device = os.getenv("WHISPER_DEVICE", "cpu")

        self.timeout = int(os.getenv("ASR_TIMEOUT", "120"))
        self.max_retries = int(os.getenv("ASR_MAX_RETRIES", "3"))

        self._setup_session()

        self.performance_metrics = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "average_response_time": 0.0,
            "total_response_time": 0.0,
        }

    @classmethod
    def _get_whisper_model(cls, model_size: str, device: str):
        """获取或加载 Whisper 模型（单例模式）"""
        cache_key = f"{model_size}_{device}"

        if cache_key not in cls._whisper_model_cache:
            import whisper

            device_to_use = device

            if device == "cuda":
                try:
                    import torch

                    if not torch.cuda.is_available():
                        print("⚠️  CUDA不可用，自动切换到CPU")
                        device_to_use = "cpu"
                        cache_key = f"{model_size}_cpu"
                    else:
                        print(f"✅ 使用GPU: {torch.cuda.get_device_name(0)}")
                except Exception as e:
                    print(f"⚠️  GPU检测失败: {e}，切换到CPU")
                    device_to_use = "cpu"
                    cache_key = f"{model_size}_cpu"

            print(f"🔧 首次加载 Whisper 模型: {model_size} (设备: {device_to_use})")
            model = whisper.load_model(model_size, device=device_to_use)
            cls._whisper_model_cache[cache_key] = model
            cls._whisper_device_cache = device_to_use

        return cls._whisper_model_cache[cache_key], cls._whisper_device_cache

    @classmethod
    def clear_whisper_cache(cls):
        """清除 Whisper 模型缓存"""
        cls._whisper_model_cache.clear()
        cls._whisper_device_cache = None

    def _setup_session(self):
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=[
                "HEAD",
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
            ],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def preprocess_audio(self, audio_path: str) -> str:
        """
        音频预处理：降噪、音量归一化、格式优化。
        使用FFmpeg进行音频质量提升。
        """
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_dir = os.path.dirname(audio_path)
        processed_audio_path = os.path.join(output_dir, f"{base_name}_processed.wav")

        try:
            ffmpeg_cmd = [
                "ffmpeg",
                "-i",
                audio_path,
                "-af",
                "loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-20",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-y",
                processed_audio_path,
            ]

            result = subprocess.run(
                ffmpeg_cmd, capture_output=True, check=True, timeout=300
            )

            print(f"✅ 音频预处理完成: {processed_audio_path}")
            return processed_audio_path

        except subprocess.CalledProcessError as e:
            print(f"⚠️  FFmpeg预处理失败: {e.stderr.decode('utf-8', errors='ignore')}")
            print("   使用原始音频进行识别")
            return audio_path
        except FileNotFoundError:
            print("⚠️  FFmpeg未安装，跳过音频预处理")
            return audio_path
        except Exception as e:
            print(f"⚠️  音频预处理失败: {e}，使用原始音频")
            return audio_path

    def transcribe_with_aliyun(
        self, audio_path: str, model: str = "paraformer-v2"
    ) -> Dict:
        """使用阿里云ASR API进行语音识别"""
        if not self.asr_api_key:
            raise ValueError("ASR_API_KEY not configured")

        start_time = time.time()

        try:
            with open(audio_path, "rb") as audio_file:
                files = {"file": ("audio.wav", audio_file, "audio/wav")}
                data = {
                    "model": model,
                    "response_format": "verbose_json",
                    "temperature": 0.0,
                }
                headers = {"Authorization": f"Bearer {self.asr_api_key}"}

                response = self.session.post(
                    self.asr_base_url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False,
                )
                response.raise_for_status()
                result = response.json()

                segments = []
                for seg in result.get("segments", []):
                    segments.append(
                        {
                            "start": seg.get("start", 0.0),
                            "end": seg.get("end", 0.0),
                            "text": seg.get("text", "").strip(),
                            "confidence": seg.get("confidence", 0.0),
                        }
                    )

                full_text = " ".join([seg["text"] for seg in segments])

                end_time = time.time()
                response_time = end_time - start_time

                self._update_performance_metrics(True, response_time)

                return {
                    "success": True,
                    "backend": f"aliyun_{model}",
                    "full_text": full_text,
                    "segments": segments,
                    "response_time": response_time,
                    "model": model,
                }

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            self._update_performance_metrics(False, response_time)
            raise e

    def transcribe_with_whisper(self, audio_path: str) -> Dict:
        """使用本地Whisper模型进行语音识别"""
        try:
            import whisper
        except ImportError:
            raise ImportError(
                "Whisper library not installed. Install with: pip install openai-whisper"
            )

        start_time = time.time()

        try:
            model, device_to_use = self._get_whisper_model(
                self.whisper_model_size, self.whisper_device
            )
            result = model.transcribe(
                audio_path,
                language="zh",
                word_timestamps=True,
                fp16=device_to_use == "cuda",
            )

            segments = []
            for seg in result.get("segments", []):
                segments.append(
                    {
                        "start": float(seg.get("start", 0.0)),
                        "end": float(seg.get("end", 0.0)),
                        "text": seg.get("text", "").strip(),
                        "confidence": float(seg.get("avg_logprob", -1.0)),
                    }
                )

            full_text = result.get("text", "").strip()

            end_time = time.time()
            response_time = end_time - start_time

            self._update_performance_metrics(True, response_time)

            return {
                "success": True,
                "backend": "whisper_local",
                "full_text": full_text,
                "segments": segments,
                "response_time": response_time,
                "model": f"whisper_{self.whisper_model_size}",
                "device": device_to_use,
            }

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            self._update_performance_metrics(False, response_time)
            raise e

    def _mock_transcription(self) -> Dict:
        """模拟语音识别结果（用于测试和演示）"""
        return {
            "success": True,
            "backend": "mock",
            "full_text": "今天天气真的很好，我来到了这家新开的咖啡店。装修风格非常有格调，咖啡的香气也很浓郁。点了一杯拿铁，拉花很漂亮，味道也很棒。强烈推荐大家来试试！",
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.0,
                    "text": "今天天气真的很好",
                    "confidence": 0.95,
                },
                {
                    "start": 3.0,
                    "end": 6.0,
                    "text": "我来到了这家新开的咖啡店",
                    "confidence": 0.94,
                },
                {
                    "start": 6.0,
                    "end": 9.0,
                    "text": "装修风格非常有格调",
                    "confidence": 0.93,
                },
                {
                    "start": 9.0,
                    "end": 12.0,
                    "text": "咖啡的香气也很浓郁",
                    "confidence": 0.95,
                },
                {
                    "start": 12.0,
                    "end": 15.0,
                    "text": "点了一杯拿铁",
                    "confidence": 0.96,
                },
                {
                    "start": 15.0,
                    "end": 18.0,
                    "text": "拉花很漂亮，味道也很棒",
                    "confidence": 0.94,
                },
                {
                    "start": 18.0,
                    "end": 21.0,
                    "text": "强烈推荐大家来试试",
                    "confidence": 0.95,
                },
            ],
            "response_time": 0.5,
            "model": "mock",
        }

    def _update_performance_metrics(self, success: bool, response_time: float):
        """更新性能指标"""
        self.performance_metrics["total_calls"] += 1
        if success:
            self.performance_metrics["success_calls"] += 1
        else:
            self.performance_metrics["failed_calls"] += 1

        self.performance_metrics["total_response_time"] += response_time
        self.performance_metrics["average_response_time"] = (
            self.performance_metrics["total_response_time"]
            / self.performance_metrics["total_calls"]
        )

    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        metrics = self.performance_metrics.copy()
        if metrics["total_calls"] > 0:
            metrics["success_rate"] = (
                metrics["success_calls"] / metrics["total_calls"] * 100
            )
        else:
            metrics["success_rate"] = 0.0
        return metrics

    def transcribe(
        self, audio_path: str, backend: Optional[str] = None, preprocess: bool = True
    ) -> Dict:
        """
        主语音识别接口，支持多种后端和自动降级策略。

        参数:
            audio_path: 音频文件路径
            backend: 指定使用的ASR后端，如果为None则使用默认后端
            preprocess: 是否进行音频预处理

        返回:
            包含识别结果的字典
        """
        if backend is None:
            backend = self.default_backend

        if preprocess:
            audio_path = self.preprocess_audio(audio_path)

        backends_to_try = []

        has_api_key = bool(self.asr_api_key and self.asr_api_key.strip())

        if not has_api_key:
            print("⚠️  未检测到 ASR_API_KEY，将优先尝试本地 Whisper 模型")
            backends_to_try = [
                ("whisper_local", lambda: self.transcribe_with_whisper(audio_path)),
            ]
        elif backend == ASRBackend.ALIYUN_PARAFORMER_V2.value:
            backends_to_try = [
                (
                    "aliyun_paraformer_v2",
                    lambda: self.transcribe_with_aliyun(audio_path, "paraformer-v2"),
                ),
                (
                    "aliyun_paraformer",
                    lambda: self.transcribe_with_aliyun(
                        audio_path, "paraformer-realtime-v1"
                    ),
                ),
                ("whisper_local", lambda: self.transcribe_with_whisper(audio_path)),
            ]
        elif backend == ASRBackend.ALIYUN_PARAFORMER.value:
            backends_to_try = [
                (
                    "aliyun_paraformer",
                    lambda: self.transcribe_with_aliyun(
                        audio_path, "paraformer-realtime-v1"
                    ),
                ),
                (
                    "aliyun_paraformer_v2",
                    lambda: self.transcribe_with_aliyun(audio_path, "paraformer-v2"),
                ),
                ("whisper_local", lambda: self.transcribe_with_whisper(audio_path)),
            ]
        elif backend == ASRBackend.WHISPER_LOCAL.value:
            backends_to_try = [
                ("whisper_local", lambda: self.transcribe_with_whisper(audio_path)),
            ]
        else:
            backends_to_try = [
                ("whisper_local", lambda: self.transcribe_with_whisper(audio_path)),
            ]

        last_exception = None
        for backend_name, transcribe_func in backends_to_try:
            try:
                print(f"🔊 尝试使用 {backend_name} 进行语音识别...")
                result = transcribe_func()
                result["backend_used"] = backend_name
                return result
            except Exception as e:
                last_exception = e
                print(f"⚠️  {backend_name} 识别失败: {e}")
                continue

        print(f"\n{'=' * 70}")
        print(f"❌ 所有ASR后端都失败了！")
        print(f"{'=' * 70}")
        print(f"最后错误: {last_exception}")
        print(f"\n解决方案：")
        print(f"1. 配置阿里云ASR API Key（推荐，识别速度快）")
        print(f"2. 或者安装本地 Whisper 模型：pip install openai-whisper torch")
        print(f"{'=' * 70}\n")

        print(f"⚠️  由于没有可用的ASR后端，只能返回模拟数据！")
        mock_result = self._mock_transcription()
        mock_result["backend_used"] = "mock_fallback"
        mock_result["warning"] = "使用了模拟数据，请配置真实ASR后端"
        return mock_result


asr_processor = ASRProcessor()
