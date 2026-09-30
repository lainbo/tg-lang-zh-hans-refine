#!/usr/bin/env python3
"""从 parsed/en.json 建立当前英文基准，输出 work/<platform>/merged.json。

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

    merged = {key: {"en": value} for key, value in en.items()}

    out = work / "merged.json"
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(f"英文基准: {len(merged)} keys → {out.relative_to(dirs['raw'].parent.parent.parent)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: merge.py <ios|macos|tdesktop|android>")
    main(sys.argv[1])
