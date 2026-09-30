#!/usr/bin/env python3
"""把 translated.json 打包成对应平台的语言资源文件。

用法: python3 scripts/build_strings.py ios [translated.json]
产出 dist/<platform>/zh-Hans-custom.strings；安卓产出 .xml。
"""
from __future__ import annotations
import json
import sys

from _common import dump_resource, platform_dirs, resource_suffix
from import_from_ai import validate


def main(platform: str, translated_name: str) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    dist = dirs["dist"]
    dist.mkdir(parents=True, exist_ok=True)

    translated_path = work / translated_name
    if not translated_path.exists():
        raise SystemExit(f"missing {translated_path}")
    translated = json.loads(translated_path.read_text(encoding="utf-8"))
    baseline = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    problems = validate(baseline, translated)
    if problems:
        raise SystemExit(f"拒绝打包：{len(problems)} 个校验问题。先运行 import_from_ai.py 查看详情。")
    final = {key: entry["final"] for key, entry in translated.items()}

    out = dist / ("zh-Hans-custom" + resource_suffix(platform))
    out.write_text(dump_resource(final, platform), encoding="utf-8")
    print(f"打包 {len(final)} 条 → {out}")
    print("上传方式: translations.telegram.org 自定义语言包页面 → Import")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: build_strings.py <ios|macos|tdesktop|android> [translated.json]")
    platform = argv[0]
    name = argv[1] if len(argv) > 1 else "translated.json"
    main(platform, name)
