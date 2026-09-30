"""把 iOS 精修译文作为 macOS 的参考源注入。

原理: iOS 和 macOS 共享大量相同英文原文 (同产品同文案), 但 key 空间独立。
以英文原文为对齐维度, 构建 TM {en: final}, 反查 macOS 每个 key 的英文,
命中则输出到 data/macos/raw/ref-ios-refined.strings。

输出仅供按需查阅。采用前须结合 macOS 的 key、功能上下文、参数角色和格式审校。

用法: python3 scripts/seed_ios_ref.py
"""
from __future__ import annotations
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _common import ROOT, platform_dirs, dump_strings


def main() -> None:
    ios = platform_dirs("ios")
    mac = platform_dirs("macos")

    ios_en_path = ios["parsed"] / "en.json"
    ios_translated_path = ios["work"] / "translated.json"
    mac_en_path = mac["parsed"] / "en.json"

    for p in (ios_en_path, ios_translated_path, mac_en_path):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    ios_en = json.loads(ios_en_path.read_text(encoding="utf-8"))
    ios_translated = json.loads(ios_translated_path.read_text(encoding="utf-8"))
    mac_en = json.loads(mac_en_path.read_text(encoding="utf-8"))

    # TM: 英文原文 -> 精修中文。同一英文在 iOS 多个 key 出现时, 取首个 (字母序)。
    tm: dict[str, str] = {}
    for key in sorted(ios_translated.keys()):
        en = ios_en.get(key)
        entry = ios_translated[key]
        if not en or not isinstance(entry, dict):
            continue
        final = entry.get("final")
        if final and en not in tm:
            tm[en] = final

    # macOS key -> 精修中文 (命中 TM 才输出)
    ref: dict[str, str] = {}
    for key, en in mac_en.items():
        if en in tm:
            ref[key] = tm[en]

    out_path = mac["raw"] / "ref-ios-refined.strings"
    out_path.write_text(dump_strings(ref), encoding="utf-8")

    total = len(mac_en)
    hit = len(ref)
    print(f"  TM 规模 (去重英文)       : {len(tm)}")
    print(f"  macOS 总 key             : {total}")
    print(f"  命中 iOS 精修 (可复用)   : {hit} ({hit/total:.1%})")
    print(f"  缺口 (需 AI 新翻)        : {total - hit}")
    print(f"  输出                     : {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
