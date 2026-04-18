# CLAUDE.md

Telegram 简体中文语言包精修工具链。本文档是 AI agent 维护本项目的**索引**，按需深入 `docs/`。

> **AGENTS.md 是本文件的软链接，只维护这一份。**

---

## 一句话定位

以官方英文为 baseline，把官方简中 + 社区包（@zhcncc 等）作为翻译记忆（TM），交给**外部翻译 AI** 做审校，本地打包成 `.strings` 后手动上传 translations.telegram.org 成为**自定义语言包**。本项目**只做数据搬运和审核辅助，不做翻译**。

---

## 目录结构

```
tg-lang-refine/
├── README.md                 用户视角使用说明
├── CLAUDE.md                 AI 维护索引 (本文件)
├── AGENTS.md                 → CLAUDE.md (软链接)
├── .gitignore
├── docs/                     渐进式披露文档
│   ├── 01-architecture.md    架构与设计原则
│   ├── 02-workflow.md        完整操作流程 (iOS/macOS)
│   ├── 03-scripts.md         脚本参考手册
│   ├── 04-data-format.md     中间产物格式定义
│   ├── 05-troubleshooting.md 踩坑、白名单、已知限制
│   └── SOURCES.md            三个源文件下载指引
├── scripts/                  Python 脚本 (零外部依赖)
│   ├── _common.py               .strings 解析/序列化 + 路径约定
│   ├── parse_strings.py         .strings → JSON
│   ├── merge.py                 三源按 key 对齐 → merged.json
│   ├── seed_ios_ref.py          iOS 精修 → macOS 参考源 (跨平台 TM 复用)
│   ├── export_for_ai.py         merged.json → 翻译 AI 输入 (分片)
│   ├── import_from_ai.py        校验 AI 回传 (全量 / 单片)
│   ├── merge_parts.py           30 分片 → translated.json
│   ├── normalize.py             风格统一 (您→你, ...→…)
│   ├── diff_report.py           审核用 HTML 报告
│   └── build_strings.py         translated.json → .strings
├── data/<platform>/
│   ├── raw/                  原始下载 (.strings, gitignore)
│   └── parsed/               解析后 JSON (gitignore)
├── work/<platform>/          工作区 (gitignore)
│   ├── merged.json
│   ├── to-translate.json + to-translate.partNN.json
│   ├── translated.partNN.json + translated.partNN.json.bak
│   ├── translated.json
│   ├── validation.json
│   ├── normalize-report.md
│   └── report.html
└── dist/<platform>/          最终 .strings (gitignore)
```

`<platform>` ∈ {`ios`, `macos`}。

---

## 文档导航（按目的选一篇读）

| 我想 …… | 读 |
|---|---|
| 理解"为什么这么设计" | `docs/01-architecture.md` |
| 从 0 走一遍完整流程 | `docs/02-workflow.md` |
| 查某个脚本参数 | `docs/03-scripts.md` |
| 搞懂 merged.json / translated.json 字段 | `docs/04-data-format.md` |
| 排查上传失败、占位符错位、54 条白名单等 | `docs/05-troubleshooting.md` |
| 下载 en / official-zh / zhcncc 三件套 | `docs/SOURCES.md` |
| 用户视角的总览 | `README.md` |

---

## 维护铁律

1. **零外部依赖**：所有脚本仅用 Python 标准库，`python3` 直接跑。新增脚本**禁止** `pip install`。
2. **每步可审可回滚**：中间产物全部落盘，`normalize.py` 改写必须留 `.bak`。
3. **翻译逻辑不进脚本**：本项目不调用任何翻译 API，审校由外部 AI 完成，脚本只做结构化 I/O。
4. **接口稳定**：脚本 I/O 字段任何变更必须同步 `docs/04-data-format.md` 和 `docs/03-scripts.md`。
5. **PROMPT.md 是合约**：`export_for_ai.py` 产出的 `PROMPT.md` 定义了翻译 AI 必须遵守的 source 标签和格式约定，改动须同步 `import_from_ai.py` 的校验规则。
6. **AGENTS.md 是软链接**：不要直接编辑，不要变成普通文件。

---

## 快速决策树

- **新增平台支持（如 android）** → 扩展 `_common.py:PLATFORMS`，其他脚本自动适配
- **新增 normalize 规则** → 改 `normalize.py:normalize()`，先 dry-run 评估规模
- **AI 输出格式变更** → 改 `export_for_ai.py:PROMPT_TEMPLATE` + `import_from_ai.py:VALID_SOURCES`
- **支持新参考源** → 下载命名 `ref-<name>.strings` 放 `data/<p>/raw/`，`merge.py` 自动识别

更详细的"怎么改"请进 `docs/03-scripts.md` 对应章节。
