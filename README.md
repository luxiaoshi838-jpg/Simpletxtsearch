# 简搜（Simpletxtsearch）

“简搜”是一个独立的安卓文件夹内容检索工具。它在指定文件夹内逐个搜索 TXT、PDF、文档和表格；每个文件第一次命中后立即停止读取该文件，结果只保留文件名，然后继续搜索下一个文件。

## v1.1 功能

- 通过安卓系统文件夹选择器授权一个总文件夹
- 自动列出总文件夹下的一级子文件夹
- 一级子文件夹默认全选，可逐项取消；取消后整棵子目录不再搜索
- 总文件夹根目录中的受支持文件始终参与搜索
- 搜索类型默认全部，可按大类勾选：
  - TXT：`.txt`、`.md`、`.log`
  - PDF：`.pdf`
  - 文档：`.doc`、`.docx`、`.odt`、`.rtf`
  - 表格：`.xls`、`.xlsx`、`.ods`、`.csv`、`.tsv`
- 每个文件第一次发现目标文字后立即停止读取该文件，并搜索下一个文件
- 结果只显示文件名，不显示正文或匹配片段
- 使用 Android 前台服务后台运行，切换应用或锁屏后仍可继续
- 通知栏显示扫描数量和命中数量，可停止任务
- 纯文本支持 UTF-8、UTF-16、GB18030/GBK/GB2312 及自动编码识别
- 可选择是否区分大小写
- 可复制全部命中文件名
- 保留总文件夹、子文件夹勾选、文件类型、关键词、大小写设置和上次搜索结果

## 搜索范围规则

选择总文件夹后，软件显示它的**一级子文件夹多选列表**。取消某个一级子文件夹后，该文件夹和其全部下级文件夹都不会被扫描。总文件夹根目录中符合已选文件类型的文件仍会参与搜索。

## 文件内容支持说明

- TXT、MD、LOG、CSV、TSV：按字符编码流式读取
- PDF：逐页提取可选择的文字；图片扫描版 PDF 不进行 OCR
- DOC、XLS：使用兼容旧版 Microsoft Office 二进制格式的解析组件
- DOCX、XLSX、ODT、ODS：读取压缩包中的正文或单元格 XML
- RTF：提取普通文字和 Unicode 转义文字
- 加密、损坏或应用无权读取的文件会被计入“无法读取”并跳过

## 后台运行

搜索由用户点击“开始后台搜索”后启动 Android 前台服务。状态栏会显示持续通知。系统“强行停止”应用后任务会结束，这是 Android 的系统限制。

## 构建

要求：JDK 17、Android SDK 35、Gradle 8.2.1。

```bash
gradle testDebugUnitTest
gradle assembleDebug
gradle assembleRelease
```

GitHub Actions 会执行单元测试并生成 Debug/Release APK；每个 Gradle 阶段均有 5 分钟硬超时。

## 签名

稳定私钥不会放进公开仓库。请查看 [SIGNING.md](SIGNING.md)。后续版本继续使用同一密钥并提高 versionCode，即可覆盖安装。

## 软件信息

- 软件名：简搜
- 仓库名：Simpletxtsearch
- applicationId：`com.luxiaoshi.simpletxtsearch`
- 当前版本：1.1.0
- 最低安卓版本：Android 8.0（API 26）
- 许可证：MIT
