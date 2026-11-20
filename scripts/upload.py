#!/usr/bin/env python3
"""把上传文件导入 translations.telegram.org 自定义语言包，提交修改并导出核验。

用法: python3 scripts/upload.py ios [--preview]
登录态读取环境变量 TG_TRANSLATIONS_COOKIE，未设置时读取项目根目录 .env 中的同名项。
--preview 只导入并显示网站识别的分组数量，不备份也不提交。
"""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

from _common import CUSTOM_LANG, PLATFORMS, ROOT, SITE, fetch_export, parse_resource, platform_dirs, resource_suffix

COOKIE_ENV = "TG_TRANSLATIONS_COOKIE"
# 导入预览的分组，对应网页 tr-<name>-keys-block 区块；现行流程只提交 change 组（EDIT ALL）。
BLOCKS = ("change", "add", "remove", "restore")
# 保存后导出可能要几分钟才出现新版本。
EXPORT_WAIT = 15 * 60
EXPORT_POLL = 30


def load_cookie() -> str:
    cookie = os.environ.get(COOKIE_ENV)
    env = ROOT / ".env"
    if not cookie and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == COOKIE_ENV:
                cookie = value.strip().strip("'\"")
    if not cookie:
        raise SystemExit(f"缺少 {COOKIE_ENV}：从已登录浏览器复制 {SITE} 请求的 Cookie 请求头，写入项目根目录 .env。")
    return cookie


def multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    # 网站只把声明为 text/xml 的文件识别为安卓 XML，其他类型返回 Invalid file format。
    file_type = "text/xml" if filename.endswith(".xml") else "application/octet-stream"
    head = "".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    head += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {file_type}\r\n\r\n'
    return head.encode() + content + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


class PreviewParser(HTMLParser):
    """按所在区块收集导入预览每一行的 data-key。"""

    def __init__(self) -> None:
        super().__init__()
        self.block: str | None = None
        self.keys: dict[str, list[str]] = {name: [] for name in BLOCKS}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = (attr.get("class") or "").split()
        block = next((name for name in BLOCKS if f"tr-{name}-keys-block" in classes), None)
        if block:
            self.block = block
        elif self.block and "tr-plain-key-row" in classes:
            self.keys[self.block].append(attr["data-key"])


class Session:
    def __init__(self, platform: str, cookie: str) -> None:
        self.platform = platform
        self.cookie = cookie
        page = self.request(f"{SITE}/{CUSTOM_LANG}/{platform}/").decode("utf-8")
        # 接口地址里的 hash 与会话 cookie 绑定，只能从已登录页面的 ajInit 参数取得。
        options, _ = json.JSONDecoder().raw_decode(page, page.index("ajInit(") + len("ajInit("))
        if options.get("unauth"):
            raise SystemExit(f"{COOKIE_ENV} 已失效或未登录，请重新复制 Cookie。")
        self.api = SITE + options["apiUrl"]

    def request(self, url: str, body: bytes | None = None, content_type: str | None = None) -> bytes:
        headers = {"Cookie": self.cookie}
        if content_type:
            headers["Content-Type"] = content_type
        with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=300) as resp:
            return resp.read()

    def call(self, method: str, fields: dict[str, str], file: tuple[str, bytes] | None = None) -> dict:
        fields = {"method": method, "lang": CUSTOM_LANG, "lang_pack": self.platform, **fields}
        if file:
            body, content_type = multipart(fields, *file)
        else:
            body, content_type = urllib.parse.urlencode(fields).encode(), "application/x-www-form-urlencoded; charset=UTF-8"
        result = json.loads(self.request(self.api, body, content_type))
        if result.get("error"):
            raise SystemExit(f"{method} 失败：{result['error']}")
        return result

    def import_file(self, filename: str, content: bytes) -> tuple[str, dict[str, list[str]]]:
        result = self.call("importFile", {}, (filename, content))
        parser = PreviewParser()
        parser.feed(result["html"])
        print("导入识别：" + "，".join(f"{name} {len(keys)}" for name, keys in parser.keys.items()))
        return result["import_id"], parser.keys

    def apply(self, import_id: str, keys: list[str]) -> None:
        # 服务端每次只处理一部分，剩余 key 放在 repeat_lang_keys 中，连同 affected_cnt 继续提交。
        pending, affected = keys, 0
        while pending:
            result = self.call("editImportedKeys", {
                "import_id": import_id, "lang_keys": ",".join(pending), "affected_cnt": str(affected)})
            pending, affected = result.get("repeat_lang_keys") or [], result.get("affected_cnt", 0)
            print(f"  已提交 {len(keys) - len(pending)}/{len(keys)}")


