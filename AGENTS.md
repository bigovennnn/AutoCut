# AGENTS.md - AutoCut Development Guide

This file provides guidance for AI coding agents working in this repository.

## Project Overview

AutoCut is a multi-modal content generation agent for social media that automatically identifies highlight segments from videos and generates platform-specific copy (Xiaohongshu, Moments, Douyin, Bilibili).

## Build & Run Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
streamlit run app.py
```

### Testing
```bash
python app.py  # Run Streamlit directly for manual testing
```

### Prerequisites
- **FFmpeg** must be installed and added to system PATH
- **Python 3.10+**
- **API Keys** (optional): Copy `config.env.example` to `config.env` and fill in keys

## Code Style Guidelines

### Python Version & Type Hints
- Use Python 3.10+ features (type hints, match statements where appropriate)
- Add type hints for all function parameters and return values
- Use `Optional[T]` instead of `Union[T, None]` for nullable types
- Use `Dict`, `List`, `Tuple` from typing module (not lowercase)

### Imports
- Standard library imports first, then third-party, then local
- Use absolute imports from package root (e.g., `from agentcore import get_llm`)
- Avoid wildcard imports (`from module import *`)
- Sort imports alphabetically within each group

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `class AutoCutAgent` |
| Functions/methods | snake_case | `def transcribe_audio()` |
| Variables | snake_case | `audio_path`, `whisper_model_size` |
| Constants | UPPER_SNAKE | `MAX_RETRIES = 3` |
| Private methods | _prefix | `def _setup_session(self)` |
| Type variables | PascalCase | `T = TypeVar('T')` |

### File Structure
```
autocut_agent.py   # Main agent class, 8-stage pipeline
asr_processor.py  # Speech-to-text with multiple backends
media_processor.py # FFmpeg/OpenCV wrapper
agentcore.py      # LLM initialization and prompts
app.py            # Streamlit web UI
```

### Error Handling
- Use specific exception types (catch `FileNotFoundError` not bare `Exception`)
- Always log errors with context: `print(f"❌ 语音识别失败: {e}")`
- Provide fallback behavior for all external API calls (mock data)
- Use try/except/finally appropriately; never swallow exceptions silently

### Class Design
- Keep classes focused and single-responsibility
- Use `@classmethod` for factory methods and cached singletons
- Initialize heavy resources lazily (e.g., Whisper model caching)
- Add docstrings to all public methods describing parameters and return values

### API Interactions
- Always set timeouts on HTTP requests (default 30s for VLM, 120s for ASR)
- Implement retry logic with exponential backoff for transient failures
- Validate external API responses before using them
- Never hardcode API keys; use environment variables via `os.getenv()`

### Working with LLMs
- Always validate LLM JSON output before using (see `_validate_highlight_result`)
- Provide fallback/default values when LLM calls fail
- Use LangChain's `JsonOutputParser` for structured output
- Keep prompts concise and include format instructions

### Video/Audio Processing
- Always verify FFmpeg availability before operations
- Check output file validity (size > 0, file exists) after video operations
- Use `ffmpeg-python` library for pipeline-style operations
- Clean up temporary files to avoid disk bloat

### Config File Discovery
Use `find_config_file()` from `agentcore` for config path resolution:
1. Environment variable `AUTOCUT_CONFIG`
2. Current working directory: `config.env`
3. Project subdirectory: `AutoCut/config.env`
4. Parent directory: `../AutoCut/config.env`

### Git Workflow
- **Commit message format**: `type(scope): description` (e.g., `fix(autocut_agent): add null check`)
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `chore`
- Commit after completing each logical change (not one big commit at the end)
- Never commit secrets or `__pycache__` directories
- Add test coverage for new features

### Testing Philosophy
- Test the 8-stage pipeline end-to-end with mock data when APIs unavailable
- Verify video trimming produces valid output files
- Test fallback behavior (simulate API failures)
- Validate JSON parsing handles malformed LLM responses

## Architecture Notes

### 4-Layer Design
```
User Layer (Streamlit) → Agent Layer (AutoCutAgent) → Media Layer (FFmpeg/OpenCV) → AI Layer (LLM/ASR/VLM)
```

### 8-Stage Processing Pipeline
1. Material Extraction (audio + keyframes)
2. Speech Recognition (ASR)
3. Clarity Pre-filtering (Laplacian variance)
4. Frame Analysis (VLM)
5. Content Scoring
6. Highlight Selection (LLM)
7. Video Trimming (FFmpeg)
8. Copywriting Generation (LLM)

### Key Implementation Patterns
- **Singleton caching** for expensive resources (Whisper models)
- **Fallback chain** for external APIs (cloud ASR → local Whisper → mock)
- **Adaptive thresholds** for quality filtering (don't hardcode magic numbers)
- **Progress callbacks** for long-running operations (Streamlit integration)
