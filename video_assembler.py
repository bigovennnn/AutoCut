"""
Video Assembler - Professional Video Assembly with MoviePy 2.x

This module provides professional video assembly capabilities including:
- Multiple highlight segment concatenation
- Crossfade and wipe transitions
- Automatic subtitle burning
- Flower text (花字) stylized effects
- Audio processing (fade in/out, background music)

Based on FireRed-OpenStoryline's MoviePy 2.x integration patterns.
"""

import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# MoviePy 2.x imports
try:
    from moviepy import (
        VideoFileClip,
        CompositeVideoClip,
        CompositeAudioClip,
        concatenate_videoclips,
        TextClip,
        ColorClip,
        ImageClip,
        AudioFileClip,
    )
    # MoviePy 2.1+ uses direct imports
    from moviepy.video.fx import CrossFadeOut, CrossFadeIn, FadeOut, FadeIn
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, MultiplyVolume
    vfx = None  # Not used with new API
    afx = None  # Not used with new API
    MOVIEPY_VERSION = 2
except ImportError:
    try:
        from moviepy.editor import (
            VideoFileClip,
            CompositeVideoClip,
            concatenate_videoclips,
            TextClip,
            AudioFileClip,
        )
        import moviepy.video.fx as vfx
        import moviepy.audio.fx as afx
        MOVIEPY_VERSION = 1
    except ImportError:
        MOVIEPY_VERSION = 0


class TransitionType(Enum):
    """Transition effect types."""
    NONE = "none"
    CROSSFADE = "crossfade"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"


@dataclass
class AssemblyConfig:
    """Configuration for video assembly."""
    # Transition settings
    transition: TransitionType = TransitionType.CROSSFADE
    transition_duration: float = 0.5  # seconds

    # Fade settings
    fade_in_duration: float = 0.3
    fade_out_duration: float = 0.5

    # Subtitle settings
    subtitle_enabled: bool = True
    subtitle_font: str = "SimHei"
    subtitle_size: int = 48
    subtitle_color: str = "white"
    subtitle_stroke_color: str = "black"
    subtitle_stroke_width: float = 2
    subtitle_position: str = "bottom"  # "bottom", "top", "center"
    subtitle_bg_color: Optional[str] = None  # e.g., "black@0.5"

    # Flower text settings
    flower_text_enabled: bool = False
    flower_text_effect: str = "glow"  # "glow", "bounce", "pulse"
    flower_text_size: int = 80
    flower_text_color: str = "yellow"

    # Audio settings
    audio_fade_in: float = 0.3
    audio_fade_out: float = 0.5
    background_music: Optional[str] = None
    background_music_volume: float = 0.25

    # Export settings
    export_codec: str = "libx264"
    export_preset: str = "fast"
    export_bitrate: str = "8M"

    # Performance
    target_resolution: Optional[Tuple[int, int]] = None  # e.g., (1920, 1080)


@dataclass
class HighlightSegment:
    """Represents a highlight segment for assembly."""
    start: float
    end: float
    reason: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    flower_text_moments: List[Dict[str, Any]] = field(default_factory=list)


