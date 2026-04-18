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

**本项目处理**：
- 解析丢弃注释，保留 key-value
- 输出按 key 字母序排序（便于 diff）
- 不输出注释

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
    "en": "<英文原文, 必有>",
    "official_zh": "<官方简中, 可选>",
    "refs": {
      "zhcncc": "<社区参考, 可选>",
      "<other>": "<其他 ref-*, 可选>"
    }
  }
}
```

**字段约束：**
- `en` 必存在（baseline）
- `official_zh` 和 `refs` 缺失表示源未覆盖该 key
- `refs` 空或全部缺失时本字段会整个省略

---

## `to-translate.json` / `to-translate.partNN.json`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

结构与 `merged.json` 完全一致，是同一份数据的复制（或分片）。分片按 key 字母序切，片间无重叠。

**分片命名**：`part01` ~ `partNN`（零填充 2 位），`NN = ceil(total / chunk)`。

---

## `PROMPT.md`

**产自**：`export_for_ai.py`
**位置**：`work/<p>/`

翻译 AI 任务合约。**内容是脚本硬编码的 `PROMPT_TEMPLATE`**，改动须同步到 `export_for_ai.py`。

核心约定：
- AI 输出必须是**纯 JSON**，不用 markdown code fence 包裹
- 顶层 key 必须与输入完全一致，不增不减
- 每 entry 必须有 `final` 和 `source`，`note` 可选
- 占位符必须保留（`%@`, `%1$@`, `%d`, `{xxx}` 等）

---

## `translated.json` / `translated.partNN.json`

**产自**：AI 回传（单片）→ `merge_parts.py`（合并）
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
| 值 | 含义 | 审核优先级 |
|---|---|---|
| `adopt` | 直接采用某个参考源（note 里写 `adopt:<ref_name>`） | 低（扫一眼） |
| `rewrite_ref` | 基于参考源微调（note 写原因） | 中 |
| `rewrite_official` | 基于官方简中改写（通常是修机翻味） | 高 |
| `fresh` | 全部候选都不可用，重新翻译 | 最高 |

**必需字段**：`final` 非空字符串、`source` 取值合法。

---

## `validation.json`

**产自**：`import_from_ai.py`
**位置**：`work/<p>/`

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
- `missing_in_translated` — baseline 有但 AI 回传里没有
- `extra_key_not_in_merged` — AI 回传多出来的 key
- `not_object` — entry 不是 object
- `missing_final` — `final` 字段缺失或空
- `invalid_source:<value>` — source 取值不在白名单
- `placeholder_mismatch` — 占位符与英文不一致（含 `en_placeholders` / `zh_placeholders` diff 字段）

**通过条件**：`problem_count == 0`。

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

## 各分片修改数
- translated.part01.json: 25 条
...

## 全部修改条目 (diff)
### `<key>`  (translated.partNN.json, 您→你×2)
```diff
- 您已限制 Telegram 对您所有照片的访问权限。
+ 你已限制 Telegram 对你所有照片的访问权限。
```
```

---

## `report.html`

**产自**：`diff_report.py`
**位置**：`work/<p>/`

HTML 审核报告。按 source 分组，每组一个 `<table>`。列顺序：

| key | en | official_zh | refs.<各个> | final | source | note |

**样式**：source 分组间用颜色区分（red/orange/yellow/green），表头 sticky。

---

## `dist/<platform>/zh-Hans-custom.strings`

**产自**：`build_strings.py`
**用途**：上传 translations.telegram.org 的最终产物。

格式见本文档开头的 `.strings` 定义，按 key 字母序输出，不带注释。

---

## `.bak` 备份

**产自**：`normalize.py --apply`
**命名**：`translated.partNN.json.bak`

仅在 normalize 首次 apply 时创建（后续 apply 不覆盖已有 `.bak`），内容是 normalize 前的原文。

**回滚**：
```bash
for f in work/ios/translated.part*.json.bak; do mv "$f" "${f%.bak}"; done
python3 scripts/merge_parts.py ios
```
