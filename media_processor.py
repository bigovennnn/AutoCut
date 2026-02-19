import ffmpeg
import cv2
import os
import glob

class MediaProcessor:
    def __init__(self, output_base_dir="./temp_workspace"):
        self.output_dir = output_base_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def extract_audio(self, video_path):
        """
        剥离音频：将视频中的音频提取为 16kHz 的单声道 WAV 文件，这是语音识别 (ASR) 的最佳格式。
        """
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_audio_path = os.path.join(self.output_dir, f"{base_name}_audio.wav")
        
        try:
            (
                ffmpeg
                .input(video_path)
                .output(output_audio_path, acodec='pcm_s16le', ac=1, ar='16k')
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
        抽取关键帧：按固定间隔（默认每秒一帧）提取视频画面 [cite: 138]。
        加入了最大帧数限制（vframes=50），防止长视频撑爆本地磁盘和后续 API 额度。
        """
        frames_dir = os.path.join(self.output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        # 每次抽帧前清空旧数据
        for f in glob.glob(os.path.join(frames_dir, "*.jpg")):
            os.remove(f)
            
        output_pattern = os.path.join(frames_dir, 'frame_%04d.jpg')
        
        try:
            (
                ffmpeg
                .input(video_path)
                .filter('fps', fps=fps)
                .output(output_pattern, vframes=50, qscale_v=2) # qscale 保证抽出图片的质量
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            print(f"✅ 关键帧提取完成，目录: {frames_dir}")
            return frames_dir
        except ffmpeg.Error as e:
            print(f"❌ 关键帧提取失败: {e.stderr.decode('utf8')}")
            return None

    def filter_best_images(self, image_dir, top_k=3, variance_threshold=100.0):
        """
        图片智能筛选：使用 OpenCV 对图片进行质量评估，计算拉普拉斯方差（清晰度） [cite: 214]。
        自动剔除糊图，并选出质量最高的 N 张图片交给多模态模型分析。
        """
        valid_images = []
        for img_path in glob.glob(os.path.join(image_dir, '*.jpg')):
            image = cv2.imread(img_path)
            if image is None:
                continue
            
            # 转换为灰度图计算方差
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            fm = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # 方差低于阈值判定为模糊废片，直接物理删除
            if fm > variance_threshold:
                valid_images.append({'path': img_path, 'clarity': fm})
            else:
                os.remove(img_path)
                
        # 按清晰度降序排列
        valid_images.sort(key=lambda x: x['clarity'], reverse=True)
        best_images = [img['path'] for img in valid_images[:top_k]]
        
        print(f"✅ 图片质量筛选完毕，选出 {len(best_images)} 张最优帧。")
        return best_images

# 测试运行
if __name__ == "__main__":
    processor = MediaProcessor()
    # 找一个测试视频放在项目目录下运行：
    # test_video = "test.mp4" 
    # audio_file = processor.extract_audio(test_video)
    # frames_folder = processor.extract_keyframes(test_video)
    # if frames_folder:
    #     best_frames = processor.filter_best_images(frames_folder)
    #     print("最终留存的高质量帧:", best_frames)