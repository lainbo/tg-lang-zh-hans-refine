"""共用工具: .strings / 安卓 XML 解析与序列化, 路径约定, 语言包导出下载。"""
from __future__ import annotations
import re
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLATFORMS = ("ios", "macos", "tdesktop", "android")
SITE = "https://translations.telegram.org"
CUSTOM_LANG = "zhcn1ainbo"

# 各平台复数后缀：(中文上传保留分支, 其余复数分支)
PLURAL_SUFFIXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "android": ("_other", ("_zero", "_one", "_two", "_few", "_many")),
    "macos": ("_other", ("_zero", "_one", "_two", "_few", "_many")),
    "ios": ("_any", ("_0", "_1", "_2", "_3_10", "_many")),
    "tdesktop": ("#other", ("#zero", "#one", "#two", "#few", "#many")),
}

# 占位符: Apple %@ / %1$@ / %d / %1$d / %s / %1$s / %1$.2f, {xxx}, 安卓 un1 / **oo** 等
PLACEHOLDER_RE = re.compile(r"%%|%(?:\d+\$)?\d*(?:\.\d+)?[@dsif]|\{[^{}]+\}|\bun\d+\b|\*\*oo\*\*")


def extract_placeholders(s: str) -> list[str]:
    return PLACEHOLDER_RE.findall(s)


def placeholders(s: str) -> list[str]:
    return sorted(extract_placeholders(s))


def unnumbered_percent_placeholders(s: str) -> list[str]:
    return [p for p in extract_placeholders(s) if p.startswith("%") and p != "%%" and "$" not in p]


def placeholder_issue(en: str, zh: str) -> str | None:
    if placeholders(en) != placeholders(zh):
        return "placeholder_mismatch"
    if unnumbered_percent_placeholders(en) != unnumbered_percent_placeholders(zh):
        return "placeholder_order_mismatch"
    return None


def resource_suffix(platform: str) -> str:
    return ".xml" if platform == "android" else ".strings"


def fetch_export(lang: str, platform: str) -> tuple[str, bytes]:
    """下载语言包某平台的导出文件，返回带版本号的文件名和原始内容；导出无需登录。"""
    url = f"{SITE}/{lang}/{platform}/export"
    with urllib.request.urlopen(url, timeout=120) as resp:
        name = resp.headers.get_filename()
        if not name:
            raise SystemExit(f"{url} 没有返回语言包文件，请检查语言包 {lang} 与平台 {platform}。")
        return name, resp.read()


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


def parse_resource(text: str, platform: str) -> dict[str, str]:
    if platform != "android":
        return parse_strings(text)
    root = ET.fromstring(text)
    if root.tag != "resources":
        raise ValueError("安卓语言文件必须以 <resources> 为根元素")
    result: dict[str, str] = {}
    for entry in root:
        key = entry.get("name")
        if entry.tag != "string" or not key or len(entry):
            raise ValueError("安卓导出文件必须包含具名的纯文本 <string> 条目")
        if key in result:
            raise ValueError(f"重复安卓 key：{key}")
        result[key] = _unescape(entry.text or "")
    return result


def dump_resource(data: dict[str, str], platform: str) -> str:
    if platform != "android":
        return dump_strings(data)
    root = ET.Element("resources")
    for key in sorted(data):
        ET.SubElement(root, "string", name=key).text = _escape(data[key]).replace("'", "\\'")
    ET.indent(root, space="    ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode", short_empty_elements=False) + "\n"
