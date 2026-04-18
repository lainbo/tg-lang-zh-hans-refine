#!/usr/bin/env python3
"""校验翻译 AI 回传的 translated.json (或单个分片)。

检查项:
1. 结构完整: 每个 key 有 {final, source, note?}, source 合法
2. 占位符一致性: %@, %1$@, %d, %1$d, %s, %1$s, {...} 数量和类型与 en 保持一致
3. key 覆盖: AI 回传的 key 是否覆盖了基准的所有 key (缺失/多余报告)

基准 baseline 选择:
  - 默认: work/<platform>/merged.json  (全量模式)
  - --part N: work/<platform>/to-translate.partNN.json  (单片模式, 只校验该片应有的 keys)

产出 work/<platform>/validation.json (详细问题清单) 和打印摘要。

用法:
  python3 scripts/import_from_ai.py ios                            # 校验 translated.json 对全量
  python3 scripts/import_from_ai.py ios --part 1                   # 只校验 translated.part01.json
  python3 scripts/import_from_ai.py ios --part 1 custom.json       # 指定任意回传文件名
"""
from __future__ import annotations
import json
import re
import sys

from _common import platform_dirs

VALID_SOURCES = {"adopt", "rewrite_ref", "rewrite_official", "fresh"}

# 占位符: Apple %@ / %1$@ / %d / %1$d / %s / %1$s / %1$.2f 等
_PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[@dsif]|%(?:\d+\$)?\.\d+[df]|\{[^{}]+\}")


def placeholders(s: str) -> list[str]:
    return sorted(_PLACEHOLDER_RE.findall(s))


def main(platform: str, translated_name: str, part: int | None) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]

    if part is None:
        baseline_path = work / "merged.json"
        default_translated = "translated.json"
    else:
        baseline_path = work / f"to-translate.part{part:02d}.json"
        default_translated = f"translated.part{part:02d}.json"

    if not baseline_path.exists():
        raise SystemExit(f"missing baseline: {baseline_path}")
    merged = json.loads(baseline_path.read_text(encoding="utf-8"))

    translated_path = work / (translated_name or default_translated)
    if not translated_path.exists():
        raise SystemExit(f"missing {translated_path}. 把 AI 回传结果放到这里")
    translated = json.loads(translated_path.read_text(encoding="utf-8"))

    problems: list[dict] = []
    missing = sorted(set(merged.keys()) - set(translated.keys()))
    extra = sorted(set(translated.keys()) - set(merged.keys()))
    for k in missing:
        problems.append({"key": k, "issue": "missing_in_translated"})
    for k in extra:
        problems.append({"key": k, "issue": "extra_key_not_in_merged"})

    for key, entry in translated.items():
        if key not in merged:
            continue
        if not isinstance(entry, dict):
            problems.append({"key": key, "issue": "not_object"})
            continue
        final = entry.get("final")
        source = entry.get("source")
        if not isinstance(final, str) or not final:
            problems.append({"key": key, "issue": "missing_final"})
            continue
        if source not in VALID_SOURCES:
            problems.append({"key": key, "issue": f"invalid_source:{source}"})
        en = merged[key]["en"]
        en_ph = placeholders(en)
        zh_ph = placeholders(final)
        if en_ph != zh_ph:
            problems.append({
                "key": key,
                "issue": "placeholder_mismatch",
                "en_placeholders": en_ph,
                "zh_placeholders": zh_ph,
                "en": en,
                "final": final,
            })

    report = {
        "total_merged": len(merged),
        "total_translated": len(translated),
        "problem_count": len(problems),
        "problems": problems,
    }
    out = work / "validation.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 摘要
    by_issue: dict[str, int] = {}
    for p in problems:
        issue = p["issue"].split(":")[0]
        by_issue[issue] = by_issue.get(issue, 0) + 1
    print(f"翻译覆盖: {len(translated)}/{len(merged)}")
    print(f"问题总数: {len(problems)}")
    for issue, n in sorted(by_issue.items(), key=lambda x: -x[1]):
        print(f"  {issue:30s} {n}")
    print(f"\n详细清单 → {out.relative_to(dirs['raw'].parent.parent.parent)}")

    if not problems:
        print("\n✅ 校验通过, 可以跑 build_strings.py 打包")
    else:
        print("\n⚠️  有问题, 修好后重跑本脚本")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit(
            "usage: import_from_ai.py <ios|macos|tdesktop> [--part N] [translated-file.json]"
        )
    platform = argv[0]
    part: int | None = None
    name: str | None = None
    i = 1
    while i < len(argv):
        if argv[i] == "--part":
            part = int(argv[i + 1])
            i += 2
        else:
            name = argv[i]
            i += 1
    main(platform, name, part)
