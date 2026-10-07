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

首次全量导出时与 `merged.json` 相同；增量更新时只包含待审校子集。只含 `en`，英文变化时额外带 `previous_en`（旧英文）。参考译文不进入输入；本项目旧精修译文单独放在 `translation-memory.json`。分片按 key 字母序切，片间无重叠。

**分片命名**：`part01` ~ `partNN`（零填充 2 位），`NN = ceil(total / chunk)`。

---

## `PROMPT.md`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

翻译 AI 任务合约。由 `export_for_ai.py` 的 `PROMPT_TEMPLATE` 与 `docs/06-translation-style.md` 合成；术语只在该规范文件维护。

核心约定：
- AI 输出必须是**纯 JSON**，不用 markdown code fence 包裹
- 顶层 key 必须与输入完全一致，不增不减
- 每 entry 必须有 `final` 和 `source`，`note` 可选
- 占位符必须保留（`%@`, `%1$@`, `%d`, `%2$02d`, `{xxx}` 等）
- 安卓服务消息的 `un1` / `un2` 等具名替换标记和输入状态的 `**oo**` 动画标记也校验数量与写法

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
- `top_level_not_object` — 回传顶层不是 object
- `invalid_note` — note 非字符串
- `placeholder_order_mismatch` — 无编号百分号参数顺序变化
- `missing_in_translated` — baseline 有但 AI 回传里没有
- `extra_key_not_in_merged` — AI 回传多出来的 key
- `not_object` — entry 不是 object
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
**用途**：上传 translations.telegram.org 的最终产物。

iOS、macOS 与 TDesktop 的格式见本文档开头的 `.strings` 定义；Android 输出 `dist/android/zh-Hans-custom.xml`。所有平台按 key 字母序输出，不带注释。

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
