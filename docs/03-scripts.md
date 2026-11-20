# 03 · 脚本参考手册

所有脚本都在 `scripts/`，零外部依赖，`python3 scripts/<name>.py` 直接跑。`<platform>` 参数为 `android`、`ios`、`macos` 或 `tdesktop`。

执行顺序（正常链路）：

```mermaid
flowchart LR
    A[parse_strings] --> B[merge]
    B --> C[export_for_ai]
    C -.子代理初译 reply.partNN.-> D[import_from_ai --part N]
    D --> E[export_for_ai --review]
    E -.差量二审 review-patch.partNN.-> F[import_from_ai --review]
    F --> G[merge_parts]
    G --> H[normalize --apply]
    H --> I[import_from_ai]
    I --> J[diff_report]
    J --> K[build_strings]
    K --> L[upload]
```

日常增量从 `download.py` 下载英文、`prepare_update.py` 归档并导出分片开始，之后与上图相同。

---

## `_common.py`

共享工具模块，不直接执行。

**导出：**
- `ROOT` — 项目根目录 `Path`
- `PLATFORMS = ("ios", "macos", "tdesktop", "android")`
- `PLURAL_SUFFIXES` — 各平台复数后缀映射 `{platform: (used_suffix, unused_suffixes)}`
- `PLACEHOLDER_RE` / `extract_placeholders(s)` / `placeholders(s)` / `placeholder_issue(en, zh)` — 统一占位符提取及数量、写法与无编号参数次序检查
- `platform_dirs(platform)` — 返回 `{raw, parsed, work, dist}` 四个 `Path`
- `parse_strings(text)` — `.strings` 文本 → `dict[str, str]`
- `dump_strings(data)` — `dict[str, str]` → `.strings` 文本（按 key 字母序输出）
- `resource_suffix(platform)` — 安卓返回 `.xml`，其他平台返回 `.strings`
- `parse_resource(text, platform)` / `dump_resource(data, platform)` — 按平台解析或序列化 XML / `.strings`，保持相同 key→value 结构
- `SITE` / `CUSTOM_LANG` — `https://translations.telegram.org` 与自定义语言包标识 `zhcn1ainbo`
- `fetch_export(lang, platform)` — 下载 `SITE/<lang>/<platform>/export`，返回响应头中带版本号的文件名和原始内容；导出无需登录，响应没有文件名（语言包或平台不存在）时退出

**内部：**
- `_STRING_RE` — Apple `.strings` 字符串正则
- `_strip_comments(text)` — 仅剥离**字符串外部**的 `/* */` / `//` 注释
- `_escape` / `_unescape` — 处理 `\"` `\\` `\n` `\t` `\r` `\'` 六种转义

**注意：**
- `TDesktop` 的 `.strings` 值里可能包含 `https://`、`**markdown**`、`[a href=\"...\"]`
- 个别值里还可能出现字面量 `/* */`
- 因此不能先用全局正则粗暴删注释，否则会误删字符串内容，直接导致 key 数偏少
- 当前实现使用按字符扫描的 `_strip_comments()`，只在**字符串外部**识别注释

---

## `download.py`

下载官方英文或参考语言包，无需登录。

```bash
python3 scripts/download.py ios [android macos tdesktop] [--lang en]
```

