#!/usr/bin/env python3
"""扫描 data/<platform>/raw/ 中的平台资源文件, 逐个解析为 parsed/<name>.json。

用法: python3 scripts/parse_strings.py ios
"""
from __future__ import annotations
import json
import sys

from _common import parse_resource, platform_dirs, resource_suffix


def main(platform: str) -> None:
    dirs = platform_dirs(platform)
    raw = dirs["raw"]
    parsed = dirs["parsed"]
    parsed.mkdir(parents=True, exist_ok=True)

    files = sorted(raw.glob("*" + resource_suffix(platform)))
    if not files:
        raise SystemExit(f"no {resource_suffix(platform)} files under {raw}. 先把源文件放进来, 见 docs/SOURCES.md")

    for f in files:
        data = parse_resource(f.read_text(encoding="utf-8-sig"), platform)
        out = parsed / (f.stem + ".json")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"  {f.name:30s} → {out.relative_to(dirs['raw'].parent.parent.parent)}  ({len(data)} keys)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: parse_strings.py <ios|macos|tdesktop|android>")
    main(sys.argv[1])
