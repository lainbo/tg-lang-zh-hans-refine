#!/usr/bin/env python3
"""把 translated.part01.json ... partNN.json 合并为 translated.json。

校验:
1. 合并时检测是否有重复 key (不应该出现, 分片按 key 排序切分)
2. 汇总 key 数, 对比 merged.json 看覆盖率

用法: python3 scripts/merge_parts.py ios
"""
from __future__ import annotations
import json
import sys

from _common import platform_dirs


def main(platform: str) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]

    parts = sorted(work.glob("translated.part*.json"))
    if not parts:
        raise SystemExit(f"no translated.part*.json under {work}")

    merged_baseline = json.loads((work / "merged.json").read_text(encoding="utf-8"))

    combined: dict[str, dict] = {}
    duplicates: list[tuple[str, str, str]] = []  # (key, first_part, second_part)
    for part_file in parts:
        data = json.loads(part_file.read_text(encoding="utf-8"))
        for key, entry in data.items():
            if key in combined:
                duplicates.append((key, combined[key].get("_from", "?"), part_file.name))
            else:
                entry_copy = dict(entry)
                combined[key] = entry_copy
        print(f"  {part_file.name}  +{len(data)}  累计 {len(combined)}")

    # 清洗内部临时字段 (如果有)
    for v in combined.values():
        v.pop("_from", None)

    out = work / "translated.json"
    out.write_text(json.dumps(combined, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # 覆盖率
    baseline_keys = set(merged_baseline.keys())
    got = set(combined.keys())
    missing = baseline_keys - got
    extra = got - baseline_keys

    print()
    print(f"合并完成: {len(combined)} 条 → {out}")
    print(f"全量基准: {len(baseline_keys)} 条 (merged.json)")
    print(f"覆盖率:   {len(got & baseline_keys)}/{len(baseline_keys)}")
    if missing:
        print(f"⚠️  基准里有 {len(missing)} 条未被分片覆盖 (例: {sorted(missing)[:3]})")
    if extra:
        print(f"⚠️  分片里有 {len(extra)} 条在基准之外 (例: {sorted(extra)[:3]})")
    if duplicates:
        print(f"⚠️  {len(duplicates)} 个 key 在多片重复 (后者覆盖前者, 例: {duplicates[:3]})")
    if not (missing or extra or duplicates):
        print("✅ 分片合并干净无瑕疵, 可以跑 import_from_ai.py ios 做全量校验")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: merge_parts.py <ios|macos>")
    main(sys.argv[1])
