# AGENTS.md

Telegram 简体中文语言包精修工具链。本文档是 AI agent 维护本项目的**索引**，按需深入 `docs/`。

> **本文件是唯一维护源；`CLAUDE.md` 通过 `@AGENTS.md` 引用本文件。**

---

## 一句话定位

以当前官方英文、功能上下文和共用术语为依据，由**翻译 AI** 核对并复用适用的精修译文，完成其余翻译，再单独复核语义与一致性。本项目精修译文作为翻译记忆稳定复用；官方简中与社区包按具体疑点查阅。脚本负责下载官方资源、数据整理、校验和打包，产出 `.strings`（安卓为 `.xml`）后由 `upload.py` 上传 translations.telegram.org 成为**自定义语言包**并导出核验。

当前维护范围：
- Android：继续维护，使用官方安卓 XML 英文源与独立 key 集合。
- iOS：继续维护。增量更新只需重新下载官方英文 `en.strings`。
- TDesktop：继续维护，和 iOS 独立处理。
- macOS 原生客户端：继续维护，使用独立英文源与 key 集合。
- 官方简中、社区包与其他参考包：保留解析后的 JSON，按需查阅，默认不进入待译输入；下载原件用后清理。

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
│   ├── _common.py               .strings / XML 解析、占位符校验、复数约定与导出下载
│   ├── download.py              下载官方英文或参考语言包到系统下载目录
│   ├── prepare_update.py        备份旧轮次并导出紧凑增量包
│   ├── parse_strings.py         平台资源 → JSON
│   ├── merge.py                 建立全量英文基准 → merged.json
│   ├── seed_ios_ref.py          按英文匹配 iOS 精修参考译文
│   ├── export_for_ai.py         导出分级紧凑分片与二审差量复核包
│   ├── import_from_ai.py        展开紧凑回传、应用二审补丁并校验
│   ├── merge_parts.py           门禁检查后合并分片与未变译文 → translated.json
│   ├── normalize.py             风格统一 (您→你, ...→…)
│   ├── diff_report.py           审核用 HTML 报告
│   ├── build_strings.py         translated.json → .strings / XML
│   └── upload.py                导入上传文件、提交修改并导出核验
├── .env                      上传用登录 Cookie (gitignore，本地自建)
├── data/<platform>/
│   ├── raw/                  下载资源临时目录 (.strings / .xml，用后清理)
│   └── parsed/               解析后 JSON (gitignore)
├── work/<platform>/          工作区 (gitignore)
│   ├── history/ + update.json       # 历史归档和来源记录
│   ├── translated.reused.json       # 原文未变译文
│   ├── translation-memory.json      # 旧英文与精修译文配对
│   ├── merged.json                  # 当前全量英文基准
│   ├── to-translate.json + .partNN  # 待审校原始 key 账本与分片基准
│   ├── compact-manifest.json        # 分层分片派发清单
│   ├── PROMPT.{md,fast.md,deep.md,review.md} # 分层初译与二审合约
│   ├── compact.partNN.json + .meta.json      # 紧凑输入包与脚本展开元数据
│   ├── reply.partNN.json            # AI 短编号回传
│   ├── review.partNN.json + .meta.json       # 待二审复核包与脚本映射元数据
│   ├── review-patch.partNN.json     # AI 二审差量修改补丁
│   ├── review-plan.json + review-summary.json # 二审计划与复核统计
│   ├── translated-draft.partNN.json # 二审前不可变初译快照
│   ├── translated.partNN.json       # 展开并复核后的标准译文分片
│   ├── translated.json + .bak       # 合并后的唯一主文件与备份
│   ├── validation.json + .partNN    # 全量与单片结构校验报告
│   ├── normalize-report.md
│   ├── review.md                    # 语义与一致性复核记录
│   └── report.html + update-report.html
└── dist/<platform>/          完整成品与上传文件 .strings / .xml (gitignore)
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

## 分层增量审校标准流程（翻译 AI 执行必读）

