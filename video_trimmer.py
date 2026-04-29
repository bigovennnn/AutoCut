"""
Enhanced Video Trimmer for AutoCut2

This module provides robust video trimming and concatenation using MoviePy 2.x
with fallback to FFmpeg for maximum compatibility.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import time

try:
    from moviepy import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class VideoTrimmer:
    """
    Enhanced video trimmer with MoviePy and FFmpeg support.

    Features:
    - Stream copy for fast, lossless trimming
    - Multiple concatenation methods for reliability
    - Progress tracking
    - Automatic fallback on failure
    """

    def __init__(self, output_dir: str = "./temp_workspace"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_ffprobe_info(self, video_path: str) -> Dict[str, Any]:
        """Get video info using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height,r_frame_rate,codec_name",
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
                fps = float(num) / float(denom) if float(denom) != 0 else 30.0
            else:
                fps = float(fps_str)

            return {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": fps,
                "codec": video_stream.get("codec_name", "unknown"),
            }
        except Exception:
            return {"duration": 0, "width": 0, "height": 0, "fps": 30, "codec": "unknown"}

    def trim(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Trim a video clip from start_time to end_time.

        Args:
            video_path: Source video path
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Output path (auto-generated if None)

        Returns:
            Path to trimmed video or None on failure
        """
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return None

        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_trim_{int(start_time)}_{int(end_time)}.mp4")

        # Validate times
        info = self._get_ffprobe_info(video_path)
        duration = info["duration"]

        if duration <= 0:
            print("Invalid video duration")
            return None

        # Clamp times to valid range
        start_time = max(0, min(start_time, duration - 0.1))
        end_time = max(start_time + 0.1, min(end_time, duration))

        # Try MoviePy first if available
        if MOVIEPY_AVAILABLE:
            try:
                result = self._trim_moviepy(video_path, start_time, end_time, output_path)
                if result:
                    return result
            except Exception as e:
                print(f"MoviePy trim failed: {e}")

        # Fallback to FFmpeg
        return self._trim_ffmpeg(video_path, start_time, end_time, output_path)

    def _trim_moviepy(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str
    ) -> Optional[str]:
        """Trim using MoviePy."""
        try:
            with VideoFileClip(video_path) as clip:
                subclip = clip.subclipped(start_time, end_time)
                subclip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    logger=None,
                    verbose=False,
                    temp_audiofile=None
                )
                subclip.close()
                clip.close()

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        except Exception as e:
            print(f"MoviePy trim error: {e}")
        return None

    def _trim_ffmpeg(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str
    ) -> Optional[str]:
        """Trim using FFmpeg stream copy (fast, lossless)."""
        # Method 1: Stream copy
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", video_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass

        # Method 2: Re-encode if stream copy fails
        print("Stream copy failed, trying re-encode...")
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", video_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass

        return None

    def concatenate(
        self,
        video_clips: List[Dict[str, float]],
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract and concatenate multiple video clips.

        Args:
            video_clips: List of dicts with 'start' and 'end' keys
            video_path: Source video path
            output_path: Output path (auto-generated if None)

        Returns:
            Path to concatenated video or None on failure
        """
        if not video_clips:
            return None

        if len(video_clips) == 1:
            return self.trim(video_path, video_clips[0]['start'], video_clips[0]['end'])

        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_concat.mp4")

        # Extract each clip to temporary files
        temp_clips = []
        for i, clip_info in enumerate(video_clips):
            start = clip_info.get('start', 0)
            end = clip_info.get('end', start + 10)
            temp_output = str(self.output_dir / f"temp_clip_{i}_{int(start)}_{int(end)}.mp4")

            result = self.trim(video_path, start, end, temp_output)
            if result and os.path.exists(result):
                temp_clips.append(result)
            else:
                print(f"Failed to extract clip {i}: {start}-{end}")

        if not temp_clips:
            return None

        if len(temp_clips) == 1:
            # Only one clip survived, rename to output
            import shutil
            shutil.move(temp_clips[0], output_path)
            return output_path

        # Concatenate using FFmpeg concat demuxer
        result = self._concatenate_ffmpeg(temp_clips, output_path)

        # Cleanup temp clips
        for temp in temp_clips:
            try:
                if os.path.exists(temp):
                    os.remove(temp)
            except Exception:
                pass

        return result

    def _concatenate_ffmpeg(
        self,
        clip_paths: List[str],
        output_path: str
    ) -> Optional[str]:
        """Concatenate clips using FFmpeg concat demuxer."""
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
                "-movflags", "+faststart",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=180)

            if result.returncode == 0 and os.path.exists(output_path):
                # Verify output
                if os.path.getsize(output_path) > 0:
                    return output_path

        except Exception as e:
            print(f"FFmpeg concat failed: {e}")
        finally:
            if list_file.exists():
                list_file.unlink()

        # Try filter_complex method as fallback
        return self._concatenate_filter_complex(clip_paths, output_path)

    def _concatenate_filter_complex(
        self,
        clip_paths: List[str],
        output_path: str
    ) -> Optional[str]:
        """Concatenate using FFmpeg filter_complex."""
        if not clip_paths:
            return None

        if len(clip_paths) == 1:
            import shutil
            shutil.copy(clip_paths[0], output_path)
            return output_path

        try:
            # Build filter_complex string
            inputs = []
            filter_parts = []
            for i, path in enumerate(clip_paths):
                inputs.extend(["-i", path])
                filter_parts.append(f"[{i}:v] [{i}:a]")

            filter_str = ''.join(filter_parts)
            filter_str += f"concat=n={len(clip_paths)}:v=1:a=1[vout][aout]"

            cmd = [
                "ffmpeg", "-y"
            ] + inputs + [
                "-filter_complex", filter_str,
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=300)

            if result.returncode == 0 and os.path.exists(output_path):
                if os.path.getsize(output_path) > 0:
                    return output_path
        except Exception as e:
            print(f"Filter complex concat failed: {e}")

        return None

    def get_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        return self._get_ffprobe_info(video_path).get("duration", 0)


# Singleton instance
_trimmer = None


def get_trimmer(output_dir: str = "./temp_workspace") -> VideoTrimmer:
    """Get the global trimmer instance."""
    global _trimmer
    if _trimmer is None:
        _trimmer = VideoTrimmer(output_dir)
    return _trimmer


# Example usage
if __name__ == "__main__":
    trimmer = VideoTrimmer()
    print("VideoTrimmer initialized successfully!")
    print(f"Output directory: {trimmer.output_dir}")
