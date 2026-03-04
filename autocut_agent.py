import os
import base64
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from dotenv import load_dotenv
from agentcore import get_llm, get_copywriting_prompt
from media_processor import MediaProcessor
from asr_processor import ASRProcessor, ASRBackend
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

load_dotenv('config.env', encoding='utf-8')

class AutoCutAgent:
    def __init__(self):
        self.media_processor = MediaProcessor()
        self.llm = get_llm()
        self.copywriting_prompt = get_copywriting_prompt()
        self.asr_processor = ASRProcessor()
        self._setup_session()
        self.progress_callback = None

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
            return base64.b64encode(image_file.read()).decode('utf-8')

    def transcribe_audio(self, audio_path):
        print(f"🔊 开始语音识别，音频文件: {audio_path}")
        
        result = self.asr_processor.transcribe(audio_path)
        
        transcription = {
            'full_text': result['full_text'],
            'segments': result['segments']
        }
        
        if 'warning' in result:
            transcription['warning'] = result['warning']
        
        if result.get('success', False):
            print(f"✅ 语音识别完成，使用后端: {result.get('backend_used', 'unknown')}")
            if 'response_time' in result:
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
            clarity_score = min(frame.get('clarity', 0) / 200.0, 1.0)
            score += clarity_score * 0.3
            
            # 2. 如果有内容描述，给予加分
            if 'description' in frame:
                desc = frame['description'].lower()
                # 检测精彩关键词
                exciting_keywords = ['精彩', '激动', '燃', '震撼', '感动', '惊艳', '高潮', '夺冠', '胜利', '欢呼']
                for keyword in exciting_keywords:
                    if keyword in frame['description']:
                        score += 0.2
                        break
            
            # 3. 结合语音内容
            if transcription and 'segments' in transcription:
                aligned_seg = self.align_frame_with_transcription(frame['timestamp'], transcription['segments'])
                if aligned_seg:
                    text = aligned_seg['text'].lower()
                    exciting_words = ['太棒了', '精彩', '厉害', '震撼', '感动', '完美', '太牛了']
                    for word in exciting_words:
                        if word in text:
                            score += 0.3
                            break
            
            scored_frames.append({
                **frame,
                'content_score': score
            })
        
        # 按综合评分排序
        scored_frames.sort(key=lambda x: x['content_score'], reverse=True)
        best_frames = scored_frames[:top_k]
        
        print(f"✅ 基于内容分析选出 {len(best_frames)} 张精彩关键帧")
        return best_frames
    
    def find_highlight_with_full_analysis(self, transcription, frames_with_analysis):
        """
        基于完整的音画分析结果选择高光片段，而不是仅靠语音。
        """
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用默认高光片段")
            return {
                'start': transcription['segments'][0]['start'],
                'end': min(transcription['segments'][-1]['end'], transcription['segments'][0]['start'] + 10),
                'reason': '默认选择中间片段（未配置LLM）'
            }
        
        parser = JsonOutputParser()
        
        # 构建完整的分析信息
        frames_summary = ""
        for idx, frame in enumerate(frames_with_analysis):
            frames_summary += f"""
关键帧 {idx+1}:
- 时间: {frame['time_interval']['start']:.1f}s - {frame['time_interval']['end']:.1f}s
- 画面: {frame.get('description', '无描述')}
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
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        segments_str = json.dumps(transcription['segments'], ensure_ascii=False, indent=2)
        chain = prompt | self.llm | parser
        
        try:
            result = chain.invoke({
                "segments": segments_str,
                "frames_summary": frames_summary
            })
            print(f"✅ 基于完整分析选出高光: {result['start']}s - {result['end']}s")
            return result
        except Exception as e:
            print(f"⚠️  高光筛选失败: {e}，使用默认片段")
            return {
                'start': transcription['segments'][0]['start'],
                'end': min(transcription['segments'][-1]['end'], transcription['segments'][0]['start'] + 10),
                'reason': '默认选择开头片段'
            }

    def _mock_transcription(self):
        return {
            'full_text': '今天天气真的很好，我来到了这家新开的咖啡店。装修风格非常有格调，咖啡的香气也很浓郁。点了一杯拿铁，拉花很漂亮，味道也很棒。强烈推荐大家来试试！',
            'segments': [
                {'start': 0.0, 'end': 3.0, 'text': '今天天气真的很好'},
                {'start': 3.0, 'end': 6.0, 'text': '我来到了这家新开的咖啡店'},
                {'start': 6.0, 'end': 9.0, 'text': '装修风格非常有格调'},
                {'start': 9.0, 'end': 12.0, 'text': '咖啡的香气也很浓郁'},
                {'start': 12.0, 'end': 15.0, 'text': '点了一杯拿铁'},
                {'start': 15.0, 'end': 18.0, 'text': '拉花很漂亮，味道也很棒'},
                {'start': 18.0, 'end': 21.0, 'text': '强烈推荐大家来试试'}
            ]
        }

    def find_highlight_segment(self, transcription):
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用默认高光片段")
            mid_idx = len(transcription['segments']) // 2
            return {
                'start': transcription['segments'][mid_idx]['start'],
                'end': min(transcription['segments'][-1]['end'], transcription['segments'][mid_idx]['start'] + 10),
                'reason': '默认选择中间片段（未配置LLM）'
            }
        
        parser = JsonOutputParser()
        
        prompt = PromptTemplate(
            template="""你是一位专业的视频剪辑师，擅长从素材中选出最精彩的高光片段。

