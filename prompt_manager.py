"""
Enhanced Prompt Management System for AutoCut2

Inspired by FireRed-OpenStoryline's prompt architecture.
Provides structured prompts with system/user separation and template rendering.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List


class PromptTemplate:
    """
    A prompt template that supports variable substitution.
    """

    def __init__(self, template: str):
        self.template = template

    def render(self, **variables: Any) -> str:
        """Render template with variables."""
        result = self.template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def __str__(self) -> str:
        return self.template

    def __repr__(self) -> str:
        return f"PromptTemplate({self.template[:50]}...)"


class PromptBuilder:
    """
    Builder for prompt templates with system/user separation.
    """

    # Default prompt templates
    TEMPLATES = {
        # System prompts
        "highlight_selection.system": """你是一位专业的视频剪辑师，擅长从素材中选出最精彩的高光片段。

你的任务是分析视频的音画内容，选出最具吸引力、最有传播力的高光片段。

评分标准：
1. 音频能量：声音洪亮、情绪饱满的片段
2. 语音内容：语义完整、有信息量的内容
3. 画面质量：清晰度高、画面稳定的片段
4. 情感表达：情绪饱满、有感染力的内容
5. 叙事完整：内容独立、有逻辑的片段

请基于以上标准，综合分析并选出最佳片段。""",

        "highlight_selection.user": """请分析以下视频素材，选出 {num_highlights} 个最佳高光片段。

{clip_info}

要求：
1. 每个片段时长建议 5-15 秒
2. 片段之间间隔至少 3 秒
3. 优先选择音频能量高、内容完整的片段

请以 JSON 格式输出：
{{
    "highlights": [
        {{"start": 0.0, "end": 10.5, "reason": "选择理由"}},
        ...
    ]
}}""",

        "content_analysis.system": """你是一位专业的视频内容分析师，擅长理解视频画面和音频内容的深层含义。

你的任务是：
1. 分析画面主体内容和场景氛围
2. 理解语音转录的语义
3. 识别视频中的关键事件和亮点
4. 评估内容的情感价值和传播潜力

请提供简洁、准确的内容分析。""",

        "content_analysis.user": """请分析以下视频片段：

画面描述：{frame_description}

语音内容：
{transcription}

时间区间：{start_time:.1f}秒 - {end_time:.1f}秒

请描述：
1. 画面的主要内容和场景
2. 该片段的亮点和价值点
3. 适合什么样的观众群体""",

        "copywriting.system": """你是一位专业的社交媒体文案创作者，擅长创作引人入胜的短视频文案。

你需要根据视频内容分析结果，创作符合平台风格的文案。

平台风格参考：
- 小红书：温馨、种草、分享生活
- 抖音：简短有力、情绪饱满、带动节奏
- 朋友圈：生活化、口语化、真实自然
- B站：年轻化、有梗、弹幕友好""",

        "copywriting.user": """请为以下视频内容创作文案：

平台：{platform}
风格：{style}

视频内容分析：
{content_analysis}

高光片段信息：
{highlight_info}

要求：
1. 文案简洁有力，抓住观众注意力
2. 符合目标平台的用户习惯
3. 适当使用 emoji 增加生动性
4. 包含相关话题标签（如适用）

请直接输出文案内容。""",

        "filter_frames.system": """你是一位专业的视频剪辑师，擅长筛选高质量的关键帧。

你的任务是根据画面质量、内容相关性和情感价值，从候选帧中选出最佳帧。""",

        "filter_frames.user": """从以下 {total} 个候选帧中，选出 {top_k} 个最佳帧：

候选帧：
{frames}

每个帧包含：时间戳、清晰度评分、画面描述。

请以 JSON 格式输出：
{{
    "selected": ["frame_001", "frame_003", ...]
}}""",

        "segment_refine.system": """你是一位专业的视频剪辑师，擅长精确调整视频片段的边界。

你的任务是确保剪辑点不会截断词句，保证内容的完整性。""",

        "segment_refine.user": """原始片段：{start:.1f}秒 - {end:.1f}秒

