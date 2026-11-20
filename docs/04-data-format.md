# 04 · 数据格式定义

所有中间产物的结构，用于 AI 排查字段异常和扩展脚本。

---

## `.strings` (Apple 原生格式)

```
/* comment */
"key" = "value";
"escaped" = "line1\nline2";
"quoted" = "say \"hi\"";
```

**规则：**
- key/value 都是双引号包裹
- 每条以 `;` 结尾
- 支持 `/* */` 块注释和 `//` 行注释
- 转义字符：`\\` `\"` `\n` `\t` `\r`

**TDesktop 补充：**
- 值中可能包含 URL，如 `https://telegram.org/...`
- 值中可能包含富文本/标记，如 `**bold**`、`[a href=\"...\"]...[/a]`
- 个别值中可能出现字面量 `/* */`
- 所以注释剥离必须基于“当前是否在字符串内”的状态机，不能对整份文本直接做全局正则替换

**本项目处理**：
- 解析丢弃注释，保留 key-value
- 输出按 key 字母序排序（便于 diff）
- 不输出注释
- 对 `TDesktop`，注释只会在**字符串外部**被剥离，避免误伤 URL 和内嵌标记

---

## 安卓 XML

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="YourPhone">你的电话号码</string>
    <string name="CallAvailableIn">%1$d:%2$02d 后可请求语音来电</string>
