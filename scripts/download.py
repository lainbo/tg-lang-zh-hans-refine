#!/usr/bin/env python3
"""从 translations.telegram.org 下载语言包导出文件到系统下载目录。

用法: python3 scripts/download.py ios [android macos tdesktop] [--lang en]
默认下载官方英文，文件名保留网站给出的版本号，可直接传给 prepare_update.py --en。
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from _common import PLATFORMS, fetch_export, parse_resource, platform_dirs

DOWNLOADS = Path.home() / "Downloads"


def main(platforms: list[str], lang: str) -> None:
    for platform in platforms:
        name, content = fetch_export(lang, platform)
        if not parse_resource(content.decode("utf-8-sig"), platform):
            raise SystemExit(f"{name} 为空或无法按 {platform} 格式解析。")
        path = DOWNLOADS / name
        path.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        print(f"{platform}: {path}  SHA-256 {sha}")
        manifest = platform_dirs(platform)["work"] / "update.json"
        if lang == "en" and manifest.exists():
            previous = json.loads(manifest.read_text(encoding="utf-8"))["sources"]["en"]
            if previous["sha256"] == sha:
                print(f"  与上一轮英文 {previous['filename']} 相同，无需更新。")
            else:
                print(f"  上一轮英文为 {previous['filename']}，运行 prepare_update.py {platform} --en {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("platforms", nargs="+", choices=PLATFORMS)
    parser.add_argument("--lang", default="en", help="语言包标识，默认 en；官方简中为 zh-hans")
    args = parser.parse_args()
    main(args.platforms, args.lang)
