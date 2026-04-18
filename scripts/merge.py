#!/usr/bin/env python3
"""按 en baseline 对齐多源翻译, 输出 work/<platform>/merged.json。

识别规则 (data/<platform>/parsed/):
  en.json               → baseline (必需)
  official-zh.json      → 官方简中 (可选)
  zhcncc.json           → @zhcncc 参考包 (可选)
  ref-*.json            → 额外参考源, 任意多个 (可选)

用法: python3 scripts/merge.py ios
"""
from __future__ import annotations
import json
import sys

from _common import platform_dirs


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main(platform: str) -> None:
    dirs = platform_dirs(platform)
    parsed = dirs["parsed"]
    work = dirs["work"]
    work.mkdir(parents=True, exist_ok=True)

    en = load_json(parsed / "en.json")
    if en is None:
        raise SystemExit(f"missing {parsed/'en.json'}. 先跑 parse_strings.py")

    official_zh = load_json(parsed / "official-zh.json") or {}

    # 收集参考源: zhcncc.json 和所有 ref-*.json
    refs: dict[str, dict] = {}
    for f in sorted(parsed.glob("*.json")):
        if f.name in ("en.json", "official-zh.json"):
            continue
        name = f.stem.removeprefix("ref-") if f.stem.startswith("ref-") else f.stem
        refs[name] = load_json(f)

    merged: dict[str, dict] = {}
    for key, en_val in en.items():
        entry: dict = {"en": en_val}
        if key in official_zh:
            entry["official_zh"] = official_zh[key]
        ref_entry: dict[str, str] = {}
        for name, data in refs.items():
            if key in data:
                ref_entry[name] = data[key]
        if ref_entry:
            entry["refs"] = ref_entry
        merged[key] = entry

    out = work / "merged.json"
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # 统计
    total = len(merged)
    has_official = sum(1 for v in merged.values() if "official_zh" in v)
    per_ref = {name: sum(1 for v in merged.values() if "refs" in v and name in v["refs"]) for name in refs}
    print(f"merged: {total} keys → {out.relative_to(dirs['raw'].parent.parent.parent)}")
    print(f"  官方简中覆盖: {has_official}/{total}")
    for name, n in per_ref.items():
        print(f"  {name:20s} 覆盖: {n}/{total}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: merge.py <ios|macos>")
    main(sys.argv[1])
