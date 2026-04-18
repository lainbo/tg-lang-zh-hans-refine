# 01 · 架构与设计原则

## 核心抓手

**问题**：Telegram 官方新版简中"机翻味"重，用户想用 AI 精修，但直接让 AI 对 14000+ 条字符串硬翻质量会崩——上下文缺失、术语不一致、占位符误伤。

**破局思路**：引入**翻译记忆（Translation Memory）**。
- 官方英文 = 权威 baseline
- 官方简中 = 机翻版，作为反面教材
- 社区包（@zhcncc 等） = 人工精品，作为正面参考

三源对齐后让 AI **做裁判**而不是**做译者**：
- 三份候选一致且地道 → 直接采用
- 候选分歧 → 挑最好的或综合改写
- 全员机翻 → 重新翻译

这就是业界专业翻译工具（Trados、Crowdin）的 TM + Review 模式，本项目只是轻量化复刻。

---

## 数据流

```mermaid
flowchart TD
    TG[translations.telegram.org<br/>手动下载] --> EN[en.strings]
    TG --> OFFZH[official-zh.strings]
    TG --> ZHCNCC[zhcncc.strings]

    EN --> PARSE[parse_strings.py]
    OFFZH --> PARSE
    ZHCNCC --> PARSE
    PARSE --> PARSED[(data/&lt;p&gt;/parsed/*.json)]

    PARSED --> MERGE[merge.py<br/>以 en 为 key 全集对齐]
    MERGE --> MERGED[(work/&lt;p&gt;/merged.json)]

    MERGED --> EXPORT[export_for_ai.py --chunk 500]
    EXPORT --> PARTS[(to-translate.partNN.json × 30<br/>+ PROMPT.md)]

    PARTS -.外部翻译 AI 审校.-> TRANS[(translated.partNN.json × 30)]

    TRANS --> MERGEP[merge_parts.py]
    MERGEP --> TRANSLATED[(work/&lt;p&gt;/translated.json)]

    TRANSLATED --> NORMALIZE[normalize.py --apply<br/>您→你, ...→…]
    NORMALIZE -.回写 + .bak 备份.-> TRANS

    TRANSLATED --> VALIDATE[import_from_ai.py 校验]
    VALIDATE --> VALIDATION[(validation.json<br/>问题数须为 0)]

    TRANSLATED --> REPORT[diff_report.py]
    REPORT --> HTML[(report.html)]

    TRANSLATED --> BUILD[build_strings.py]
    BUILD --> DIST[(dist/&lt;p&gt;/zh-Hans-custom.strings)]

    DIST -.手动上传.-> UPLOAD[translations.telegram.org<br/>自定义语言包 Import + EDIT PHRASES]
    UPLOAD --> USER[Sharing Link<br/>应用到客户端]

    classDef artifact fill:#e8f4f8,stroke:#2c7da0,stroke-width:1px
    classDef script fill:#fdf6e3,stroke:#b58900,stroke-width:1px
    classDef external fill:#fce4ec,stroke:#c2185b,stroke-width:1px
    class EN,OFFZH,ZHCNCC,PARSED,MERGED,PARTS,TRANS,TRANSLATED,VALIDATION,HTML,DIST artifact
    class PARSE,MERGE,EXPORT,MERGEP,NORMALIZE,VALIDATE,REPORT,BUILD script
    class TG,UPLOAD,USER external
```

---

## 为什么这么设计

### 为什么不直接调 AI API 自动化全流程？

1. **翻译质量需要人工审核点**：AI 偶发漏译/误译，全自动化会埋雷。本流程把"审校"显式切出来，生成 HTML 报告强制人工扫一眼 `rewrite_*` 和 `fresh` 类别。
2. **翻译成本/厂商选择解耦**：用户可以用任意 AI（Claude / GPT / 豆包 / 自建），本项目不绑定任何翻译服务。
3. **中间产物可检查**：每步落盘，出错能定位到条目级别。

### 为什么分片 500 条？

- 单次喂 AI 的 token 预算上限（含输入输出） ≈ 40k tokens
- 14923 条全量约 60k tokens 输入 → 单次放不下
- 500 条 × 3 份译文候选 ≈ 20k 输入 + 20k 输出，稳定在上下文中段，不容易触发截断

### 为什么 AI 输出要带 `source` 标签？

`adopt / rewrite_ref / rewrite_official / fresh` 四选一。核心用途：
- **审核优先级分流**：人工只需重点看 `fresh` + `rewrite_official`，`adopt` 几乎免检
- **成本对齐**：让 AI 显式做决策而不是默认全量重写，降低 AI 自说自话比例
- **可解释性**：后续 diff 报告按 source 分组，高亮"AI 真的下刀改了的"

### 为什么 normalize 是后处理 pass 而不是 AI 自己做？

AI 逐条处理时很难保证"您→你"全覆盖——`adopt` 直接采用了 zhcncc 的"您"就漏了。把全局一致性规则抽到独立 pass，保证命中率 100%。

### 为什么 base language 选简中而不是英文？

详见 `docs/05-troubleshooting.md#base-language 选择`。简单说：新 key fallback 到官方简中比 fallback 到英文体面得多。

---

## 边界（这个项目不做什么）

- **不做翻译**：翻译由外部 AI 完成，本项目只校验和打包
- **不做自动上传**：Telegram 平台需要账号+人工点 `EDIT PHRASES` 确认，脚本化有风险
- **不做 .stringsdict 复数字典**：Telegram iOS 对复数有独立格式，当前版本用 `_one/_other` 后缀 key 应付绝大部分场景
- **不做版本管理**：每次全量跑一遍即可，历史译文存在于 git 和 `.bak`

---

## 扩展方向

| 需求 | 动手位置 |
|---|---|
| 新增参考源 | `data/<p>/raw/ref-<name>.strings`，`merge.py` 自动识别 |
| 新增平台（Android/Desktop） | `_common.py:PLATFORMS` 追加，其他脚本基本适配 |
| 新增 normalize 规则 | `normalize.py:normalize()`，先 dry-run |
| 增强 PROMPT 语气基线 | `export_for_ai.py:PROMPT_TEMPLATE` |
| 更严格的占位符校验 | `import_from_ai.py:_PLACEHOLDER_RE` |