进入本项目执行语言包更新的 AI 必须遵循以下分层流水线，将检索、去重、折叠、预检与展开交给本地脚本，AI 专注语义与语境判断：

1. **单平台串行更新**：每次处理单个平台。多平台同时有更新时，优先完成待译量小或核心平台（如 `ios` → `tdesktop` → `android` → `macos`）；前序平台合并生成 `translated.json` 后，下一平台的导出脚本会自动将其最新译文纳入跨端候选池。
2. **准备分层紧凑分片**：
   - 下载并导入新英文源：`python3 scripts/download.py <platform>`，按输出提示运行 `python3 scripts/prepare_update.py <platform> --en <下载文件路径>`；英文与上一轮相同时无需更新
   - 工作区已有待译 `to-translate.json` 且尚无已译分片：`python3 scripts/export_for_ai.py <platform>`
   - 工作区已有部分校验通过的旧分片需续跑：`python3 scripts/export_for_ai.py <platform> --repack`
   - 脚本自动折叠复数分支、聚合相同英文词条、预注入四端精修候选（精确匹配、占位符安全投影与大小写不敏感提示）、附上变化条目的 `p_en`/`p_zh` 与同模块邻居 `context`，并按复杂度切分为 `fast`（常规片，默认 ≤350 组）和 `deep`（疑难片，默认 ≤120 组）两档 `compact.partNN.json`（脚本展开所需的映射元数据存放在同目录 `.meta.json`，AI 无需读取）。
3. **独立子会话初译与单片展开校验**：
   - 主会话仅读取 `work/<p>/compact-manifest.json` 调度任务，不在长会话中连续处理大量分片，也不通读 `merged.json`、`translation-memory.json` 等大文件。
   - 每个待译分片派发一个独立干净的子代理：首轮并行读取对应档位的 `work/<p>/PROMPT.fast.md` 或 `PROMPT.deep.md` 以及 `work/<p>/compact.partNN.json`，随后直接写出 `work/<p>/reply.partNN.json`。仅当 `deep` 片内上下文仍无法消解具体功能歧义时，才定向查阅最小必要上下文。
   - 模型与思考档位：全程使用用户选定的同一主力模型。宿主子代理支持调节思考强度时，`fast` 片设为低/中档、`deep` 片设为高档；宿主不支持调节思考强度时，直接用该模型派发全部子代理。
   - `reply.partNN.json` 短编号取值：`"="` 或 `"=1"`（确认采用对应候选 `c`）、`"=prev"`（微调词条沿用 `p_zh`）、`"译文"`（独立新译，默认 `fresh`）、`["译文", "rewrite_ref", "来源与理由"]`（改写或附备注）；同英文多 key 组存在语境差异时支持对象覆写 `{"*": "默认译文", "特殊Key": "特殊译文"}`。
   - 每片完成后运行 `python3 scripts/import_from_ai.py <platform> --part N`，展开写出标准 `translated.partNN.json` 并确保校验 0 问题。
4. **本地静态预检与差量二审（只输出修改补丁）**：
   - 初译全部通过后，运行 `python3 scripts/export_for_ai.py <platform> --review`。脚本先留存不可变初译快照 `translated-draft.partNN.json`，并对术语、称呼/省略号、首尾空白、长度比例及本端同英文多译差异做静态预检（命中项附 `flags` 置顶展示）。常规片中精确采用四端候选且无风险标记的词条自动免除二审，其余词条导出为 `review.partNN.json`（默认 ≤350 组/片）。
   - 按二审分片派发独立复核子代理：首轮并行读取 `work/<p>/PROMPT.review.md` 与 `work/<p>/review.partNN.json`（不读 `.meta.json`）。确认无误的词条省略不写，整片无修改直接输出 `{}`；仅将需修正条目按 `Rxxx` 写入 `work/<p>/review-patch.partNN.json`（多 key 组支持按 key 局部修正）。
   - 运行 `python3 scripts/import_from_ai.py <platform> --review` 基于初译快照幂等应用补丁并生成 `review-summary.json`，再将实际复核统计、术语决策与疑点依据写入 `work/<p>/review.md`。