</resources>
```

原始英文为 `data/android/raw/en.xml`，本地参考也使用 `.xml`。支持 Telegram 官方导出的具名纯文本 `string`；复数分支以 key 后缀展开，每个分支单独保留。XML 实体由标准库处理，字符串转义沿用换行、引号与反斜杠规则，并输出转义单引号。重复 key、错误根元素或子元素会阻断解析。JSON 字段和分片命名与其他平台相同。

语言元数据 `LanguageName`、`LanguageNameInEnglish` 和 `LanguageCode` 用于客户端识别语言，分别填写语言显示名、英文显示名和中文语言代码。日期格式字符串依据 Android `LocaleController` 的格式化调用审校，保留有效的日期模式。

---

## `parsed/<name>.json`

**产自**：`parse_strings.py`
**位置**：`data/<p>/parsed/`

```json
{
  "AUTH_REGION": "Login from a new device %1$@, location: %2$@",
  "AccentColor.Title": "Accent Color"
}
```

扁平 key→value，按 key 排序。

---

## `merged.json`

**产自**：`merge.py`
**位置**：`work/<p>/`

```json
{
  "<key>": {
    "en": "当前英文原文"
  }
}
```

`en` 是唯一必需字段。当前生成的基准只包含英文；历史归档中可能保留 `official_zh` 和 `refs`，用于追溯当时的数据。

---

## `to-translate.json` / `to-translate.partNN.json`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

首次全量导出时与 `merged.json` 相同；增量更新时只包含待审校原始 key 集合。只含 `en`，英文变化时额外带 `previous_en`（旧英文）。`to-translate.partNN.json` 与同编号 `compact.partNN.json` 的展开 key 集合严格一致，作为单片校验与最终合并的原始基准。

---

## `compact-manifest.json`、`compact.partNN.json` 与 `.meta.json`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

`compact-manifest.json` 汇总本轮分片调度信息（`total_pending_keys`、`completed_keys`、`remaining_raw_keys`、`compact_units`、`plural_collapsed_saved`、`same_en_grouped_saved`、`candidate_hit_units`、`completed_parts`、`fast_parts`、`deep_parts`）。

`compact.partNN.json` 是翻译 AI 子代理读取的单行紧凑输入包（每条 `context` 前缀与每条 `items` 各占一行，合法 JSON；展开所需的完整成员映射与候选结构存放在同目录 `compact.partNN.meta.json`，AI 无需读取）：

```json
{
"platform":"ios",
"part":1,
"tier":"fast",
"count":3,
"context":{
"Gift.MoveToWallet":{"Gift.MoveToWallet.Move":["Move","移动"],"Gift.MoveToWallet.Success":["Gift moved to your wallet.","礼物已移至你的钱包。"]}
},
"items":{
"001":{"k":"BotInvite.SelectUsers.Title","en":"Select Users","c":["选择用户 [ios:ChatListFolder.SelectUsers.Title]"]},
"002":{"k":"BotInvite.Sent_any","en":"Invite sent to **%d** users.","p":1,"one":"Invite sent to **%1$@**."},
"003":{"k":["AIAgent.EditController.Name","Checkout.Name"],"en":"NAME","c":["姓名 [ci|macos:Checkout.Name]"]}
}
}
```

字段说明：
- 顶层 `tier`：`"fast"`（常规片）或 `"deep"`（疑难片），决定子代理读取 `PROMPT.fast.md` 或 `PROMPT.deep.md`。
- 顶层 `context`（可选）：按功能前缀汇总本平台已译邻居 `[en, zh]`，每前缀最多 3 条，整片去重。
- `items.<短编号>`：
  - `k`：单条 key 字符串，或共享同一英文的多个代表 key 列表。
  - `en`：当前英文原文。
  - `p`（可选，值为 `1`）：表示该组包含折叠后的复数分支，只需输出 1 条占位符匹配 `en` 的中文，脚本依据 `.meta.json` 自动回填全部分支。
  - `one`（可选）：同词根单数分支的不同英文，仅供语义参考，输出译文的占位符须严格匹配 `en`。
  - `p_en` / `p_zh`（可选）：英文变更或定向重审时的旧英文与上一轮精修译文。
  - `c`（可选）：四端精修候选提示列表（最多 3 条），格式 `"译文 [来源]"`；`[~来源]` 表示占位符安全双射投影，`[ci|来源]` 表示大小写不敏感匹配。

---

## `reply.partNN.json`

**产自**：初译 AI 子代理
**位置**：`work/<p>/`

与同编号 `compact.partNN.json` 的 `items` 短编号一一对应的纯 JSON 对象（初译完成后保持只读，二审不改写此文件）：

```json
{
  "001": "=",
  "002": "已向 **%d** 位用户发送邀请。",
  "003": {"*": "名称", "Checkout.Name": "姓名"},
  "004": "=prev",
  "005": ["此礼物已移至你的个人资料。", "rewrite_ref", "rewrite:ios:Gift.MoveToWallet.Success 调整目标位置"]
}
```

合法取值：
- `"="` 或 `"=0"`、 `"=1"` …：采用对应下标候选，`import_from_ai.py --part N` 按 `.meta.json` 自动展开为 `final`、`"source": "adopt"` 及 `"note": "adopt:<from>"`。
- `"=prev"`：沿用该条的 `p_zh`，展开为 `"source": "adopt"` 与 `"note": "adopt:translation-memory"`。
- 普通字符串 `"译文"`：独立新译，展开为 `"source": "fresh"`（译文字面量恰好匹配引用语法时用数组 `["=", "fresh"]`）。
- 长度 2 或 3 的字符串数组 `["译文", "source"]` / `["译文", "source", "note"]`：显式指定合法 `source` 与可选备注。
- JSON 对象 `{"*": ..., "<key>": ...}`：仅用于同英文多 key 组存在语境差异时按 key 分别覆写（`"*"` 为组内默认值，各值支持上述全部标量语法）。

---

## `review-plan.json`、`review.partNN.json`、`review-patch.partNN.json` 与 `review-summary.json`

**产自**：`export_for_ai.py --review` → 二审 AI 子代理 → `import_from_ai.py --review`
**位置**：`work/<p>/`

- `translated-draft.partNN.json`：`export_for_ai.py --review` 留存的二审前不可变初译快照，确保补丁可幂等重放与完整回滚。
- `review-plan.json`：记录 `total_keys`、`member_units`、`skipped_fast_adopt`（豁免二审的无风险常规精确复用组数）、`reviewed_units`、`flagged_units`（命中本地规则预检组数）、`parts_covered` 与 `review_parts`。
- `review.partNN.json`：待二审条目集合（单行紧凑 JSON；分片路由与完整 key 列表存于同目录 `review.partNN.meta.json`，AI 无需读取）。顶层 `items` 以 `"R001"` 等编号索引，每项含 `k`、`en`、`zh` 及可选的 `one`、`p_en`、`p_zh`、`note`、`flags`（本地静态预检提示，命中项优先排在前部）。
- `review-patch.partNN.json`：二审 AI 输出的**差量补丁**。确认无误的编号省略不写，整片无问题输出 `{}`；需要修改的编号取值为 `"修正后译文"`（原 `source` 为 `adopt` 时自动转为 `rewrite_ref` 并将 `adopt:` 备注转为 `rewrite:`，其余保留原 `source`）、`["修正后译文", "source", "note?"]`，或针对多 key 组的对象局部修正 `{"<key>": "修正译文"}`（未列出 key 保持原草稿，可配合 `"*"`）。
- `review-summary.json`：`import_from_ai.py --review` 基于初译快照重放全部补丁并全量复检通过后生成，汇总二审统计与全部 `patches` 明细，同时作为 `merge_parts.py` 的二审完成门禁凭据。

---

## `PROMPT.md` / `PROMPT.fast.md` / `PROMPT.deep.md` / `PROMPT.review.md`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

翻译与复核 AI 任务合约，由 `export_for_ai.py` 模板与 `docs/06-translation-style.md` 合成（术语仅在该规范文件维护）：
- `PROMPT.fast.md`：常规片指令 + 共用术语表，引导零外部搜索、快速确认候选或直译短词。
- `PROMPT.deep.md`：疑难片指令 + 完整审校规范与易错点核对表。
- `PROMPT.review.md`：差量二审指令 + 共用术语表与易错语义核对表，约束只输出修改补丁。
- `PROMPT.md`：完整总合约概览。

核心约定：
- AI 输出必须是**纯 JSON**，不用 markdown code fence 包裹
- 初译 `reply.partNN.json` 顶层短编号与 `compact.partNN.json` 的 `items` 完全一致；二审 `review-patch.partNN.json` 仅包含需修改的 `Rxxx` 编号（无修改为 `{}`）
- 占位符必须保留（`%@`, `%1$@`, `%d`, `%2$02d`, `%%`, `{xxx}`, 安卓 `un1`/`un2` 与 `**oo**` 等），无编号百分号参数保持次序

---

## `translated.json` / `translated.partNN.json`

**产自**：AI 回传（单片）与原文未变的复用译文 → `merge_parts.py`（合并）；合并后规范化与人工修订以 `translated.json` 为主。
**位置**：`work/<p>/`

```json
{
  "<key>": {
    "final": "<最终译文>",
    "source": "adopt | rewrite_ref | rewrite_official | fresh",
    "note": "<可选, AI 的决策备注>"
  }
}
```

**`source` 字段语义**：
| 值 | 含义 | 审核要求 |
|---|---|---|
| `adopt` | 原样采用经核实的已有译文（note 写明来源，如 `adopt:translation-memory`） | 对照当前英文复核 |
| `rewrite_ref` | 实际基于精修记忆或按需查阅的社区译文改写（note 写来源与理由） | 复核完整语义与上下文 |
| `rewrite_official` | 实际基于按需查阅的官方简中改写（note 写理由） | 复核完整语义与上下文 |
| `fresh` | 以英文和上下文独立翻译，日常默认使用 | 复核完整语义及上下文 |

`source` 只记录实际来源，不代表质量高低。历史条目的来源和备注保留原意。

**必需字段**：`final` 为字符串，英文非空时译文必须非空；官方空串分支允许原样保留。`source` 取值合法；`note` 存在时须为字符串。

---

## `validation.json`

**产自**：`import_from_ai.py`
**位置**：`work/<p>/`，单片校验使用 `validation.partNN.json`，全量使用 `validation.json`。

```json
{
  "total_merged": 14923,
  "total_translated": 14923,
  "problem_count": 0,
  "problems": [
    {
      "key": "<key>",
      "issue": "<issue_type>",
      "en_placeholders": [...],
      "zh_placeholders": [...],
      "en": "...",
      "final": "..."
    }
  ]
}
```

**`issue` 类型**：
- `top_level_not_object` — 回传顶层非 JSON object
- `missing_compact_id` / `extra_compact_id` — `reply.partNN.json` 短编号缺失或多余
- `invalid_candidate_ref:<ref>` — `"="` / `"=N"` 越界或 `"=prev"` 缺少 `previous_zh`
- `invalid_compact_entry` — 紧凑条目值既非字符串、非 2～3 项字符串数组也非合法的按 key 覆写对象
- `unknown_group_key` / `missing_group_key` — 同英文多 key 组覆写对象中出现未知 key 或缺失未覆盖的成员 key
- `unknown_review_id` / `invalid_review_patch_entry` — 二审补丁编号不存在或值格式非法
- `invalid_note` — note 非字符串
- `placeholder_order_mismatch` — 无编号百分号参数顺序变化
- `missing_in_translated` — baseline 有但展开译文里缺失
- `extra_key_not_in_merged` — 展开译文里多出非 baseline 的 key
- `not_object` — 标准译文 entry 非 object
- `missing_final` — `final` 字段缺失、类型错误，或英文非空而译文为空
- `invalid_source:<value>` — source 取值不在白名单
- `placeholder_mismatch` — 占位符与英文不一致（含 `en_placeholders` / `zh_placeholders` diff 字段）

**通过条件**：`problem_count == 0`；失败以状态码 1 退出。占位符比较保留重复次数，包含 `%%`。

---

## `normalize-report.md`

**产自**：`normalize.py`
**位置**：`work/<p>/`

Markdown 格式的 diff 报告。结构：

```md
# normalize DRY-RUN 报告 — ios
- 受影响条目: 779
  - `您→你`: 902 次
  - `...→…`: 47 次

