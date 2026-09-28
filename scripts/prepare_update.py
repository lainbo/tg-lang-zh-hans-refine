#!/usr/bin/env python3
"""归档当前成果，安装已下载的官方源，只导出需要审校的增量。"""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

from _common import parse_strings, platform_dirs
from export_for_ai import main as export
from import_from_ai import validate
from merge import main as merge
from parse_strings import main as parse


def main(platform: str, en_path: Path, chunk: int) -> None:
    if chunk <= 0:
        raise SystemExit("--chunk 必须为正整数")
    dirs = platform_dirs(platform)
    work = dirs["work"]
    old = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    translated = json.loads((work / "translated.json").read_text(encoding="utf-8"))
    problems = validate(old, translated)
    if problems:
        raise SystemExit(f"当前译文有 {len(problems)} 个问题，请先修复再开始新一轮。")
    en_path = en_path.resolve()
    content = en_path.read_bytes()
    text = content.decode("utf-8-sig")
    incoming = parse_strings(text)
    if not incoming:
        raise SystemExit("下载文件为空或无法解析为 .strings。")
    if len(incoming.keys() & old.keys()) < len(old) / 2:
        raise SystemExit("新旧英文 key 重合不足一半，请检查下载的平台。")

    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d-%H%M%S-%f")
    archive = work / "history" / stamp
    archive.mkdir(parents=True)
    for name in ("raw", "parsed", "dist"):
        shutil.copytree(dirs[name], archive / name)
    (archive / "work").mkdir()
    for path in list(work.iterdir()):
        if path.is_file() and path.name != ".gitkeep":
            shutil.move(str(path), archive / "work" / path.name)

    (dirs["raw"] / "en.strings").write_text(text, encoding="utf-8")
    parse(platform)
    merge(platform)
    baseline = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    added = sorted(baseline.keys() - old.keys())
    removed = sorted(old.keys() - baseline.keys())
    changed = sorted(k for k in baseline.keys() & old.keys() if baseline[k]["en"] != old[k]["en"])
    review_keys = set(added + changed)
    review = {k: dict(baseline[k]) for k in sorted(review_keys)}
    for key in changed:
        review[key]["previous_en"] = old[key]["en"]
    reused = {k: translated[k] for k in sorted(baseline.keys() - review_keys)}
    memory = {k: {"en": old[k]["en"], "final": translated[k]["final"]} for k in sorted(old)}
    manifest = {
        "platform": platform,
        "created_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "archive": str(archive.relative_to(work)),
        "sources": {"en": {"filename": en_path.name, "sha256": hashlib.sha256(content).hexdigest()}},
        "previous_total": len(old), "total": len(baseline),
        "added": added, "changed": changed, "removed": removed, "reused_count": len(reused),
    }
    for name, data in (("update.json", manifest), ("translated.reused.json", reused),
                       ("translation-memory.json", memory)):
        (work / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    export(platform, chunk, review)
    print(f"新增 {len(added)}，原文变化 {len(changed)}，移除 {len(removed)}，复用 {len(reused)}。")
    print(f"上一轮完整备份 → {archive}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("ios", "tdesktop"))
    parser.add_argument("--en", type=Path, required=True)
    parser.add_argument("--chunk", type=int, default=100)
    args = parser.parse_args()
    main(args.platform, args.en, args.chunk)
