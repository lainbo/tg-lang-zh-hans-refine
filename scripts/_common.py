"""共用工具: .strings 解析/序列化, 路径约定。"""
from __future__ import annotations
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLATFORMS = ("ios", "macos", "tdesktop")


def platform_dirs(platform: str) -> dict[str, pathlib.Path]:
    if platform not in PLATFORMS:
        raise SystemExit(f"unknown platform: {platform}, expect one of {PLATFORMS}")
    base = ROOT
    return {
        "raw": base / "data" / platform / "raw",
        "parsed": base / "data" / platform / "parsed",
        "work": base / "work" / platform,
        "dist": base / "dist" / platform,
    }


# Apple .strings 格式:
#   /* comment */
#   "key" = "value";
# 支持转义 \" \\ \n \t
_STRING_RE = re.compile(
    r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;',
    re.MULTILINE,
)
def _unescape(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _escape(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\t", "\\t")
         .replace("\r", "\\r")
    )


def _strip_comments(text: str) -> str:
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt)
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 < len(text) else 0
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def parse_strings(text: str) -> dict[str, str]:
    """解析 .strings 文本为 key→value 字典。注释被丢弃。"""
    # 只剥离字符串外部的注释, 避免误伤 https:// 或 markdown 中的 /* */
    cleaned = _strip_comments(text)
    result: dict[str, str] = {}
    for m in _STRING_RE.finditer(cleaned):
        key = _unescape(m.group(1))
        val = _unescape(m.group(2))
        result[key] = val
    return result


def dump_strings(data: dict[str, str]) -> str:
    """dict→.strings 文本。按 key 字母序输出, 便于 diff。"""
    lines = []
    for key in sorted(data.keys()):
        lines.append(f'"{_escape(key)}" = "{_escape(data[key])}";')
    return "\n".join(lines) + "\n"