class VideoAssembler:
    """
    Professional video assembler using MoviePy 2.x.

    Orchestrates highlight concatenation with transitions, subtitles,
    flower text effects, and audio processing.

    Example:
        assembler = VideoAssembler(output_dir="./temp_workspace")
        config = AssemblyConfig(
            transition=TransitionType.CROSSFADE,
            subtitle_enabled=True
        )
        result = assembler.assemble(
            video_path="input.mp4",
            highlights=[
                {"start": 0.0, "end": 10.0, "reason": "开场精彩"},
                {"start": 25.0, "end": 35.0, "reason": "高潮部分"},
                {"start": 50.0, "end": 60.0, "reason": "结尾亮点"}
            ],
            transcription={"segments": [...]},
            config=config
        )
    """

    def __init__(
        self,
        output_dir: str = "./temp_workspace",
        temp_dir: Optional[str] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.temp_dir = Path(temp_dir) if temp_dir else self.output_dir / "assembler_temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Sub-components
        self.subtitle_generator = None
        self.flower_text_effect = None
        self.audio_processor = None

    def _get_subtitle_generator(self):
        if self.subtitle_generator is None:
            from subtitle_generator import SubtitleGenerator
            self.subtitle_generator = SubtitleGenerator()
        return self.subtitle_generator

    def _get_flower_text_effect(self):
        if self.flower_text_effect is None:
            from flower_text_effects import FlowerTextEffect
            self.flower_text_effect = FlowerTextEffect()
        return self.flower_text_effect

    def _get_audio_processor(self):
        if self.audio_processor is None:
            from audio_processor import AudioProcessor
            self.audio_processor = AudioProcessor()
        return self.audio_processor

    def assemble(
        self,
        video_path: str,
        highlights: List[Dict[str, Any]],
        transcription: Optional[Dict[str, Any]] = None,
        config: Optional[AssemblyConfig] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Assemble multiple highlight segments into a final video.

        Args:
            video_path: Source video path
            highlights: List of highlight segments with start/end times
            transcription: Transcription dict with segments list
            config: Assembly configuration
            output_path: Output video path (auto-generated if None)

        Returns:
            Dict with output_path, duration, num_segments, and metadata
        """
        if config is None:
            config = AssemblyConfig()

        if MOVIEPY_VERSION == 0:
            raise RuntimeError("MoviePy is not installed. Please run: pip install moviepy")

        if output_path is None:
            base_name = Path(video_path).stem
            output_path = str(self.output_dir / f"{base_name}_assembled.mp4")

        print(f"🎬 Starting video assembly: {len(highlights)} segments")

        # Step 1: Extract each highlight segment
        print("📦 Extracting highlight clips...")
        highlight_clips = []
        clip_metadata = []

        for i, hl in enumerate(highlights):
            start = hl.get("start", 0.0)
            end = hl.get("end", start + 5.0)

            clip_path = self._extract_clip(video_path, start, end)
            if clip_path and os.path.exists(clip_path):
                try:
                    clip = VideoFileClip(clip_path)

                    # Resize if target resolution is set
                    if config.target_resolution:
                        clip = clip.resized(config.target_resolution)

                    highlight_clips.append(clip)
                    clip_metadata.append(hl)
                    print(f"   Clip {i+1}: {start:.1f}s - {end:.1f}s ({clip.duration:.1f}s)")
                except Exception as e:
                    print(f"   ⚠️  Failed to load clip {i+1}: {e}")

        if not highlight_clips:
            raise ValueError("No valid highlight clips could be extracted")

        # Step 2: Apply transitions
        if len(highlight_clips) > 1 and config.transition != TransitionType.NONE:
            print(f"✨ Applying {config.transition.value} transitions...")
            highlight_clips = self._apply_transitions(
                highlight_clips,
                config.transition,
                config.transition_duration
            )

        # Step 3: Concatenate clips
        print("🎞️  Concatenating clips...")
        if len(highlight_clips) == 1:
            final_video = highlight_clips[0]
        else:
            final_video = concatenate_videoclips(highlight_clips, method="compose")

        # Step 4: Apply fade in/out
        if config.fade_in_duration > 0:
            print(f"   Fade in: {config.fade_in_duration}s")
            final_video = final_video.fx(FadeIn, config.fade_in_duration)

        if config.fade_out_duration > 0:
            print(f"   Fade out: {config.fade_out_duration}s")
            final_video = final_video.fx(FadeOut, config.fade_out_duration)

        # Step 5: Add subtitles
        subtitle_clips = []
        if config.subtitle_enabled and transcription:
            print("📝 Adding subtitles...")
            sub_gen = self._get_subtitle_generator()
            subtitle_clips = sub_gen.generate(
                transcription,
                final_video.size,
                final_video.fps,
                font=config.subtitle_font,
                size=config.subtitle_size,
                color=config.subtitle_color,
                stroke_color=config.subtitle_stroke_color,
                stroke_width=config.subtitle_stroke_width,
                position=config.subtitle_position,
                bg_color=config.subtitle_bg_color
            )

        # Step 6: Add flower text effects
        flower_clips = []
        if config.flower_text_enabled and clip_metadata:
            print("🌸 Adding flower text effects...")
            flower_effect = self._get_flower_text_effect()
            flower_clips = self._create_flower_text_clips(
                clip_metadata,
                final_video.size,
                final_video.fps,
                config
            )

        # Composite all overlays
        if subtitle_clips or flower_clips:
            print("🎭 Compositing overlays...")
            overlay_clips = subtitle_clips + flower_clips
            final_video = CompositeVideoClip([final_video] + overlay_clips, size=final_video.size)

        # Step 7: Handle audio
        if final_video.audio is not None:
            print("🔊 Processing audio...")
            audio_proc = self._get_audio_processor()

            # Apply audio fade
            if config.audio_fade_in > 0 or config.audio_fade_out > 0:
                final_video = audio_proc.apply_fade_in_out(
                    final_video,
                    fade_in=config.audio_fade_in,
                    fade_out=config.audio_fade_out
                )

            # Mix background music
            if config.background_music and os.path.exists(config.background_music):
                print(f"🎵 Adding background music: {config.background_music}")
                final_video = audio_proc.mix_background_music(
                    final_video,
                    config.background_music,
                    volume=config.background_music_volume
                )

        # Step 8: Export
        print(f"💾 Exporting to {output_path}...")
        try:
            final_video.write_videofile(
                output_path,
                codec=config.export_codec,
                preset=config.export_preset,
                bitrate=config.export_bitrate,
                logger=None,
                verbose=False
            )
        except Exception as e:
            print(f"⚠️  Export error: {e}")
            # Fallback export without bitrate
            final_video.write_videofile(
                output_path,
                codec=config.export_codec,
                preset=config.export_preset,
                logger=None,
                verbose=False
            )

        # Cleanup
        final_video.close()
        for clip in highlight_clips:
            clip.close()

        # Cleanup temp files
        self._cleanup_temp()

        # Calculate total duration
        total_duration = sum(
            hl.get("end", 0) - hl.get("start", 0)
            for hl in highlights
        )

        print(f"✅ Assembly complete: {output_path}")
        print(f"   Duration: {total_duration:.1f}s, Segments: {len(highlights)}")

        return {
            "output_path": output_path,
            "duration": total_duration,
            "num_segments": len(highlights),
            "transition": config.transition.value,
            "subtitle_enabled": config.subtitle_enabled,
            "flower_text_enabled": config.flower_text_enabled
        }

    def _extract_clip(self, video_path: str, start: float, end: float) -> Optional[str]:
        """Extract a clip from video using FFmpeg (fast, stream copy)."""
        clip_path = str(self.temp_dir / f"clip_{int(start)}_{int(end)}.mp4")

        try:
            import subprocess

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", video_path,
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                clip_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60
            )

            if result.returncode == 0 and os.path.exists(clip_path):
                return clip_path
        except Exception:
            pass

        return None

    def _apply_transitions(
        self,
        clips: List[VideoFileClip],
        transition_type: TransitionType,
        duration: float
    ) -> List[VideoFileClip]:
        """Apply transition effect between consecutive clips."""
        if len(clips) < 2:
            return clips

        if transition_type == TransitionType.CROSSFADE:
            return self._apply_crossfade_transition(clips, duration)
        elif transition_type in (TransitionType.WIPE_LEFT, TransitionType.WIPE_RIGHT):
            return self._apply_wipe_transition(clips, duration, transition_type)
        elif transition_type in (TransitionType.SLIDE_UP, TransitionType.SLIDE_DOWN):
            return self._apply_slide_transition(clips, duration, transition_type)
        else:
            return clips

    def _apply_crossfade_transition(
        self,
        clips: List[VideoFileClip],
        duration: float
    ) -> List[VideoFileClip]:
        """Apply crossfade transition between clips."""
        if len(clips) < 2:
            return clips

        result = [clips[0]]

        for i in range(1, len(clips)):
            prev_clip = result[-1]
            curr_clip = clips[i]

            # Calculate actual transition duration
            actual_duration = min(
                duration,
                prev_clip.duration / 2,
                curr_clip.duration / 2
            )

            if actual_duration < 0.1:
                # Too short, just concatenate
                result.append(curr_clip)
                continue

            # Get overlap regions
            prev_overlap = prev_clip.subclipped(
                prev_clip.duration - actual_duration,
                prev_clip.duration
            )
            next_overlap = curr_clip.subclipped(0, actual_duration)

            # Apply crossfade effects
            faded_out = prev_overlap.fx(CrossFadeOut, actual_duration)
            faded_in = next_overlap.fx(CrossFadeIn, actual_duration)

            # Create transition composite
            transition = CompositeVideoClip([faded_out, faded_in])

            # Build final sequence:
            # prev_main + transition + next_main
            prev_main = prev_clip.subclipped(0, prev_clip.duration - actual_duration)
            next_main = curr_clip.subclipped(actual_duration, curr_clip.duration)

            # Replace last clip with transitioned version
            result.pop()

            try:
                transitioned = concatenate_videoclips(
                    [prev_main, transition, next_main],
                    method="compose"
                )
                result.append(transitioned)
            except Exception:
                # Fallback: just append clips
                result.append(prev_clip)
                result.append(curr_clip)

            result.append(curr_clip)

        return result

    def _apply_wipe_transition(
        self,
        clips: List[VideoFileClip],
        duration: float,
        direction: TransitionType
    ) -> List[VideoFileClip]:
        """Apply wipe transition (left or right)."""
        is_left = (direction == TransitionType.WIPE_LEFT)

        result = [clips[0]]

        for i in range(1, len(clips)):
            prev_clip = result[-1]
            curr_clip = clips[i]

            actual_duration = min(duration, prev_clip.duration / 2, curr_clip.duration / 2)

            if actual_duration < 0.1:
                result.append(curr_clip)
                continue

            # For wipe, we use margin to hide/reveal
            w = prev_clip.size[0]

            prev_main = prev_clip.subclipped(0, prev_clip.duration - actual_duration)
            prev_tail = prev_clip.subclipped(prev_clip.duration - actual_duration, prev_clip.duration)
            next_head = curr_clip.subclipped(0, actual_duration)
            next_main = curr_clip.subclipped(actual_duration, curr_clip.duration)

            if is_left:
                # Wipe from left: prev slides out to right, next slides in from left
                prev_tail = prev_tail.margin(left=-int(w * 0.5), opacity=0)
                next_head = next_head.margin(left=int(w * 0.5), opacity=1)
            else:
                # Wipe from right: prev slides out to left, next slides in from right
                prev_tail = prev_tail.margin(right=-int(w * 0.5), opacity=0)
                next_head = next_head.margin(right=int(w * 0.5), opacity=1)

            transition = CompositeVideoClip([prev_tail, next_head])

            result.pop()
            try:
                transitioned = concatenate_videoclips(
                    [prev_main, transition, next_main],
                    method="compose"
                )
                result.append(transitioned)
            except Exception:
                result.append(prev_clip)

            result.append(curr_clip)

        return result

    def _apply_slide_transition(
        self,
        clips: List[VideoFileClip],
        duration: float,
        direction: TransitionType
    ) -> List[VideoFileClip]:
        """Apply slide transition (up or down)."""
        # Similar to wipe but vertical
        is_up = (direction == TransitionType.SLIDE_UP)

        result = [clips[0]]

        for i in range(1, len(clips)):
            prev_clip = result[-1]
            curr_clip = clips[i]

            actual_duration = min(duration, prev_clip.duration / 2, curr_clip.duration / 2)

            if actual_duration < 0.1:
                result.append(curr_clip)
                continue

            h = prev_clip.size[1]

            prev_main = prev_clip.subclipped(0, prev_clip.duration - actual_duration)
            prev_tail = prev_clip.subclipped(prev_clip.duration - actual_duration, prev_clip.duration)
            next_head = curr_clip.subclipped(0, actual_duration)
            next_main = curr_clip.subclipped(actual_duration, curr_clip.duration)

            if is_up:
                prev_tail = prev_tail.margin(top=-int(h * 0.5), opacity=0)
                next_head = next_head.margin(top=int(h * 0.5), opacity=1)
            else:
                prev_tail = prev_tail.margin(bottom=-int(h * 0.5), opacity=0)
                next_head = next_head.margin(bottom=int(h * 0.5), opacity=1)

            transition = CompositeVideoClip([prev_tail, next_head])

            result.pop()
            try:
                transitioned = concatenate_videoclips(
                    [prev_main, transition, next_main],
                    method="compose"
                )
                result.append(transitioned)
            except Exception:
                result.append(prev_clip)

            result.append(curr_clip)

        return result

    def _create_flower_text_clips(
        self,
        clip_metadata: List[Dict],
        video_size: Tuple[int, int],
        fps: float,
        config: AssemblyConfig
    ) -> List:
        """Create flower text effect clips for key moments."""
        flower_clips = []
        flower_effect = self._get_flower_text_effect()

        # Calculate global timestamps for each clip
        current_time = 0.0
        clip_times = []

        for metadata in clip_metadata:
            clip_start = current_time
            clip_end = clip_start + (metadata.get("end", 0) - metadata.get("start", 0))
            clip_times.append((clip_start, clip_end, metadata))
            current_time = clip_end

        for i, (clip_start, clip_end, metadata) in enumerate(clip_times):
            moments = metadata.get("flower_text_moments", [])

            for moment in moments:
                text = moment.get("text", "")
                relative_start = moment.get("start", 0)  # Relative to clip start
                duration = moment.get("duration", 2.0)

                global_start = clip_start + relative_start

                if config.flower_text_effect == "glow":
                    clip = flower_effect.create_glow(
                        text, duration, video_size, fps
                    )
                elif config.flower_text_effect == "bounce":
                    clip = flower_effect.create_bounce(
                        text, duration, video_size
                    )
                elif config.flower_text_effect == "pulse":
                    clip = flower_effect.create_pulse(
                        text, duration, video_size
                    )
                else:
                    continue

                if clip:
                    clip = clip.with_start(global_start)
                    flower_clips.append(clip)

        return flower_clips

    def _cleanup_temp(self):
        """Clean up temporary files."""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


# Quick test
if __name__ == "__main__":
    assembler = VideoAssembler(output_dir="./temp_workspace")
    print(f"MoviePy version: {MOVIEPY_VERSION}")
    print("VideoAssembler initialized successfully!")