任务：根据以下带有时间戳的字幕，分析语义，选出最具吸引力、最有传播力的一段内容，并返回对应的时间戳范围。

字幕片段：
{segments}

要求：
1. 选择的片段应该完整、有逻辑
2. 时长建议在 3-10 秒之间
3. 返回 JSON 格式，包含 start（开始时间，秒）、end（结束时间，秒）、reason（选择理由）
4. {format_instructions}

请直接输出 JSON，不要包含其他内容。""",
            input_variables=["segments"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        segments_str = json.dumps(transcription['segments'], ensure_ascii=False, indent=2)
        chain = prompt | self.llm | parser
        
        try:
            result = chain.invoke({"segments": segments_str})
            print(f"✅ 高光片段已选出: {result['start']}s - {result['end']}s")
            return result
        except Exception as e:
            print(f"⚠️  高光筛选失败: {e}，使用默认片段")
            return {
                'start': transcription['segments'][0]['start'],
                'end': min(transcription['segments'][-1]['end'], transcription['segments'][0]['start'] + 10),
                'reason': '默认选择开头片段'
            }

    def trim_video(self, video_path, start_time, end_time):
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(self.media_processor.output_dir, f"{base_name}_highlight.mp4")
        
        try:
            import ffmpeg
            import subprocess
            
            try:
                subprocess.run(
                    ['ffmpeg', '-version'],
                    capture_output=True,
                    check=True,
                    timeout=5
                )
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                print("❌ FFmpeg 未安装或不可用")
                return None
            
            (
                ffmpeg
                .input(video_path, ss=start_time, to=end_time)
                .output(output_path, c='copy')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            print(f"✅ 视频裁剪完成: {output_path}")
            return output_path
        except ImportError:
            print("❌ ffmpeg-python 库未安装")
            return None
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'stderr') and e.stderr:
                error_msg += f" | stderr: {e.stderr.decode('utf-8', errors='ignore')}"
            print(f"❌ 视频裁剪失败: {error_msg}")
            return None

    def align_frame_with_transcription(self, frame_timestamp, transcription_segments):
        """
        将关键帧时间戳与语音转录片段对齐，找到时间上最相关的语音内容。
        """
        best_segment = None
        min_distance = float('inf')
        
        for seg in transcription_segments:
            seg_start = seg['start']
            seg_end = seg['end']
            
            if seg_start <= frame_timestamp <= seg_end:
                return seg
            
            distance = min(abs(frame_timestamp - seg_start), abs(frame_timestamp - seg_end))
            if distance < min_distance:
                min_distance = distance
                best_segment = seg
        
        return best_segment
    
    def analyze_frames_with_timestamps(self, frames_info, transcription=None, progress_callback=None):
        """
        分析带时间戳的关键帧，支持音画联合分析（方案3）或单帧分析（方案1兜底）。
        返回带时间区间和描述的帧信息列表。
        """
        api_key = os.getenv("VLM_API_KEY", os.getenv("LLM_API_KEY"))
        base_url = os.getenv("VLM_BASE_URL", os.getenv("LLM_BASE_URL"))
        
        if not api_key or api_key == "your_api_key_here" or api_key == "your_vlm_api_key_here":
            print("⚠️  未配置 VLM API Key，使用模拟分析结果")
            return self._mock_frame_analysis(frames_info)
        
        results = []
        total_frames = len(frames_info)
        
        try:
            for idx, frame in enumerate(frames_info):
                if progress_callback:
                    progress_value = 50 + int((idx / total_frames) * 10)
                    progress_callback(4, f"正在分析第 {idx+1}/{total_frames} 个关键帧", progress_value)
                
                img_path = frame['path']
                timestamp = frame['timestamp']
                time_interval = {
                    'start': max(0, timestamp - 0.5),
                    'end': timestamp + 0.5
                }
                
                base64_image = self.encode_image(img_path)
                
                audio_context = ""
                if transcription and 'segments' in transcription:
                    aligned_segment = self.align_frame_with_transcription(timestamp, transcription['segments'])
                    if aligned_segment:
                        audio_context = f"\n\n该时间段的语音内容：{aligned_segment['text']}"
                
                prompt = f"""请分析这张图片，并描述：
