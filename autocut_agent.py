import os
import base64
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from dotenv import load_dotenv
from agentcore import get_llm, get_copywriting_prompt, find_config_file
from media_processor import MediaProcessor
from asr_processor import ASRProcessor, ASRBackend
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

# New enhanced components from FireRed-OpenStoryline
from moviepy_processor import MoviePyProcessor
from video_trimmer import VideoTrimmer, get_trimmer
from video_assembler import VideoAssembler, AssemblyConfig, TransitionType
from prompt_manager import get_prompt_builder, PromptBuilder

load_dotenv(find_config_file(), encoding="utf-8")


class AutoCutAgent:
    def __init__(self):
        self.media_processor = MediaProcessor()
        self.llm = get_llm()
        self.copywriting_prompt = get_copywriting_prompt()
        self.asr_processor = ASRProcessor()
        self._setup_session()
        self.progress_callback = None

        # Enhanced components from FireRed-OpenStoryline
        self.moviepy_processor = MoviePyProcessor(output_dir=self.media_processor.output_dir)
        self.video_trimmer = get_trimmer(output_dir=self.media_processor.output_dir)
        self.prompt_builder = get_prompt_builder()

    def _setup_session(self):
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def _update_progress(self, step, message, progress):
        if self.progress_callback:
            self.progress_callback(step, message, progress)

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def transcribe_audio(self, audio_path):
        print(f"🔊 开始语音识别，音频文件: {audio_path}")

        result = self.asr_processor.transcribe(audio_path)

        transcription = {
            "full_text": result["full_text"],
            "segments": result["segments"],
        }

        if "warning" in result:
            transcription["warning"] = result["warning"]

        if result.get("success", False):
            print(f"✅ 语音识别完成，使用后端: {result.get('backend_used', 'unknown')}")
            if "response_time" in result:
                print(f"   响应时间: {result['response_time']:.2f}秒")
            print(f"   共 {len(result.get('segments', []))} 个片段")
        else:
            print(f"⚠️  语音识别失败")

        return transcription

    def select_best_frames_by_content(self, all_frames_info, transcription, top_k=5):
        """
        基于内容分析选择最精彩的关键帧，而不仅仅靠清晰度。
        结合语音内容和画面描述综合评分。
        """
        print("🎯 开始基于内容分析选择精彩关键帧...")

        scored_frames = []
        for frame in all_frames_info:
            score = 0

            # 1. 清晰度基础分（权重30%）
            clarity_score = min(frame.get("clarity", 0) / 200.0, 1.0)
            score += clarity_score * 0.3

            # 2. 如果有内容描述，给予加分
            if "description" in frame:
                desc = frame["description"].lower()
                # 检测精彩关键词
                exciting_keywords = [
                    "精彩",
                    "激动",
                    "燃",
                    "震撼",
                    "感动",
                    "惊艳",
                    "高潮",
                    "夺冠",
                    "胜利",
                    "欢呼",
                ]
                for keyword in exciting_keywords:
                    if keyword in frame["description"]:
                        score += 0.2
                        break

            # 3. 结合语音内容
            if transcription and "segments" in transcription:
                aligned_seg = self.align_frame_with_transcription(
                    frame["timestamp"], transcription["segments"]
                )
                if aligned_seg:
                    text = aligned_seg["text"].lower()
                    exciting_words = [
                        "太棒了",
                        "精彩",
                        "厉害",
                        "震撼",
                        "感动",
                        "完美",
                        "太牛了",
                    ]
                    for word in exciting_words:
                        if word in text:
                            score += 0.3
                            break

            scored_frames.append({**frame, "content_score": score})

        # 按综合评分排序
        scored_frames.sort(key=lambda x: x["content_score"], reverse=True)
        best_frames = scored_frames[:top_k]

        print(f"✅ 基于内容分析选出 {len(best_frames)} 张精彩关键帧")
        return best_frames

    def find_highlight_with_full_analysis(self, transcription, frames_with_analysis):
        """
        基于完整的音画分析结果选择高光片段，而不是仅靠语音。
        """
        api_key = os.getenv("LLM_API_KEY", "")
        segments = transcription.get("segments", [])
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用默认高光片段")
            if not segments:
                return {
                    "start": 0.0,
                    "end": 10.0,
                    "reason": "默认选择开头片段（无语音数据）",
                }
            return {
                "start": segments[0]["start"],
                "end": min(segments[-1]["end"], segments[0]["start"] + 10),
                "reason": "默认选择开头片段（未配置LLM）",
            }

        parser = JsonOutputParser()

        # 构建完整的分析信息
        frames_summary = ""
        for idx, frame in enumerate(frames_with_analysis):
            frames_summary += f"""
关键帧 {idx + 1}:
- 时间: {frame["time_interval"]["start"]:.1f}s - {frame["time_interval"]["end"]:.1f}s
- 画面: {frame.get("description", "无描述")}
"""

        prompt = PromptTemplate(
            template="""你是一位专业的视频剪辑师，擅长从素材中选出最精彩的高光片段。

任务：根据以下完整的音画分析，选出最具吸引力、最有传播力的一段内容。

语音转录（带时间戳）：
{segments}

关键帧分析：
{frames_summary}

要求：
1. 选择的片段应该完整、有逻辑
2. 时长建议在 3-10 秒之间
3. 要结合语音和画面信息综合判断
4. 返回 JSON 格式，包含 start（开始时间，秒）、end（结束时间，秒）、reason（选择理由）
5. {format_instructions}

请直接输出 JSON，不要包含其他内容。""",
            input_variables=["segments", "frames_summary"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        segments = transcription.get("segments", [])
        segments_str = json.dumps(segments, ensure_ascii=False, indent=2)
        chain = prompt | self.llm | parser
        max_end = segments[-1]["end"] if segments else None

        try:
            result = chain.invoke(
                {"segments": segments_str, "frames_summary": frames_summary}
            )
            is_valid, validated = self._validate_highlight_result(result, max_end)
            if is_valid:
                print(
                    f"✅ 基于完整分析选出高光: {validated['start']}s - {validated['end']}s"
                )
                return validated
            print(f"⚠️  LLM 返回结果无效，使用默认片段")
        except Exception as e:
            print(f"⚠️  高光筛选失败: {e}，使用默认片段")

        if not segments:
            return {
                "start": 0.0,
                "end": 10.0,
                "reason": "默认选择开头片段（无语音数据）",
            }
        return {
            "start": segments[0]["start"],
            "end": min(segments[-1]["end"], segments[0]["start"] + 10),
            "reason": "默认选择开头片段",
        }

    def _validate_highlight_result(self, result, max_end_time=None):
        """
        验证 LLM 返回的高光结果是否有效。
        返回 (is_valid, validated_result) 元组。
        """
        if not isinstance(result, dict):
            return False, None

        required_fields = ["start", "end", "reason"]
        for field in required_fields:
            if field not in result:
                return False, None

        try:
            start = float(result["start"])
            end = float(result["end"])

            if start < 0 or end <= 0 or start >= end:
                return False, None

            if max_end_time is not None and end > max_end_time:
                return False, None

            if end - start > 60:
                return False, None

            return True, {
                "start": start,
                "end": end,
                "reason": str(result.get("reason", "")),
            }
        except (ValueError, TypeError):
            return False, None

    def _mock_transcription(self):
        return {
            "full_text": "今天天气真的很好，我来到了这家新开的咖啡店。装修风格非常有格调，咖啡的香气也很浓郁。点了一杯拿铁，拉花很漂亮，味道也很棒。强烈推荐大家来试试！",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "今天天气真的很好"},
                {"start": 3.0, "end": 6.0, "text": "我来到了这家新开的咖啡店"},
                {"start": 6.0, "end": 9.0, "text": "装修风格非常有格调"},
                {"start": 9.0, "end": 12.0, "text": "咖啡的香气也很浓郁"},
                {"start": 12.0, "end": 15.0, "text": "点了一杯拿铁"},
                {"start": 15.0, "end": 18.0, "text": "拉花很漂亮，味道也很棒"},
                {"start": 18.0, "end": 21.0, "text": "强烈推荐大家来试试"},
            ],
        }

    def find_highlight_segment(self, transcription):
        """
        使用增强的提示管理系统选择高光片段。
        """
        api_key = os.getenv("LLM_API_KEY", "")
        segments = transcription.get("segments", [])
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用默认高光片段")
            if not segments:
                return {
                    "start": 0.0,
                    "end": 10.0,
                    "reason": "默认选择开头片段（无语音数据）",
                }
            mid_idx = len(segments) // 2
            return {
                "start": segments[mid_idx]["start"],
                "end": min(segments[-1]["end"], segments[mid_idx]["start"] + 10),
                "reason": "默认选择中间片段（未配置LLM）",
            }

        parser = JsonOutputParser()

        # 构建片段信息
        clip_info = "\n".join([
            f"片段{i+1}: {seg['start']:.1f}秒 - {seg['end']:.1f}秒, 内容: {seg['text']}"
            for i, seg in enumerate(segments)
        ])

        segments_str = json.dumps(segments, ensure_ascii=False, indent=2)
        format_instructions = parser.get_format_instructions()

        prompt = PromptTemplate(
            template=f"""你是一位专业的视频剪辑师，擅长从素材中选出最精彩的高光片段。

任务：根据以下带有时间戳的字幕，分析语义，选出最具吸引力、最有传播力的一段内容，并返回对应的时间戳范围。

字幕片段：
{clip_info}

要求：
1. 选择的片段应该完整、有逻辑
2. 时长建议在 3-10 秒之间
3. 返回 JSON 格式，包含 start（开始时间，秒）、end（结束时间，秒）、reason（选择理由）
4. {format_instructions}

请直接输出 JSON，不要包含其他内容。""",
            input_variables=[],
        )

        chain = prompt | self.llm | parser

        max_end = segments[-1]["end"] if segments else None

        try:
            result = chain.invoke({})
            is_valid, validated = self._validate_highlight_result(result, max_end)
            if is_valid:
                print(f"✅ 高光片段已选出: {validated['start']}s - {validated['end']}s")
                return validated
            print(f"⚠️  LLM 返回结果无效，使用默认片段")
        except Exception as e:
            print(f"⚠️  高光筛选失败: {e}，使用默认片段")

        if not segments:
            return {
                "start": 0.0,
                "end": 10.0,
                "reason": "默认选择开头片段（无语音数据）",
            }
        return {
            "start": segments[0]["start"],
            "end": min(segments[-1]["end"], segments[0]["start"] + 10),
            "reason": "默认选择开头片段",
        }

    def trim_video(self, video_path, start_time, end_time):
        import os as _os
        base_name = _os.path.splitext(_os.path.basename(video_path))[0]
        output_path = _os.path.join(
            self.media_processor.output_dir, f"{base_name}_highlight.mp4"
        )

        # 验证输入文件存在
        if not _os.path.exists(video_path):
            print(f"❌ 视频文件不存在: {video_path}")
            return None

        try:
            import ffmpeg
            import subprocess

            # 检查 FFmpeg 是否可用
            try:
                subprocess.run(
                    ["ffmpeg", "-version"], capture_output=True, check=True, timeout=5
                )
            except (
                subprocess.CalledProcessError,
                FileNotFoundError,
                subprocess.TimeoutExpired,
            ):
                print("❌ FFmpeg 未安装或不可用")
                return None

            # 验证时间参数
            duration = end_time - start_time
            if duration <= 0:
                print(f"❌ 无效的时间区间: {start_time} - {end_time}")
                return None

            # 使用 ffprobe 获取视频时长
            import subprocess as sp
            probe_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            probe_result = sp.run(probe_cmd, capture_output=True, text=True, timeout=10)
            if probe_result.returncode == 0:
                try:
                    video_duration = float(probe_result.stdout.strip())
                    print(f"📹 视频时长: {video_duration:.2f}秒")

                    # 调整时间区间确保在有效范围内
                    if start_time < 0:
                        start_time = 0
                    if end_time > video_duration:
                        end_time = video_duration
                    if start_time >= end_time:
                        print(f"❌ 调整后无效的时间区间: {start_time} - {end_time}")
                        return None
                except ValueError:
                    print("⚠️  无法解析视频时长")

            # 尝试流复制模式（快速，无损）
            for attempt in range(2):
                try:
                    print(f"🔧 尝试裁剪: {start_time}s - {end_time}s (尝试 {attempt + 1})")
                    (
                        ffmpeg.input(video_path, ss=start_time, to=end_time)
                        .output(output_path, c="copy")
                        .overwrite_output()
                        .run(
                            capture_stdout=True,
                            capture_stderr=True,
                        )
                    )
                    break
                except ffmpeg.Error as e:
                    stderr = e.stderr or b""
                    if isinstance(stderr, bytes):
                        stderr_str = stderr.decode('utf-8', errors='ignore')
                    else:
                        stderr_str = stderr
                    print(f"⚠️  流复制失败: {stderr_str[:200]}")
                    if attempt == 0:
                        print("🔄 尝试重新编码模式...")
                        try:
                            (
                                ffmpeg.input(video_path, ss=max(0, start_time - 0.1), to=end_time + 0.1)
                                .output(
                                    output_path,
                                    vcodec="libx264",
                                    acodec="aac",
                                    **{"q:v": 2},
                                )
                                .overwrite_output()
                                .run(capture_stdout=True, capture_stderr=True)
                            )
                            break
                        except Exception as re_encode_error:
                            print(f"⚠️  重新编码也失败: {re_encode_error}")
                            if attempt == 1:
                                raise

            # 验证输出文件
            if not _os.path.exists(output_path) or _os.path.getsize(output_path) == 0:
                print("❌ 裁剪后的视频文件无效")
                return None

            output_size = _os.path.getsize(output_path)
            print(f"✅ 视频裁剪完成: {output_path} ({output_size / 1024 / 1024:.2f} MB)")
            return output_path

        except ImportError:
            print("❌ ffmpeg-python 库未安装")
            return None
        except Exception as e:
            import traceback
            print(f"❌ 视频裁剪异常: {str(e)}")
            traceback.print_exc()
            return None

    def concat_highlight_segments(self, video_path, highlights, output_path=None):
        """
        拼接多个高光片段为一个完整视频。
        使用增强的VideoTrimmer，支持MoviePy和FFmpeg双引擎。
        """
        if not highlights:
            print("⚠️  没有高光片段可拼接")
            return None

        # 确定输出路径
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(
                self.media_processor.output_dir, f"{base_name}_combined.mp4"
            )

        print(f"🔧 开始拼接 {len(highlights)} 个高光片段...")

        # 使用新的VideoTrimmer进行拼接
        video_clips = [
            {"start": seg['start'], "end": seg['end']}
            for seg in highlights
        ]

        result = self.video_trimmer.concatenate(
            video_clips=video_clips,
            video_path=video_path,
            output_path=output_path
        )

        if result:
            output_size = os.path.getsize(result)
            total_duration = sum(seg['end'] - seg['start'] for seg in highlights)
            print(f"✅ 视频拼接完成: {result}")
            print(f"   文件大小: {output_size / 1024 / 1024:.2f} MB")
            print(f"   总时长: {total_duration:.1f}秒")
            return result
        else:
            print("❌ 视频拼接失败")
            return None

    def _concat_sequentially(self, video_path, highlights, output_path):
        """逐个合并模式（最可靠但最慢）"""
        import ffmpeg
        import subprocess

        temp_dir = self.media_processor.output_dir
        segment_files = []

        try:
            # 提取所有片段
            for i, seg in enumerate(highlights):
                seg_file = os.path.join(temp_dir, f'seg_{i}.mp4')
                start_time = seg['start']
                end_time = seg['end']

                print(f"   提取片段 {i+1}: {start_time:.1f}s - {end_time:.1f}s")

                try:
                    subprocess.run([
                        'ffmpeg', '-y',
                        '-i', video_path,
                        '-ss', str(start_time),
                        '-to', str(end_time),
                        '-c', 'copy',
                        seg_file
                    ], capture_output=True, timeout=60, check=True)
                    segment_files.append(seg_file)
                except Exception as e:
                    print(f"⚠️  片段 {i+1} 提取失败: {e}")
                    continue

            if not segment_files:
                return None

            if len(segment_files) == 1:
                return segment_files[0]

            # 创建文件列表
            list_file = os.path.join(temp_dir, 'concat_list.txt')
            with open(list_file, 'w', encoding='utf-8') as f:
                for seg_file in segment_files:
                    seg_file_abs = os.path.abspath(seg_file).replace('\\', '/')
                    f.write(f"file '{seg_file_abs}'\n")

            # 使用 concat demuxer
            subprocess.run([
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_path
            ], capture_output=True, timeout=120, check=True)

            # 验证
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"✅ 逐个合并完成: {output_path}")
                return output_path

        except Exception as e:
            print(f"❌ 逐个合并失败: {e}")
        finally:
            # 清理
            for f in segment_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception:
                    pass
            try:
                if os.path.exists(list_file):
                    os.remove(list_file)
            except Exception:
                pass

        return None

    def align_frame_with_transcription(self, frame_timestamp, transcription_segments):
        """
        将关键帧时间戳与语音转录片段对齐，找到时间上最相关的语音内容。
        """
        best_segment = None
        min_distance = float("inf")

        for seg in transcription_segments:
            seg_start = seg["start"]
            seg_end = seg["end"]

            if seg_start <= frame_timestamp <= seg_end:
                return seg

            distance = min(
                abs(frame_timestamp - seg_start), abs(frame_timestamp - seg_end)
            )
            if distance < min_distance:
                min_distance = distance
                best_segment = seg

        return best_segment

    def analyze_audio_energy(self, audio_path):
        """
        分析音频能量，检测高光时段。
        返回音频能量曲线和峰值时段。
        """
        try:
            import librosa
            import numpy as np
            from scipy.signal import find_peaks

            print(f"📊 分析音频能量...")

            # 加载音频
            y, sr = librosa.load(audio_path, sr=16000)

            # 短时能量 (RMS)
            rms = librosa.feature.rms(y=y)[0]
            times = librosa.times_like(rms, sr=sr)

            # 归一化能量
            rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-8)

            # 检测能量峰值（前70%分位数以上）
            peak_threshold = np.percentile(rms_normalized, 70)
            peaks, properties = find_peaks(rms_normalized, height=peak_threshold, distance=int(sr/512*2))

            peak_times = [float(times[p]) for p in peaks]
            peak_values = [float(rms_normalized[p]) for p in peaks]

            print(f"✅ 检测到 {len(peaks)} 个能量峰值点")

            return {
                'times': times.tolist(),
                'energy': rms_normalized.tolist(),
                'peak_times': peak_times,
                'peak_values': peak_values,
                'duration': float(times[-1]) if len(times) > 0 else 0
            }

        except ImportError:
            print("⚠️  librosa 未安装，使用简化能量分析")
            return self._simple_energy_analysis(audio_path)
        except Exception as e:
            print(f"⚠️  音频能量分析失败: {e}")
            return {'peak_times': [], 'peak_values': [], 'duration': 0}

    def _simple_energy_analysis(self, audio_path):
        """简化版能量分析（当 librosa 不可用时）"""
        try:
            import subprocess
            # 使用 ffprobe 获取音频信息
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', audio_path],
                capture_output=True, text=True, timeout=10
            )
            import json
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 0))

            # 返回均匀分布的峰值（简化版）
            peak_times = [i * 10 for i in range(int(duration / 10))]
            return {
                'peak_times': peak_times,
                'peak_values': [0.7] * len(peak_times),
                'duration': duration
            }
        except Exception:
            return {'peak_times': [], 'peak_values': [], 'duration': 0}

    def detect_audio_highlights(self, audio_path, transcription, num_highlights=3):
        """
        基于音频能量检测高光时段，结合语音内容筛选。
        """
        print(f"🎯 检测音频高光时段...")

        # 获取音频能量分析
        audio_analysis = self.analyze_audio_energy(audio_path)
        peak_times = audio_analysis.get('peak_times', [])
        duration = audio_analysis.get('duration', 0)

        if not peak_times:
            print("⚠️  未检测到能量峰值，使用默认分段")
            return self._default_highlights(transcription, num_highlights)

        segments = transcription.get('segments', [])

        # 构建候选高光区间
        candidates = []
        for peak_time in peak_times:
            # 以峰值为中心，前后扩展
            start = max(0, peak_time - 4)
            end = min(duration, peak_time + 6)

            # 找到该时段对应的语音内容
            aligned_speech = []
            for seg in segments:
                if seg['start'] < end and seg['end'] > start:
                    aligned_speech.append(seg['text'])

            speech_text = ' '.join(aligned_speech)

            # 计算情感关键词得分
            keywords_score = self._check_emotion_keywords(speech_text)

            candidates.append({
                'start': start,
                'end': end,
                'peak_time': peak_time,
                'speech_text': speech_text,
                'keywords_score': keywords_score,
                'energy_peak': peak_time in peak_times
            })

        # 按关键词得分和能量排序
        candidates.sort(key=lambda x: (x['keywords_score'], x['peak_time']), reverse=True)

        # 选择 top N 不重叠的片段
        selected = []
        used_ranges = []

        for cand in candidates:
            if len(selected) >= num_highlights:
                break

            # 检查是否与已选片段重叠
            overlaps = False
            for used_start, used_end in used_ranges:
                if cand['start'] < used_end and cand['end'] > used_start:
                    overlaps = True
                    break

            if not overlaps:
                selected.append(cand)
                used_ranges.append((cand['start'], cand['end']))

        # 按时间排序
        selected.sort(key=lambda x: x['start'])

        print(f"✅ 选定 {len(selected)} 个高光时段")
        return selected

    def _check_emotion_keywords(self, text):
        """检查文本中的情感关键词"""
        if not text:
            return 0

        text_lower = text.lower()
        keywords = {
            # 高价值词
            '太棒了': 2.0, '太牛了': 2.0, '太厉害了': 2.0, '绝了': 1.5,
            '精彩': 1.5, '惊艳': 1.5, '震撼': 1.5, '激动': 1.5,
            '感动': 1.5, '完美': 1.5, '推荐': 1.2, '必看': 1.5,
            # 一般价值词
            '厉害': 1.0, '很好': 1.0, '不错': 0.8, '喜欢': 0.8,
            '超': 0.5, '非常': 0.3, '特别': 0.3
        }

        score = 0
        for keyword, weight in keywords.items():
            if keyword in text_lower:
                score += weight

        return min(score, 5.0)  # 最高5分

    def _default_highlights(self, transcription, num_highlights):
        """默认高光选择（当能量分析失败时）"""
        segments = transcription.get('segments', [])
        if not segments:
            return [{'start': 0, 'end': 10, 'reason': '默认选择'}]

        duration = segments[-1]['end']
        segment_duration = duration / num_highlights

        highlights = []
        for i in range(num_highlights):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, duration)
            highlights.append({
                'start': start,
                'end': end,
                'peak_time': (start + end) / 2,
                'speech_text': '',
                'keywords_score': 1.0
            })

        return highlights

    def refine_segment_boundaries(self, segment, transcription):
        """
        调整片段边界，确保不截断词句。
        基于语音转录的句子边界进行调整。
        """
        segments = transcription.get('segments', [])
        if not segments:
            return segment

        start = segment['start']
        end = segment['end']

        # 找到起始时间之后最近的句子开始
        refined_start = start
        for seg in segments:
            if seg['end'] > start + 1:  # 找到一个在起始时间之后的句子
                refined_start = seg['start']
                break

        # 找到结束时间之前最近的句子结束
        refined_end = end
        for seg in reversed(segments):
            if seg['start'] < end - 1:  # 找到一个在结束时间之前的句子
                refined_end = seg['end']
                break

        # 确保调整后的区间合理
        if refined_end - refined_start >= 3:  # 至少3秒
            segment['start'] = refined_start
            segment['end'] = refined_end
            segment['refined'] = True

        return segment

    def find_multiple_highlights(self, transcription, frames_info, audio_path,
                                 num_highlights=3, min_duration=5, max_duration=60):
        """
        综合多维信息选择多个高光片段。

        评分维度：
        - 音频能量 (25%)
        - 语音质量 (20%)
        - 画面清晰度 (15%)
        - 运动强度 (15%)
        - 情感峰值 (15%)
        - 叙事完整性 (10%)
        """
        print(f"🎯 综合多维评分选择 Top {num_highlights} 高光...")

        # 获取音频高光候选
        audio_highlights = self.detect_audio_highlights(
            audio_path, transcription, num_highlights=num_highlights * 2
        )

        # 评分权重
        weights = {
            'audio_energy': 0.25,
            'speech_quality': 0.20,
            'visual_clarity': 0.15,
            'motion_intensity': 0.15,
            'emotion_peak': 0.15,
            'narrative': 0.10
        }

        scored_segments = []

        for cand in audio_highlights:
            scores = {}

            # 1. 音频能量得分（基于峰值时间）
            peak_time = cand.get('peak_time', 0)
            if audio_highlights[0].get('peak_time') == peak_time:
                scores['audio_energy'] = 1.0
            else:
                time_diff = abs(peak_time - audio_highlights[0].get('peak_time', 0))
                scores['audio_energy'] = max(0, 1.0 - time_diff / 30)

            # 2. 语音质量得分
            speech_text = cand.get('speech_text', '')
            if len(speech_text) > 20:  # 有实质内容
                scores['speech_quality'] = min(len(speech_text) / 100, 1.0)
            else:
                scores['speech_quality'] = 0.5

            # 3. 画面清晰度得分
            clarity_scores = []
            for frame in frames_info:
                ts = frame.get('timestamp', 0)
                if cand['start'] <= ts <= cand['end']:
                    clarity_scores.append(min(frame.get('clarity', 0) / 200.0, 1.0))
            scores['visual_clarity'] = max(clarity_scores) if clarity_scores else 0.5

            # 4. 运动强度得分（简化版：基于场景变化）
            scores['motion_intensity'] = 0.6  # 默认中等

            # 5. 情感峰值得分
            scores['emotion_peak'] = cand.get('keywords_score', 0) / 5.0

            # 6. 叙事完整性（简化：时长合理）
            duration = cand['end'] - cand['start']
            if 5 <= duration <= 15:
                scores['narrative'] = 1.0
            elif 3 <= duration < 5 or 15 < duration <= 30:
                scores['narrative'] = 0.7
            else:
                scores['narrative'] = 0.4

            # 综合得分
            total_score = sum(weights[k] * scores[k] for k in weights)

            scored_segments.append({
                **cand,
                'scores': scores,
                'total_score': total_score,
                'duration': cand['end'] - cand['start']
            })

        # 按得分排序
        scored_segments.sort(key=lambda x: x['total_score'], reverse=True)

        # 选择不重叠的 top N（确保最小5秒间隔）
        selected = []
        used_ranges = []
        MIN_INTERVAL = 5.0  # 最小间隔5秒

        for seg in scored_segments:
            if len(selected) >= num_highlights:
                break

            seg_start = seg['start']
            seg_end = seg['end']

            # 检查与已选片段的间隔是否足够（最小5秒间隔）
            too_close = False
            for used_start, used_end in used_ranges:
                # 如果新片段与已选片段间隔小于5秒，认为太近
                if seg_start - used_end < MIN_INTERVAL and seg_end - used_start > 0:
                    too_close = True
                    break
                # 如果新片段完全包含已选片段，也认为太近
                if seg_start <= used_start and seg_end >= used_end:
                    too_close = True
                    break

            if too_close:
                continue

            # 边界对齐
            seg = self.refine_segment_boundaries(seg, transcription)
            selected.append(seg)
            used_ranges.append((seg['start'], seg['end']))

        # 按时间排序
        selected.sort(key=lambda x: x['start'])

        # 生成原因说明
        for seg in selected:
            reasons = []
            if seg['scores']['audio_energy'] > 0.8:
                reasons.append('音频能量高')
            if seg['scores']['emotion_peak'] > 0.6:
                reasons.append('情感表达强')
            if seg['scores']['visual_clarity'] > 0.7:
                reasons.append('画面清晰')
            if seg['scores']['speech_quality'] > 0.7:
                reasons.append('语音内容丰富')
            seg['reason'] = '、'.join(reasons) if reasons else '综合评分高'

        print(f"✅ 最终选定 {len(selected)} 个高光片段")
        for i, seg in enumerate(selected):
            print(f"   片段 {i+1}: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s) - {seg['reason']}")

        return selected

    def _fill_missing_highlights(self, existing_highlights, transcription, target_count):
        """
        填充缺失的高光片段，确保至少有 target_count 个片段。

        当检测到的高光片段不足时，在时间线上均匀分布补充默认片段。
        """
        segments = transcription.get("segments", [])

        if not existing_highlights:
            # 没有任何片段，创建均匀分布的默认片段
            if segments:
                total_duration = segments[-1]["end"]
            else:
                total_duration = 60.0

            segment_duration = total_duration / target_count

            for i in range(target_count):
                existing_highlights.append({
                    "start": i * segment_duration,
                    "end": (i + 1) * segment_duration,
                    "reason": "默认填充片段",
                    "scores": {"filled": True}
                })
            return existing_highlights

        # 已有一些片段，补充缺失的
        while len(existing_highlights) < target_count:
            # 找到已有片段之间的最大间隔
            max_gap_start = 0
            max_gap_end = 0
            max_gap_size = 0

            sorted_highlights = sorted(existing_highlights, key=lambda x: x["start"])

            # 检查开头到第一个片段的间隔
            if sorted_highlights[0]["start"] > 10:
                max_gap_start = 0
                max_gap_end = sorted_highlights[0]["start"]
                max_gap_size = max_gap_end - max_gap_start

            # 检查片段之间的间隔
            for i in range(len(sorted_highlights) - 1):
                gap_start = sorted_highlights[i]["end"]
                gap_end = sorted_highlights[i + 1]["start"]
                gap_size = gap_end - gap_start

                if gap_size > max_gap_size:
                    max_gap_size = gap_size
                    max_gap_start = gap_start
                    max_gap_end = gap_end

            # 检查最后一个片段到结尾的间隔
            if segments:
                end_boundary = segments[-1]["end"]
            else:
                end_boundary = max(h.get("end", 60) for h in existing_highlights) + 30

            if end_boundary - sorted_highlights[-1]["end"] > max_gap_size:
                max_gap_start = sorted_highlights[-1]["end"]
                max_gap_end = end_boundary
                max_gap_size = max_gap_end - max_gap_start

            # 在最大间隔的中间添加新片段
            if max_gap_size > 5:  # 间隔至少5秒才添加
                mid_point = (max_gap_start + max_gap_end) / 2
                new_start = max(max_gap_start + 1, mid_point - 3)
                new_end = min(max_gap_end - 1, mid_point + 3)

                existing_highlights.append({
                    "start": new_start,
                    "end": new_end,
                    "reason": "间隔填充片段",
                    "scores": {"filled": True}
                })
            else:
                # 间隔太小，在末尾添加
                if segments:
                    last_end = segments[-1]["end"]
                else:
                    last_end = max(h.get("end", 0) for h in existing_highlights)

                existing_highlights.append({
                    "start": last_end,
                    "end": last_end + 5,
                    "reason": "末尾填充片段",
                    "scores": {"filled": True}
                })

        # 按时间排序
        existing_highlights.sort(key=lambda x: x["start"])

        # 去重（合并重叠的片段）
        deduplicated = []
        for h in existing_highlights:
            if not deduplicated:
                deduplicated.append(h)
            elif h["start"] < deduplicated[-1]["end"]:
                # 重叠，合并
                deduplicated[-1]["end"] = max(deduplicated[-1]["end"], h["end"])
            else:
                deduplicated.append(h)

        return deduplicated[:target_count]

    def analyze_frames_with_timestamps(
        self, frames_info, transcription=None, progress_callback=None
    ):
        """
        分析带时间戳的关键帧，支持音画联合分析（方案3）或单帧分析（方案1兜底）。
        返回带时间区间和描述的帧信息列表。
        """
        api_key = os.getenv("VLM_API_KEY", os.getenv("LLM_API_KEY"))
        base_url = os.getenv("VLM_BASE_URL", os.getenv("LLM_BASE_URL"))

        if (
            not api_key
            or api_key == "your_api_key_here"
            or api_key == "your_vlm_api_key_here"
        ):
            print("⚠️  未配置 VLM API Key，使用模拟分析结果")
            return self._mock_frame_analysis(frames_info)

        results = []
        total_frames = len(frames_info)

        try:
            for idx, frame in enumerate(frames_info):
                if progress_callback:
                    progress_value = 50 + int((idx / total_frames) * 10)
                    progress_callback(
                        4,
                        f"正在分析第 {idx + 1}/{total_frames} 个关键帧",
                        progress_value,
                    )

                img_path = frame["path"]
                timestamp = frame["timestamp"]
                time_interval = {
                    "start": max(0, timestamp - 0.5),
                    "end": timestamp + 0.5,
                }

                base64_image = self.encode_image(img_path)

                audio_context = ""
                if transcription and "segments" in transcription:
                    aligned_segment = self.align_frame_with_transcription(
                        timestamp, transcription["segments"]
                    )
                    if aligned_segment:
                        audio_context = (
                            f"\n\n该时间段的语音内容：{aligned_segment['text']}"
                        )

                prompt = f"""请分析这张图片，并描述：
1. 画面的主体内容
2. 场景氛围和情绪基调
3. 该时间点可能发生的事件

时间区间：{time_interval["start"]:.1f}秒 - {time_interval["end"]:.1f}秒
{audio_context}

请用中文回答，简洁明了，控制在100字以内。"""

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ]

                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "qwen-vl-max",
                        "messages": messages,
                        "max_tokens": 300,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                description = result["choices"][0]["message"]["content"]

                results.append(
                    {
                        "path": img_path,
                        "timestamp": timestamp,
                        "time_interval": time_interval,
                        "description": description,
                        "clarity": frame.get("clarity", 0),
                    }
                )

                print(f"✅ 关键帧 {idx + 1}/{total_frames} 分析完成")

            print(f"✅ 所有关键帧分析完成")
            return results

        except Exception as e:
            print(f"⚠️  关键帧分析失败: {e}，使用模拟结果")
            return self._mock_frame_analysis(frames_info)

    def _mock_frame_analysis(self, frames_info):
        """
        模拟关键帧分析结果（兜底方案）。
        """
        mock_descriptions = [
            "展示了温馨的咖啡店内部，暖色调灯光营造舒适氛围",
            "可以看到精致的咖啡杯和拉花漂亮的拿铁",
            "简约现代的装修风格，给人宁静惬意的感觉",
            "咖啡师正在制作饮品，动作专业流畅",
            "顾客享受咖啡时光，表情放松愉悦",
        ]

        results = []
        for idx, frame in enumerate(frames_info):
            timestamp = frame["timestamp"]
            time_interval = {"start": max(0, timestamp - 0.5), "end": timestamp + 0.5}
            desc_idx = idx % len(mock_descriptions)
            results.append(
                {
                    "path": frame["path"],
                    "timestamp": timestamp,
                    "time_interval": time_interval,
                    "description": mock_descriptions[desc_idx],
                    "clarity": frame.get("clarity", 0),
                }
            )
        return results

    def analyze_images(self, image_paths):
        api_key = os.getenv("VLM_API_KEY", os.getenv("LLM_API_KEY"))
        base_url = os.getenv("VLM_BASE_URL", os.getenv("LLM_BASE_URL"))

        if (
            not api_key
            or api_key == "your_api_key_here"
            or api_key == "your_vlm_api_key_here"
        ):
            print("⚠️  未配置 VLM API Key，使用模拟分析结果")
            return self._mock_image_analysis()

        try:
            images_content = []
            for img_path in image_paths:
                base64_image = self.encode_image(img_path)
                images_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    }
                )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请分析这些图片，描述画面的主体内容、场景氛围和情绪基调。用中文回答，简洁明了。",
                        },
                        *images_content,
                    ],
                }
            ]

            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "qwen-vl-max", "messages": messages, "max_tokens": 500},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            analysis = result["choices"][0]["message"]["content"]
            print(f"✅ 图片分析完成")
            return analysis

        except Exception as e:
            print(f"⚠️  图片分析失败: {e}，使用模拟结果")
            return self._mock_image_analysis()

    def _mock_image_analysis(self):
        return "图片展示了一家温馨的咖啡店内部，暖色调的灯光营造出舒适放松的氛围。可以看到精致的咖啡杯、拉花漂亮的拿铁咖啡，以及简约现代的装修风格。整体画面给人一种宁静、惬意的感觉。"

    def generate_copywriting(
        self, content_analysis, platform="小红书", style="温馨治愈", highlight_info=""
    ):
        """
        使用增强的提示管理系统生成文案。

        Args:
            content_analysis: 内容分析结果
            platform: 目标平台 (小红书/朋友圈/抖音/B站)
            style: 文案风格 (温馨治愈/激动人心/幽默风趣/专业严谨)
            highlight_info: 高光片段信息
        """
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用模拟文案")
            return self._mock_copywriting(platform, style)

        try:
            # 使用prompt builder构建提示
            prompts = self.prompt_builder.build_copywriting(
                platform=platform,
                style=style,
                content_analysis=content_analysis,
                highlight_info=highlight_info
            )

            # 构建完整提示
            full_prompt = f"{prompts['system']}\n\n{prompts['user']}"

            from langchain_core.prompts import ChatPromptTemplate
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", prompts["system"]),
                ("user", prompts["user"])
            ])

            chain = chat_prompt | self.llm
            result = chain.invoke({
                "platform": platform,
                "style": style,
                "content_analysis": content_analysis,
                "highlight_info": highlight_info
            })
            print(f"✅ 文案生成完成")
            return result.content
        except Exception as e:
            print(f"⚠️  文案生成失败: {e}，使用模拟文案")
            return self._mock_copywriting(platform, style)

    def _mock_copywriting(self, platform="小红书", style="温馨治愈"):
        """模拟文案生成（兜底方案）"""
        if platform == "小红书":
            emojis = "✨🎬📸"
            tags = "#视频剪辑 #精彩瞬间 #高光时刻"
            return f"""{emojis} 太精彩了！
这个片段真的绝了，反复看了好几遍！
每一秒都很精彩，忍不住分享给大家～
快来看看吧！

{tags}"""
        elif platform == "朋友圈":
            return f"分享一个精彩片段～ 记录美好时刻 ✨"
        elif platform == "抖音":
            return f"#精彩瞬间 #高光时刻 这个片段太燃了！🔥"
        elif platform == "B站":
            return f"【高能预警】这个片段真的太顶了！建议反复观看！弹幕：前方高能！"
        else:
            return f"精彩内容分享，值得一看！"

    def process_video(self, video_path, platform="小红书", style="温馨治愈"):
        print(f"开始处理视频: {video_path}")
        print("=" * 70)

        # ====================== 阶段1：素材提取 ======================
        print("\n阶段1: 提取素材")
        self._update_progress(1, "正在初始化视频处理模块", 5)
        audio_path = self.media_processor.extract_audio(video_path)
        self._update_progress(1, "音频提取完成，正在抽取关键帧", 10)
        frames_dir, all_frames_info = self.media_processor.extract_keyframes(video_path)
        frames_count = len(all_frames_info) if all_frames_info else 0
        self._update_progress(1, f"成功抽取 {frames_count} 个关键帧", 15)

        # ====================== 阶段2：语音识别 ======================
        print("\n阶段2: 语音识别")
        self._update_progress(2, "加载语音识别模型", 20)
        self._update_progress(2, "正在处理音频数据", 25)
        transcription = (
            self.transcribe_audio(audio_path)
            if audio_path
            else self._mock_transcription()
        )
        seg_count = len(transcription.get("segments", []))
        self._update_progress(2, f"语音识别完成，共识别 {seg_count} 个语音片段", 35)

        # ====================== 阶段3：先用清晰度预筛选（避免API调用过多） ======================
        print("\n阶段3: 先用清晰度预筛选（Top 15）")
        self._update_progress(3, "正在计算关键帧清晰度", 38)
        self._update_progress(3, "基于清晰度进行排序和筛选", 40)
        candidate_frames = []
        if all_frames_info:
            candidate_frames = self.media_processor.filter_best_images(
                frames_dir, all_frames_info, top_k=15
            )
        self._update_progress(
            3,
            f"从 {frames_count} 帧中筛选出 {len(candidate_frames)} 个高质量关键帧",
            45,
        )

        # ====================== 阶段4：分析候选关键帧 ======================
        print("\n阶段4: 分析候选关键帧")
        self._update_progress(4, "准备关键帧分析", 48)
        candidate_frames_with_analysis = []
        if candidate_frames:
            candidate_frames_with_analysis = self.analyze_frames_with_timestamps(
                candidate_frames, transcription, self._update_progress
            )
        self._update_progress(
            4, f"成功完成 {len(candidate_frames_with_analysis)} 个关键帧的内容分析", 60
        )

        # ====================== 阶段5：选择精彩关键帧用于后续分析 ======================
        print("\n阶段5: 选择精彩关键帧")
        self._update_progress(5, "计算关键帧内容评分", 63)
        self._update_progress(5, "结合语音和画面综合评分", 68)
        if candidate_frames_with_analysis:
            best_frames_info = self.select_best_frames_by_content(
                candidate_frames_with_analysis, transcription, top_k=5
            )
        else:
            best_frames_info = (
                self.media_processor.filter_best_images(frames_dir, all_frames_info)
                if all_frames_info
                else []
            )

        best_frames = [frame["path"] for frame in best_frames_info]
        self._update_progress(5, f"精选出 {len(best_frames_info)} 个最精彩的关键帧", 72)

        # ====================== 阶段6：基于完整分析选择多个高光 ======================
        print("\n阶段6: 基于完整音画分析选择多个高光")
        self._update_progress(6, "整合音画分析数据", 75)
        self._update_progress(6, "智能分析最佳高光时间段", 78)

        # 使用新的多高光选择
        if candidate_frames_with_analysis and audio_path:
            highlights = self.find_multiple_highlights(
                transcription, candidate_frames_with_analysis, audio_path,
                num_highlights=5, min_duration=5, max_duration=60
            )
        else:
            # 回退到单高光
            if candidate_frames_with_analysis:
                single = self.find_highlight_with_full_analysis(
                    transcription, candidate_frames_with_analysis
                )
            else:
                single = self.find_highlight_segment(transcription)
            highlights = [single]

        # 强制确保至少3个高光片段
        MIN_HIGHLIGHTS = 3
        if len(highlights) < MIN_HIGHLIGHTS:
            print(f"⚠️  高光片段不足 {MIN_HIGHLIGHTS} 个，填充默认片段...")
            highlights = self._fill_missing_highlights(highlights, transcription, MIN_HIGHLIGHTS)

        total_duration = sum(h['end'] - h['start'] for h in highlights)
        self._update_progress(
            6,
            f"确定 {len(highlights)} 个高光片段，总时长 {total_duration:.1f}秒",
            82,
        )

        # ====================== 阶段7：使用VideoAssembler拼接视频 ======================
        print("\n阶段7: 使用专业拼接器组装视频")
        self._update_progress(7, "初始化VideoAssembler", 85)
        self._update_progress(7, "正在拼接高光片段并添加转场", 88)

        # 使用新的VideoAssembler进行专业拼接
        assembler = VideoAssembler(output_dir=self.media_processor.output_dir)
        assembly_config = AssemblyConfig(
            transition=TransitionType.CROSSFADE,
            transition_duration=0.5,
            fade_in_duration=0.3,
            fade_out_duration=0.5,
            subtitle_enabled=True,
            subtitle_font="SimHei",
            subtitle_size=48,
            subtitle_color="white",
            subtitle_stroke_color="black",
            subtitle_stroke_width=2,
            subtitle_position="bottom",
            audio_fade_in=0.3,
            audio_fade_out=0.5,
        )

        try:
            assembly_result = assembler.assemble(
                video_path=video_path,
                highlights=highlights,
                transcription=transcription,
                config=assembly_config
            )
            trimmed_video = assembly_result.get("output_path")
            print(f"✅ VideoAssembler 完成: {trimmed_video}")
        except Exception as e:
            print(f"⚠️  VideoAssembler 失败，回退到简单拼接: {e}")
            trimmed_video = self.concat_highlight_segments(video_path, highlights)

        self._update_progress(7, "高光视频拼接完成", 92)

        # ====================== 阶段8：整体画面分析与文案生成 ======================
        print("\n阶段8: 生成整体分析与文案")
        self._update_progress(8, "分析整体画面内容", 94)
        image_analysis = self.analyze_images(best_frames)
        self._update_progress(8, "画面分析完成，正在生成文案", 96)

        content_analysis = f"""
画面分析：{image_analysis}

语音内容：{transcription["full_text"]}
        """.strip()

        # 构建高光片段信息
        highlight_info = "\n".join([
            f"高光{i+1}: {h['start']:.1f}秒 - {h['end']:.1f}秒, {h.get('reason', '')}"
            for i, h in enumerate(highlights)
        ])

        self._update_progress(8, "调用文案生成模型", 98)
        copywriting = self.generate_copywriting(content_analysis, platform, style, highlight_info)
        self._update_progress(8, "文案生成完成，所有处理结束", 100)

        print("\n" + "=" * 70)
        print("✅ 所有处理完成！")

        return {
            "trimmed_video": trimmed_video,
            "best_frames": best_frames,
            "best_frames_info": best_frames_info,
            "candidate_frames_with_analysis": candidate_frames_with_analysis,
            "frames_with_analysis": best_frames_info,
            "transcription": transcription,
            "highlights": highlights,  # 多个高光片段
            "image_analysis": image_analysis,
            "copywriting": copywriting,
        }


if __name__ == "__main__":
    agent = AutoCutAgent()
    print("智能体初始化完成！")
