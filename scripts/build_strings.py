#!/usr/bin/env python3
"""把 translated.json 打包成对应平台的语言资源文件。

用法: python3 scripts/build_strings.py ios [translated.json]
产出完整成品 dist/<platform>/zh-Hans-custom.strings，以及只含中文复数分支的
上传文件 zh-Hans-custom.upload.strings；安卓均为 .xml。
"""
from __future__ import annotations
import json
import sys

from _common import PLURAL_SUFFIXES, dump_resource, platform_dirs, resource_suffix
from import_from_ai import validate

# 网站上的简中语言包每个复数词条只启用一个分支；上传文件含其余分支时，导入会清空已启用分支的线上译文。
UPLOAD_PLURAL = PLURAL_SUFFIXES
# 网页按复数词条编辑这个 key，同名的无后缀旧句与之冲突。
UPLOAD_EXCLUDE = {"macos": {"Star.Auction.Preview.TopBidders"}}


def upload_entries(final: dict[str, str], platform: str) -> dict[str, str]:
    used, unused = UPLOAD_PLURAL[platform]
    exclude = UPLOAD_EXCLUDE.get(platform, set())

    def keep(key: str) -> bool:
        suffix = next((s for s in unused if key.endswith(s)), None)
        return key not in exclude and (suffix is None or key.removesuffix(suffix) + used not in final)

    return {key: value for key, value in final.items() if keep(key)}


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

    suffix = resource_suffix(platform)
    out = dist / f"zh-Hans-custom{suffix}"
    out.write_text(dump_resource(final, platform), encoding="utf-8")
    upload = upload_entries(final, platform)
    upload_out = dist / f"zh-Hans-custom.upload{suffix}"
    upload_out.write_text(dump_resource(upload, platform), encoding="utf-8")
    print(f"打包 {len(final)} 条 → {out}")
    print(f"上传文件 {len(upload)} 条 → {upload_out}")
    print(f"上传: python3 scripts/upload.py {platform}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: build_strings.py <ios|macos|tdesktop|android> [translated.json]")
    platform = argv[0]
    name = argv[1] if len(argv) > 1 else "translated.json"
    main(platform, name)
