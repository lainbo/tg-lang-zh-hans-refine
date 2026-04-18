#!/usr/bin/env python3
"""全局风格统一化 pass。对 translated.part*.json 的 final 字段应用规则。

规则 (保守, 可扩展):
  1. '您' → '你'        (Telegram 官方风格偏口语)
  2. '...' (3+ 半角点) → '…'  (U+2026)
  3. '。。。' (3+ 全角句号) → '…'

模式:
  默认 dry-run     — 只产出 work/<platform>/normalize-report.md, 不改原文件
  --apply          — 备份原文件为 .bak, 写回修改后内容

用法:
  python3 scripts/normalize.py ios
  python3 scripts/normalize.py ios --apply
"""
from __future__ import annotations
import json
import re
import shutil
import sys

from _common import platform_dirs


def normalize(text: str) -> tuple[str, dict[str, int]]:
    hits: dict[str, int] = {}
    new = text

    cnt = new.count("您")
    if cnt:
        new = new.replace("您", "你")
        hits["您→你"] = cnt

    new2, cnt = re.subn(r"\.{3,}", "…", new)
    if cnt:
        hits["...→…"] = cnt
        new = new2

    new2, cnt = re.subn(r"。{3,}", "…", new)
    if cnt:
        hits["。。。→…"] = cnt
        new = new2

    return new, hits


def main(platform: str, apply: bool) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]

    parts = sorted(work.glob("translated.part*.json"))
    if not parts:
        raise SystemExit(f"no translated.part*.json under {work}")

    rule_totals: dict[str, int] = {}
    changed_entries: list[dict] = []
    per_file_changes: dict[str, int] = {}

    for part_file in parts:
        data = json.loads(part_file.read_text(encoding="utf-8"))
        file_changed = 0
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            final = entry.get("final")
            if not isinstance(final, str):
                continue
            new_final, hits = normalize(final)
            if hits:
                changed_entries.append({
                    "part": part_file.name,
                    "key": key,
                    "before": final,
                    "after": new_final,
                    "rules": hits,
                })
                for rule, n in hits.items():
                    rule_totals[rule] = rule_totals.get(rule, 0) + n
                file_changed += 1
                if apply:
                    entry["final"] = new_final
        if file_changed:
            per_file_changes[part_file.name] = file_changed
        if apply and file_changed:
            bak = part_file.with_suffix(".json.bak")
            if not bak.exists():
                shutil.copy2(part_file, bak)
            part_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )

    # 报告
    report_lines: list[str] = []
    report_lines.append(f"# normalize {'APPLY' if apply else 'DRY-RUN'} 报告 — {platform}\n")
    report_lines.append(f"- 受影响条目: **{len(changed_entries)}**")
    for rule, n in sorted(rule_totals.items(), key=lambda x: -x[1]):
        report_lines.append(f"  - `{rule}`: {n} 次")
    report_lines.append("")
    report_lines.append("## 各分片修改数")
    for f, n in sorted(per_file_changes.items()):
        report_lines.append(f"- {f}: {n} 条")

    report_lines.append("\n## 全部修改条目 (diff)\n")
    for e in changed_entries:
        rules_str = ", ".join(f"{r}×{n}" for r, n in e["rules"].items())
        report_lines.append(f"### `{e['key']}`  ({e['part']}, {rules_str})")
        report_lines.append("```diff")
        for line_b, line_a in zip(e["before"].splitlines() or [e["before"]], e["after"].splitlines() or [e["after"]]):
            if line_b != line_a:
                report_lines.append(f"- {line_b}")
                report_lines.append(f"+ {line_a}")
            else:
                report_lines.append(f"  {line_b}")
        # 处理多行数不等的情况
        b_lines = e["before"].splitlines() or [e["before"]]
        a_lines = e["after"].splitlines() or [e["after"]]
        if len(b_lines) != len(a_lines):
            report_lines.append(f"(行数: before={len(b_lines)} after={len(a_lines)})")
        report_lines.append("```\n")

    report = work / "normalize-report.md"
    report.write_text("\n".join(report_lines), encoding="utf-8")

    # 摘要打印
    print(f"模式: {'APPLY (已写回)' if apply else 'DRY-RUN (未写回)'}")
    print(f"受影响条目: {len(changed_entries)}")
    for rule, n in sorted(rule_totals.items(), key=lambda x: -x[1]):
        print(f"  {rule:20s} {n} 次")
    print(f"\n详细 diff → {report.relative_to(dirs['raw'].parent.parent.parent)}")
    if apply:
        print("原文件已备份为 .bak, 若要回滚: mv file.json.bak file.json")
    else:
        print("若要真改, 加 --apply 重跑")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        raise SystemExit("usage: normalize.py <ios|macos|tdesktop> [--apply]")
    platform = argv[0]
    apply = "--apply" in argv
    main(platform, apply)
