# AutoCut · 轻量自动剪辑

把几段生活、校园或活动视频，剪成可下载的短片。

**当前可运行版本在 [`studio/`](studio/)，更新于 2026-10-12。** 基于固定版本 FireRed-OpenStoryline，采用云端画面理解与剪辑规划、本机轻量渲染，面向 8GB Mac 开发。

## 已实现

- 上传或读取本地视频，用一句要求自动选段、组织时间线并导出 MP4。
- 自动打磨剪辑方案；支持横、竖、方形画幅、剪辑节奏和原声，最长边 720px。
- 三种花字：橙黄冲击、薄荷贴纸、漫画强调，支持成片后换样式。
- 可选轻量本地语音识别，生成语音字幕和 SRT；核对改字后另存新成片。
- 保留源区间、真实模型调用、失败原因、实际输出检查和导出历史。

目前未完成本地视觉/文本模型部署、自动配乐、配音和完整讲解剪辑。模型服务可以选择云端或已部署的本地兼容接口，本地选项需要用户自行准备服务。自动剪辑和识别结果仍需观看、听音核对。

## 快速启动

需要 Python 3.11 和 FFmpeg（含 ffprobe）。macOS 可用 `brew install ffmpeg` 安装媒体工具。

```bash
git clone https://github.com/bigovennnn/AutoCut.git
cd AutoCut/studio
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-cloud.lock.txt
python scripts/bootstrap_cloud_resources.py
python scripts/bootstrap_fancy_fonts.py
python scripts/start_cloud.py
```

打开 <http://127.0.0.1:8005>，在页面填写支持相应能力的模型 API Key。可以直接上传视频，也可以把视频放进 `studio/uploads/`。首次未安装本地语音识别时关闭语音字幕，随后按安装指南启用。

- [详细安装、模型配置与语音字幕](studio/CLOUD_SETUP.md)
- [花字制作与验收流程](studio/docs/FANCY_TITLE_WORKFLOW.md)
- [验证范围和已知限制](studio/docs/VALIDATION.md)
- [上游来源、固定版本和许可证](studio/UPSTREAM.md)

## 验证与目录

发布前在整理后的代码目录执行 31 项工程测试，覆盖供应商契约、异常拒绝、时间线、真实 FFmpeg 输出、旋转素材、语音映射和花字。已有四组日常素材的真实云端开发验证；这不代表普遍剪辑质量或论文实验结论，详见验证说明。

```text
studio/              当前轻量出片版本
  cloud_app.py       服务入口
  web/cloud/         出片页面
  src/.../quickcut/  剪辑规划、复核、字幕与运行记录
  tests/cloud/       工程测试
docs/legacy/         历史版本说明
```

根目录的 `app.py`、`api_server.py` 等是历史原型，已发现模拟输出和正确性缺陷，不作为当前产品入口。其历史说明保存在 [README-v2.2.md](docs/legacy/README-v2.2.md)，保留源码和 Git 历史以供追溯。

API Key、个人视频、模型与字体二进制、真实运行记录不随源码提交。源视频、安装资源和成片留在本机相应忽略目录。

## 来源

当前版本复用 [FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline)，固定提交 `c9e945215586f45c12a61c1951ee9a8e9c43a027`，保留 [Apache-2.0 许可证](studio/LICENSE)和 [修改说明](studio/NOTICE)。字体和 Whisper 资源另附各自许可。工程适配本身不等于研究创新或专利授权。
