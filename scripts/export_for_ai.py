#!/usr/bin/env python3
"""把 merged.json 转成翻译 AI 友好的输入格式, 并写出 PROMPT.md。

输出 work/<platform>/to-translate.json, 结构:
{
  "lng_xxx": {
    "en": "...",
    "previous_en": "..."        // 英文变化时提供
  },
  ...
}

可选参数 --chunk N 切分为 to-translate.part01.json ... 便于分批喂给 AI。
用法: python3 scripts/export_for_ai.py ios [--chunk 100]
"""
from __future__ import annotations
import json
import sys

from _common import ROOT, platform_dirs

PROMPT_TEMPLATE = """# 翻译 AI 审校任务 Prompt

你是 Telegram 简体中文语言包审校者。以当前英文、功能上下文和共用术语为依据，逐条翻译，再单独进行语义与一致性复核。
输入是一份 JSON，每个 key 对应一条字符串：
- `en`：当前官方英文，决定语义
- `previous_en`：英文变化时提供的旧英文，用于识别条件、范围与操作后果的变化

## 工作顺序

1. 阅读下方术语表，结合 key 和同功能英文理解界面用途。需要更多上下文时，在本平台 `merged.json` 查找相关条目；歧义仍存在时查客户端界面或官方源码。分片只是存储边界。
2. 先根据当前英文拟定中文。随后按相关 key 查阅 `translation-memory.json` 中成对保存的旧英文与精修译文，核对术语和表达；英文变更时重新核对旧译的适用范围。首次初始化可能没有翻译记忆。
3. 官方简中和社区包按需查阅 `data/<平台>/parsed/` 或 `raw/` 中的对应文件。只查具体疑点，在 note 记录来源、判断依据和决定；候选译文不能代替界面或源码证据。
4. 初译完成后，再逐条对照当前英文复核主体、条件、否定、参数角色与格式；随后检查同功能和两平台的术语、按钮、说明及复数分支。可在新会话复核，也可在当前会话单独完成这一遍检查。
5. 在 `review.md` 记录实际审校范围、发现的问题、上下文依据和未决项。会影响含义的疑点解决前不将该条视为完成。结构校验通过后，再合并、生成报告和打包。

## 你的职责

对每个 key 输出一个对象:
```json
{
  "final": "最终译文",
  "source": "fresh",
  "note": "可选，语义判断、术语例外或查证依据"
}
```

`source` 如实记录来源，不用于评价质量或决定审核优先级：
- `fresh` — 以英文和上下文独立翻译，日常默认使用
- `adopt` — 对照当前英文核实后，原样采用已有译文；note 写明实际来源，如 `adopt:translation-memory`
- `rewrite_ref` — 实际以精修译文或按需查阅的社区译文为基础改写；note 写明来源与理由
- `rewrite_official` — 实际以按需查阅的官方简中为基础改写；note 写明理由

所有本轮条目均须完整复核。模型版本变化也遵循相同要求，已有历史来源记录保持原意。

## 翻译原则

1. **信**：以英文为准，完整保留主体、条件、否定、范围、金额、时间和操作后果。旧译文只有在新原文下仍准确才可复用。
2. **达**：结合 key、同功能相邻文案和界面用途消除歧义。按钮用简洁动作，说明交代清楚条件与结果；不逐词硬译。
3. **雅**：使用自然、克制的现代简体中文，称呼统一为“你”。不添加原文没有的承诺、语气或解释。
4. **一致性**：遵守下方共用术语表；同一功能的标题、按钮和说明用词一致。复数各分支都必须提供，中文通常使用相同句式。
5. **保留占位符**：`%@`、`%d`、`%.2d`、`%%`、`{user}` 等数量与写法不变。无编号的百分号参数必须保持原有次序；`%1$@` 等带编号参数和具名参数可按中文语序移动，参数角色不变。
6. **保留格式**：保留 Markdown 标记、链接目标、标签、必要换行及链接前后的语义；省略号统一为 `…`。不要改动 URL、代码和协议字面量。
7. **稳定复用**：原文未变且现有译文准确自然时保留现有译文。发现既有错误或术语冲突时，定向列入审校；模型升级本身不触发全量重译。
8. **上下文不足**：查同功能相关 key 或官方客户端代码；仍无法确认时在 note 写明具体疑点，不能自行补造功能。

## 输出要求

输出一个纯 JSON, 顶层 key 与输入完全一致, 不增不减, 不要输出除 JSON 外任何内容 (便于脚本 parse)。
"""


def main(platform: str, chunk: int | None, entries: dict | None = None) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    merged_path = work / "merged.json"
    if not merged_path.exists():
        raise SystemExit(f"missing {merged_path}. 先跑 merge.py")

    merged = entries if entries is not None else json.loads(merged_path.read_text(encoding="utf-8"))
    merged = {key: {name: entry[name] for name in ("en", "previous_en") if name in entry}
              for key, entry in merged.items()}
    if chunk is not None and chunk <= 0:
        raise SystemExit("--chunk 必须为正整数")
    if list(work.glob("translated.part*.json")):
        raise SystemExit("已有审校分片。增量更新请先运行 prepare_update.py 归档上一轮。")
    for stale in work.glob("to-translate.part*.json"):
        stale.unlink()

    out = work / "to-translate.json"
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"写入 {out.relative_to(dirs['raw'].parent.parent.parent)}  ({len(merged)} keys)")

    if chunk:
        keys = sorted(merged.keys())
        total = (len(keys) + chunk - 1) // chunk
        for i in range(total):
            part = {k: merged[k] for k in keys[i * chunk : (i + 1) * chunk]}
            part_path = work / f"to-translate.part{i+1:02d}.json"
            part_path.write_text(json.dumps(part, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"切分为 {total} 个分片 (每片 ≤{chunk} keys)")

    prompt_path = work / "PROMPT.md"
    glossary = (ROOT / "docs" / "06-translation-style.md").read_text(encoding="utf-8")
    prompt_path.write_text(PROMPT_TEMPLATE + "\n" + glossary, encoding="utf-8")
    print(f"写入 {prompt_path.relative_to(dirs['raw'].parent.parent.parent)}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: export_for_ai.py <ios|macos|tdesktop> [--chunk N]")
    platform = argv[0]
    chunk = None
    if "--chunk" in argv:
        i = argv.index("--chunk")
        chunk = int(argv[i + 1])
    main(platform, chunk)