## 文件修改数
- translated.json: 25 条
...

## 全部修改条目 (diff)
### `<key>`  (translated.json, 您→你×2)
```diff
- 您已限制 Telegram 对您所有照片的访问权限。
+ 你已限制 Telegram 对你所有照片的访问权限。
```
```

---

## `report.html`

**产自**：`diff_report.py`
**位置**：`work/<p>/`

默认全量报告；`--update` 输出 `update-report.html`，范围为 `to-translate.json`。按尚无译文、新增、英文变化、既有审校和其他条目分组，每组一个表格，空组省略。

列顺序：key、当前英文、旧英文（变化时）、上一轮精修译文、最终译文、来源记录、审校备注。历史对照来自 `translation-memory.json`，变更类型来自 `update.json`，旧英文相同时该格留空。参考包不作为默认对照列，来源标签不决定颜色或审核优先级。

---

## `dist/<platform>/zh-Hans-custom.strings`

**产自**：`build_strings.py`
**用途**：完整成品，包含 `translated.json` 的全部 key 与复数分支，用于再解析核对和留档。

iOS、macOS 与 TDesktop 的格式见本文档开头的 `.strings` 定义；Android 输出 `dist/android/zh-Hans-custom.xml`。所有平台按 key 字母序输出，不带注释。

---

## `dist/<platform>/zh-Hans-custom.upload.strings`

**产自**：`build_strings.py`
**用途**：上传 translations.telegram.org 的文件。

格式与完整成品相同，Android 为 `dist/android/zh-Hans-custom.upload.xml`。内容是完整成品的子集：每个复数词条只保留中文使用的分支，macOS 另外省略无后缀的 `Star.Auction.Preview.TopBidders`，保留的值与完整成品一致。删除规则见 [`build_strings.py`](03-scripts.md#build_stringspy)。

---

## `.bak` 备份

**产自**：`normalize.py --apply`
**命名**：`translated.json.bak`

仅在 normalize 首次 apply 时创建（后续 apply 不覆盖已有 `.bak`），内容是 normalize 前的原文。

**回滚**：
```bash
cp work/ios/translated.json.bak work/ios/translated.json
python3 scripts/import_from_ai.py ios
python3 scripts/build_strings.py ios
```


## `update.json` 与历史归档

由 `prepare_update.py` 生成：

```json
{
  "platform": "ios",
  "created_at": "2026-09-28T15:00:00+08:00",
  "archive": "history/<时间>",
  "sources": {
    "en": {"filename": "ios_en_VERSION.strings", "sha256": "<SHA-256>"}
  },
  "previous_total": 100,
  "total": 103,
  "added": ["new.key"],
  "changed": ["changed.key"],
  "removed": [],
  "reused_count": 98,
  "reviewed_existing": []
}
```

`added`、`changed`、`removed` 是 key 列表；示例数量仅展示字段。`archive` 相对当前平台 work 目录，内含旧 `raw/`、`parsed/`、`work/` 与 `dist/`。`reviewed_existing` 为可选字段，记录本轮额外审校的既有 key（如术语修订）；相应条目须从复用集合移入待审校集合，更新 `reused_count`。

任务结束后，归档中的下载原件及复制件按 [下载资源清理规则](../AGENTS.md#维护铁律) 删除，`raw/` 可为空；旧英文和参考内容保留在 `parsed/` 及 `work/merged.json` 中。

`translated.reused.json` 与 `translated.json` 使用相同条目结构，只包含未进入本轮审校的译文。其 key 与审校 key 不得重叠，二者并集必须覆盖当前 `merged.json`。


## `translation-memory.json`

由 `prepare_update.py` 从上一轮英文基准和精修主文件生成，与默认待译输入分开：

```json
{
  "<key>": {
    "en": "上一轮英文",
    "final": "对应的上一轮精修译文"
  }
}
```

保存上一轮全部 key，包括本轮已删除的条目，供按需检索历史表达。它不参与合并和打包。原文未变的实际复用对象是 `translated.reused.json`；翻译时可查此记忆核对术语和表达。

## `review.md`

由实际审校者填写，记录本轮语义与一致性复核范围、发现的问题及处理、术语例外、歧义查证依据和未决项。它是人工审校记录，脚本不根据文件存在与否认定语义通过，也不自动生成“审校通过”结论。