- `--lang`：语言包标识，默认 `en`；官方简中为 `zh-hans`。
- 输出：`~/Downloads/<平台>_<语言包>_v<版本>.strings`（安卓为 `.xml`），文件名取自网站响应头；同名文件直接覆盖。
- 每个文件先按平台格式解析，为空或无法解析时退出；随后打印路径与 SHA-256。
- 下载英文时与 `work/<p>/update.json` 的 `sources.en.sha256` 比较：相同提示无需更新，不同则打印对应的 `prepare_update.py` 命令。
- 下载文件属于下载资源，任务结束按 [清理规则](../AGENTS.md#维护铁律) 删除。

---

## `prepare_update.py`

日常增量入口；用于已有完整译文的 Android、iOS、TDesktop 与 macOS 原生客户端。

```bash
python3 scripts/prepare_update.py ios --en /path/to/ios_en.strings [--chunk N]
```

先校验上一轮 `merged.json` 与 `translated.json`，读取并检查新下载；归档旧 raw、parsed、dist 与 work 文件，再安装新英文；从上一轮主文件保存成对的英文与精修译文。

输出 `update.json`、全量 `merged.json`、`translated.reused.json`、`translation-memory.json`、增量 `to-translate.json`、原始分片 `to-translate.partNN.json`、预注入上下文的紧凑分层分片 `compact.partNN.json` 与 `.meta.json`、`compact-manifest.json` 及 `PROMPT.{md,fast.md,deep.md,review.md}`。只有英文完全未变的 key 会复用；英文改变和新增 key 进入审校；删除 key 不进入最终包。无变化时输出空审校集，仍可合并和打包。

不传 `--chunk` 时默认采用分层切片上限（`fast=350` 组/片，`deep=120` 组/片）；显式传 `--chunk N` 时须为正整数，`deep` 取 `N`、`fast` 取 `3N`。来源文件名与 SHA-256 写入 `update.json`，历史保存在 `work/<p>/history/<时间>/`。旧英文与译文缺失或不匹配、新源为空、误下载其他平台时停止。

脚本保留下载输入及安装到 raw 的资源，供本轮工作使用；任务结束时由维护者按 [下载资源清理规则](../AGENTS.md#维护铁律) 清理原件和复制件。下一轮使用保存的 `merged.json`、`translated.json` 与新下载的英文准备增量。

---

## `parse_strings.py`

**作用**：扫 `data/<p>/raw/*.strings`（安卓扫 `*.xml`）→ `data/<p>/parsed/<stem>.json`

**用法**：
```bash
python3 scripts/parse_strings.py ios
```

**输入**：`data/<p>/raw/` 下任意数量对应平台的资源文件。安卓英文命名为 `en.xml`，其他平台为 `en.strings`。
**输出**：同名 `.json`（key→value 字典），按 key 排序。

**错误**：raw 为空时 `SystemExit`；安卓 XML 格式错误、根元素错误、重复 key 或非纯文本 `string` 时解析失败。

---

## `merge.py`

**作用**：从 `data/<p>/parsed/en.json` 建立全量英文基准，输出 `work/<p>/merged.json`。参考文件保留在 parsed 中供按需查阅，默认基准仅含 `en`。

**用法**：
```bash
python3 scripts/merge.py ios
```

**输出结构**：见 `docs/04-data-format.md`。打印当前英文 key 数。

---

## `seed_ios_ref.py`

按英文匹配 iOS 精修译文，生成 `data/macos/raw/ref-ios-refined.strings`，供按需查阅。采用前须核对 macOS 的功能上下文、参数角色与格式；默认待译输入保持英文。

---

## `export_for_ai.py`

**作用**：导出紧凑自包含的初译分片（默认由 `prepare_update.py` 调用，也可独立运行），或在初译全部通过后导出二审差量复核包（`--review`）。

**用法**：
```bash
python3 scripts/export_for_ai.py ios                                      # 按默认分层上限导出 (fast=350, deep=120)
python3 scripts/export_for_ai.py ios --fast-chunk 350 --deep-chunk 120    # 自定义分层分片大小
python3 scripts/export_for_ai.py ios --repack                             # 保留已校验分片为 part01，剩余条目重切紧凑包
python3 scripts/export_for_ai.py ios --review [--review-chunk 350]        # 导出二审差量复核包
```

**初译导出输出**：
- `work/<p>/to-translate.json` — 本轮待审校全部原始 key 账本（存在 `translated.reused.json` 时自动取增量差集，无复用文件时取全量 `merged.json`）
- `work/<p>/to-translate.partNN.json` — 各分片对应的原始 key 基准（供校验与合并使用）
- `work/<p>/compact.partNN.json` — 供翻译 AI 子代理读取的单行紧凑输入包（不含脚本展开元数据）
- `work/<p>/compact.partNN.meta.json` — 脚本自用的成员映射、复数 key 与候选元数据（AI 无需读取）
- `work/<p>/compact-manifest.json` — 分片统计与派发清单（列出 `plural_collapsed_saved`、`same_en_grouped_saved`、`fast_parts`、`deep_parts` 及 `--repack` 保留的 `completed_parts`）
- `work/<p>/PROMPT.md`、`PROMPT.fast.md`、`PROMPT.deep.md`、`PROMPT.review.md` — 总合约与分层审校指令

**二审导出输出（`--review`）**：
- `work/<p>/translated-draft.partNN.json` — 本轮二审前的不可变初译快照（供补丁幂等重放与回滚）
- `work/<p>/review.partNN.json` — 豁免无风险常规精确复用项后的待二审复核包（命中本地规则预检的条目附 `flags` 置顶排序）
- `work/<p>/review.partNN.meta.json` — 脚本自用的分片路由与 key 映射元数据
- `work/<p>/review-plan.json` — 二审计划统计（含 `flagged_units` 与 `parts_covered`；若待复核项为 0，同时直接生成 `review-summary.json`）

**核心规则**：
- **复数折叠与同英文聚合**：同一词根在 `merged.json` 含主分支且至少有 2 个复数后缀时，按 `(占位符签名, 是否为变更条目)` 折叠为 1 条；共享相同 `(en, one_en, previous_en, previous_zh)` 的条目聚合为 1 个短编号审阅（支持回传时按 key 单独覆写语境差异）。
- **四端记忆与上下文预注入**：扫描本端及另外三端最新精修译文，提供精确匹配、严格双射占位符安全投影（`[~来源]`，禁止静默参数换序）与大小写不敏感提示（`[ci|来源]`）候选 `c`（最多 3 条）；原文变更或定向重审项附上 `p_en`/`p_zh`；分片顶层 `context` 按功能前缀附带本端最多 3 条已译邻居。
- **复杂度分层**：含 `previous_en`、含实际语境词的 `≥2` 占位符句子、无精确候选的单复数差异词条、多行或超长句、`>4` 词的条件/否定句或敏感业务长句归入 `deep`，其余归入 `fast`。总组数不超过 `deep_chunk` 时合并为单片。
- **本地静态预检（`--review`）**：自动检查称呼“您”、ASCII 省略号、首尾多余空格、译文长度异常比例、高确定性术语表碰撞及本端同英文多译差异，结果写入 `flags`。仅对无 `flags` 且精确采用四端候选的 `fast` 非变更词条豁免二审。
- 已有 `translated.part*.json` 且未加 `--repack` 时拒绝覆盖；加 `--repack` 时先逐片校验已有译文分片，通过后合并保留为 `part01` 并同步纳入候选索引，再将剩余未译 key 切为紧凑分片。

---

## `import_from_ai.py`

**作用**：展开紧凑初译回传并校验，基于初译快照幂等应用二审差量修改补丁，或对全量/单片标准译文执行结构与占位符校验。

**用法**：
```bash
python3 scripts/import_from_ai.py ios                          # 校验 translated.json 对 merged.json
python3 scripts/import_from_ai.py ios --part 1                 # 展开 reply.part01.json (若存在) 写出 translated.part01.json 并校验
python3 scripts/import_from_ai.py ios --part 1 custom.json     # 指定紧凑或标准回传文件校验
python3 scripts/import_from_ai.py ios --review                 # 基于初译快照应用 review-patch.part*.json 并复检全部分片
```

**校验与处理项**：
1. **紧凑语法与展开（`--part N`）**：优先读取 `compact.partNN.meta.json`，校验 `reply.partNN.json` 顶层短编号覆盖完整；解析 `"="` / `"=N"`、`"=prev"`、普通字符串、`["译文", "source", "note?"]` 数组以及同英文多 key 组的对象覆写 `{"*": ..., "Key": ...}`，自动展开回全部原始 key 写入 `translated.partNN.json`（同时清理旧的二审快照与 `review-summary.json`）。
2. **二审差量补丁应用（`--review`）**：检查全部 `review.partNN.json` 均有对应的 `review-patch.partNN.json`（无修改为 `{}`）；校验 `Rxxx` 编号与局部 key 有效，始终基于 `translated-draft.partNN.json` 幂等重放全部补丁（不改写 `reply.partNN.json`；原 `adopt` 条目经纯字符串修改时同步将 `source` 转为 `rewrite_ref` 并将 `adopt:` 备注转为 `rewrite:`），全量校验通过后写回 `translated.partMM.json` 并输出 `review-summary.json`。
3. **source 合法性**：四选一 `adopt / rewrite_ref / rewrite_official / fresh`。
4. **final 必须为字符串**：英文非空时译文必须非空；官方空串分支允许原样保留。
5. **占位符一致性**：数量、类型和写法必须相同，`%%` 也保留；无编号百分号参数必须保持顺序，带编号参数可调整顺序。
6. **key 覆盖**：对照 `to-translate.partNN.json` 或 `merged.json`，缺失与多余均报错。

**占位符正则** `PLACEHOLDER_RE`（定义于 `_common.py`）：
- `%@` / `%1$@` — Apple object
- `%d` / `%1$d` — 整数
- `%s` / `%1$s` — C string
- `%.2f` / `%1$.2f` — 浮点
- `%.2d`、`%2$02d` — 含精度或宽度的格式化整数
- `%%` — 字面量百分号
- `{xxx}` — Telegram 自定义占位符（如 `{user}`）
- `un1` / `un2` 等 — 安卓服务消息中的具名替换标记
- `**oo**` — 安卓输入状态中的动画替换标记

**错误**：全量输出 `validation.json`，单片输出 `validation.partNN.json`；问题数大于 0 时以状态码 1 退出。共享函数 `validate()` 也用于合并和打包门禁。

---

## `merge_parts.py`

**作用**：按 `to-translate.part*.json` 确定本轮应有分片，门禁检查通过后合并对应译文与 `translated.reused.json`（存在时）。

```bash
python3 scripts/merge_parts.py ios
```

缺片、多余片、未完成差量二审（存在 `compact-manifest.json`、`review-plan.json` 或 `compact.part*.json` 但缺少 `review-summary.json`，或 `total_keys` 不匹配，或 `review-patch`/`translated.part`/`reply.part` 在二审后有新改动）、重复 key、任一片校验失败或合并后全量校验失败，均以非零状态退出并保留已有主文件。通过后输出 `translated.json`；若已有主文件，先复制到 `.bak`。首次全量审校不需要 `translated.reused.json`。

合并后只修改主文件；旧分片留作审校记录，重新合并会覆盖主文件上的后续编辑。

---

## `normalize.py`

**作用**：对合并后的 `translated.json` 的 `final` 字段应用全局风格规则。

**用法**：
```bash
python3 scripts/normalize.py ios              # dry-run, 生成 normalize-report.md
python3 scripts/normalize.py ios --apply      # 真改, 自动创建 .bak
```

**当前规则**（按顺序执行）：
1. `您` → `你`
2. `\.{3,}` → `…`（U+2026）
3. `。{3,}` → `…`

**输出**：
- `work/<p>/normalize-report.md` — Markdown diff 报告（全量 diff）
- `--apply` 时会在被改动的 `translated.json` 同目录创建 `.json.bak`（首次）

**回滚**：
```bash
cp work/ios/translated.json.bak work/ios/translated.json
python3 scripts/import_from_ai.py ios
```

**扩展新规则**：改 `normalize()` 函数内部，加一段 `re.subn` 或 `.count/.replace`。务必先 dry-run 看规模。

---

## `diff_report.py`

**作用**：按文案变更类型展示当前英文、变化前英文、上一轮精修译文、最终译文、来源记录和备注。

**用法**：
```bash
python3 scripts/diff_report.py ios [translated.json] [--update]
```

**输出**：默认 `work/<p>/report.html`；`--update` 按 `to-translate.json` 仅展示本轮审校条目，输出 `update-report.html`。

**数据来源**：英文来自基准，旧英文与精修译文来自 `translation-memory.json`，变更分类来自 `update.json`。首次初始化没有历史数据时，显示全量文案。

**分组**：尚无译文、新增文案、英文变化、既有文案审校和其他条目。仅显示有条目的组。官方英文与译文均为空的分支视为完整条目。所有本轮条目均需审校，`source` 仅作追溯，参考包不作为默认对照列。

---

## `build_strings.py`

**作用**：把 `translated.json` 的 `final` 字段打包为 `.strings`（安卓为 `.xml`），同时生成只含中文复数分支的上传文件。

**用法**：
```bash
python3 scripts/build_strings.py ios [translated.json]
```

**输出**（均按 key 字母序）：
- `dist/<p>/zh-Hans-custom.strings`：完整成品，保留全部 key 与复数分支；安卓为 `dist/android/zh-Hans-custom.xml`。
- `dist/<p>/zh-Hans-custom.upload.strings`：上传文件；安卓为 `dist/android/zh-Hans-custom.upload.xml`。对应的中文分支存在时，删除其余复数分支：

  | 平台 | 保留 | 删除 |
  |---|---|---|
  | Android、macOS | `_other` | `_zero`、`_one`、`_two`、`_few`、`_many` |
  | iOS | `_any` | `_0`、`_1`、`_2`、`_3_10`、`_many` |
  | TDesktop | `#other` | `#zero`、`#one`、`#two`、`#few`、`#many` |

  macOS 另外删除无后缀的 `Star.Auction.Preview.TopBidders`。规则定义在 `UPLOAD_PLURAL` 与 `UPLOAD_EXCLUDE`，原因见 [上传文件只保留中文使用的复数分支](05-troubleshooting.md#上传文件只保留中文使用的复数分支)。

**门禁**：每次打包都对当前英文重新校验 key 覆盖、结构和占位符；失败不会覆盖已有成品。

**保证**：通过 `_common.dump_resource` 选择平台格式并正确转义 `"` `\\` `\n` `\t` `\r`。XML 使用标准库序列化实体与属性。端到端测试验证 `.strings` 与 XML 的解析、构建和再解析结果一致。

**下一步**：运行 `upload.py` 上传。

---

## `upload.py`

**作用**：把上传文件导入自定义语言包 `zhcn1ainbo` 的对应平台，提交网站识别的修改，再导出核验。

**用法**：
```bash
python3 scripts/upload.py ios [--preview]
```

- 登录态：读取环境变量 `TG_TRANSLATIONS_COOKIE`，未设置时读取项目根目录 `.env` 中的 `TG_TRANSLATIONS_COOKIE=...`（值可加引号）。内容为已登录浏览器请求 translations.telegram.org 时的整段 `Cookie` 请求头。缺失或页面显示未登录时退出并提示。
- `--preview`：只导入上传文件，打印 `change`（修改）、`add`（新增）、`remove`（删除）、`restore`（恢复）四组数量，不备份也不提交。

**流程**：
1. 导入 `dist/<p>/zh-Hans-custom.upload.strings`（安卓为 `.upload.xml`），打印各组数量。
2. 导出当前线上包并打印版本与 SHA-256；`update.json` 的 `archive` 目录中还没有 `online-before-upload.json` 时，解析后写入作为回滚备份，已有则沿用。
3. 提交 `change` 组，处理完服务端的分批后重新导入。剩余修改有变化就继续提交，同一批连续两次没有变化时停止。其余三组不提交。
4. 有新写入时每 30 秒检查一次导出文件名，出现新版本号后核验，最长等待 15 分钟；超时退出，稍后重新运行即可。没有新写入时直接用当前导出核验。
5. 本轮词条取 `update.json` 的 `added`、`changed`、`reviewed_existing` 与上传文件 key 的交集，输出：与上传文件一致数（其中上传前备份已一致数）、仍不同或未导出数、首次导入识别修改数、保存后导入残留数、本轮以外导出变化数，以及对应的 key 清单。

导出内容只在内存中解析，不写入下载原件；脚本只新增 `online-before-upload.json`。网站返回错误时退出并显示原文，重新运行时沿用已有备份，并以它统计“上传前已一致”。

**接口**（translations.telegram.org 前端使用的未公开接口，网站改版后需重新核对）：
- 先带 Cookie 请求 `/zhcn1ainbo/<p>/`，从页面 `ajInit({...})` 参数取 `apiUrl`（`/api?hash=...`，hash 与会话绑定）和 `unauth`。
- `importFile`：multipart 表单，字段 `method`、`lang`、`lang_pack`、`file`。安卓 XML 的文件部分须声明 `Content-Type: text/xml`，声明为 `application/xml` 或 `application/octet-stream` 时返回 `Invalid file format`；`.strings` 用 `application/octet-stream`。返回 `import_id`、`href` 与预览 HTML。预览中 `tr-<组名>-keys-block` 区块内 `tr-plain-key-row` 行的 `data-key` 即该组 key；没有条目的组不输出区块。`data-key` 是网站上的 key 名，复数词条不带后缀（如上传文件的 `Chat.GiftPurchaseOffer.AcceptConfirmation.Text.Stars_any` 在预览中为 `Chat.GiftPurchaseOffer.AcceptConfirmation.Text.Stars`），因此导入残留清单也按这个写法输出。
- `editImportedKeys`：普通表单，字段 `method`、`lang`、`lang_pack`、`import_id`、`lang_keys`（逗号分隔）、`affected_cnt`。返回的 `repeat_lang_keys` 非空时，连同返回的 `affected_cnt` 继续提交，直到为空；2026-11-20 实测每次处理 50 条。
- 出错时返回 `{"error": "..."}`：未登录为 `Access denied`，hash 不匹配为 `Bad request`。
