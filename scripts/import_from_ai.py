#!/usr/bin/env python3
"""导入并校验翻译 AI 回传结果（支持紧凑回传展开、二审差量补丁幂等应用与全量/单片标准校验）。

检查项:
1. 紧凑协议完整性: 短编号覆盖、候选引用 (= / =N / =prev)、同英文组按 key 覆写与数组结构合法
2. 标准结构完整: 每个原始 key 有 {final, source, note?}, source 合法
3. 占位符一致性: 数量、写法及无编号百分号参数次序与当前英文完全一致
4. key 覆盖: 覆盖基准的所有原始 key（含展开后的全部复数分支），无缺失或多余

用法:
  python3 scripts/import_from_ai.py ios                            # 校验 translated.json 对全量 merged.json
  python3 scripts/import_from_ai.py ios --part 1                   # 展开 reply.part01.json (若存在) 并校验 part01
  python3 scripts/import_from_ai.py ios --part 1 custom.json       # 指定任意紧凑或标准回传文件
  python3 scripts/import_from_ai.py ios --review                   # 基于初译快照幂等应用 review-patch.part*.json 并复检
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil

from _common import PLATFORMS, placeholder_issue, placeholders, platform_dirs

VALID_SOURCES = {"adopt", "rewrite_ref", "rewrite_official", "fresh"}
_REF_RE = re.compile(r"^=(?:(\d+)|prev)?$")


def validate(merged: dict, translated: dict) -> list[dict]:
    if not isinstance(translated, dict):
        return [{"key": "", "issue": "top_level_not_object"}]
    problems: list[dict] = []
    for k in sorted(merged.keys() - translated.keys()):
        problems.append({"key": k, "issue": "missing_in_translated"})
    for k in sorted(translated.keys() - merged.keys()):
        problems.append({"key": k, "issue": "extra_key_not_in_merged"})

    for key, entry in translated.items():
        if key not in merged:
            continue
        if not isinstance(entry, dict):
            problems.append({"key": key, "issue": "not_object"})
            continue
        final = entry.get("final")
        source = entry.get("source")
        en = merged[key]["en"]
        if not isinstance(final, str) or (not final and en):
            problems.append({"key": key, "issue": "missing_final"})
            continue
        if not isinstance(source, str) or source not in VALID_SOURCES:
            problems.append({"key": key, "issue": f"invalid_source:{source}"})
        if "note" in entry and not isinstance(entry["note"], str):
            problems.append({"key": key, "issue": "invalid_note"})
        issue = placeholder_issue(en, final)
        if issue == "placeholder_mismatch":
            problems.append({
                "key": key,
                "issue": issue,
                "en_placeholders": placeholders(en),
                "zh_placeholders": placeholders(final),
                "en": en,
                "final": final,
            })
        elif issue:
            problems.append({"key": key, "issue": issue})
    return problems


def _parse_compact_scalar(raw, item: dict, cid: str, key: str) -> tuple[dict | None, dict | None]:
    if isinstance(raw, str):
        m = _REF_RE.match(raw)
        if m:
            if raw == "=prev":
                if "previous_zh" not in item:
                    return None, {"key": key, "compact_id": cid, "issue": "invalid_candidate_ref:=prev"}
                return {
                    "final": item["previous_zh"],
                    "source": "adopt",
                    "note": "adopt:translation-memory",
                }, None
            idx = int(m.group(1)) if m.group(1) is not None else 0
            candidates = item.get("candidates") or []
            if idx >= len(candidates):
                return None, {"key": key, "compact_id": cid, "issue": f"invalid_candidate_ref:{raw}"}
            chosen = candidates[idx]
            return {
                "final": chosen["zh"],
                "source": "adopt",
                "note": f"adopt:{chosen['from']}",
            }, None
        return {"final": raw, "source": "fresh"}, None

    if isinstance(raw, list) and 2 <= len(raw) <= 3 and all(isinstance(x, str) for x in raw):
        entry = {"final": raw[0], "source": raw[1]}
        if len(raw) == 3 and raw[2]:
            entry["note"] = raw[2]
        return entry, None

    return None, {"key": key, "compact_id": cid, "issue": "invalid_compact_entry"}


def _item_members(item: dict) -> list[dict]:
    if "members" in item:
        return item["members"]
    rep_key = item["key"]
    return [{"key": rep_key, "keys": item.get("plural_keys") or [rep_key]}]


def expand_compact(compact_meta: dict, reply: dict) -> tuple[dict, list[dict]]:
    if not isinstance(reply, dict):
        return {}, [{"key": "", "issue": "top_level_not_object"}]
    items: dict[str, dict] = compact_meta.get("items", {})
    problems: list[dict] = []
    for cid in sorted(items.keys() - reply.keys()):
        rep_key = _item_members(items[cid])[0]["key"]
        problems.append({"key": rep_key, "compact_id": cid, "issue": "missing_compact_id"})
    for cid in sorted(reply.keys() - items.keys()):
        problems.append({"key": str(cid), "compact_id": str(cid), "issue": "extra_compact_id"})

    expanded: dict[str, dict] = {}
    for cid, item in items.items():
        if cid not in reply:
            continue
        members = _item_members(item)
        raw = reply[cid]
        if isinstance(raw, dict):
            valid_member_keys = {m["key"] for m in members}
            for k in sorted(raw.keys()):
                if k != "*" and k not in valid_member_keys:
                    problems.append({"key": str(k), "compact_id": cid, "issue": "unknown_group_key"})
            for m in members:
                rep_key = m["key"]
                if rep_key in raw:
                    sub_raw = raw[rep_key]
                elif "*" in raw:
                    sub_raw = raw["*"]
                else:
                    problems.append({"key": rep_key, "compact_id": cid, "issue": "missing_group_key"})
                    continue
                entry, err = _parse_compact_scalar(sub_raw, item, cid, rep_key)
                if err:
                    problems.append(err)
                    continue
                for orig_k in m["keys"]:
                    expanded[orig_k] = dict(entry)
        else:
            entry, err = _parse_compact_scalar(raw, item, cid, members[0]["key"])
            if err:
                problems.append(err)
                continue
            for m in members:
                for orig_k in m["keys"]:
                    expanded[orig_k] = dict(entry)
    return expanded, problems


def resolve_part_suffix(work: Path, part: int) -> str:
    for p in sorted(work.glob("to-translate.part*.json")):
        stem_part = p.stem.removeprefix("to-translate.part")
        if stem_part.isdigit() and int(stem_part) == part:
            return f".part{stem_part}"
    return f".part{part:02d}"


def _write_validation(out: Path, root: Path, total_merged: int, total_translated: int, problems: list[dict]) -> None:
    report = {
        "total_merged": total_merged,
        "total_translated": total_translated,
        "problem_count": len(problems),
        "problems": problems,
    }
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_issue: dict[str, int] = {}
    for p in problems:
        issue = p["issue"].split(":")[0]
        by_issue[issue] = by_issue.get(issue, 0) + 1
    print(f"翻译覆盖: {total_translated}/{total_merged}")
    print(f"问题总数: {len(problems)}")
    for issue, n in sorted(by_issue.items(), key=lambda x: -x[1]):
        print(f"  {issue:30s} {n}")
    print(f"\n详细清单 → {out.relative_to(root)}")
    if not problems:
        print("\n✅ 校验通过")
    else:
        print("\n⚠️  有问题, 修好后重跑本脚本")
        raise SystemExit(1)


def _parse_review_scalar(val, old_entry: dict, fname: str, rid: str, rep_key: str) -> tuple[dict | None, dict | None]:
    if isinstance(val, str):
        old_source = old_entry.get("source", "fresh")
        new_source = "rewrite_ref" if old_source == "adopt" else old_source
        new_entry: dict = {"final": val, "source": new_source}
        old_note = old_entry.get("note")
        if old_note:
            if old_source == "adopt" and old_note.startswith("adopt:"):
                new_entry["note"] = "rewrite:" + old_note.removeprefix("adopt:")
            else:
                new_entry["note"] = old_note
        return new_entry, None
    if isinstance(val, list) and 2 <= len(val) <= 3 and all(isinstance(x, str) for x in val):
        if val[1] not in VALID_SOURCES:
            return None, {"file": fname, "review_id": rid, "key": rep_key, "issue": f"invalid_source:{val[1]}"}
        new_entry = {"final": val[0], "source": val[1]}
        if len(val) == 3 and val[2]:
            new_entry["note"] = val[2]
        return new_entry, None
    return None, {"file": fname, "review_id": rid, "key": rep_key, "issue": "invalid_review_patch_entry"}


def _review_targets(info: dict) -> list[dict]:
    if "targets" in info:
        return info["targets"]
    return [{"part_file": info["part_file"], "rep_key": info["keys"][0], "keys": info["keys"]}]


def apply_review(platform: str) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    root = dirs["raw"].parent.parent.parent
    plan_path = work / "review-plan.json"
    if not plan_path.exists():
        raise SystemExit(f"缺少 {plan_path.relative_to(root)}。请先运行: python3 scripts/export_for_ai.py {platform} --review")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    review_files = [work / name for name in plan.get("review_parts", [])]
    if not review_files:
        review_files = sorted(
            p for p in work.glob("review.part*.json") if not p.name.endswith(".meta.json")
        )
    missing_patches = [
        rf.name.replace("review.", "review-patch.")
        for rf in review_files
        if not (work / rf.name.replace("review.", "review-patch.")).exists()
    ]
    if missing_patches:
        raise SystemExit(f"缺少二审补丁文件: {missing_patches}")

    parts_covered = plan.get("parts_covered") or sorted(p.name for p in work.glob("translated.part*.json"))
    part_cache: dict[str, dict] = {}
    for part_file in parts_covered:
        trans_path = work / part_file
        draft_path = work / part_file.replace("translated.", "translated-draft.")
        if not draft_path.exists():
            shutil.copy2(trans_path, draft_path)
        part_cache[part_file] = json.loads(draft_path.read_text(encoding="utf-8"))

    problems: list[dict] = []
    applied_patches: list[dict] = []

    for rf in review_files:
        meta_path = work / rf.name.replace(".json", ".meta.json")
        src_path = meta_path if meta_path.exists() else rf
        rdata = json.loads(src_path.read_text(encoding="utf-8"))
        items: dict[str, dict] = rdata.get("items", {})
        pf = work / rf.name.replace("review.", "review-patch.")
        pdata = json.loads(pf.read_text(encoding="utf-8"))
        if not isinstance(pdata, dict):
            problems.append({"file": pf.name, "issue": "top_level_not_object"})
            continue

        for rid, val in pdata.items():
            if rid not in items:
                problems.append({"file": pf.name, "review_id": str(rid), "issue": "unknown_review_id"})
                continue
            info = items[rid]
            targets = _review_targets(info)
            if isinstance(val, dict):
                valid_rep_keys = {t["rep_key"] for t in targets}
                for k in sorted(val.keys()):
                    if k != "*" and k not in valid_rep_keys:
                        problems.append({"file": pf.name, "review_id": rid, "key": str(k), "issue": "unknown_group_key"})
                for t in targets:
                    rep_key = t["rep_key"]
                    if rep_key in val:
                        sub_val = val[rep_key]
                    elif "*" in val:
                        sub_val = val["*"]
                    else:
                        continue
                    part_file = t["part_file"]
                    if part_file not in part_cache:
                        draft_path = work / part_file.replace("translated.", "translated-draft.")
                        if not draft_path.exists():
                            shutil.copy2(work / part_file, draft_path)
                        part_cache[part_file] = json.loads(draft_path.read_text(encoding="utf-8"))
                    target_dict = part_cache[part_file]
                    old_entry = target_dict.get(rep_key, {})
                    new_entry, err = _parse_review_scalar(sub_val, old_entry, pf.name, rid, rep_key)
                    if err:
                        problems.append(err)
                        continue
                    for k in t["keys"]:
                        target_dict[k] = dict(new_entry)
                    applied_patches.append({
                        "review_id": rid,
                        "keys": t["keys"],
                        "before": old_entry.get("final"),
                        "after": new_entry["final"],
                        "source": new_entry["source"],
                        **({"note": new_entry["note"]} if "note" in new_entry else {}),
                    })
            else:
                for t in targets:
                    part_file = t["part_file"]
                    if part_file not in part_cache:
                        draft_path = work / part_file.replace("translated.", "translated-draft.")
                        if not draft_path.exists():
                            shutil.copy2(work / part_file, draft_path)
                        part_cache[part_file] = json.loads(draft_path.read_text(encoding="utf-8"))
                    target_dict = part_cache[part_file]
                    rep_key = t["rep_key"]
                    old_entry = target_dict.get(rep_key, {})
                    new_entry, err = _parse_review_scalar(val, old_entry, pf.name, rid, rep_key)
                    if err:
                        problems.append(err)
                        continue
                    for k in t["keys"]:
                        target_dict[k] = dict(new_entry)
                    applied_patches.append({
                        "review_id": rid,
                        "keys": t["keys"],
                        "before": old_entry.get("final"),
                        "after": new_entry["final"],
                        "source": new_entry["source"],
                        **({"note": new_entry["note"]} if "note" in new_entry else {}),
                    })

    if problems:
        print(f"二审补丁格式错误 ({len(problems)} 项): {problems[:5]}")
        raise SystemExit(1)

    # 全量校验所有覆盖分片，全部通过后再落盘（保证失败不留半成品、删补丁可完整回退）
    for part_file in sorted(part_cache):
        baseline_file = work / part_file.replace("translated.", "to-translate.")
        part_baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        part_problems = validate(part_baseline, part_cache[part_file])
        if part_problems:
            print(f"二审补丁导致 {part_file} 校验失败 ({len(part_problems)} 项): {part_problems[:5]}")
            raise SystemExit(1)

    for part_file in sorted(part_cache):
        rendered = json.dumps(part_cache[part_file], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        out_path = work / part_file
        if not out_path.exists() or out_path.read_text(encoding="utf-8") != rendered:
            out_path.write_text(rendered, encoding="utf-8")
            val_file = work / part_file.replace("translated.", "validation.")
            total = len(part_cache[part_file])
            val_file.write_text(
                json.dumps({"total_merged": total, "total_translated": total, "problem_count": 0, "problems": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    summary = {
        "platform": platform,
        "total_keys": plan["total_keys"],
        "member_units": plan.get("member_units", plan.get("compact_units", 0)),
        "skipped_fast_adopt": plan["skipped_fast_adopt"],
        "reviewed_units": plan["reviewed_units"],
        "flagged_units": plan.get("flagged_units", 0),
        "patched_units": len(applied_patches),
        "patches": applied_patches,
    }
    summary_path = work / "review-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"二审复核完成：复核 {plan['reviewed_units']} 组（免二审精确复用 {plan['skipped_fast_adopt']} 组），"
        f"应用修正 {len(applied_patches)} 处 → {summary_path.relative_to(root)}"
    )


def main(platform: str, translated_name: str | None, part: int | None, review: bool = False) -> None:
    if review:
        apply_review(platform)
        return

    dirs = platform_dirs(platform)
    work = dirs["work"]
    root = dirs["raw"].parent.parent.parent

    if part is None:
        baseline = json.loads((work / "merged.json").read_text(encoding="utf-8"))
        target_path = work / (translated_name or "translated.json")
        translated = json.loads(target_path.read_text(encoding="utf-8"))
        problems = validate(baseline, translated)
        _write_validation(work / "validation.json", root, len(baseline), len(translated), problems)
        return

    suffix = resolve_part_suffix(work, part)
    baseline = json.loads((work / f"to-translate{suffix}.json").read_text(encoding="utf-8"))
    compact_meta_path = work / f"compact{suffix}.meta.json"
    compact_path = work / f"compact{suffix}.json"
    reply_path = work / f"reply{suffix}.json"
    out_translated = work / f"translated{suffix}.json"
    val_out = work / f"validation{suffix}.json"

    meta_source = compact_meta_path if compact_meta_path.exists() else compact_path
    use_compact = False
    if translated_name:
        input_path = Path(translated_name) if Path(translated_name).is_absolute() else work / translated_name
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if meta_source.exists():
            compact_meta = json.loads(meta_source.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and (input_path.name.startswith("reply.") or not (payload.keys() & baseline.keys())):
                use_compact = True
    elif meta_source.exists() and reply_path.exists():
        compact_meta = json.loads(meta_source.read_text(encoding="utf-8"))
        payload = json.loads(reply_path.read_text(encoding="utf-8"))
        use_compact = True
    else:
        payload = json.loads(out_translated.read_text(encoding="utf-8"))

    if use_compact:
        expanded, compact_problems = expand_compact(compact_meta, payload)
        if compact_problems:
            _write_validation(val_out, root, len(baseline), len(expanded), compact_problems)
            return
        out_translated.write_text(
            json.dumps(expanded, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # 重导初译分片时清理旧的二审快照与二审凭据，强制后续重新二审
        draft_path = work / f"translated-draft{suffix}.json"
        if draft_path.exists():
            draft_path.unlink()
        summary_path = work / "review-summary.json"
        if summary_path.exists():
            summary_path.unlink()
        print(f"已展开紧凑回传 → {out_translated.relative_to(root)} ({len(expanded)} keys)")
        translated = expanded
    else:
        translated = payload

    problems = validate(baseline, translated)
    _write_validation(val_out, root, len(baseline), len(translated), problems)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("translated_file", nargs="?", default=None)
    parser.add_argument("--part", type=int, default=None)
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    main(args.platform, args.translated_file, args.part, args.review)
