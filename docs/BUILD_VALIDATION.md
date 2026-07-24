# 首版构建验证

本文件用于触发首版 Pull Request 构建验证。验证范围包括：

- TXT 关键词首次命中即停止当前文件
- 跨读取块关键词不漏检
- Debug 单元测试
- Debug APK 构建
- Release APK 构建
- 每个 Gradle 阶段 5 分钟硬超时
