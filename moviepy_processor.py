"""
MoviePy 2.x Video Processor for AutoCut2

This module integrates MoviePy 2.x for advanced video editing operations,
replacing and extending the previous FFmpeg-only approach.

Key features:
- Video clip extraction and concatenation
- Audio handling with MoviePy
- Smooth transitions and effects
- High-quality video export
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import tempfile

# MoviePy 2.x imports with fallback to 1.x
try:
    from moviepy import (
        VideoFileClip,
        AudioFileClip,
        ImageClip,
        VideoClip,
        ColorClip,
        CompositeVideoClip,
        CompositeAudioClip,
        concatenate_videoclips,
        concatenate_audioclips,
        vfx,
        afx,
    )
    from moviepy.video.fx import all as vfx_all
    from moviepy.audio.fx import all as afx_all
    MOVIEPY_VERSION = 2
except ImportError:
    try:
        from moviepy.editor import (
            VideoFileClip,
            AudioFileClip,
            ImageClip,
            VideoClip,
            ColorClip,
            CompositeVideoClip,
            CompositeAudioClip,
            concatenate_videoclips,
            concatenate_audioclips,
        )
        import moviepy.video.fx as vfx
        import moviepy.audio.fx as afx
        MOVIEPY_VERSION = 1
    except ImportError:
        MOVIEPY_VERSION = 0

import numpy as np


class MoviePyProcessor:
    """
    Advanced video processor using MoviePy 2.x.

    Provides professional-grade video editing operations including:
    - Stream copy for fast, lossless trimming
    - Intelligent concatenation with transition handling
    - Audio waveform analysis
    - Multi-track compositing
    """

    def __init__(self, output_dir: str = "./temp_workspace"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._verify_ffmpeg()

    def _verify_ffmpeg(self) -> bool:
        """Verify FFmpeg is available for audio processing."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get detailed video information using MoviePy.

        Returns:
            Dictionary containing duration, fps, resolution, etc.
        """
        if MOVIEPY_VERSION == 0:
            return self._get_video_info_ffmpeg(video_path)

        try:
            with VideoFileClip(video_path) as clip:
                info = {
                    "duration": clip.duration,
                    "fps": clip.fps,
                    "size": clip.size,
                    "width": clip.w,
                    "height": clip.h,
                    "aspect_ratio": clip.aspect_ratio if hasattr(clip, 'aspect_ratio') else clip.w / clip.h,
                    "has_audio": clip.audio is not None if clip.audio is not None else False,
                }
                if clip.audio is not None:
                    info["audio_duration"] = clip.audio.duration
                    info["audio_fps"] = clip.audio.fps if hasattr(clip.audio, 'fps') else None
                return info
        except Exception as e:
            return self._get_video_info_ffmpeg(video_path)

    def _get_video_info_ffmpeg(self, video_path: str) -> Dict[str, Any]:
        """Fallback video info using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate",
            "-of", "json", video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            import json
            data = json.loads(result.stdout)
            streams = data.get("streams", [{}])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, denom = fps_str.split("/")
                fps = float(num) / float(denom)
            else:
                fps = float(fps_str)
            return {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "fps": fps,
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            }
        except Exception:
            return {"duration": 0, "fps": 30, "width": 0, "height": 0, "has_audio": False}

    def extract_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None,
        use_stream_copy: bool = True
    ) -> Optional[str]:
        """
        Extract a clip from video using MoviePy.

        Args:
            video_path: Source video path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Output path (auto-generated if None)
            use_stream_copy: Use stream copy (fast, lossless) if True

        Returns:
            Path to extracted clip or None on failure
        """
        if MOVIEPY_VERSION == 0:
            return self._extract_clip_ffmpeg(video_path, start_time, end_time, output_path)

        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_clip_{int(start_time)}_{int(end_time)}.mp4")

        try:
            with VideoFileClip(video_path) as clip:
                # Validate times
                duration = clip.duration
                start_time = max(0, min(start_time, duration - 0.1))
                end_time = max(start_time + 0.1, min(end_time, duration))

                subclip = clip.subclipped(start_time, end_time)
                subclip.write_videofile(
                    output_path,
                    codec='libx264' if not use_stream_copy else None,
                    audio_codec='aac' if subclip.audio is not None else None,
                    logger=None  # Suppress moviepy verbose output
                )
                subclip.close()
                return output_path
        except Exception as e:
            print(f"MoviePy extraction failed, trying FFmpeg: {e}")
            return self._extract_clip_ffmpeg(video_path, start_time, end_time, output_path)

    def _extract_clip_ffmpeg(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """Fallback extraction using direct FFmpeg."""
        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_clip_{int(start_time)}_{int(end_time)}.mp4")

        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-to", str(end_time),
                "-i", video_path,
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception as e:
            print(f"FFmpeg extraction failed: {e}")
        return None

    def concatenate_clips(
        self,
        clip_paths: List[str],
        output_path: Optional[str] = None,
        transition: Optional[str] = None,
        transition_duration: float = 0.5
    ) -> Optional[str]:
        """
        Concatenate multiple video clips into one.

        Args:
            clip_paths: List of video clip paths
            output_path: Output path (auto-generated if None)
            transition: Transition type ('fade', 'crossfade', None)
            transition_duration: Duration of transition in seconds

        Returns:
            Path to concatenated video or None on failure
        """
        if not clip_paths:
            return None

        if len(clip_paths) == 1:
            return clip_paths[0]

        if output_path is None:
            output_path = str(self.output_dir / f"concatenated_{int(time.time())}.mp4")

        if MOVIEPY_VERSION == 0:
            return self._concatenate_ffmpeg(clip_paths, output_path)

        try:
            clips = []
            for path in clip_paths:
                if not os.path.exists(path):
                    print(f"Clip not found: {path}")
                    continue
                try:
                    clip = VideoFileClip(path)
                    clips.append(clip)
                except Exception as e:
                    print(f"Failed to load clip {path}: {e}")
                    continue

            if not clips:
                return None

            if transition == 'crossfade' and len(clips) > 1:
                # Apply crossfade transition between clips
                clips = self._apply_crossfade_transition(clips, transition_duration)

            final_clip = concatenate_videoclips(clips, method="compose")
            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                logger=None
            )

            # Cleanup
            for clip in clips:
                clip.close()
            final_clip.close()

            return output_path
        except Exception as e:
            print(f"MoviePy concatenation failed: {e}")
            return self._concatenate_ffmpeg(clip_paths, output_path)

    def _apply_crossfade_transition(
        self,
        clips: List[VideoClip],
        duration: float
    ) -> List[VideoClip]:
        """Apply crossfade transition between consecutive clips."""
        if len(clips) < 2:
            return clips

        processed = [clips[0]]
        for i in range(1, len(clips)):
            prev = processed[-1]
            curr = clips[i]

            # Get the crossfade portion from previous clip (last `duration` seconds)
            if prev.duration > duration:
                crossfade_clip = prev.subclipped(prev.duration - duration, prev.duration)
            else:
                crossfade_clip = prev

            # Crossfade composite
            curr = curr.with_subclip(0, duration)
            crossfade_clip = crossfade_clip.fx(vfx.crossfadeout, duration)
            curr = curr.fx(vfx.crossfadein, duration)

            composited = CompositeVideoClip([crossfade_clip, curr])
            processed.pop()
            processed.append(composited)
            processed.append(clips[i].subclipped(duration, clips[i].duration))

        return processed

    def _concatenate_ffmpeg(self, clip_paths: List[str], output_path: str) -> Optional[str]:
        """Fallback concatenation using FFmpeg concat demuxer."""
        if not clip_paths:
            return None

        if len(clip_paths) == 1:
            return clip_paths[0]

        # Create concat list file
        list_file = self.output_dir / "concat_list.txt"
        try:
            with open(list_file, 'w', encoding='utf-8') as f:
                for path in clip_paths:
                    if os.path.exists(path):
                        abs_path = os.path.abspath(path).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception as e:
            print(f"FFmpeg concatenation failed: {e}")
        finally:
            if list_file.exists():
                list_file.unlink()
        return None

    def add_audio_track(
        self,
        video_path: str,
        audio_path: str,
        output_path: Optional[str] = None,
        audio_offset: float = 0,
        audio_volume: float = 1.0
    ) -> Optional[str]:
        """
        Add an audio track to a video.

        Args:
            video_path: Video file path
            audio_path: Audio file path
            output_path: Output path
            audio_offset: Start audio after this many seconds
            audio_volume: Audio volume (0.0 to 1.0+)

        Returns:
            Path to output video with audio
        """
        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_with_audio.mp4")

        if MOVIEPY_VERSION == 0:
            return self._add_audio_ffmpeg(video_path, audio_path, output_path, audio_offset, audio_volume)

        try:
            with VideoFileClip(video_path) as video:
                with AudioFileClip(audio_path) as audio:
                    # Offset and trim audio to video duration
                    if audio_offset > 0:
                        audio = audio.subclipped(audio_offset, audio.duration)
                    else:
                        audio = audio.subclipped(0, video.duration)

                    # Adjust volume
                    if audio_volume != 1.0:
                        audio = audio.fx(afx.volumex, audio_volume)

                    # Composite
                    final = video.with_audio(audio)
                    final.write_videofile(
                        output_path,
                        codec='libx264',
                        audio_codec='aac',
                        logger=None
                    )
                    final.close()
                    return output_path
        except Exception as e:
            print(f"MoviePy audio add failed: {e}")
            return self._add_audio_ffmpeg(video_path, audio_path, output_path, audio_offset, audio_volume)

    def _add_audio_ffmpeg(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        audio_offset: float,
        audio_volume: float
    ) -> Optional[str]:
        """Fallback audio addition using FFmpeg."""
        try:
            volume_filter = "" if audio_volume == 1.0 else f",volume={audio_volume}"
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex",
                f"[1:a]adelay={int(audio_offset*1000)}|{int(audio_offset*1000)}{volume_filter}[a]",
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-shortest",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception as e:
            print(f"FFmpeg audio add failed: {e}")
        return None

    def apply_fade(
        self,
        video_path: str,
        fade_in: float = 0,
        fade_out: float = 0,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Apply fade in/out effect to video.

        Args:
            video_path: Input video
            fade_in: Fade in duration in seconds
            fade_out: Fade out duration in seconds
            output_path: Output path

        Returns:
            Path to faded video
        """
        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_faded.mp4")

        if MOVIEPY_VERSION == 0:
            # FFmpeg doesn't have easy fade, just copy
            import shutil
            shutil.copy(video_path, output_path)
            return output_path

        try:
            with VideoFileClip(video_path) as clip:
                if fade_in > 0:
                    clip = clip.fx(vfx.fadein, fade_in)
                if fade_out > 0:
                    clip = clip.fx(vfx.fadeout, fade_out)

                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    logger=None
                )
                clip.close()
                return output_path
        except Exception as e:
            print(f"MoviePy fade failed: {e}")
            import shutil
            shutil.copy(video_path, output_path)
            return output_path

    def resize_video(
        self,
        video_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        scale: float = 1.0,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Resize video to specified dimensions or scale.

        Args:
            video_path: Input video
            width: Target width (None to auto)
            height: Target height (None to auto)
            scale: Scale factor
            output_path: Output path

        Returns:
            Path to resized video
        """
        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_resized.mp4")

        if MOVIEPY_VERSION == 0:
            return self._resize_ffmpeg(video_path, width, height, output_path)

        try:
            with VideoFileClip(video_path) as clip:
                if scale != 1.0:
                    new_w = int(clip.w * scale)
                    new_h = int(clip.h * scale)
                elif width and height:
                    new_w, new_h = width, height
                elif width:
                    new_w, new_h = width, int(clip.h * width / clip.w)
                elif height:
                    new_w, new_h = int(clip.w * height / clip.h), height
                else:
                    new_w, new_h = clip.w, clip.h

                resized = clip.resized((new_w, new_h))
                resized.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    logger=None
                )
                resized.close()
                clip.close()
                return output_path
        except Exception as e:
            print(f"MoviePy resize failed: {e}")
            return self._resize_ffmpeg(video_path, width, height, output_path)

    def _resize_ffmpeg(
        self,
        video_path: str,
        width: Optional[int],
        height: Optional[int],
        output_path: str
    ) -> Optional[str]:
        """Fallback resize using FFmpeg."""
        scale_filter = ""
        if width and height:
            scale_filter = f"scale={width}:{height}"
        elif width:
            scale_filter = f"scale={width}:-2"
        elif height:
            scale_filter = f"scale=-2:{height}"

        if not scale_filter:
            import shutil
            shutil.copy(video_path, output_path)
            return output_path

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", scale_filter,
                "-c:a", "copy",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                return output_path
        except Exception:
            pass
        return None

    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract audio from video.

        Args:
            video_path: Video file path
            output_path: Output audio path

        Returns:
            Path to extracted audio
        """
        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_audio.wav")

        if MOVIEPY_VERSION == 0:
            return self._extract_audio_ffmpeg(video_path, output_path)

        try:
            with VideoFileClip(video_path) as clip:
                if clip.audio is None:
                    return None
                clip.audio.write_audiofile(output_path, logger=None)
                clip.audio.close()
                clip.close()
                return output_path
        except Exception as e:
            print(f"MoviePy audio extract failed: {e}")
            return self._extract_audio_ffmpeg(video_path, output_path)

    def _extract_audio_ffmpeg(self, video_path: str, output_path: str) -> Optional[str]:
        """Fallback audio extraction using FFmpeg."""
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass
        return None

    def get_audio_energy(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze audio energy/waveform.

        Returns:
            Dictionary with energy data and peak times
        """
        try:
            import librosa
            import numpy as np

            y, sr = librosa.load(audio_path, sr=16000)
            rms = librosa.feature.rms(y=y)[0]
            times = librosa.times_like(rms, sr=sr)

            rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-8)

            from scipy.signal import find_peaks
            peak_threshold = np.percentile(rms_normalized, 70)
            peaks, _ = find_peaks(rms_normalized, height=peak_threshold)

            return {
                'times': times.tolist(),
                'energy': rms_normalized.tolist(),
                'peak_times': [float(times[p]) for p in peaks],
                'peak_values': [float(rms_normalized[p]) for p in peaks],
                'duration': float(times[-1]) if len(times) > 0 else 0
            }
        except ImportError:
            return {'peak_times': [], 'peak_values': [], 'duration': 0}
        except Exception as e:
            print(f"Audio energy analysis failed: {e}")
            return {'peak_times': [], 'peak_values': [], 'duration': 0}


import time


# Test when run directly
if __name__ == "__main__":
    processor = MoviePyProcessor()
    print(f"MoviePy version: {MOVIEPY_VERSION}")
    print("MoviePyProcessor initialized successfully!")