5. **合并、规范化、打包与上传**：
   依次运行 `merge_parts.py` → `normalize.py`（核对 `normalize-report.md` 无误后加 `--apply`）→ `import_from_ai.py` → `diff_report.py --update` → `build_strings.py` → `upload.py`（可先加 `--preview` 只看导入识别结果），将脚本输出的版本、SHA-256、核验统计与残留写入 `docs/05-troubleshooting.md`，任务结束按铁律清理下载原件。

---

## 维护铁律

1. **零外部依赖**：所有脚本仅用 Python 标准库，`python3` 直接跑。新增脚本**禁止** `pip install`。
2. **每步可审可回滚**：中间产物全部落盘，`normalize.py` 改写必须留 `.bak`。
3. **翻译逻辑不进脚本**：本项目不调用任何翻译 API，审校由外部 AI 完成，脚本只做结构化 I/O。
4. **接口稳定**：脚本 I/O 字段任何变更必须同步 `docs/04-data-format.md` 和 `docs/03-scripts.md`。
5. **PROMPT.md 是合约**：`export_for_ai.py` 产出的 `PROMPT.md` 定义了翻译 AI 必须遵守的 source 标签和格式约定，改动须同步 `import_from_ai.py` 的校验规则。
6. **增量与质量**：更新前运行 `prepare_update.py` 归档；默认只复用英文未变且已通过结构校验的译文。所有新增、原文变化与定向修订均须先理解原文，再核对精修记忆，完成翻译后单独复核语义与一致性。跨平台译文须核对用途、参数角色与格式后复用。模型升级不触发全量重译，实际问题决定审校范围。`translated.json` 是合并后的主文件；遵循 `docs/06-translation-style.md`。
7. **规则单一来源**：只维护 `AGENTS.md`；`CLAUDE.md` 仅保留 `@AGENTS.md` 引用。
8. **验证产物清理**：验证结束后，将必要结论和可复用经验写入文档，清理临时测试脚本、测试数据、验证报告、日志和截图，包括历史归档中的副本；本地和仓库均不保留测试文件。保留生产脚本的结构校验功能，以及解析后的英文基准和参考数据、翻译主文件、翻译记忆、审校记录、语言包成品和业务数据备份。
9. **下载资源用后清理**：每次下载的官方英文、参考语言包、线上导出、查证用源码等资源仅供当次工作使用。任务完成后，无论是否有新增内容、是否发生翻译或上传，都必须删除下载原件及其复制件，覆盖系统下载目录、临时目录、项目 `data/*/raw/`、工作区和历史归档；仓库内不留下载资源，Git 忽略不能代替清理。清理前记录来源、版本、SHA-256 和必要结论；增量维护所需的英文与参考数据保留为解析后的 JSON，线上回滚备份保留为可恢复资源格式的 key/value JSON。自行生成的译文成品和业务数据备份继续保留，原目录及 `.gitkeep` 保留。

---

## 快速决策树

- **新增平台支持（如其他客户端）** → 扩展 `_common.py:PLATFORMS`，同格式脚本自动适配；新文件格式须同步解析、构建与增量入口
- **新增 normalize 规则** → 改 `normalize.py:normalize()`，先 dry-run 评估规模
- **AI 输出格式变更** → 改 `export_for_ai.py` 的 `PROMPT_*` 模板 + `import_from_ai.py` 的 `expand_compact()` / `VALID_SOURCES`
- **查阅参考译文** → 优先使用 `compact.partNN.json` 预注入的 `c`、`p_zh` 和 `context`；仅在具体功能疑点未消解时按 key 定向查 `data/<p>/parsed/` 并记录依据

更详细的"怎么改"请进 `docs/03-scripts.md` 对应章节。
