# AutoCut Studio：轻量直接出片

当前发布：2026-10-12。基于固定版本 FireRed-OpenStoryline，详见 [UPSTREAM.md](UPSTREAM.md)。已验证的主入口是 `cloud_app.py`，上游完整 Agent 保留在目录内。

## 1. 安装和启动

需要 Python 3.11、FFmpeg 和 ffprobe。当前开发与媒体验证环境是 8GB Apple Silicon Mac；其他平台尚未实测。macOS 可通过 `brew install ffmpeg` 安装媒体工具。

在仓库根目录执行：

```bash
cd studio
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-cloud.lock.txt
python scripts/bootstrap_cloud_resources.py
python scripts/bootstrap_fancy_fonts.py
python scripts/start_cloud.py
```

打开 <http://127.0.0.1:8005>，停止服务按 `Ctrl+C`。不要用根目录的旧 `requirements.txt` 安装这个入口，也不要为启动轻量版运行上游的整包模型下载脚本。

也可用 uv 创建环境和安装锁定依赖：

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-cloud.lock.txt
```

字体准备脚本下载并校验固定 SHA-256，保留 OFL 许可；它们不会下载视觉或语言模型。使用三种花字需要完成两个字体准备步骤。

## 2. 第一次出片

1. 在页面上传 1—5 段自有视频，或把视频放入 `studio/uploads/` 后刷新列表。合计限制为 500MB、5 分钟，首次建议 1—2 分钟素材、约 15—30 秒成片。
2. 选择云端方案，填写账号可用的 API 地址、模型名与 Key。当前默认由 DeepSeek 兼容接口承担画面理解与剪辑规划，也可配置独立的视觉服务。模型必须支持各自所需能力，页面选择本地服务不等于自动安装了本地模型。
3. 填写剪辑要求，选择画幅、节奏、花字样式和是否保留原声，点击“一键剪辑并导出”。首次未安装语音识别时，关闭语音字幕；画面标题与语音字幕分别处理。
4. 成功后观看切点、动作和原声，下载 MP4 与运行记录。语音字幕可以核对改字；花字可以换样式，两者均生成新运行，保留原版。

如需读取其他素材目录，在启动前设置 `AUTOCUT_UPLOADS`。例如：

```bash
export AUTOCUT_UPLOADS=/absolute/path/to/your/videos
python scripts/start_cloud.py
```

Key 可以只填页面，也可复制 `.env.cloud.example` 为 `.env.cloud` 后在本地填写。该文件不提交 Git。页面不把 Key 写入浏览器存储，运行记录不保存 Key。模型请求默认直接连接并校验证书；确实需要环境代理时设置 `AUTOCUT_TRUST_ENV_PROXY=1`。

## 3. 轻量本地语音字幕，可选

云端负责画面理解与规划时，也可以用本地 Whisper.cpp 识别语音。音频在本机识别，得到的转录文字会提交给所选规划模型。自动转录需要人工核对，嘈杂餐厅尤其容易错字。

在 `studio/` 内执行以下命令。需要 Apple 命令行编译工具；此配置启用 Apple Metal，未验证其他平台的构建方式。

```bash
python -m pip install cmake==4.4.4
mkdir -p runtime-local/vendor
git clone --depth 1 --branch v1.9.4 https://github.com/ggml-org/whisper.cpp.git runtime-local/vendor/whisper.cpp
cmake -S runtime-local/vendor/whisper.cpp -B runtime-local/vendor/whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_BUILD_EXAMPLES=ON -DGGML_METAL=ON -DBUILD_SHARED_LIBS=OFF
cmake --build runtime-local/vendor/whisper.cpp/build --target whisper-cli -j4
python scripts/bootstrap_local_asr.py --model small-q5_1
```

Whisper.cpp 固定版本为 v1.9.4；模型脚本校验固定哈希并保留许可证。small-q5_1 模型约 181MiB，另可安装约 141MiB 的 base。未安装识别程序和对应模型时不要开启语音字幕。没有在这个发布目录重复下载或编译语音模型；集成已经在原开发环境和真实视频中验证。

## 4. 自动剪辑和花字

自动打磨默认开启：均匀候选窗结合已识别语句调整，最多 40 窗；每窗首、中、尾抽样，识图后规划，再对选段做至多一次有上限的画面复核。所有方案、源区间、过滤记录、阶段失败与实际用量保留在运行 JSON 中。抽样不能证明整段动作或语义完整。

当前提供橙黄冲击、薄荷贴纸、漫画强调三种花字，使用渐变、描边、阴影与整体弹入。制作、素材来源和验收流程见 [FANCY_TITLE_WORKFLOW.md](docs/FANCY_TITLE_WORKFLOW.md)。固定位置仍需人工检查遮挡，尚未实现自动人脸避让、逐字跳动或音乐卡点。

输出最长边为 720px，支持横、竖、方形画幅、硬切、原声、画面标题、可选语音字幕与 SRT。未实现新增配音、配乐、自动搜素材和完整讲解模式。完全本地画面理解与规划要求用户另行部署兼容服务，目前尚未完成本地模型验证。

## 5. 数据和验证

任务数据位于 `studio/runtime-local/runs/<run_id>/`，输入按任务隔离，输出在报告成功前检查大小、音视频信息、实测时长并完整解码。失败不会用原视频或模板文本冒充成功。可选复核失败保留明确的降级状态。

```bash
PYTHONPATH=src:. python -m pytest tests/cloud -q
python -m pip check
```

若使用 uv 创建的无 pip 环境，可改用 `uv pip check --python .venv/bin/python`。

工程测试包含注入式供应商契约和真实 FFmpeg 渲染。真实云端开发验证的汇总与限制见 [VALIDATION.md](docs/VALIDATION.md)。它们不证明剪辑观感、一般 ASR 准确率或研究创新。

个人视频、真实运行记录、资源二进制和 Key 不随源码发布。页面的 `/examples` 使用本地样片台账生成的页面；新克隆不附带个人样片，尚无该页面时会提示不存在。
