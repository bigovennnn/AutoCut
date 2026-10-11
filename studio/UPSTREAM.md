# 上游来源和修改

- 项目：[FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline)
- 固定提交：`c9e945215586f45c12a61c1951ee9a8e9c43a027`
- 许可证：[Apache License 2.0](LICENSE)
- 分发及修改说明：[NOTICE](NOTICE)
- 上游说明：[英文](README.upstream.md)、[中文](README_zh.md)

上游源码以独立提交导入 `studio/`，随后提交 AutoCut 的适配改动。原始版权和许可声明保留；被修改的上游 Python 文件带修改说明。

新增轻量入口采用有上限的固定流程，复用上游视频渲染器。它包括 `cloud_app.py`、`quickcut/`、轻量配置、安装脚本、网页、花字和工程测试。上游完整 Agent、工具节点和界面保留，但未在轻量配置下完成真实出片验证。

修改涉及延迟加载、轻量镜头与检索路径、字体与增益处理、时间线拒绝、输出验证和异常处理。它们是产品工程实现，不能直接作为论文新颖性或专利授权证据。

字体和 Whisper 的许可证由安装脚本保留在各自资源目录。上游代码的许可不替代用户视频、外部素材或模型资源的许可。
