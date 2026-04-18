"""共用工具: .strings 解析/序列化, 路径约定。"""
from __future__ import annotations
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLATFORMS = ("ios", "macos")


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
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")


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


def parse_strings(text: str) -> dict[str, str]:
    """解析 .strings 文本为 key→value 字典。注释被丢弃。"""
    # 先去掉注释, 避免注释里的伪字符串干扰
    cleaned = _COMMENT_RE.sub("", text)
    cleaned = _LINE_COMMENT_RE.sub("", cleaned)
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