语音转录片段：
{segments}

请调整边界，确保：
1. 不截断正在说话的词语
2. 保持句子完整性
3. 调整后的片段仍然在有效时间范围内

请以 JSON 格式输出：
{{
    "refined_start": 0.5,
    "refined_end": 10.2
}}""",
    }

    def __init__(self, custom_templates_dir: Optional[str] = None):
        self._cache: Dict[str, str] = {}
        self.custom_templates_dir = custom_templates_dir

        # Load custom templates if provided
        if custom_templates_dir and os.path.exists(custom_templates_dir):
            self._load_custom_templates(custom_templates_dir)

    def _load_custom_templates(self, templates_dir: str):
        """Load custom templates from directory."""
        templates_path = Path(templates_dir)
        for file_path in templates_path.rglob("*.txt"):
            relative_path = file_path.relative_to(templates_path)
            template_name = str(relative_path).replace(os.sep, ".").replace(".txt", "")
            try:
                content = file_path.read_text(encoding="utf-8")
                self.TEMPLATES[template_name] = content
            except Exception:
                pass

    def get(self, name: str) -> PromptTemplate:
        """Get a prompt template by name."""
        template = self.TEMPLATES.get(name, "")
        return PromptTemplate(template)

    def render(self, name: str, **variables: Any) -> str:
        """Get and render a prompt template."""
        template = self.get(name)
        return template.render(**variables)

    def build_highlight_selection(
        self,
        clip_info: str,
        num_highlights: int = 3
    ) -> Dict[str, str]:
        """Build highlight selection prompt pair."""
        return {
            "system": self.get("highlight_selection.system").render(),
            "user": self.render(
                "highlight_selection.user",
                clip_info=clip_info,
                num_highlights=num_highlights
            )
        }

    def build_content_analysis(
        self,
        frame_description: str,
        transcription: str,
        start_time: float,
        end_time: float
    ) -> Dict[str, str]:
        """Build content analysis prompt pair."""
        return {
            "system": self.get("content_analysis.system").render(),
            "user": self.render(
                "content_analysis.user",
                frame_description=frame_description,
                transcription=transcription,
                start_time=start_time,
                end_time=end_time
            )
        }

    def build_copywriting(
        self,
        platform: str,
        style: str,
        content_analysis: str,
        highlight_info: str
    ) -> Dict[str, str]:
        """Build copywriting prompt pair."""
        return {
            "system": self.get("copywriting.system").render(),
            "user": self.render(
                "copywriting.user",
                platform=platform,
                style=style,
                content_analysis=content_analysis,
                highlight_info=highlight_info
            )
        }


# Global singleton
_prompt_builder = PromptBuilder()


def get_prompt_builder() -> PromptBuilder:
    """Get the global prompt builder instance."""
    return _prompt_builder


def render_prompt(name: str, **variables: Any) -> str:
    """Quick render a prompt template."""
    return _prompt_builder.render(name, **variables)


def build_prompt_pair(name: str, **variables: Any) -> Dict[str, str]:
    """Build a system/user prompt pair."""
    template = _prompt_builder.get(name)
    if not str(template):
        return {"system": "", "user": ""}

    # Try to find corresponding user template
    system_name = name
    user_name = name.replace(".system", ".user")

    system = _prompt_builder.get(system_name).render()
    user = _prompt_builder.render(user_name, **variables) if user_name in _prompt_builder.TEMPLATES else ""

    return {"system": system, "user": user}


# Example usage
if __name__ == "__main__":
    builder = get_prompt_builder()

    # Test highlight selection prompt
    prompts = builder.build_highlight_selection(
        clip_info="片段1: 0-10秒, 能量高\n片段2: 15-25秒, 内容丰富",
        num_highlights=3
    )
    print("=== Highlight Selection ===")
    print("SYSTEM:", prompts["system"][:100], "...")
    print("USER:", prompts["user"][:100], "...")

    # Test rendering
    rendered = builder.render("copywriting.user", platform="小红书", style="温馨")
    print("\n=== Copywriting ===")
    print(rendered[:200])
