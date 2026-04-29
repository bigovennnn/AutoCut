"""
Audio Processor - Audio Post-Processing for Video Assembly

Provides audio processing capabilities:
- Fade in/out effects
- Volume normalization
- Background music mixing
- Audio ducking

Based on MoviePy 2.x audio effects.
"""

import os
from typing import Optional

try:
    from moviepy import AudioFileClip, CompositeAudioClip
    from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, MultiplyVolume
    MOVIEPY_AVAILABLE = True
except ImportError:
    try:
        import moviepy.audio.fx as afx
        MOVIEPY_AVAILABLE = False
    except ImportError:
        MOVIEPY_AVAILABLE = False


class AudioProcessor:
    """
    Audio post-processor for video assembly.

    Handles:
    - Fade in/out at video start/end
    - Background music mixing with loop
    - Audio normalization
    """

    def __init__(self):
        pass

    def apply_fade_in_out(
        self,
        video_clip,
        fade_in: float = 0.3,
        fade_out: float = 0.5
    ):
        """
        Apply audio fade in and/or fade out effects.

        Args:
            video_clip: VideoClip with audio
            fade_in: Fade in duration in seconds
            fade_out: Fade out duration in seconds

        Returns:
            VideoClip with faded audio
        """
        if not MOVIEPY_AVAILABLE:
            return video_clip

        if not hasattr(video_clip, 'audio') or video_clip.audio is None:
            print("⚠️  No audio track to fade")
            return video_clip

        audio = video_clip.audio

        try:
            if fade_in > 0:
                print(f"   Applying fade in: {fade_in}s")
                audio = audio.fx(AudioFadeIn, fade_in)

            if fade_out > 0:
                print(f"   Applying fade out: {fade_out}s")
                audio = audio.fx(AudioFadeOut, fade_out)

            return video_clip.with_audio(audio)

        except Exception as e:
            print(f"⚠️  Fade effect failed: {e}")
            return video_clip

    def mix_background_music(
        self,
        video_clip,
        music_path: str,
        volume: float = 0.25,
        fade_out_duration: float = 2.0
    ):
        """
        Mix background music with video audio.

        Args:
            video_clip: VideoClip with original audio
            music_path: Path to background music file
            volume: Volume of background music (0.0 to 1.0)
            fade_out_duration: Fade out duration for music at end

        Returns:
            VideoClip with mixed audio
        """
        if not MOVIEPY_AVAILABLE:
            return video_clip

        if not os.path.exists(music_path):
            print(f"⚠️  Background music file not found: {music_path}")
            return video_clip

        if not hasattr(video_clip, 'audio') or video_clip.audio is None:
            print("⚠️  No original audio track")
            return video_clip

        try:
            # Load background music
            music = AudioFileClip(music_path)
            video_duration = video_clip.duration

            print(f"   Music duration: {music.duration:.1f}s, Video: {video_duration:.1f}s")

            # Loop music to match video duration
            if music.duration < video_duration:
                loops_needed = int(video_duration / music.duration) + 1
                music = music.loop(n=loops_needed)

            # Trim to video length
            if music.duration > video_duration:
                music = music.subclipped(0, video_duration)

            # Apply fade out to music at end
            if fade_out_duration > 0:
                music = music.fx(AudioFadeOut, fade_out_duration)

            # Lower music volume
            music = music.fx(MultiplyVolume, volume)

            # Composite original audio and music
            original_audio = video_clip.audio.with_volume(1.0)

            mixed_audio = CompositeAudioClip([original_audio, music])

            return video_clip.with_audio(mixed_audio)

        except Exception as e:
            print(f"⚠️  Background music mixing failed: {e}")
            return video_clip

    def normalize_volume(
        self,
        video_clip,
        target_db: float = -16.0
    ):
        """
        Normalize audio volume to target level.

        Note: This is a simplified implementation. For proper LUFS
        normalization, consider using ffmpeg-normalize or pyloudnorm.

        Args:
            video_clip: VideoClip with audio
            target_db: Target peak level in dB

        Returns:
            VideoClip with normalized audio
        """
        if not MOVIEPY_AVAILABLE:
            return video_clip

        if not hasattr(video_clip, 'audio') or video_clip.audio is None:
            return video_clip

        try:
            import librosa
            import soundfile as sf
            import tempfile

            # Extract audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_audio = f.name

            video_clip.audio.write_audiofile(temp_audio, logger=None)

            # Analyze volume
            y, sr = librosa.load(temp_audio, sr=None, mono=True)
            rms = librosa.feature.rms(y=y)[0]
            current_db = 20 * np.log10(np.mean(rms) + 1e-8)

            # Calculate gain
            gain_db = target_db - current_db
            gain_linear = 10 ** (gain_db / 20)

            print(f"   Volume: {current_db:.1f}dB -> {target_db}dB (gain: {gain_linear:.2f}x)")

            # Apply gain
            y_normalized = y * gain_linear
            y_normalized = np.clip(y_normalized, -1.0, 1.0)

            # Save normalized audio
            sf.write(temp_audio, y_normalized, sr)

            # Load as new audio clip
            normalized_audio = AudioFileClip(temp_audio)

            # Cleanup temp file
            try:
                os.unlink(temp_audio)
            except Exception:
                pass

            return video_clip.with_audio(normalized_audio)

        except ImportError:
            print("⚠️  librosa/soundfile not available for normalization")
            return video_clip
        except Exception as e:
            print(f"⚠️  Volume normalization failed: {e}")
            return video_clip

    def apply_audio_ducking(
        self,
        video_clip,
        music_path: Optional[str] = None,
        duck_level: float = 0.3,
        threshold_db: float = -30.0
    ):
        """
        Apply audio ducking - lower music volume when speech is present.

        Note: This is a simplified implementation. For proper ducking,
        consider using a video editing library with audio analysis.

        Args:
            video_clip: VideoClip with audio
            music_path: Path to background music (optional)
            duck_level: Volume level during speech (0.0 to 1.0)
            threshold_db: Speech threshold in dB

        Returns:
            VideoClip with ducked audio
        """
        if not MOVIEPY_AVAILABLE:
            return video_clip

        print("⚠️  Audio ducking is a simplified implementation")
        print("   For best results, use a dedicated audio editing tool")

        # For now, just mix with lower music volume
        if music_path:
            return self.mix_background_music(video_clip, music_path, volume=duck_level)

        return video_clip

    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract audio from video.

        Args:
            video_path: Path to video file
            output_path: Output audio path (auto-generated if None)

        Returns:
            Path to extracted audio file
        """
        if not MOVIEPY_AVAILABLE:
            return None

        if output_path is None:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = f"{base_name}_audio.wav"

        try:
            from moviepy import VideoFileClip

            with VideoFileClip(video_path) as clip:
                if clip.audio:
                    clip.audio.write_audiofile(output_path, logger=None)
                    return output_path
                else:
                    print("⚠️  No audio track in video")
                    return None

        except Exception as e:
            print(f"⚠️  Audio extraction failed: {e}")
            return None

    def get_audio_info(
        self,
        audio_path: str
    ) -> dict:
        """
        Get audio file information.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with duration, sample_rate, channels, etc.
        """
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            return {
                "duration": info.frames / info.samplerate,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype
            }
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback using MoviePy
        if MOVIEPY_AVAILABLE:
            try:
                audio = AudioFileClip(audio_path)
                return {
                    "duration": audio.duration,
                    "fps": audio.fps if hasattr(audio, 'fps') else None,
                }
            except Exception:
                pass

        return {}


import numpy as np

# Quick test
if __name__ == "__main__":
    processor = AudioProcessor()
    print("AudioProcessor initialized successfully!")