def export(platform: str) -> tuple[str, bytes]:
    name, content = fetch_export(CUSTOM_LANG, platform)
    print(f"线上导出 {name}  SHA-256 {hashlib.sha256(content).hexdigest()}")
    return name, content


def main(platform: str, preview: bool) -> None:
    dirs = platform_dirs(platform)
    work = dirs["work"]
    path = dirs["dist"] / f"zh-Hans-custom.upload{resource_suffix(platform)}"
    content = path.read_bytes()
    upload = parse_resource(content.decode("utf-8"), platform)
    manifest = json.loads((work / "update.json").read_text(encoding="utf-8"))
    session = Session(platform, load_cookie())

    import_id, blocks = session.import_file(path.name, content)
    if preview:
        return
    online_name, online = export(platform)
    backup = work / manifest["archive"] / "online-before-upload.json"
    if backup.exists():
        print(f"沿用本轮已有的回滚备份 {backup}")
    else:
        data = parse_resource(online.decode("utf-8-sig"), platform)
        backup.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"回滚备份 → {backup}")
    before = json.loads(backup.read_text(encoding="utf-8"))

    # 与网页重试规则一致：重新导入后剩余修改仍在减少就继续提交，同一批连续两次没有变化时停止。
    first = changes = blocks["change"]
    stalls = 0
    while changes and stalls < 2:
        session.apply(import_id, changes)
        import_id, blocks = session.import_file(path.name, content)
        stalls = stalls + 1 if set(blocks["change"]) == set(changes) else 0
        changes = blocks["change"]

    after_name, after = online_name, online
    if set(changes) != set(first):
        deadline = time.monotonic() + EXPORT_WAIT
        while after_name == online_name:
            if time.monotonic() > deadline:
                raise SystemExit(f"导出仍为上传前的 {online_name}，稍后重新运行本脚本完成核验。")
            time.sleep(EXPORT_POLL)
            after_name, after = export(platform)
    exported = parse_resource(after.decode("utf-8-sig"), platform)

    round_all = {*manifest["added"], *manifest["changed"], *manifest.get("reviewed_existing", [])}
    round_keys = sorted(round_all & upload.keys())
    same = [k for k in round_keys if exported.get(k) == upload[k]]
    kept = [k for k in same if before.get(k) == upload[k]]
    differ = [k for k in round_keys if k not in same]
    others = [k for k in exported.keys() | before.keys() if k not in round_all and exported.get(k) != before.get(k)]
    print(f"本轮中文有效词条 {len(round_keys)}：与上传文件一致 {len(same)}（上传前已一致 {len(kept)}），"
          f"仍不同或未导出 {len(differ)}")
    print(f"导入识别修改 {len(first)}，保存后导入残留 {len(changes)}；本轮以外导出变化 {len(others)}")
    for label, keys in (("本轮未生效", differ), ("导入残留", changes), ("本轮以外变化", sorted(others))):
        if keys:
            print(f"{label}：{', '.join(keys)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("--preview", action="store_true", help="只导入预览，不备份也不提交")
    args = parser.parse_args()
    main(args.platform, args.preview)
