# tg-lang-refine

Telegram 简体中文语言包精修工具链。以当前官方英文、功能上下文和共用术语为依据，由翻译 AI 翻译并复核，生成可上传到 translations.telegram.org 的自定义语言包。

质量标准是**信、达、雅与跨平台一致性**，详见 [审校规范与共用术语](docs/06-translation-style.md)。脚本只负责数据整理、校验和打包，使用 Python 标准库，不调用翻译 API。

## 维护范围

- Android、iOS、TDesktop、macOS 原生客户端独立更新，共用术语规范。
- 日常更新只下载官方英文。官方简中和社区包保留解析后的 JSON，按具体疑点查阅。
- 自己的精修译文作为翻译记忆。英文未变时稳定复用，发现错误或术语冲突时定向修订。

## 日常增量更新

通过已登录的浏览器，在对应平台的官方英文页面导出 `.strings`（安卓导出 `.xml`），详见 [下载指引](docs/SOURCES.md)。将实际下载路径传给以下命令，**保留现有英文基准、译文与成品，交给脚本先备份再替换**：

```bash
python3 scripts/prepare_update.py ios \
  --en ~/Downloads/ios_en_VERSION.strings
```

脚本会把上一轮源文件、中间产物与成品归档到 `work/ios/history/<时间>/`，保存来源文件名和 SHA-256，比较新旧英文，并自动完成**复数折叠、同英文聚合、四端精修候选预注入（精确匹配、占位符安全投影与大小写不敏感提示）、变更词条旧译注入、同模块邻居 `context` 注入与复杂度分层切片**（常规片 `fast` 默认 ≤350 组，疑难片 `deep` 默认 ≤120 组），输出 `compact.partNN.json`、`compact.partNN.meta.json` 与 `compact-manifest.json`。其余未变译文保留在 `translated.reused.json`，旧英文与精修译文另存为 `translation-memory.json`。多平台同时更新时建议按规模由小到大串行执行，前序平台产出的新译文会自动进入后续平台的候选池。

翻译 AI 按分片派发独立子代理：首轮并行读取对应档位的 `PROMPT.fast.md` 或 `PROMPT.deep.md` 与 `compact.partNN.json`，结合片内上下文直接输出短编号 JSON `reply.partNN.json`（确认候选写 `"="` / `"=1"`，微调沿用旧译写 `"=prev"`，独立新译写 `"译文"`，同英文组存在语境分歧时按 key 覆写）。每片完成后展开并校验：

```bash
python3 scripts/import_from_ai.py ios --part 1
```

初译全部通过后，导出并执行带本地规则预检的差量二审（常规片精确复用且无预检提示的词条自动豁免，二审仅输出需修改的编号补丁，整片无修改输出 `{}`）：

```bash
python3 scripts/export_for_ai.py ios --review
# 独立复核子代理按 review.partNN.json 写出 review-patch.partNN.json 后：
python3 scripts/import_from_ai.py ios --review
```

在 `work/ios/review.md` 记录复核范围与疑点决策后，合并、规范化并打包：

```bash
python3 scripts/merge_parts.py ios
python3 scripts/normalize.py ios
# 查看 normalize-report.md，有修改且确认符合上下文时执行：
python3 scripts/normalize.py ios --apply
python3 scripts/import_from_ai.py ios
python3 scripts/diff_report.py ios --update
python3 scripts/build_strings.py ios
```

完整成品为 `dist/ios/zh-Hans-custom.strings`，上传文件为 `dist/ios/zh-Hans-custom.upload.strings`，本次审校报告为 `work/ios/update-report.html`，按新增、英文变化和既有修订展示原文及新旧译文。Android、TDesktop 和 macOS 原生客户端使用相同命令，把 `ios` 换为 `android`、`tdesktop` 或 `macos`，并传入对应平台的下载文件。安卓首次源文件为 `data/android/raw/en.xml`，成品为 `dist/android/zh-Hans-custom.xml`。

校验失败会以非零状态退出；合并与打包均在写入前检查。打包完成后，将上传文件 `dist/<platform>/zh-Hans-custom.upload.strings`（安卓为 `.upload.xml`）人工上传至自定义语言包对应平台，并点击 **EDIT PHRASES** 入库。上传文件只保留中文使用的复数分支，原因见 [上传文件只保留中文使用的复数分支](docs/05-troubleshooting.md#上传文件只保留中文使用的复数分支)。

上传可能需要刷新并重复提交几轮。若同一批 key 连续两次重试及导出核验均无进展，应按 [上传停滞与残留判断](docs/05-troubleshooting.md#上传停滞反复提交与停止条件) 核对平台限制，保存差异后停止重复尝试；网站显示 `100%` 仍须导出核验。

工作结束后，按 [下载资源清理规则](AGENTS.md#维护铁律) 删除下载原件及项目、历史归档中的复制件，保留解析后的基准、译文、成品和必要备份。没有新内容、没有翻译或没有上传时，同样执行清理。

## 从零初始化与文档

首次准备英文源文件后，依次运行 `parse_strings.py`、`merge.py`、`export_for_ai.py`，然后按紧凑分片完成初译与差量二审。完整步骤见 [操作流程](docs/02-workflow.md)。

- [架构与设计原则](docs/01-architecture.md)
- [脚本参数](docs/03-scripts.md)
- [中间产物格式](docs/04-data-format.md)
- [故障排查与上传限制](docs/05-troubleshooting.md)

模型升级后继续遵循相同的审校标准，按实际问题决定修订范围。

解析数据、工作区和成品均由 Git 忽略，需自行备份；每轮本地归档不能替代异地备份。下载资源仅临时使用，任务结束后清理。
