#!/usr/bin/env python3
"""合并本轮审校分片与未变译文；校验失败时保留原 translated.json。"""
from __future__ import annotations
import json
import shutil
import sys

from _common import platform_dirs
from import_from_ai import validate


def main(platform: str) -> None:
    work = platform_dirs(platform)["work"]
    baseline = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    inputs = sorted(work.glob("to-translate.part*.json"))
    expected = {p.name.replace("to-translate", "translated") for p in inputs}
    actual = {p.name for p in work.glob("translated.part*.json")}
    if actual != expected:
        raise SystemExit(f"分片不匹配：缺少 {sorted(expected - actual)}；多余 {sorted(actual - expected)}")

    reused = work / "translated.reused.json"
    combined = json.loads(reused.read_text(encoding="utf-8")) if reused.exists() else {}
    for part in inputs:
        data = json.loads((work / part.name.replace("to-translate", "translated")).read_text(encoding="utf-8"))
        part_baseline = json.loads(part.read_text(encoding="utf-8"))
        problems = validate(part_baseline, data)
        if problems:
            raise SystemExit(f"{part.name}：{len(problems)} 个校验问题，合并已停止。")
        duplicates = combined.keys() & data.keys()
        if duplicates:
            raise SystemExit(f"分片重复 key：{sorted(duplicates)[:5]}")
        combined.update(data)

    problems = validate(baseline, combined)
    if problems:
        raise SystemExit(f"全量校验失败：{len(problems)} 个问题，例：{problems[:3]}")
    out = work / "translated.json"
    if out.exists():
        shutil.copy2(out, out.with_suffix(".json.bak"))
    out.write_text(json.dumps(combined, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"合并并校验通过：{len(combined)}/{len(baseline)} 条 → {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: merge_parts.py <ios|macos|tdesktop>")
    main(sys.argv[1])
