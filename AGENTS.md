# AGENTS.md

Telegram 简体中文语言包精修工具链。本文档是 AI agent 维护本项目的**索引**，按需深入 `docs/`。

> **本文件是唯一维护源；`CLAUDE.md` 通过 `@AGENTS.md` 引用本文件。**

---

## 一句话定位

以当前官方英文、功能上下文和共用术语为依据，由**翻译 AI** 核对并复用适用的精修译文，完成其余翻译，再单独复核语义与一致性。本项目精修译文作为翻译记忆稳定复用；官方简中与社区包按具体疑点查阅。脚本只做数据整理、校验和打包，产出 `.strings`（安卓为 `.xml`）后人工上传 translations.telegram.org 成为**自定义语言包**。

当前维护范围：
- Android：继续维护，使用官方安卓 XML 英文源与独立 key 集合。
- iOS：继续维护。增量更新只需重新下载官方英文 `en.strings`。
- TDesktop：继续维护，和 iOS 独立处理。
- macOS 原生客户端：继续维护，使用独立英文源与 key 集合。
- `official-zh.strings`、`zhcncc.strings` 与 `ref-*.strings`：保留本地参考，按需查阅，默认不进入待译输入。

---

## 目录结构

```
tg-lang-refine/
├── README.md                 用户视角使用说明
├── AGENTS.md                 AI 维护索引（本文件）
├── CLAUDE.md                 → @AGENTS.md（Claude Code 适配层）
├── .gitignore
├── docs/                     渐进式披露文档
│   ├── 01-architecture.md    架构与设计原则
│   ├── 02-workflow.md        完整操作流程 (Android/iOS/TDesktop/macOS)
│   ├── 03-scripts.md         脚本参考手册
│   ├── 04-data-format.md     中间产物格式定义
│   ├── 05-troubleshooting.md 故障排查与上传经验
│   ├── 06-translation-style.md 共用术语与信达雅审校规范
│   └── SOURCES.md            英文下载与参考查阅指引
├── scripts/                  Python 脚本 (零外部依赖)
│   ├── _common.py               .strings / XML 解析与序列化 + 路径约定
│   ├── prepare_update.py        备份旧轮次并准备增量审校
│   ├── parse_strings.py         平台资源 → JSON
│   ├── merge.py                 建立全量英文基准 → merged.json
│   ├── seed_ios_ref.py          按英文匹配 iOS 精修参考译文
│   ├── export_for_ai.py         merged.json → 翻译 AI 输入 (分片)
│   ├── import_from_ai.py        校验 AI 回传 (全量 / 单片)
│   ├── merge_parts.py           本轮分片 + 未变译文 → translated.json
│   ├── normalize.py             风格统一 (您→你, ...→…)
│   ├── diff_report.py           审核用 HTML 报告
│   └── build_strings.py         translated.json → .strings / XML
├── data/<platform>/
│   ├── raw/                  原始下载 (.strings / .xml, gitignore)
│   └── parsed/               解析后 JSON (gitignore)
├── work/<platform>/          工作区 (gitignore)
│   ├── history/ + update.json # 历史归档和来源记录
│   ├── translated.reused.json # 原文未变译文
│   ├── translation-memory.json # 旧英文与精修译文配对
│   ├── merged.json
│   ├── to-translate.json + to-translate.partNN.json
│   ├── translated.partNN.json
│   ├── translated.json + translated.json.bak
│   ├── validation.json
│   ├── normalize-report.md
│   ├── review.md              # 语义与一致性复核记录
│   └── report.html + update-report.html
└── dist/<platform>/          最终 .strings / .xml (gitignore)
```

`<platform>` ∈ {`android`, `ios`, `macos`, `tdesktop`}。

---

## 文档导航（按目的选一篇读）

| 我想 …… | 读 |
|---|---|
| 理解"为什么这么设计" | `docs/01-architecture.md` |
| 从 0 走一遍完整流程 | `docs/02-workflow.md` |
| 查某个脚本参数 | `docs/03-scripts.md` |
| 搞懂 merged.json / translated.json 字段 | `docs/04-data-format.md` |
| 判断上传重试与停止条件、核对平台残留、排查占位符错位 | `docs/05-troubleshooting.md` |
| 下载当前维护源文件 | `docs/SOURCES.md` |
| 共用术语与信、达、雅审校要求 | `docs/06-translation-style.md` |
| 用户视角的总览 | `README.md` |

---

## 维护铁律

1. **零外部依赖**：所有脚本仅用 Python 标准库，`python3` 直接跑。新增脚本**禁止** `pip install`。
2. **每步可审可回滚**：中间产物全部落盘，`normalize.py` 改写必须留 `.bak`。
3. **翻译逻辑不进脚本**：本项目不调用任何翻译 API，审校由外部 AI 完成，脚本只做结构化 I/O。
4. **接口稳定**：脚本 I/O 字段任何变更必须同步 `docs/04-data-format.md` 和 `docs/03-scripts.md`。
5. **PROMPT.md 是合约**：`export_for_ai.py` 产出的 `PROMPT.md` 定义了翻译 AI 必须遵守的 source 标签和格式约定，改动须同步 `import_from_ai.py` 的校验规则。
6. **增量与质量**：更新前运行 `prepare_update.py` 归档；默认只复用英文未变且已通过结构校验的译文。所有新增、原文变化与定向修订均须先理解原文，再核对精修记忆，完成翻译后单独复核语义与一致性。跨平台译文须核对用途、参数角色与格式后复用。模型升级不触发全量重译，实际问题决定审校范围。`translated.json` 是合并后的主文件；遵循 `docs/06-translation-style.md`。
7. **规则单一来源**：只维护 `AGENTS.md`；`CLAUDE.md` 仅保留 `@AGENTS.md` 引用。
8. **验证产物清理**：验证结束后，将必要结论和可复用经验写入文档，清理临时测试脚本、测试数据、验证报告、日志、截图和核验下载副本，包括历史归档中的副本；本地和仓库均不保留测试文件。保留生产脚本的结构校验功能，以及英文源、翻译主文件、翻译记忆、审校记录、语言包成品和业务数据备份。

---

## 快速决策树

- **新增平台支持（如其他客户端）** → 扩展 `_common.py:PLATFORMS`，同格式脚本自动适配；新文件格式须同步解析、构建与增量入口
- **新增 normalize 规则** → 改 `normalize.py:normalize()`，先 dry-run 评估规模
- **AI 输出格式变更** → 改 `export_for_ai.py:PROMPT_TEMPLATE` + `import_from_ai.py:VALID_SOURCES`
- **查阅参考译文** → 在 `translation-memory.json` 或 `data/<p>/parsed/` 按相关 key 检索，记录依据；默认输入保持英文

更详细的"怎么改"请进 `docs/03-scripts.md` 对应章节。
