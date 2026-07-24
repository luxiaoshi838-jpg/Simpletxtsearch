# 稳定签名说明

公开仓库不会保存 APK 私钥或密码。

Release 构建可通过以下环境变量加载同一把稳定签名：

- `SIMPLETXTSEARCH_KEYSTORE_PATH`
- `SIMPLETXTSEARCH_KEYSTORE_PASSWORD`
- `SIMPLETXTSEARCH_KEY_ALIAS`
- `SIMPLETXTSEARCH_KEY_PASSWORD`
- `SIMPLETXTSEARCH_VERSION_CODE`
- `SIMPLETXTSEARCH_VERSION_NAME`

只要后续版本保持：

1. applicationId 不变：`com.luxiaoshi.simpletxtsearch`
2. 使用同一 keystore 和 alias
3. versionCode 高于已安装版本

就可以直接覆盖安装，不会出现签名不一致。

首版稳定 keystore 单独交付给仓库所有者，不提交到 GitHub。请至少保留两份离线备份。
