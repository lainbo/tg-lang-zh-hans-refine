#!/usr/bin/env python3
"""扫描 data/<platform>/raw/*.strings, 逐个解析为 parsed/<name>.json。

用法: python3 scripts/parse_strings.py ios
"""
from __future__ import annotations
import json
import sys

from _common import parse_strings, platform_dirs


def main(platform: str) -> None:
    dirs = platform_dirs(platform)
    raw = dirs["raw"]
    parsed = dirs["parsed"]
    parsed.mkdir(parents=True, exist_ok=True)

    files = sorted(raw.glob("*.strings"))
    if not files:
        raise SystemExit(f"no .strings files under {raw}. 先把源文件放进来, 见 docs/SOURCES.md")

    for f in files:
        data = parse_strings(f.read_text(encoding="utf-8"))
        out = parsed / (f.stem + ".json")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"  {f.name:30s} → {out.relative_to(dirs['raw'].parent.parent.parent)}  ({len(data)} keys)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: parse_strings.py <ios|macos|tdesktop>")
    main(sys.argv[1])
