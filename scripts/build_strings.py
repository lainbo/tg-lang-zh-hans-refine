#!/usr/bin/env python3
"""把 translated.json 打包成最终的 .strings 文件。

用法: python3 scripts/build_strings.py ios [translated.json]
产出 dist/<platform>/zh-Hans-custom.strings。
"""
from __future__ import annotations
import json
import sys

from _common import dump_strings, platform_dirs


def main(platform: str, translated_name: str) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    dist = dirs["dist"]
    dist.mkdir(parents=True, exist_ok=True)

    translated_path = work / translated_name
    if not translated_path.exists():
        raise SystemExit(f"missing {translated_path}")
    translated = json.loads(translated_path.read_text(encoding="utf-8"))

    final: dict[str, str] = {}
    for key, entry in translated.items():
        if isinstance(entry, dict) and isinstance(entry.get("final"), str) and entry["final"]:
            final[key] = entry["final"]

    out = dist / "zh-Hans-custom.strings"
    out.write_text(dump_strings(final), encoding="utf-8")
    print(f"打包 {len(final)} 条 → {out}")
    print("上传方式: translations.telegram.org 自定义语言包页面 → Import")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: build_strings.py <ios|macos|tdesktop> [translated.json]")
    platform = argv[0]
    name = argv[1] if len(argv) > 1 else "translated.json"
    main(platform, name)
