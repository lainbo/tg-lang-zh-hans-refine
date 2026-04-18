"""把 dist/<p>/zh-Hans-custom.strings 按字母序切成 N 份, 便于二分定位 Telegram 平台拒收的 key。

用法:
    python3 scripts/split_strings.py macos --chunk 500
    # 产物: dist/macos/splits/part01.strings ... partNN.strings

二分建议:
    1. 依次上传每份 .strings → Import phrases → Edit Phrases
    2. 成功的进下一份, 失败的记下序号
    3. 失败份再切细 (--chunk 100 / --chunk 20) 继续缩小范围
    4. 定位到具体 key 后, 从 translated.json 里删掉那条 (或改 key 名) 再重新 build
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, platform_dirs, dump_strings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform", choices=("ios", "macos", "tdesktop"))
    ap.add_argument("--chunk", type=int, default=500, help="每份 key 数量上限 (默认 500)")
    ap.add_argument("--source", default=None, help="可选, 指定 translated.json 路径")
    args = ap.parse_args()

    dirs = platform_dirs(args.platform)
    src_path = Path(args.source) if args.source else dirs["work"] / "translated.json"
    if not src_path.exists():
        raise SystemExit(f"missing: {src_path}")

    tr = json.loads(src_path.read_text(encoding="utf-8"))
    data = {k: v["final"] for k, v in tr.items()}

    out_dir = dirs["dist"] / "splits"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 清空老 part
    for p in out_dir.glob("part*.strings"):
        p.unlink()

    keys_sorted = sorted(data.keys())
    total = len(keys_sorted)
    n = (total + args.chunk - 1) // args.chunk
    for i in range(n):
        part = keys_sorted[i * args.chunk : (i + 1) * args.chunk]
        subset = {k: data[k] for k in part}
        fn = out_dir / f"part{i+1:02d}.strings"
        fn.write_text(dump_strings(subset), encoding="utf-8")
        print(f"  part{i+1:02d}  keys[{part[0][:30]} .. {part[-1][:30]}]  {len(part)} 条  → {fn.name}")

    print(f"\n共 {n} 份, 总 {total} 条 → {out_dir.relative_to(ROOT)}/")
    print("\n上传提示:")
    print("  1. 打开 translations.telegram.org 对应 macOS 页面")
    print("  2. 逐份 Import phrases → Edit Phrases, 记录哪份失败")
    print("  3. 对失败份用 --chunk 50 / 10 再次切分, 继续二分")


if __name__ == "__main__":
    main()
