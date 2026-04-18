#!/usr/bin/env python3
"""把 merged.json 转成翻译 AI 友好的输入格式, 并写出 PROMPT.md。

输出 work/<platform>/to-translate.json, 结构:
{
  "lng_xxx": {
    "en": "...",
    "official_zh": "...",        // 待替换的机翻版, 可能缺失
    "refs": {"zhcncc": "..."}    // 参考源, 可能缺失
  },
  ...
}

可选参数 --chunk N 切分为 to-translate.part01.json ... 便于分批喂给 AI。
用法: python3 scripts/export_for_ai.py ios [--chunk 500]
"""
from __future__ import annotations
import json
import sys

from _common import platform_dirs

PROMPT_TEMPLATE = """# 翻译 AI 审校任务 Prompt

你是 Telegram 简体中文语言包审校者。输入是一份 JSON, 每个 key 对应一条字符串, 带:
- `en`: 官方英文原文 (权威)
- `official_zh`: Telegram 官方新出的简中译文 (通常机翻味重, 待改版的对象)
- `refs`: 社区参考包译文 (例如 `zhcncc`, 质量通常更好)

## 你的职责

对每个 key 输出一个对象:
```json
{
  "final": "最终译文",
  "source": "adopt|rewrite_ref|rewrite_official|fresh",
  "note": "可选, 改写原因或不确定的点"
}
```

`source` 取值语义 (严格遵守, 便于人工审核时分类):
- `adopt`          — 直接采用某个 ref (note 里写采用哪个, 如 "adopt:zhcncc")
- `rewrite_ref`    — 基于某个 ref 微调 (note 里写基础来源 + 改动原因)
- `rewrite_official` — 基于 official_zh 改写 (官方没毛病, 只是不够地道)
- `fresh`          — 全部候选都不行, 重新翻译

## 翻译原则

1. **保留占位符**: `%@`, `%1$@`, `%d`, `%1$d`, `%s`, `{user}`, `**markdown**` 必须原样保留, 位置可调但不能增删。
2. **保留格式**: 换行 `\\n`、省略号 `…`、标点对齐原文风格。
3. **口吻**: 母语中文用户, 简洁、自然、尊重。避免"您" 和"您的"泛滥 (Telegram 官方风格偏口语)。
4. **一致性**: 常见词统一 (Chat=聊天, Channel=频道, Group=群组, Bot=机器人, Sticker=贴纸, Reaction=表情回应 等)。
5. **不过度创作**: 如果 ref 已经很好, 直接 `adopt` 就行, 别手痒。
6. **key 名当上下文线索**: 如 `lng_chat_*` 是聊天内, `lng_settings_*` 是设置界面。

## 输出要求

输出一个纯 JSON, 顶层 key 与输入完全一致, 不增不减, 不要输出除 JSON 外任何内容 (便于脚本 parse)。
"""


def main(platform: str, chunk: int | None) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    merged_path = work / "merged.json"
    if not merged_path.exists():
        raise SystemExit(f"missing {merged_path}. 先跑 merge.py")

    merged = json.loads(merged_path.read_text(encoding="utf-8"))

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
    prompt_path.write_text(PROMPT_TEMPLATE, encoding="utf-8")
    print(f"写入 {prompt_path.relative_to(dirs['raw'].parent.parent.parent)}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: export_for_ai.py <ios|macos> [--chunk N]")
    platform = argv[0]
    chunk = None
    if "--chunk" in argv:
        i = argv.index("--chunk")
        chunk = int(argv[i + 1])
    main(platform, chunk)
