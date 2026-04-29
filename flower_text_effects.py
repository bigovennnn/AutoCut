"""
Flower Text Effects - Stylized Chinese Text Animations

Provides animated text effects (花字) for key video moments:
- Glow effect: Layered shadows creating neon/glow appearance
- Bounce effect: Vertical sinusoidal bounce animation
- Pulse effect: Rhythmic scale animation

Based on common Chinese social media text styling.
"""

import numpy as np
from typing import Optional, Tuple

try:
    from moviepy import TextClip, CompositeVideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class FlowerTextEffect:
    """
    Stylized Chinese text effects for social media highlights.

    Supports glow (霓虹发光), bounce (弹跳), and pulse (脉冲) animations.
    """

    def __init__(self):
        self.default_font = "SimHei"
        self.default_size = 80
        self.default_color = "yellow"

    def create_glow(
        self,
        text: str,
        duration: float,
        video_size: Tuple[int, int],
        fps: float = 30,
        font: Optional[str] = None,
        size: Optional[int] = None,
        color: Optional[str] = None
    ) -> Optional:
        """
        Create glow effect text - layered shadows for neon appearance.

        Creates a multi-layer effect:
        - Outer glow: Red/Orange with blur and offset
        - Mid glow: Yellow/orange
        - Core: Bright white/yellow

        Args:
            text: Text to display
            duration: How long to show
            video_size: (width, height) of video
            fps: Frames per second
            font: Font name
            size: Font size
            color: Primary color

        Returns:
            VideoClip with glow effect or None on failure
        """
        if not MOVIEPY_AVAILABLE:
            return None

        font = font or self.default_font
        size = size or self.default_size
        color = color or self.default_color

        try:
            # Glow layer configuration: (color, opacity, offset, blur simulation)
            # We simulate blur by using multiple offset layers
            glow_layers = [
                ("#FF0000", 0.2, 6),   # Red outer glow
                ("#FF4500", 0.3, 4),   # Orange-red
                ("#FF8C00", 0.4, 3),   # Dark orange
            ]

            layers = []

            # Create glow shadow layers
            for glow_color, opacity, offset in glow_layers:
                try:
                    layer = TextClip(
                        text,
                        font=font,
                        font_size=size,
                        color=glow_color,
                        duration=duration
                    )
                    layer = layer.with_opacity(opacity)

                    # Position with offset for shadow effect
                    layer = layer.with_position((offset, offset))
                    layers.append(layer)
                except Exception:
                    pass

            # Create main text with stroke
            try:
                main_text = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color=color,
                    stroke_color="white",
                    stroke_width=2,
                    duration=duration
                )
                layers.append(main_text)
            except Exception:
                # Fallback without stroke
                try:
                    main_text = TextClip(
                        text,
                        font=font,
                        font_size=size,
                        color=color,
                        duration=duration
                    )
                    layers.append(main_text)
                except Exception:
                    return None

            # Composite all layers
            if not layers:
                return None

            # Calculate composite size (larger to accommodate offset)
            composite_w = video_size[0]
            composite_h = video_size[1]

            composite = CompositeVideoClip(layers, size=composite.size if hasattr(composite, 'size') else video_size)

            # Center the text
            center_x = (video_size[0] - composite.size[0]) // 2 if hasattr(composite, 'size') else 0
            center_y = (video_size[1] - composite.size[1]) // 2 if hasattr(composite, 'size') else 0

            # If we couldn't get composite size, create centered version
            if not hasattr(composite, 'size'):
                # Just return the main text centered
                main_text = main_text.with_position(("center", "center"))
                return main_text

            composite = composite.with_position((center_x, center_y))

            return composite

        except Exception as e:
            print(f"⚠️  Glow effect failed: {e}")
            # Fallback: return simple centered text
            try:
                simple = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color=color,
                    duration=duration
                )
                simple = simple.with_position(("center", "center"))
                return simple
            except Exception:
                return None

    def create_bounce(
        self,
        text: str,
        duration: float,
        video_size: Tuple[int, int],
        font: Optional[str] = None,
        size: Optional[int] = None,
        color: Optional[str] = None
    ) -> Optional:
        """
        Create bounce animation effect.

        Text bounces vertically using sinusoidal motion.

        Args:
            text: Text to display
            duration: How long to show
            video_size: (width, height) of video
            font: Font name
            size: Font size
            color: Text color

        Returns:
            VideoClip with bounce animation or None on failure
        """
        if not MOVIEPY_AVAILABLE:
            return None

        font = font or self.default_font
        size = size or self.default_size
        color = color or "#00FFFF"  # Cyan for bounce effect

        try:
            base = TextClip(
                text,
                font=font,
                font_size=size,
                color=color,
                stroke_color="black",
                stroke_width=1,
                duration=duration
            )

            # Define bounce position function
            def bounce_position(t: float):
                # Sinusoidal bounce: completes about 2 bounces per duration
                bounce_freq = 2.0 / duration  # bounces per second
                bounce_amp = 30  # pixels

                # Calculate vertical offset using sin
                offset_y = bounce_amp * abs(np.sin(2 * np.pi * bounce_freq * t))

                # Return position tuple (x, y)
                # x stays centered, y oscillates
                return ("center", offset_y)

            # Apply position animation using fl()
            animated = base.with_position(bounce_position)

            # Position at vertical center with offset
            center_y = video_size[1] // 2
            animated = animated.with_start(0)

            return animated

        except Exception as e:
            print(f"⚠️  Bounce effect failed: {e}")
            try:
                # Fallback: simple centered text
                simple = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color=color,
                    duration=duration
                )
                simple = simple.with_position(("center", "center"))
                return simple
            except Exception:
                return None

    def create_pulse(
        self,
        text: str,
        duration: float,
        video_size: Tuple[int, int],
        font: Optional[str] = None,
        size: Optional[int] = None,
        color: Optional[str] = None
    ) -> Optional:
        """
        Create pulse (scale) animation effect.

        Text scales up and down rhythmically.

        Args:
            text: Text to display
            duration: How long to show
            video_size: (width, height) of video
            font: Font name
            size: Font size
            color: Text color

        Returns:
            VideoClip with pulse animation or None on failure
        """
        if not MOVIEPY_AVAILABLE:
            return None

        font = font or self.default_font
        size = size or self.default_size
        color = color or "#FF00FF"  # Magenta for pulse effect

        try:
            base = TextClip(
                text,
                font=font,
                font_size=size,
                color=color,
                stroke_color="white",
                stroke_width=1,
                duration=duration
            )

            # Define pulse scale function
            def pulse_scale(t: float):
                # Pulse frequency: ~3 pulses per second
                pulse_freq = 3.0
                # Scale range: 1.0 to 1.3
                scale = 1.0 + 0.3 * abs(np.sin(2 * np.pi * pulse_freq * t))
                return scale

            # Apply scale animation
            animated = base.resize(pulse_scale)
            animated = animated.with_position(("center", "center"))

            return animated

        except Exception as e:
            print(f"⚠️  Pulse effect failed: {e}")
            try:
                # Fallback
                simple = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color=color,
                    duration=duration
                )
                simple = simple.with_position(("center", "center"))
                return simple
            except Exception:
                return None

    def create_shake(
        self,
        text: str,
        duration: float,
        video_size: Tuple[int, int],
        font: Optional[str] = None,
        size: Optional[int] = None,
        color: Optional[str] = None
    ) -> Optional:
        """
        Create shake animation effect.

        Text shakes horizontally with random-like motion.

        Args:
            text: Text to display
            duration: How long to show
            video_size: (width, height) of video
            font: Font name
            size: Font size
            color: Text color

        Returns:
            VideoClip with shake animation or None on failure
        """
        if not MOVIEPY_AVAILABLE:
            return None

        font = font or self.default_font
        size = size or self.default_size
        color = color or "#FF6600"  # Orange for shake

        try:
            base = TextClip(
                text,
                font=font,
                font_size=size,
                color=color,
                stroke_color="black",
                stroke_width=2,
                duration=duration
            )

            # Define shake position function (using deterministic noise-like pattern)
            def shake_position(t: float):
                # Simulate shake with high-frequency sin waves
                shake_freq1, shake_freq2 = 15.0, 23.0
                shake_amp = 5  # pixels

                offset_x = shake_amp * (
                    np.sin(2 * np.pi * shake_freq1 * t) +
                    0.5 * np.sin(2 * np.pi * shake_freq2 * t)
                )
                offset_y = shake_amp * np.cos(2 * np.pi * shake_freq1 * t)

                return (offset_x, offset_y)

            animated = base.with_position(shake_position)

            return animated

        except Exception as e:
            print(f"⚠️  Shake effect failed: {e}")
            return None

    def create_rainbow(
        self,
        text: str,
        duration: float,
        video_size: Tuple[int, int],
        font: Optional[str] = None,
        size: Optional[int] = None
    ) -> Optional:
        """
        Create rainbow color animation effect.

        Text cycles through rainbow colors.

        Args:
            text: Text to display
            duration: How long to show
            video_size: (width, height) of video
            font: Font name
            size: Font size

        Returns:
            VideoClip with rainbow animation or None on failure
        """
        if not MOVIEPY_AVAILABLE:
            return None

        font = font or self.default_font
        size = size or self.default_size

        try:
            # Rainbow colors
            rainbow_colors = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", "#8B00FF"]

            layers = []
            for i, color in enumerate(rainbow_colors):
                try:
                    layer = TextClip(
                        text,
                        font=font,
                        font_size=size,
                        color=color,
                        duration=duration
                    )
                    # Stagger the position slightly for rainbow depth effect
                    offset = (i - len(rainbow_colors) // 2) * 2
                    layer = layer.with_position((offset, offset))
                    layer = layer.with_opacity(0.3)
                    layers.append(layer)
                except Exception:
                    pass

            if layers:
                composite = CompositeVideoClip(layers, size=video_size)
                composite = composite.with_position(("center", "center"))
                return composite
            else:
                # Fallback
                base = TextClip(
                    text,
                    font=font,
                    font_size=size,
                    color="#FF0000",
                    duration=duration
                )
                base = base.with_position(("center", "center"))
                return base

        except Exception as e:
            print(f"⚠️  Rainbow effect failed: {e}")
            return None


# Quick test
if __name__ == "__main__":
    effect = FlowerTextEffect()
    print("FlowerTextEffect initialized successfully!")

    # Test glow
    glow = effect.create_glow("精彩瞬间", 3.0, (1920, 1080))
    print(f"Glow clip: {glow is not None}")

    # Test bounce
    bounce = effect.create_bounce("弹跳效果", 2.0, (1920, 1080))
    print(f"Bounce clip: {bounce is not None}")

    # Test pulse
    pulse = effect.create_pulse("脉冲效果", 2.0, (1920, 1080))
    print(f"Pulse clip: {pulse is not None}")
