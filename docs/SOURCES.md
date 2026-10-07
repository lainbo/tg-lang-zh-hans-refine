# 源文件下载指引

日常更新只需要当前平台的官方英文。用户授权时，AI 可以操作已登录的浏览器完成下载。增量更新时暂留下载文件原名，将路径传给 `prepare_update.py`，由脚本先归档旧数据再安装新英文。任务结束后按 [下载资源清理规则](../AGENTS.md#维护铁律) 删除原件及项目、历史归档中的复制件；即使没有内容更新，也要完成清理。

## 平台与英文源

| 平台 | 官方英文 | 维护状态 |
|---|---|---|
| Android | https://translations.telegram.org/en/android/ | 独立维护，导出 XML |
| iOS | https://translations.telegram.org/en/ios/ | 持续维护 |
| TDesktop | https://translations.telegram.org/en/tdesktop/ | 独立维护 |
| macOS 原生客户端 | https://translations.telegram.org/en/macos/ | 独立维护 |

在对应页面登录后，点击 **Export**，下载全部字符串。iOS、TDesktop、macOS 选择 `.strings`，Android 导出 `.xml`。

增量更新示例：

```bash
python3 scripts/prepare_update.py android --en ~/Downloads/android_en_VERSION.xml
python3 scripts/prepare_update.py ios --en ~/Downloads/ios_en_VERSION.strings
python3 scripts/prepare_update.py tdesktop --en ~/Downloads/tdesktop_en_VERSION.strings
python3 scripts/prepare_update.py macos --en ~/Downloads/macos_en_VERSION.strings
```

各平台分别运行，文件必须匹配对应平台。首次初始化才将英文暂存为 `data/<platform>/raw/en.strings`（安卓为 `en.xml`）。完成解析和核验后，英文基准保留在 `parsed/en.json` 与 `merged.json`，任务结束时清理 raw 中的下载文件。

## 本项目精修记忆

`prepare_update.py` 从当前 `merged.json` 与 `translated.json` 生成 `work/<platform>/translation-memory.json`，同时保存旧英文和旧精修译文。它供翻译时核对术语和历史表达；原文未变的译文另存到 `translated.reused.json`，用于稳定复用。

当前精修主文件是本项目自己的积累，每次更新前必须保留。历史参考以解析后的 JSON 保存，当前翻译记忆以成对记录为准。

## 官方简中与社区包按需查阅

遇到具体疑点时，可先按 key 查阅本地 `data/<platform>/parsed/official-zh.json`、`zhcncc.json` 或 `ref-*.json`。文件可能过时，须结合当前英文核对。

需要最新官方简中时，使用与英文相同的导出方式：

- Android：https://translations.telegram.org/zh-hans/android/
- iOS：https://translations.telegram.org/zh-hans/ios/
- TDesktop：https://translations.telegram.org/zh-hans/tdesktop/
- macOS 原生客户端：https://translations.telegram.org/zh-hans/macos/

先备份现有 `parsed/official-zh.json`，再将下载文件暂存为 `data/<platform>/raw/official-zh.strings`（安卓为 `official-zh.xml`）。运行 `parse_strings.py <平台>` 后即可在对应 JSON 中按 key 查阅。它不进入默认待译输入，查阅时在审校备注中记录来源、文件版本、SHA-256、相关 key 和采用依据；任务结束时清理下载原件及 raw 中的副本。

社区包与其他参考包保留已有解析 JSON。默认流程不需要下载或维护新版社区包。任何参考译文都不能代替功能上下文的查证。

## 上传回写

审校完产出 `dist/<platform>/zh-Hans-custom.strings`（安卓为 `.xml`）后，人工上传至自定义语言包的对应平台，核对后点击 **EDIT PHRASES → EDIT ALL** 提交，导出线上结果与本地核对，再在客户端检查实际效果。上传停滞时可刷新重试；固定残留的停止条件与判断依据见 [上传经验](05-troubleshooting.md#上传停滞反复提交与停止条件)，详细步骤见 [操作流程](02-workflow.md)。
