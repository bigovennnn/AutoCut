import ffmpeg
import cv2
import os
import glob
import time


class MediaProcessor:
    def __init__(self, output_base_dir="./temp_workspace"):
        self.output_dir = output_base_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def extract_audio(self, video_path):
        """
        提取音频：将视频中的音频提取为 16kHz 的单声道 WAV 文件，这是语音识别 (ASR) 的最佳格式。
        """
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_audio_path = os.path.join(self.output_dir, f"{base_name}_audio.wav")

        try:
            (
                ffmpeg.input(video_path)
                .output(output_audio_path, acodec="pcm_s16le", ac=1, ar="16k")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            print(f"✅ 音频提取成功: {output_audio_path}")
            return output_audio_path
        except ffmpeg.Error as e:
            print(f"❌ 音频提取失败: {e.stderr.decode('utf8')}")
            return None

    def extract_keyframes(self, video_path, fps=1):
        """
        抽取关键帧：按固定间隔（默认每秒一帧）提取视频画面。
        精确设置为每1秒从视频流中提取1帧图像数据，无最大帧数限制。
        返回帧目录及帧信息列表（包含时间戳）。
        """
        frames_dir = os.path.join(self.output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # 每次抽帧前清空旧数据
        for f in glob.glob(os.path.join(frames_dir, "*.jpg")):
            os.remove(f)

        output_pattern = os.path.join(frames_dir, "frame_%04d.jpg")

        try:
            (
                ffmpeg.input(video_path)
                .filter("fps", fps=fps)
                .output(output_pattern, **{"q:v": 2})
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # 生成帧信息列表（包含时间戳）
            frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
            frame_info = []
            for idx, frame_path in enumerate(frame_files):
                timestamp = idx / fps  # 计算时间戳（秒）
                frame_info.append(
                    {"path": frame_path, "timestamp": timestamp, "frame_index": idx}
                )

            print(f"✅ 关键帧提取完成，共 {len(frame_info)} 帧，目录: {frames_dir}")
            return frames_dir, frame_info
        except ffmpeg.Error as e:
            print(f"❌ 关键帧提取失败: {e.stderr.decode('utf8')}")
            return None, None

    def _compute_adaptive_threshold(
        self, clarity_values, top_k, min_threshold=50.0, default_threshold=100.0
    ):
        """
        根据清晰度分布计算自适应阈值。
        使用统计方法确保选取足够数量的高质量帧。
        """
        if not clarity_values:
            return default_threshold

        clarity_values_sorted = sorted(clarity_values)
        n = len(clarity_values)

        if n <= top_k:
            return min_threshold

        target_idx = max(0, n - top_k - 2)
        adaptive_threshold = clarity_values_sorted[target_idx]

        return max(adaptive_threshold, min_threshold)

    def filter_best_images(
        self, image_dir, frame_info=None, top_k=5, variance_threshold=100.0
    ):
        """
        图片智能筛选：使用 OpenCV 对图片进行质量评估，计算拉普拉斯方差（清晰度）。
        自动剔除模糊图，并选出质量最高的 N 张图片交给多模态模型分析。
        返回包含路径、时间戳、清晰度的完整帧信息。
        """
        all_images_clarity = []
        valid_images = []

        if frame_info:
            for frame in frame_info:
                img_path = frame["path"]
                image = cv2.imread(img_path)
                if image is None:
                    continue

                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                fm = cv2.Laplacian(gray, cv2.CV_64F).var()

                all_images_clarity.append(fm)

                if fm > variance_threshold:
                    valid_images.append(
                        {
                            "path": img_path,
                            "clarity": fm,
                            "timestamp": frame["timestamp"],
                            "frame_index": frame["frame_index"],
                        }
                    )
                else:
                    os.remove(img_path)
        else:
            for img_path in glob.glob(os.path.join(image_dir, "*.jpg")):
                image = cv2.imread(img_path)
                if image is None:
                    continue

                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                fm = cv2.Laplacian(gray, cv2.CV_64F).var()

                all_images_clarity.append(fm)

                if fm > variance_threshold:
                    valid_images.append({"path": img_path, "clarity": fm})
                else:
                    os.remove(img_path)

        if len(valid_images) < top_k and all_images_clarity:
            adaptive_threshold = self._compute_adaptive_threshold(
                all_images_clarity, top_k, min_threshold=variance_threshold * 0.5
            )

            for frame in frame_info if frame_info else []:
                img_path = frame["path"]
                if any(v["path"] == img_path for v in valid_images):
                    continue

                image = cv2.imread(img_path)
                if image is None:
                    continue

                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                fm = cv2.Laplacian(gray, cv2.CV_64F).var()

                if fm > adaptive_threshold:
                    valid_images.append(
                        {
                            "path": img_path,
                            "clarity": fm,
                            "timestamp": frame.get("timestamp", 0),
                            "frame_index": frame.get("frame_index", 0),
                        }
                    )

        valid_images.sort(key=lambda x: x["clarity"], reverse=True)
        best_images = valid_images[:top_k]

        deleted_count = len(all_images_clarity) - len(valid_images)
        print(
            f"✅ 图片质量筛选完毕，删除 {deleted_count} 张模糊帧，保留 {len(best_images)} 张最优帧。"
        )
        return best_images

    def detect_scene_boundaries(self, video_path, threshold=30.0, sample_fps=None):
        """
        基于帧差异检测场景切换边界。

        Args:
            video_path: 视频文件路径
            threshold: 场景切换阈值 (0-100)，越小越敏感
            sample_fps: 采样帧率，默认自动

        Returns:
            场景边界时间点列表 [0.0, 5.2, 12.8, ...]
        """
        print(f"🎬 检测场景边界...")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ 无法打开视频: {video_path}")
            return [0.0]

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        # 自动采样率（每秒采样2帧，避免太慢）
        if sample_fps is None:
            sample_fps = min(2, fps)

        sample_interval = int(fps / sample_fps) if sample_fps > 0 else 1
        threshold_normalized = threshold / 100.0

        prev_gray = None
        scene_changes = [0.0]  # 起始点

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                # 计算直方图差异
                hist_prev = cv2.calcHist([prev_gray], [0], None, [256], [0, 256])
                hist_curr = cv2.calcHist([gray], [0], None, [256], [0, 256])

                # 相关性比较
                correlation = cv2.compareHist(hist_prev, hist_curr, cv2.HISTCMP_CORREL)

                # 相关性低于阈值 = 场景切换
                if correlation < (1.0 - threshold_normalized):
                    timestamp = frame_idx / fps
                    # 避免太接近的时间点
                    if not scene_changes or (timestamp - scene_changes[-1]) > 0.5:
                        scene_changes.append(timestamp)

            prev_gray = gray
            frame_idx += sample_interval

        cap.release()

        # 添加结束点
        if scene_changes[-1] < duration - 0.5:
            scene_changes.append(duration)

        print(f"✅ 检测到 {len(scene_changes)} 个场景边界")
        return scene_changes

    def extract_keyframes_with_scenes(self, video_path, scenes):
        """
        在场景边界附近提取关键帧。

        Args:
            video_path: 视频文件路径
            scenes: 场景边界时间列表

        Returns:
            每个场景的代表性关键帧
        """
        print(f"🖼️  在场景边界提取关键帧...")

        frames_info = []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return frames_info

        fps = cap.get(cv2.CAP_PROP_FPS)
        frames_dir = os.path.join(self.output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        for i, scene_time in enumerate(scenes):
            # 在场景开始后一小段时间提取帧
            target_time = scene_time + 0.5
            frame_idx = int(target_time * fps)

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(frames_dir, f"scene_{i}_frame.jpg")
                cv2.imwrite(frame_path, frame)

                # 计算清晰度
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                clarity = cv2.Laplacian(gray, cv2.CV_64F).var()

                frames_info.append({
                    'path': frame_path,
                    'timestamp': target_time,
                    'scene_index': i,
                    'clarity': clarity
                })

        cap.release()
        print(f"✅ 提取了 {len(frames_info)} 个场景关键帧")
        return frames_info

    def cleanup_old_files(self, max_age_hours=24):
        """
        清理临时工作目录中的旧文件。
        """
        if not os.path.exists(self.output_dir):
            return 0

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0

        for root, dirs, files in os.walk(self.output_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        deleted_count += 1
                except OSError:
                    pass

        if deleted_count > 0:
            print(f"🧹 已清理 {deleted_count} 个过期临时文件")
        return deleted_count


# 测试运行
if __name__ == "__main__":
    processor = MediaProcessor()
    # 找一个测试视频放在项目目录下运行：
    # test_video = "test.mp4"
    # audio_file = processor.extract_audio(test_video)
    # frames_folder = processor.extract_keyframes(test_video)
    # if frames_folder:
    #     best_frames = processor.filter_best_images(frames_folder)
    #     print("最终保留的高质量帧:", best_frames)