1. 画面的主体内容
2. 场景氛围和情绪基调
3. 该时间点可能发生的事件

时间区间：{time_interval['start']:.1f}秒 - {time_interval['end']:.1f}秒
{audio_context}

请用中文回答，简洁明了，控制在100字以内。"""
                
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ]
                
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "qwen-vl-max",
                        "messages": messages,
                        "max_tokens": 300
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                description = result['choices'][0]['message']['content']
                
                results.append({
                    'path': img_path,
                    'timestamp': timestamp,
                    'time_interval': time_interval,
                    'description': description,
                    'clarity': frame.get('clarity', 0)
                })
                
                print(f"✅ 关键帧 {idx+1}/{total_frames} 分析完成")
            
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
            "顾客享受咖啡时光，表情放松愉悦"
        ]
        
        results = []
        for idx, frame in enumerate(frames_info):
            timestamp = frame['timestamp']
            time_interval = {
                'start': max(0, timestamp - 0.5),
                'end': timestamp + 0.5
            }
            desc_idx = idx % len(mock_descriptions)
            results.append({
                'path': frame['path'],
                'timestamp': timestamp,
                'time_interval': time_interval,
                'description': mock_descriptions[desc_idx],
                'clarity': frame.get('clarity', 0)
            })
        return results
    
    def analyze_images(self, image_paths):
        api_key = os.getenv("VLM_API_KEY", os.getenv("LLM_API_KEY"))
        base_url = os.getenv("VLM_BASE_URL", os.getenv("LLM_BASE_URL"))
        
        if not api_key or api_key == "your_api_key_here" or api_key == "your_vlm_api_key_here":
            print("⚠️  未配置 VLM API Key，使用模拟分析结果")
            return self._mock_image_analysis()

        try:
            images_content = []
            for img_path in image_paths:
                base64_image = self.encode_image(img_path)
                images_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                })
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请分析这些图片，描述画面的主体内容、场景氛围和情绪基调。用中文回答，简洁明了。"},
                        *images_content
                    ]
                }
            ]
            
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "qwen-vl-max",
                    "messages": messages,
                    "max_tokens": 500
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            analysis = result['choices'][0]['message']['content']
            print(f"✅ 图片分析完成")
            return analysis
            
        except Exception as e:
            print(f"⚠️  图片分析失败: {e}，使用模拟结果")
            return self._mock_image_analysis()

    def _mock_image_analysis(self):
        return "图片展示了一家温馨的咖啡店内部，暖色调的灯光营造出舒适放松的氛围。可以看到精致的咖啡杯、拉花漂亮的拿铁咖啡，以及简约现代的装修风格。整体画面给人一种宁静、惬意的感觉。"

    def generate_copywriting(self, content_analysis, platform="小红书", style="温馨治愈"):
        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            print("⚠️  未配置 LLM API Key，使用模拟文案")
            return self._mock_copywriting(platform, style)
        
        try:
            chain = self.copywriting_prompt | self.llm
            result = chain.invoke({
                "platform": platform,
                "style": style,
                "content_analysis": content_analysis
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
        self._update_progress(1, f"成功抽取 {len(all_frames_info)} 个关键帧", 15)
        
        # ====================== 阶段2：语音识别 ======================
        print("\n阶段2: 语音识别")
        self._update_progress(2, "加载语音识别模型", 20)
        self._update_progress(2, "正在处理音频数据", 25)
        transcription = self.transcribe_audio(audio_path) if audio_path else self._mock_transcription()
        seg_count = len(transcription.get('segments', []))
        self._update_progress(2, f"语音识别完成，共识别 {seg_count} 个语音片段", 35)
        
        # ====================== 阶段3：先用清晰度预筛选（避免API调用过多） ======================
        print("\n阶段3: 先用清晰度预筛选（Top 15）")
        self._update_progress(3, "正在计算关键帧清晰度", 38)
        self._update_progress(3, "基于清晰度进行排序和筛选", 40)
        candidate_frames = []
        if all_frames_info:
            candidate_frames = self.media_processor.filter_best_images(frames_dir, all_frames_info, top_k=15)
        self._update_progress(3, f"从 {len(all_frames_info)} 帧中筛选出 {len(candidate_frames)} 个高质量关键帧", 45)
        
        # ====================== 阶段4：分析候选关键帧 ======================
        print("\n阶段4: 分析候选关键帧")
        self._update_progress(4, "准备关键帧分析", 48)
        candidate_frames_with_analysis = []
        if candidate_frames:
            candidate_frames_with_analysis = self.analyze_frames_with_timestamps(candidate_frames, transcription, self._update_progress)
        self._update_progress(4, f"成功完成 {len(candidate_frames_with_analysis)} 个关键帧的内容分析", 60)
        
        # ====================== 阶段5：基于内容选择精彩关键帧 ======================
        print("\n阶段5: 基于内容选择精彩关键帧（Top 5）")
        self._update_progress(5, "正在计算关键帧内容评分", 63)
        self._update_progress(5, "结合语音和画面进行综合评分", 65)
        if candidate_frames_with_analysis:
            best_frames_info = self.select_best_frames_by_content(candidate_frames_with_analysis, transcription, top_k=5)
        else:
            best_frames_info = self.media_processor.filter_best_images(frames_dir, all_frames_info) if all_frames_info else []
        
        best_frames = [frame['path'] for frame in best_frames_info]
        self._update_progress(5, f"精选出 {len(best_frames_info)} 个最精彩的关键帧", 70)
        
        # ====================== 阶段6：基于完整分析选择高光 ======================
        print("\n阶段6: 基于完整音画分析选择高光")
        self._update_progress(6, "整合音画分析数据", 73)
        self._update_progress(6, "智能分析最佳高光时间段", 75)
        if candidate_frames_with_analysis:
            highlight = self.find_highlight_with_full_analysis(transcription, candidate_frames_with_analysis)
        else:
            highlight = self.find_highlight_segment(transcription)
        duration = highlight['end'] - highlight['start']
        self._update_progress(6, f"确定高光片段: {highlight['start']:.1f}s - {highlight['end']:.1f}s ({duration:.1f}秒)", 80)
        
        # ====================== 阶段7：裁剪视频 ======================
        print("\n阶段7: 裁剪高光视频")
        self._update_progress(7, "初始化视频裁剪模块", 82)
        self._update_progress(7, "正在裁剪高光视频片段", 85)
        trimmed_video = self.trim_video(video_path, highlight['start'], highlight['end'])
        self._update_progress(7, "高光视频裁剪完成", 90)
        
        # ====================== 阶段8：整体画面分析与文案生成 ======================
        print("\n阶段8: 生成整体分析与文案")
        self._update_progress(8, "分析整体画面内容", 92)
        image_analysis = self.analyze_images(best_frames)
        self._update_progress(8, "画面分析完成，正在生成文案", 95)
        
        content_analysis = f"""
画面分析：{image_analysis}

语音内容：{transcription['full_text']}
        """.strip()
        
        self._update_progress(8, "调用文案生成模型", 97)
        copywriting = self.generate_copywriting(content_analysis, platform, style)
        self._update_progress(8, "文案生成完成，所有处理结束", 100)
        
        print("\n" + "=" * 70)
        print("✅ 所有处理完成！")
        
        return {
            'trimmed_video': trimmed_video,
            'best_frames': best_frames,
            'best_frames_info': best_frames_info,
            'candidate_frames_with_analysis': candidate_frames_with_analysis,
            'frames_with_analysis': best_frames_info,
            'transcription': transcription,
            'highlight': highlight,
            'image_analysis': image_analysis,
            'copywriting': copywriting
        }

if __name__ == "__main__":
    agent = AutoCutAgent()
    print("智能体初始化完成！")
