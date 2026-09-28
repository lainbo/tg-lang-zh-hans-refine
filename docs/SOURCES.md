# 源文件下载指引

日常更新只需要当前平台的官方英文。用户授权时，AI 可以操作已登录的浏览器完成下载。增量更新保留下载文件原名，将路径传给 `prepare_update.py`，由脚本先归档旧数据再安装新英文。

## 平台与英文源

| 平台 | 官方英文 | 维护状态 |
|---|---|---|
| iOS | https://translations.telegram.org/en/ios/ | 持续维护 |
| TDesktop | https://translations.telegram.org/en/tdesktop/ | 独立维护 |
| macOS | 保留现有文件 | 停止维护 |

在对应页面登录后，点击 **Export**，选择 `.strings` 格式，下载全部字符串。

增量更新示例：

```bash
python3 scripts/prepare_update.py ios --en ~/Downloads/ios_en_VERSION.strings
python3 scripts/prepare_update.py tdesktop --en ~/Downloads/tdesktop_en_VERSION.strings
```

两平台分别运行，文件必须匹配对应平台。首次初始化才将英文重命名为 `en.strings` 放入 `data/<platform>/raw/`。

## 本项目精修记忆

`prepare_update.py` 从当前 `merged.json` 与 `translated.json` 生成 `work/<platform>/translation-memory.json`，同时保存旧英文和旧精修译文。它供初译后的术语与历史表达核对；原文未变的译文另存到 `translated.reused.json`，用于稳定复用。

当前精修主文件是本项目自己的积累，每次更新前必须保留。原有 `ref-current-refined.strings` 作为历史文件保留，当前翻译记忆以成对记录为准。

## 官方简中与社区包按需查阅

遇到具体疑点时，可先按 key 查阅本地 `data/<platform>/parsed/official-zh.json`、`zhcncc.json` 或 `ref-*.json`。文件可能过时，须结合当前英文核对。

需要最新官方简中时，使用与英文相同的导出方式：

- iOS：https://translations.telegram.org/zh-hans/ios/
- TDesktop：https://translations.telegram.org/zh-hans/tdesktop/

保留下载原件；先备份现有同名文件，再另存为 `data/<platform>/raw/official-zh.strings`。运行 `parse_strings.py <平台>` 后即可在对应 JSON 中按 key 查阅。它不进入默认待译输入，查阅时在审校备注中记录文件版本、相关 key 和采用依据。

社区包 `zhcncc.strings` 与其他 `ref-*.strings` 保留已有文件。默认流程不需要下载或维护新版社区包。任何参考译文都不能代替功能上下文的查证。

## 上传回写

审校完产出 `dist/<platform>/zh-Hans-custom.strings` 后，人工上传至自定义语言包的对应平台，核对后点击 **EDIT PHRASES → EDIT ALL** 提交，导出线上结果与本地核对，再在客户端检查实际效果。上传停滞时可刷新重试；固定残留的停止条件与判断依据见 [上传经验](05-troubleshooting.md#上传停滞反复提交与停止条件)，详细步骤见 [操作流程](02-workflow.md)。
