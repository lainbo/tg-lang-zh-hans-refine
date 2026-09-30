#!/usr/bin/env python3
"""生成当前英文、旧英文、精修译文与最终译文的 HTML 审核报告。

用法: python3 scripts/diff_report.py ios [translated.json] [--update]
"""
from __future__ import annotations
import html
import json
import sys

from _common import platform_dirs


def esc(s):
    if s is None:
        return '<span style="color:#999">—</span>'
    return html.escape(str(s)).replace("\n", "<br>")


def main(platform: str, translated_name: str, update: bool = False) -> None:
    work = platform_dirs(platform)["work"]
    merged = json.loads((work / ("to-translate.json" if update else "merged.json")).read_text(encoding="utf-8"))
    tp = work / translated_name
    translated = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
    mp = work / "translation-memory.json"
    memory = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    up = work / "update.json"
    manifest = json.loads(up.read_text(encoding="utf-8")) if up.exists() else {}
    added = set(manifest.get("added", []))
    changed = set(manifest.get("changed", []))
    reviewed = set(manifest.get("reviewed_existing", []))
    labels = {
        "missing": "尚无译文",
        "added": "新增文案",
        "changed": "英文变化",
        "reviewed": "既有文案审校",
        "other": "其他条目" if manifest else "全量文案",
    }
    rows_by_kind = {kind: [] for kind in labels}

    for key in sorted(merged):
        entry = merged[key]
        t = translated.get(key) or {}
        previous = memory.get(key, {})
        if not isinstance(t.get("final"), str) or (not t["final"] and entry["en"]):
            kind = "missing"
        elif key in added:
            kind = "added"
        elif key in changed:
            kind = "changed"
        elif key in reviewed or update:
            kind = "reviewed"
        else:
            kind = "other"
        previous_en = entry.get("previous_en", previous.get("en"))
        if previous_en == entry["en"]:
            previous_en = None
        row = (
            "<tr>"
            f"<td class='key'>{esc(key)}</td>"
            f"<td>{esc(entry['en'])}</td>"
            f"<td>{esc(previous_en)}</td>"
            f"<td>{esc(previous.get('final'))}</td>"
            f"<td><b>{esc(t.get('final'))}</b></td>"
            f"<td>{esc(t.get('source'))}</td>"
            f"<td>{esc(t.get('note'))}</td>"
            "</tr>"
        )
        rows_by_kind[kind].append(row)

    sections = []
    for kind, label in labels.items():
        rows = rows_by_kind[kind]
        if rows:
            sections.append(
                f"<h2>{label} · {len(rows)} 条</h2>"
                "<table><thead><tr><th>key</th><th>当前英文</th><th>旧英文（变化时）</th>"
                "<th>上一轮精修译文</th><th>最终译文</th><th>来源记录</th><th>审校备注</th>"
                f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
            )
    stats = " · ".join(f"{label} {len(rows_by_kind[kind])}" for kind, label in labels.items() if rows_by_kind[kind])
    html_out = f"""<!doctype html>
<html lang="zh-Hans"><head><meta charset="utf-8"><title>tg-lang-refine · {platform}</title>
<style>
body {{ font-family: -apple-system, sans-serif; font-size: 13px; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; text-align: left; overflow-wrap: anywhere; }}
th {{ background: #f5f5f5; position: sticky; top: 0; }}
td.key {{ font-family: ui-monospace, monospace; color: #555; max-width: 220px; }}
h2 {{ border-bottom: 2px solid #333; padding-bottom: 4px; }}
</style></head>
<body>
<h1>tg-lang-refine 审核报告 · {platform}</h1>
<p>{stats or '本轮没有待审校条目'}</p>
<p>所有本轮条目均须对照当前英文复核。来源记录只用于追溯。</p>
{''.join(sections)}
</body></html>"""

    out = work / ("update-report.html" if update else "report.html")
    out.write_text(html_out, encoding="utf-8")
    print(f"报告 → {out}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: diff_report.py <ios|macos|tdesktop|android> [translated.json] [--update]")
    platform = argv[0]
    name = next((arg for arg in argv[1:] if arg != "--update"), "translated.json")
    main(platform, name, "--update" in argv)
