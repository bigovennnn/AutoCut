"""
Subtitle Generator - Automatic Subtitle Burning for Video

Generates subtitle clips from transcription timestamps and burns them
into video using MoviePy 2.x TextClip.
"""

from typing import List, Dict, Any, Optional, Tuple

try:
    from moviepy import TextClip, CompositeVideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class SubtitleGenerator:
    """
    Generates subtitle clips from transcription segments.

    Supports:
    - Configurable font, size, color
    - Stroke/outline for readability
    - Background box for contrast
    - Multiple position options (bottom, top, center)
    """

    def __init__(self):
        self.default_font = "SimHei"
        self.default_size = 48
        self.default_color = "white"
        self.default_stroke_color = "black"
        self.default_stroke_width = 2
        self.default_position = "bottom"

    def generate(
        self,
        transcription: Dict[str, Any],
        video_size: Tuple[int, int],
        fps: float,
        font: Optional[str] = None,
        size: Optional[int] = None,
        color: Optional[str] = None,
        stroke_color: Optional[str] = None,
        stroke_width: Optional[float] = None,
        position: str = "bottom",
        bg_color: Optional[str] = None
    ) -> List:
        """
        Generate subtitle clips from transcription.

        Args:
            transcription: Dict with segments: [{start, end, text}, ...]
            video_size: (width, height) of video
            fps: Frames per second
            font: Font name (default: SimHei)
            size: Font size in pixels (default: 48)
            color: Text color (default: white)
            stroke_color: Outline color (default: black)
            stroke_width: Outline width (default: 2)
            position: "bottom", "top", or "center"
            bg_color: Background color with alpha (e.g., "black@0.5")

        Returns:
            List of TextClip subtitle clips positioned at correct times
        """
        if not MOVIEPY_AVAILABLE:
            print("⚠️  MoviePy not available, skipping subtitles")
            return []

        segments = transcription.get("segments", [])
        if not segments:
            print("⚠️  No transcription segments, skipping subtitles")
            return []

        font = font or self.default_font
        size = size or self.default_size
        color = color or self.default_color
        stroke_color = stroke_color or self.default_stroke_color
        stroke_width = stroke_width if stroke_width is not None else self.default_stroke_width

        subtitle_clips = []
        video_width, video_height = video_size

        for seg in segments:
            start = seg.get("start", 0.0)
            end = seg.get("end", start + 1.0)
            text = seg.get("text", "").strip()

            if not text or end <= start:
                continue

            duration = end - start

            # Skip very short segments
            if duration < 0.3:
                duration = 0.3

            try:
                # Create text clip
                txt_clip = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color=color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    bg_color=bg_color,
                    duration=duration,
                    text_align="center",
                    method="caption"
                )

                # Calculate position
                pos = self._calculate_position(
                    position,
                    txt_clip.size,
                    video_size,
                    margin=60
                )

                txt_clip = txt_clip.with_position(pos)
                txt_clip = txt_clip.with_start(start)

                subtitle_clips.append(txt_clip)

            except Exception as e:
                # If specific font fails, try default
                if font != self.default_font:
                    try:
                        txt_clip = TextClip(
                            text,
                            font=self.default_font,
                            font_size=size,
                            color=color,
                            stroke_color=stroke_color,
                            stroke_width=stroke_width,
                            bg_color=bg_color,
                            duration=duration,
                            text_align="center",
                            method="caption"
                        )
                        pos = self._calculate_position(
                            position,
                            txt_clip.size,
                            video_size,
                            margin=60
                        )
                        txt_clip = txt_clip.with_position(pos)
                        txt_clip = txt_clip.with_start(start)
                        subtitle_clips.append(txt_clip)
                    except Exception:
                        pass
                else:
                    print(f"⚠️  Subtitle creation failed for '{text[:20]}...': {e}")

        print(f"   Generated {len(subtitle_clips)} subtitle clips")
        return subtitle_clips

    def _calculate_position(
        self,
        position: str,
        text_size: Tuple[int, int],
        video_size: Tuple[int, int],
        margin: int = 60
    ) -> Tuple:
        """
        Calculate subtitle position based on position string.

        Args:
            position: "bottom", "top", or "center"
            text_size: (width, height) of text clip
            video_size: (width, height) of video
            margin: Margin from edge in pixels

        Returns:
            Position tuple for MoviePy
        """
        text_width, text_height = text_size
        video_width, video_height = video_size

        if position == "bottom":
            # Center horizontally, near bottom
            x = (video_width - text_width) // 2
            y = video_height - text_height - margin
            return (x, y)

        elif position == "top":
            # Center horizontally, near top
            x = (video_width - text_width) // 2
            y = margin
            return (x, y)

        elif position == "center":
            # Dead center
            x = (video_width - text_width) // 2
            y = (video_height - text_height) // 2
            return (x, y)

        elif position == "center_bottom":
            # Center horizontally, 25% from bottom
            x = (video_width - text_width) // 2
            y = video_height * 0.75 - text_height
            return (x, y)

        else:
            # Default to bottom
            x = (video_width - text_width) // 2
            y = video_height - text_height - margin
            return (x, y)

    def create_srt_subtitle_clips(
        self,
        srt_path: str,
        video_size: Tuple[int, int],
        fps: float,
        **style
    ) -> List:
        """
        Create subtitle clips from SRT file.

        Args:
            srt_path: Path to SRT subtitle file
            video_size: (width, height) of video
            fps: Frames per second
            **style: Additional style options

        Returns:
            List of subtitle clips
        """
        import re

        segments = []
        current_start = None
        current_end = None
        current_text = []

        with open(srt_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # Parse timestamp line: 00:00:01,000 --> 00:00:03,000
                timestamp_match = re.match(
                    r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
                    line
                )

                if timestamp_match:
                    start_str, end_str = timestamp_match.groups()
                    current_start = self._parse_srt_time(start_str)
                    current_end = self._parse_srt_time(end_str)

                elif line and current_start is not None:
                    if line.isdigit():
                        continue  # Skip sequence numbers
                    current_text.append(line)

                elif not line and current_start is not None:
                    # End of current subtitle block
                    text = ' '.join(current_text)
                    if text:
                        segments.append({
                            "start": current_start,
                            "end": current_end,
                            "text": text
                        })
                    current_start = None
                    current_end = None
                    current_text = []

        transcription = {"segments": segments}
        return self.generate(transcription, video_size, fps, **style)

    def _parse_srt_time(self, time_str: str) -> float:
        """Parse SRT time string to seconds."""
        import re
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        return 0.0


# Quick test
if __name__ == "__main__":
    generator = SubtitleGenerator()
    print("SubtitleGenerator initialized successfully!")

    # Test generation
    test_transcription = {
        "segments": [
            {"start": 0.0, "end": 3.0, "text": "这是第一条字幕"},
            {"start": 3.0, "end": 6.0, "text": "这是第二条字幕"},
            {"start": 6.0, "end": 9.5, "text": "这是第三条字幕"},
        ]
    }

    clips = generator.generate(
        test_transcription,
        video_size=(1920, 1080),
        fps=30,
        position="bottom"
    )
    print(f"Generated {len(clips)} subtitle clips")
