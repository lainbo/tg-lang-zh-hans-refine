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
    pending_key_count = 0
    for part in inputs:
        data = json.loads((work / part.name.replace("to-translate", "translated")).read_text(encoding="utf-8"))
        part_baseline = json.loads(part.read_text(encoding="utf-8"))
        pending_key_count += len(part_baseline)
        problems = validate(part_baseline, data)
        if problems:
            raise SystemExit(f"{part.name}：{len(problems)} 个校验问题，合并已停止。")
        duplicates = combined.keys() & data.keys()
        if duplicates:
            raise SystemExit(f"分片重复 key：{sorted(duplicates)[:5]}")
        combined.update(data)

    # 只要本轮有待审校分片且通过分层紧凑导出（含 --repack 全完成场景），合并前强制校验二审完成状态与时效
    need_review_gate = bool(inputs) and (
        (work / "compact-manifest.json").exists()
        or (work / "review-plan.json").exists()
        or bool(list(work.glob("compact.part*.json")))
    )
    if need_review_gate:
        summary_path = work / "review-summary.json"
        if not summary_path.exists():
            raise SystemExit(
                f"尚未完成差量二审。请先运行 export_for_ai.py {platform} --review，"
                f"完成复核补丁后再运行 import_from_ai.py {platform} --review。"
            )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("total_keys") != pending_key_count:
            raise SystemExit(
                f"二审统计 key 数（{summary.get('total_keys')}）与当前分片总数（{pending_key_count}）不一致，"
                f"请重新运行 export_for_ai.py {platform} --review。"
            )
        summary_mtime_ns = summary_path.stat().st_mtime_ns
        if any(p.stat().st_mtime_ns > summary_mtime_ns for p in work.glob("review-patch.part*.json")):
            raise SystemExit(f"检测到二审补丁有新修改，请先重跑 python3 scripts/import_from_ai.py {platform} --review。")
        stale_inputs = [
            p.name
            for pat in ("translated.part*.json", "reply.part*.json")
            for p in work.glob(pat)
            if p.stat().st_mtime_ns > summary_mtime_ns
        ]
        if stale_inputs:
            raise SystemExit(
                f"检测到初译文件在二审后被修改（{sorted(stale_inputs)[:5]}），"
                f"请先重跑 export_for_ai.py {platform} --review 完成二审。"
            )

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
        raise SystemExit("usage: merge_parts.py <ios|macos|tdesktop|android>")
    main(sys.argv[1])
