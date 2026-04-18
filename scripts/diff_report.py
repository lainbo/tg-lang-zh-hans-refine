#!/usr/bin/env python3
"""生成 HTML 审核报告。

左列 key, 然后依次列: en | official_zh | refs.* | final (AI 产出) | source 标签。
按 source 分组, 重点展示 rewrite_*/fresh, 便于人工扫视。

用法: python3 scripts/diff_report.py ios [translated.json]
产出 work/<platform>/report.html
"""
from __future__ import annotations
import html
import json
import sys

from _common import platform_dirs

SOURCE_COLOR = {
    "adopt": "#d4f4dd",              # 绿, 直接采用, 低优先级
    "rewrite_ref": "#fff3b0",        # 黄, 微调
    "rewrite_official": "#ffd6a5",   # 橙, 改写官方
    "fresh": "#ffadad",              # 红, 全部重写, 最高优先级
    "missing": "#cccccc",
}


def esc(s):
    if s is None:
        return '<span style="color:#999">—</span>'
    return html.escape(str(s)).replace("\n", "<br>")


def main(platform: str, translated_name: str) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    merged = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    tp = work / translated_name
    translated = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}

    # 收集所有 ref 名字
    ref_names = set()
    for v in merged.values():
        ref_names.update((v.get("refs") or {}).keys())
    ref_names = sorted(ref_names)

    rows_by_source: dict[str, list[str]] = {k: [] for k in ("fresh", "rewrite_official", "rewrite_ref", "adopt", "missing")}

    for key in sorted(merged.keys()):
        entry = merged[key]
        t = translated.get(key) or {}
        source = t.get("source") if t else "missing"
        final = t.get("final")
        note = t.get("note") or ""

        refs_html = "".join(
            f"<td>{esc((entry.get('refs') or {}).get(n))}</td>" for n in ref_names
        )
        bg = SOURCE_COLOR.get(source, "#eee")
        row = (
            f'<tr style="background:{bg}">'
            f"<td class='key'>{esc(key)}</td>"
            f"<td>{esc(entry.get('en'))}</td>"
            f"<td>{esc(entry.get('official_zh'))}</td>"
            f"{refs_html}"
            f"<td><b>{esc(final)}</b></td>"
            f"<td>{esc(source)}</td>"
            f"<td>{esc(note)}</td>"
            f"</tr>"
        )
        rows_by_source.setdefault(source, []).append(row)

    head_refs = "".join(f"<th>{esc(n)}</th>" for n in ref_names)
    sections = []
    order = ["fresh", "rewrite_official", "rewrite_ref", "adopt", "missing"]
    labels = {
        "fresh": "🔴 重新翻译 (fresh) — 最高优先级",
        "rewrite_official": "🟠 改写官方版 (rewrite_official)",
        "rewrite_ref": "🟡 微调参考包 (rewrite_ref)",
        "adopt": "🟢 直接采用 (adopt) — 扫一眼即可",
        "missing": "⚫ 未处理 (missing/unknown)",
    }
    for s in order:
        rows = rows_by_source.get(s, [])
        if not rows:
            continue
        sections.append(
            f"<h2>{labels.get(s, s)} · {len(rows)} 条</h2>"
            f"<table><thead><tr>"
            f"<th>key</th><th>en</th><th>official_zh</th>{head_refs}"
            f"<th>final</th><th>source</th><th>note</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )

    stats = " · ".join(f"{labels.get(s, s).split(' ')[0]} {len(rows_by_source.get(s, []))}" for s in order)
    html_out = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>tg-lang-refine · {platform}</title>
<style>
body {{ font-family: -apple-system, sans-serif; font-size: 13px; margin: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 32px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; text-align: left; }}
th {{ background: #f5f5f5; position: sticky; top: 0; }}
td.key {{ font-family: ui-monospace, monospace; color: #555; max-width: 260px; word-break: break-all; }}
h2 {{ border-bottom: 2px solid #333; padding-bottom: 4px; }}
</style></head>
<body>
<h1>tg-lang-refine 审核报告 · {platform}</h1>
<p>{stats}</p>
{''.join(sections)}
</body></html>"""

    out = work / "report.html"
    out.write_text(html_out, encoding="utf-8")
    print(f"报告 → {out}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit("usage: diff_report.py <ios|macos> [translated.json]")
    platform = argv[0]
    name = argv[1] if len(argv) > 1 else "translated.json"
    main(platform, name)
