"""修补 macOS AI 跑完后残留的英文条目 (一次性脚本, 可复用于未来 patch)。

背景: AI 对少量条目看 refs.zhcncc 也是英文就直接 adopt, 违反 PROMPT 合约。
本脚本直接改写 work/macos/translated.json 的 final 字段, 然后 build_strings。

用法:
    python3 scripts/patch_macos_leftover_english.py
    python3 scripts/build_strings.py macos    # 重新打包
"""
from __future__ import annotations
import json
from pathlib import Path


PATCHES: dict[str, tuple[str, str]] = {
    "ApplyLanguage.ChangeLanguageOfficialText": (
        "你将要应用语言包 **%@**。\n\n"
        "此操作将翻译整个界面。你可以在 [翻译平台]() 中提交修改建议。\n\n"
        "你可以随时在「偏好设置」中切换回原语言。",
        "rewrite_official",
    ),
    "ApplyLanguage.ChangeLanguageUnofficialText": (
        "你将要使用一个完成度为 %@% 的自定义语言包（**%@**）。\n\n"
        "此操作将翻译整个界面。你可以在 [翻译平台]() 中提交修改建议。\n\n"
        "你可以随时在「偏好设置」中切换回原语言。",
        "rewrite_official",
    ),
    "ApplyLanguage.ChangeLanguageUnofficialText1": (
        "你将要使用一个完成度为 %2$@% 的自定义语言包 **%1$@**。\n\n"
        "此操作将翻译整个界面。你可以在 [翻译平台]() 中提交修改建议。\n\n"
        "你可以随时在「偏好设置」中切换回原语言。",
        "rewrite_official",
    ),
    "SecureId.Accept.Policy": (
        "你同意 [登录组件示例隐私政策](_applyPolicy_)，并允许其 **%@** 向你发送消息。",
        "rewrite_ref",
    ),
    "ChatList.Service.GameScored1_zero": ("在 %@ 中得分 %d", "fresh"),
    "ChatList.Service.GameScored1_one":  ("在 %@ 中得分 %d", "fresh"),
    "ChatList.Service.GameScored1_two":  ("在 %@ 中得分 %d", "fresh"),
    "ChatList.Service.GameScored1_few":  ("在 %@ 中得分 %d", "fresh"),
    "ChatList.Service.GameScored1_many": ("在 %@ 中得分 %d", "fresh"),
}


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    tr_path = root / "work" / "macos" / "translated.json"
    tr = json.loads(tr_path.read_text(encoding="utf-8"))

    applied = skipped = 0
    for k, (new_final, new_src) in PATCHES.items():
        if k not in tr:
            print(f"  ⚠️  key 不存在, 跳过: {k}")
            skipped += 1
            continue
        tr[k]["final"] = new_final
        tr[k]["source"] = new_src
        tr[k]["note"] = "manual_patch: AI 留英文, 人工改写"
        applied += 1

    tr_path.write_text(
        json.dumps(tr, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"✅ 已 patch {applied} 条, 跳过 {skipped} 条 → {tr_path.relative_to(root)}")


if __name__ == "__main__":
    main()
