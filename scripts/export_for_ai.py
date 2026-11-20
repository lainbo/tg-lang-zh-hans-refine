#!/usr/bin/env python3
"""导出分层紧凑的 AI 翻译分片或二审差量复核包，并生成对应的任务 Prompt。

核心机制:
1. 复数折叠与同英文聚合: 同词根复数分支安全折叠，同英文词条合并审阅（支持按 key 单独覆写语境差异），导入时自动展开回全部原始 key
2. 上下文与精修记忆预注入: 自动注入四端精修候选（精确匹配、占位符安全投影、大小写不敏感提示）、变更旧译文 previous_zh 及同功能前缀已译邻居
3. 复杂度分层切片: 按语义复杂度切分为常规片 (fast, 默认 ≤350 组) 与疑难片 (deep, 默认 ≤120 组)，脚本映射元数据独立存入 .meta.json
4. 本地规则预检与差量二审 (--review): 本地静态检查标记术语、格式与一致性风险；常规片精确复用的无风险词条免二审，其余词条导出紧凑复核包并仅输出修改补丁

用法:
  python3 scripts/export_for_ai.py ios                          # 按默认分层上限导出紧凑分片
  python3 scripts/export_for_ai.py ios --repack                 # 保留已校验分片，将剩余未译条目重切为紧凑分片
  python3 scripts/export_for_ai.py ios --review                 # 初译校验全部通过后，导出二审差量复核包
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil

from _common import (
    PLACEHOLDER_RE,
    PLATFORMS,
    PLURAL_SUFFIXES,
    ROOT,
    extract_placeholders,
    placeholder_issue,
    platform_dirs,
)
from import_from_ai import validate

_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_COND_RE = re.compile(
    r"\b(?:not|never|unless|except|without|only|if|when|until|before|after|"
    r"cannot|can't|won't|don't|doesn't|didn't|aren't|isn't|least|most|"
    r"irrevocable|permanently)\b|\bup to\b",
    re.IGNORECASE,
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:wallet|gram|onchain|passkey|passcode|password|privacy|auth|"
    r"payment|refund|withdraw|fee|commission|secret|recovery)",
    re.IGNORECASE,
)

# 本地二审静态预检用的高确定性术语规则（仅含无跨模块歧义的专名与功能名）
_STRICT_GLOSSARY_RULES: tuple[tuple[re.Pattern[str], str, str, re.Pattern[str] | None], ...] = (
    (re.compile(r"\bTelegram Premium\b"), "Telegram Premium", "Telegram 高级版", re.compile(r"\bPremium Bot\b")),
    (re.compile(r"\bTelegram Business\b"), "Telegram Business", "Telegram 商业版", None),
    (re.compile(r"\bTelegram Stars\b"), "Telegram Stars", "Telegram 星星", None),
    (re.compile(r"\bSaved Messages\b"), "Saved Messages", "收藏夹", None),
    (re.compile(r"\bSecret Chats?\b"), "Secret Chat", "私密聊天", None),
    (re.compile(r"\bPasskeys?\b", re.IGNORECASE), "Passkey", "通行密钥", None),
    (re.compile(r"\bPasscodes?\b", re.IGNORECASE), "Passcode", "锁定密码", None),
    (re.compile(r"\bMini Apps?\b"), "Mini App", "迷你应用", None),
    (re.compile(r"\bQuick Repl(?:y|ies)\b"), "Quick Reply", "快捷回复", None),
    (re.compile(r"\bClose Friends\b"), "Close Friends", "密友", None),
    (re.compile(r"\bGiveaways?\b", re.IGNORECASE), "Giveaway", "抽奖活动", None),
    (re.compile(r"\bAffiliate Program\b", re.IGNORECASE), "Affiliate Program", "联盟计划", None),
    (re.compile(r"\bSelf-Destruct Timer\b", re.IGNORECASE), "Self-Destruct Timer", "自毁计时器", None),
    (re.compile(r"\bView Once\b"), "View Once", "仅查看一次", None),
    (re.compile(r"\bNetwork Fees?\b", re.IGNORECASE), "Network Fee", "网络手续费", None),
    (re.compile(r"\bGreeting Messages?\b", re.IGNORECASE), "Greeting Message", "问候消息", None),
    (re.compile(r"\bAway Messages?\b", re.IGNORECASE), "Away Message", "离开消息", None),
    (re.compile(r"\bWelcome Messages?\b", re.IGNORECASE), "Welcome Message", "欢迎消息", None),
    (re.compile(r"\bDirect Messages?\b"), "Direct Messages", "私信", None),
)

PROMPT_OVERVIEW = """# 翻译 AI 审校任务总合约

你是 Telegram 简体中文语言包审校者。本项目采用**上下文预注入 + 分层紧凑回传 + 差量二审**流程：
- 初译分片为 `compact.partNN.json`（同目录的 `.meta.json` 仅供脚本展开使用，无需读取）。根据分片顶层 `"tier"` 字段阅读对应的 `PROMPT.fast.md`（常规片）或 `PROMPT.deep.md`（疑难片），将结果写入 `reply.partNN.json`。
- 片内已预注入四端精修候选（`c`）、原文变更前的旧精修译文（`p_en` / `p_zh`）及本平台同模块已译邻居（顶层 `context`）。除片内信息仍无法消解具体功能歧义外，**无需检索 `merged.json`、`translation-memory.json` 或其他平台大文件**。
- 每个分片在独立干净的子会话中完成：首轮并行读取对应 `PROMPT.*.md` 与 `compact.partNN.json`，随后直接写出 `reply.partNN.json`，再运行 `python3 scripts/import_from_ai.py <platform> --part N` 展开并校验。
- 全部初译分片校验通过后，运行 `python3 scripts/export_for_ai.py <platform> --review` 导出二审包，阅读 `PROMPT.review.md` 完成差量复核补丁 `review-patch.partNN.json`，再运行 `python3 scripts/import_from_ai.py <platform> --review` 应用补丁。

## 输入字段说明（`compact.partNN.json`）

- `k`：单条 key 字符串，或共享同一英文的多个 key 列表。
- `en`：当前官方英文。
- `p`（可选，值为 `1`）：表示该条已折叠同词根复数分支，只需输出 1 条中文译文（占位符严格匹配 `en`）。
- `one`（可选）：同词根单数分支的不同英文，仅供语义参考，占位符仍须匹配 `en`。
- `p_en` / `p_zh`（可选）：英文变更或定向重审时的旧英文与上一轮精修译文。
- `c`（可选）：四端精修候选列表，格式 `"译文 [来源]"`；`[~来源]` 表示占位符安全投影候选，`[ci|来源]` 表示大小写不敏感匹配候选，均须核对语境后再决定是否采用。

## 紧凑回传格式（`reply.partNN.json`）

输出一个纯 JSON 对象，顶层键与分片 `items` 短编号完全一致，不要使用 Markdown 代码块包裹：
- `"="` 或 `"=0"`、 `"=1"`：核对 key 业务语境与参数角色一致后，原样采用 `c[0]`（或指定下标候选）；脚本自动展开为对应中文、`"source": "adopt"` 及来源备注。
- `"=prev"`：仅用于带 `p_zh` 的英文微调词条，确认新英文下旧译文仍完全准确且占位符一致时直接沿用。
- `"最终译文"`：以当前英文和上下文独立新译（默认 `"source": "fresh"`；若译文字面量恰好为 `"="` 等引用格式，请用数组形式 `["=", "fresh"]`）。
- `["最终译文", "rewrite_ref", "改写来源与理由"]`：基于候选/旧译改写，或需要补充备注（第 2 项须为 `"fresh"` / `"adopt"` / `"rewrite_ref"` / `"rewrite_official"`，第 3 项可选）。
- **同英文组内有语境差异时**：当 `k` 为多个 key 列表且个别 key 需不同译法，可输出对象按 key 分别指定，支持 `"*"` 作为组内默认译法，例如：`{"*": "名称", "Checkout.Name": "姓名"}`（对象内各值同样支持 `"="`、`"=1"`、字符串或数组）。

## 核心翻译与格式守则

1. **信、达、雅**：以当前官方英文为准，完整保留主体、条件、否定、范围与操作后果；称呼统一为“你”，省略号统一为 `…`，不添加原文没有的语气或承诺。
2. **保留占位符与格式**：`%@`、`%1$@`、`%d`、`%2$02d`、`%%`、`{user}`、安卓 `un1`/`un2` 与 `**oo**` 等数量与写法必须完全一致；无编号百分号参数保持原有次序；保留 Markdown 标记、链接目标与必要换行，官方空串原样保留 `""`。
3. **复数折叠**：带 `"p": 1` 的条目输出 1 条符合中文习惯且占位符匹配 `en` 的译文即可，脚本会自动回填该组各复数分支。
"""

PROMPT_FAST_HEADER = """# 常规分片（fast）初译指令

当前处理的 `compact.partNN.json` 为**常规分片**（短按钮、标题、状态词或已有跨端候选）：
1. **基于片内上下文直接完成**：同模块参考已内联在顶层 `context` 与条目的 `c` 中，**不要读取 `.meta.json` 或外部大文件**，单轮直接写出对应的 `reply.partNN.json`。
2. **核对语境再复用**：有候选 `c` 时，核对 `k` 所属功能模块（警惕同词不同义，如礼物 `Model` 为“款式”，AI `AgentModel` 为“模型”；结账 `NAME` 为“姓名”，智能体 `NAME` 为“名称”；`[~...]` 为占位符投影，`[ci|...]` 为大小写不敏感匹配）。适用时直接输出 `"="`（或 `"=1"`）；同英文多 key 组若个别 key 语境不同，用 `{"*": "默认译文", "特殊Key": "特殊译文"}` 分别处理。
3. **输出纯 JSON 对象**（顶层键与 `items` 短编号完全一致，不加代码块）：
   - 采用候选：`"001": "="` 或 `"001": "=1"`
   - 独立新译：`"002": "最终译文"`
   - 改写或附注：`"003": ["最终译文", "rewrite_ref", "来源与理由"]`
   - 组内分歧覆写：`"004": {"*": "名称", "Checkout.Name": "姓名"}`
4. **严守占位符与格式**：占位符数量、写法及无编号百分号次序必须与 `en` 完全一致；称呼用“你”，省略号用 `…`；带 `"p": 1` 的复数组按 `en` 占位符输出 1 条中文即可。
"""

PROMPT_DEEP_HEADER = """# 疑难分片（deep）精译指令

当前处理的 `compact.partNN.json` 为**疑难分片**（包含英文变更、多占位符句子、条件/否定边界、多行说明或敏感业务词条）：
1. **优先使用片内上下文**：片内已提供 `p_en` + `p_zh`（原文变化时）、`c`（四端精修候选）及顶层 `context`（本平台同模块已译邻居），不要读取 `.meta.json`。仅当片内信息仍不足以判断界面用途或参数包含内容时，才定向查阅本平台必要上下文并在备注说明依据。
2. **逐项精审要点**：
   - **原文变化（含 `p_en`）**：仔细比对新旧英文在条件、范围、主体或操作后果上的差异；旧译仍完全准确且占位符匹配可输出 `"=prev"`，否则按新英文改写或重译。
   - **多参数与复数**：核对每个参数的角色与是否自带数量/单位，无编号百分号参数严禁调换次序；带 `"p": 1` / `one` 的复数组可参考 `one` 理解含义，最终译文占位符必须严格匹配 `en`。
   - **条件与否定**：完整保留 `not`、`unless`、`except`、`only`、`without` 等限定条件及不可逆后果。
   - **同英文多 key 组**：逐一核对 `k` 列表中各 key 的所属模块，若存在语境差异用 `{"*": "默认译文", "特殊Key": "特殊译文"}` 分别给出译文。
3. **输出纯 JSON 对象**写入 `reply.partNN.json`（顶层键与 `items` 短编号完全一致，不加代码块）：
   - 采用候选：`"001": "="`（或 `"=1"`、 `"=prev"`）
   - 独立新译：`"002": "最终译文"`
   - 改写或附注：`"003": ["最终译文", "rewrite_ref", "来源与理由"]`
"""

PROMPT_REVIEW_HEADER = """# 二审差量复核指令（只输出修改补丁）

你是独立的第二遍语义与一致性审校者。输入 `review.partNN.json` 包含已完成结构校验的初译草稿 `zh`（同目录的 `.meta.json` 仅供脚本使用，无需读取）。
常规分片中精确采用四端精修候选且未命中本地风险规则的词条已自动豁免，当前列表均为**新译、改写、投影/模糊候选复用、疑难词条或命中预检提示的词条**。

## 复核重点

1. **优先核查带 `flags` 的条目**：脚本已对术语、称呼/省略号、首尾空白、长度比例与本端同英文多译差异做了静态预检，带 `flags` 的条目务必逐项核实。
2. **逐条对照 `en` 与 `zh`**：核对主体、对象、否定、条件边界、金额/时间单位及操作后果是否准确完整；有 `p_en` 时确认英文变更点已在译文中准确体现；`k` 为多个 key 列表时确认各 key 语境一致。
3. **核对参数与显示格式**：确认参数角色未张冠李戴、参数外层单位无重复、Markdown 粗体/链接标记及换行完整保留、称呼统一为“你”、省略号为 `…`。
4. **术语与同组一致性**：遵守下方共用术语表；同一功能模块的按钮、标题与说明用词保持一致。

## 差量补丁输出要求（`review-patch.partNN.json`）

- **确认无误的条目一律不要输出！** 若整片全部准确无误，直接输出空对象 `{}`。
- 仅对确实存在语义偏差、术语冲突、语病或格式瑕疵的条目，按其 `Rxxx` 编号输出修正（不加 Markdown 代码块）：
  ```json
  {
    "R005": "修正后的最终译文",
    "R012": ["修正后的最终译文", "fresh", "修正原因说明"],
    "R019": {"Checkout.Name": "姓名"}
  }
  ```
  当 `Rxxx` 对应多个 key（`k` 为列表）且仅需修正其中个别 key 时，可输出对象只列需要改动的 key（未列出的 key 保持原草稿；也可配合 `"*"` 统一改写其余 key）。
- 不要为了同义换词改动已经准确自然的译文。修正后的译文占位符必须与 `en` 完全一致。
"""


def _dump_compact_json(payload: dict) -> str:
    """顶层分行、context 与 items 每条单行紧凑序列化，兼顾可读性与紧凑性。"""
    lines: list[str] = ["{"]
    top_keys = list(payload.keys())
    for ti, tk in enumerate(top_keys):
        val = payload[tk]
        comma = "," if ti + 1 < len(top_keys) else ""
        if tk in ("context", "items") and isinstance(val, dict):
            if not val:
                lines.append(f'"{tk}":{{}}{comma}')
            else:
                lines.append(f'"{tk}":{{')
                sub_items = list(val.items())
                for si, (sk, sv) in enumerate(sub_items):
                    scomma = "," if si + 1 < len(sub_items) else ""
                    sk_s = json.dumps(sk, ensure_ascii=False)
                    sv_s = json.dumps(sv, ensure_ascii=False, separators=(",", ":"))
                    lines.append(f"{sk_s}:{sv_s}{scomma}")
                lines.append(f"}}{comma}")
        else:
            lines.append(f'"{tk}":{json.dumps(val, ensure_ascii=False, separators=(",", ":"))}{comma}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _extract_style_sections(style_text: str, titles: set[str]) -> str:
    blocks: list[str] = []
    current_title = ""
    current_lines: list[str] = []
    for line in style_text.splitlines():
        if line.startswith("## "):
            if current_title in titles:
                blocks.append("\n".join(current_lines).strip())
            current_title = line[3:].strip()
            current_lines = [line]
        elif current_title:
            current_lines.append(line)
    if current_title in titles:
        blocks.append("\n".join(current_lines).strip())
    return "\n\n".join(blocks) if blocks else style_text


def _is_unnumbered_pct(tok: str) -> bool:
    return tok.startswith("%") and tok != "%%" and "$" not in tok


def _non_pct_slots(s: str) -> list[str]:
    return [t for t in extract_placeholders(s) if t != "%%"]


def _skeleton(s: str) -> str:
    idx = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal idx
        tok = m.group(0)
        if tok == "%%":
            return "%%"
        idx += 1
        return f"\x00{idx}\x00"

    return PLACEHOLDER_RE.sub(repl, s)


def _project_zh(src_en: str, src_zh: str, dst_en: str) -> str | None:
    if src_en == dst_en:
        return src_zh if placeholder_issue(dst_en, src_zh) is None else None
    src_slots = _non_pct_slots(src_en)
    dst_slots = _non_pct_slots(dst_en)
    if not src_slots or len(src_slots) != len(dst_slots):
        return None
    zh_slots = _non_pct_slots(src_zh)
    if len(zh_slots) != len(src_slots):
        return None

    # 校验 src_slots 与 dst_slots 是否存在严格双射，防止静默换序或参数错位
    s2d: dict[str, str] = {}
    d2s: dict[str, str] = {}
    bijection = True
    for s, d in zip(src_slots, dst_slots):
        if (s in s2d and s2d[s] != d) or (d in d2s and d2s[d] != s):
            bijection = False
            break
        s2d[s] = d
        d2s[d] = s

    if bijection:
        dst_unnum_src_order = [s for s, d in zip(src_slots, dst_slots) if _is_unnumbered_pct(d)]
        if dst_unnum_src_order:
            zh_unnum_src_order = [t for t in zh_slots if _is_unnumbered_pct(s2d[t])]
            if zh_unnum_src_order != dst_unnum_src_order:
                return None
        cand = PLACEHOLDER_RE.sub(lambda m: s2d.get(m.group(0), m.group(0)), src_zh)
    elif zh_slots == src_slots:
        # 非双射（如 %1$@ %2$@ -> %@ %@ 或 %@ %@ -> %1$@ %2$@）：
        # 仅允许源译文未调换槽位顺序，且源端不存在重复的具名/编号占位符
        for s in set(src_slots):
            if src_slots.count(s) > 1 and not _is_unnumbered_pct(s):
                return None
        it = iter(dst_slots)
        cand = PLACEHOLDER_RE.sub(
            lambda m: m.group(0) if m.group(0) == "%%" else next(it, m.group(0)),
            src_zh,
        )
    else:
        return None

    return cand if placeholder_issue(dst_en, cand) is None else None


def key_prefix(platform: str, key: str) -> str:
    base = key.split("#")[0]
    if platform in ("ios", "macos") and "." in base:
        parts = base.split(".")
        return ".".join(parts[:2]) if len(parts) >= 3 else parts[0]
    if platform == "tdesktop" and "_" in base:
        parts = base.split("_")
        return "_".join(parts[:3]) if len(parts) >= 4 else "_".join(parts[:2])
    words = _CAMEL_RE.findall(base)
    return "".join(words[:2]) if len(words) >= 3 else (words[0] if words else base)


def _load_platform_pairs(platform: str, is_current: bool) -> list[tuple[str, str, str]]:
    """返回 [(key, en, zh), ...]，仅包含已有精修译文。"""
    work = platform_dirs(platform)["work"]
    merged_path = work / "merged.json"
    merged = json.loads(merged_path.read_text(encoding="utf-8")) if merged_path.exists() else {}
    pairs: list[tuple[str, str, str]] = []
    seen_keys: set[str] = set()

    primary_files = ["translated.reused.json"] if is_current else ["translated.json", "translated.reused.json"]
    for fname in primary_files:
        fpath = work / fname
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for k in sorted(data):
            entry = data[k]
            en = merged.get(k, {}).get("en")
            zh = entry.get("final") if isinstance(entry, dict) else None
            if en and zh and k not in seen_keys:
                seen_keys.add(k)
                pairs.append((k, en, zh))
        if not is_current and fname == "translated.json":
            break

    tm_path = work / "translation-memory.json"
    if tm_path.exists():
        tm = json.loads(tm_path.read_text(encoding="utf-8"))
        for k in sorted(tm):
            if k in seen_keys:
                continue
            item = tm[k]
            en = item.get("en")
            zh = item.get("final")
            if en and zh:
                seen_keys.add(k)
                pairs.append((k, en, zh))
    return pairs


def _index_pair(
    en: str,
    zh: str,
    origin: str,
    exact_idx: dict[str, list[tuple[str, str]]],
    skel_idx: dict[str, list[tuple[str, str, str]]],
    lower_idx: dict[str, list[tuple[str, str]]],
    *,
    prepend: bool = False,
) -> None:
    if prepend:
        exact_idx.setdefault(en, []).insert(0, (zh, origin))
        lower_idx.setdefault(en.lower(), []).insert(0, (zh, origin))
        if _non_pct_slots(en) and _WORD_RE.search(PLACEHOLDER_RE.sub(" ", en)):
            skel_idx.setdefault(_skeleton(en), []).insert(0, (en, zh, origin))
    else:
        exact_idx.setdefault(en, []).append((zh, origin))
        lower_idx.setdefault(en.lower(), []).append((zh, origin))
        if _non_pct_slots(en) and _WORD_RE.search(PLACEHOLDER_RE.sub(" ", en)):
            skel_idx.setdefault(_skeleton(en), []).append((en, zh, origin))


def _build_knowledge_base(
    platform: str,
) -> tuple[
    dict[str, list[tuple[str, str]]],
    dict[str, list[tuple[str, str, str]]],
    dict[str, list[tuple[str, str]]],
    dict[str, list[tuple[str, str, str]]],
]:
    exact_idx: dict[str, list[tuple[str, str]]] = {}
    skel_idx: dict[str, list[tuple[str, str, str]]] = {}
    lower_idx: dict[str, list[tuple[str, str]]] = {}
    prefix_neighbors: dict[str, list[tuple[str, str, str]]] = {}

    ordered_platforms = (platform,) + tuple(p for p in PLATFORMS if p != platform)
    for p in ordered_platforms:
        is_current = p == platform
        for k, en, zh in _load_platform_pairs(p, is_current):
            origin = f"{p}:{k}"
            _index_pair(en, zh, origin, exact_idx, skel_idx, lower_idx)
            if is_current:
                pref = key_prefix(platform, k)
                if len(prefix_neighbors.get(pref, ())) < 3:
                    prefix_neighbors.setdefault(pref, []).append((k, en, zh))
    return exact_idx, skel_idx, lower_idx, prefix_neighbors


def _lookup_candidates(
    en: str,
    exact_idx: dict[str, list[tuple[str, str]]],
    skel_idx: dict[str, list[tuple[str, str, str]]],
    lower_idx: dict[str, list[tuple[str, str]]],
    *,
    max_candidates: int = 3,
) -> tuple[list[dict], bool]:
    if not en:
        return [], False
    candidates: list[dict] = []
    seen_zh: set[str] = set()
    has_exact = False

    for zh, origin in exact_idx.get(en, ()):
        if placeholder_issue(en, zh) is None and zh not in seen_zh:
            seen_zh.add(zh)
            candidates.append({"zh": zh, "from": origin, "match": "exact"})
            has_exact = True
            if len(candidates) >= max_candidates:
                return candidates, has_exact

    if _non_pct_slots(en) and _WORD_RE.search(PLACEHOLDER_RE.sub(" ", en)):
        for src_en, src_zh, origin in skel_idx.get(_skeleton(en), ()):
            proj = _project_zh(src_en, src_zh, en)
            if proj and proj not in seen_zh:
                seen_zh.add(proj)
                candidates.append({"zh": proj, "from": origin, "match": "skel"})
                if len(candidates) >= max_candidates:
                    return candidates, has_exact

    if not has_exact and len(candidates) < max_candidates:
        for zh, origin in lower_idx.get(en.lower(), ()):
            if placeholder_issue(en, zh) is None and zh not in seen_zh:
                seen_zh.add(zh)
                candidates.append({"zh": zh, "from": origin, "match": "ci"})
                if len(candidates) >= max_candidates:
                    break

    return candidates, has_exact


def _format_candidate_hint(cand: dict) -> str:
    match = cand.get("match", "exact")
    if match == "skel":
        return f"{cand['zh']} [~{cand['from']}]"
    if match == "ci":
        return f"{cand['zh']} [ci|{cand['from']}]"
    return f"{cand['zh']} [{cand['from']}]"


def _ph_signature(en: str) -> tuple:
    if en == "":
        return ("EMPTY",)
    tokens = extract_placeholders(en)
    unnum = tuple(p for p in tokens if _is_unnumbered_pct(p))
    return ("NONEMPTY", tuple(sorted(tokens)), unnum)


def _singular_suffix(platform: str) -> str:
    if platform == "ios":
        return "_1"
    if platform == "tdesktop":
        return "#one"
    return "_one"


def _classify_tier(item: dict, has_exact_candidate: bool) -> str:
    en = item["en"]
    phs = _non_pct_slots(en)
    words = en.split()
    non_ph_words = PLACEHOLDER_RE.sub(" ", en).split()
    if (
        "previous_en" in item
        or (len(phs) >= 2 and len(non_ph_words) >= 3)
        or ("one_en" in item and not has_exact_candidate)
        or "\n" in en
        or len(words) > 12
        or len(en) > 80
        or (len(words) > 4 and bool(_COND_RE.search(en)))
        or (not has_exact_candidate and len(words) > 4 and bool(_SENSITIVE_KEY_RE.search(item["key"])))
    ):
        return "deep"
    return "fast"


def _fold_and_group(
    platform: str,
    pending: dict[str, dict],
    full_merged: dict[str, dict],
    memory: dict[str, dict],
    exact_idx: dict[str, list[tuple[str, str]]],
    skel_idx: dict[str, list[tuple[str, str, str]]],
    lower_idx: dict[str, list[tuple[str, str]]],
) -> tuple[list[dict], int, int]:
    """先折叠同词根复数分支，再聚合共享相同英文的条目。
    返回 (groups, plural_saved, same_en_saved)。
    """
    used_suf, unused_sufs = PLURAL_SUFFIXES[platform]
    all_sufs = (used_suf,) + unused_sufs
    sing_suf = _singular_suffix(platform)

    # 仅当 merged.json 中同一词根含主分支且至少有 2 个复数后缀时视为复数组
    plural_bases: set[str] = set()
    by_base_merged: dict[str, set[str]] = {}
    for k in full_merged:
        suf = next((s for s in all_sufs if k.endswith(s)), None)
        if suf:
            by_base_merged.setdefault(k[: -len(suf)], set()).add(suf)
    for base, sufs in by_base_merged.items():
        if used_suf in sufs and len(sufs) >= 2:
            plural_bases.add(base)

    buckets: dict[tuple, list[str]] = {}
    bucket_order: list[tuple] = []
    for k in sorted(pending):
        entry = pending[k]
        suf = next((s for s in all_sufs if k.endswith(s) and k[: -len(s)] in plural_bases), None)
        if suf:
            base = k[: -len(suf)]
            # 使用布尔变更标记而非原始 previous_en 文本，避免 #one / #other 因旧文单复数差异被拆散
            bkey = ("PLURAL", base, _ph_signature(entry["en"]), "previous_en" in entry)
        else:
            bkey = ("SINGLE", k)
        if bkey not in buckets:
            buckets[bkey] = []
            bucket_order.append(bkey)
        buckets[bkey].append(k)

    folded_units: list[dict] = []
    for bkey in bucket_order:
        keys = sorted(buckets[bkey])
        if bkey[0] == "PLURAL":
            base = bkey[1]
            preferred = base + used_suf
            rep_key = preferred if preferred in keys else keys[0]
        else:
            base = None
            rep_key = keys[0]

        src_entry = pending[rep_key]
        en = src_entry["en"]
        unit: dict = {"key": rep_key, "keys": keys, "en": en}
        if base is not None:
            sing_en = full_merged.get(base + sing_suf, {}).get("en", "")
            if sing_en and sing_en != en:
                unit["one_en"] = sing_en
        if "previous_en" in src_entry:
            unit["previous_en"] = src_entry["previous_en"]
            prev_zh = memory.get(rep_key, {}).get("final")
            if prev_zh:
                unit["previous_zh"] = prev_zh
        elif rep_key in memory and memory[rep_key].get("final"):
            unit["previous_zh"] = memory[rep_key]["final"]

        cands, has_exact = _lookup_candidates(en, exact_idx, skel_idx, lower_idx)
        unit["candidates"] = cands
        unit["has_exact"] = has_exact
        unit["tier"] = _classify_tier(unit, has_exact)
        folded_units.append(unit)

    plural_saved = len(pending) - len(folded_units)

    # 聚合共享同一 (en, one_en, previous_en, previous_zh) 的单元
    grouped_map: dict[tuple, list[dict]] = {}
    group_order: list[tuple] = []
    for unit in folded_units:
        gsig = (
            unit["en"],
            unit.get("one_en", ""),
            unit.get("previous_en", ""),
            unit.get("previous_zh", ""),
        )
        if gsig not in grouped_map:
            grouped_map[gsig] = []
            group_order.append(gsig)
        grouped_map[gsig].append(unit)

    groups: list[dict] = []
    for gsig in group_order:
        members = sorted(grouped_map[gsig], key=lambda u: u["key"])
        rep = members[0]
        tier = "deep" if any(m["tier"] == "deep" for m in members) else "fast"
        has_plural = any(len(m["keys"]) > 1 for m in members)
        group: dict = {
            "rep_key": rep["key"],
            "en": rep["en"],
            "tier": tier,
            "has_exact": rep["has_exact"],
            "has_plural": has_plural,
            "candidates": rep["candidates"],
            "members": [{"key": m["key"], "keys": m["keys"], "tier": m["tier"]} for m in members],
        }
        for opt in ("one_en", "previous_en", "previous_zh"):
            if opt in rep:
                group[opt] = rep[opt]
        groups.append(group)

    groups.sort(key=lambda g: g["rep_key"])
    same_en_saved = len(folded_units) - len(groups)
    return groups, plural_saved, same_en_saved


def _lint_draft(en: str, zh: str, same_en_variants: dict[str, list[str]]) -> list[str]:
    flags: list[str] = []
    if "您" in zh:
        flags.append("honorific:含「您」")
    if "..." in zh and "http://" not in zh and "https://" not in zh:
        flags.append("ellipsis:含ASCII省略号")
    if zh and en:
        if (zh[0] == " " and en[0] != " ") or (zh[-1] == " " and en[-1] != " "):
            flags.append("whitespace:首尾多余空格")
        if (len(en) >= 35 and len(zh) <= 4) or (len(en) <= 8 and len(zh) >= 36):
            flags.append("length:译文与原文长度比例异常")
    for pat, en_term, zh_term, excl in _STRICT_GLOSSARY_RULES:
        if pat.search(en) and (excl is None or not excl.search(en)):
            if zh_term not in zh:
                flags.append(f"term:{en_term}→{zh_term}")
    others = [v for v in same_en_variants.get(en, ()) if v != zh]
    if others:
        flags.append(f"diff_same_en:本端另有译法「{others[0]}」")
    return flags


def _write_prompts(work: Path) -> None:
    style_text = (ROOT / "docs" / "06-translation-style.md").read_text(encoding="utf-8")
    glossary_only = _extract_style_sections(style_text, {"共用术语"})
    review_sections = _extract_style_sections(style_text, {"共用术语", "容易通过结构校验的语义错误"})

    (work / "PROMPT.md").write_text(PROMPT_OVERVIEW + "\n" + style_text, encoding="utf-8")
    (work / "PROMPT.fast.md").write_text(PROMPT_FAST_HEADER + "\n" + glossary_only + "\n", encoding="utf-8")
    (work / "PROMPT.deep.md").write_text(PROMPT_DEEP_HEADER + "\n" + style_text, encoding="utf-8")
    (work / "PROMPT.review.md").write_text(PROMPT_REVIEW_HEADER + "\n" + review_sections + "\n", encoding="utf-8")


def _load_compact_meta_items(work: Path, part_in: Path, platform: str, part_baseline: dict, full_merged: dict, memory: dict, exact_idx: dict, skel_idx: dict, lower_idx: dict) -> list[dict]:
    meta_path = work / part_in.name.replace("to-translate.", "compact.").replace(".json", ".meta.json")
    if meta_path.exists():
        mdata = json.loads(meta_path.read_text(encoding="utf-8"))
        return list(mdata.get("items", {}).values())

    compact_path = work / part_in.name.replace("to-translate.", "compact.")
    if compact_path.exists():
        cdata = json.loads(compact_path.read_text(encoding="utf-8"))
        legacy_groups: list[dict] = []
        for item in cdata.get("items", {}).values():
            rep_key = item["key"]
            keys = item.get("plural_keys") or [rep_key]
            cands = [
                {**c, "match": c.get("match", "exact" if item["en"] in exact_idx else "skel")}
                for c in (item.get("candidates") or [])
            ]
            grp = {
                "en": item["en"],
                "tier": item.get("tier", "deep"),
                "candidates": cands,
                "members": [{"key": rep_key, "keys": keys, "tier": item.get("tier", "deep")}],
            }
            for opt in ("one_en", "previous_en", "previous_zh"):
                if opt in item:
                    grp[opt] = item[opt]
            legacy_groups.append(grp)
        return legacy_groups

    groups, _, _ = _fold_and_group(platform, part_baseline, full_merged, memory, exact_idx, skel_idx, lower_idx)
    return groups


def export_review(platform: str, review_chunk: int = 350) -> None:
    if review_chunk <= 0:
        raise SystemExit("--review-chunk 必须为正整数")
    dirs = platform_dirs(platform)
    work = dirs["work"]
    root = dirs["raw"].parent.parent.parent
    full_merged = json.loads((work / "merged.json").read_text(encoding="utf-8"))
    memory_path = work / "translation-memory.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.exists() else {}

    part_inputs = sorted(work.glob("to-translate.part*.json"))
    expected_trans = {p.name.replace("to-translate.", "translated.") for p in part_inputs}
    actual_trans = {p.name for p in work.glob("translated.part*.json")}
    if actual_trans != expected_trans:
        raise SystemExit(
            f"初译分片尚未齐备：缺少 {sorted(expected_trans - actual_trans)}；多余 {sorted(actual_trans - expected_trans)}"
        )

    for pat in ("review.part*.json", "review.part*.meta.json", "review-patch.part*.json", "translated-draft.part*.json"):
        for stale in work.glob(pat):
            stale.unlink()
    for meta_name in ("review-plan.json", "review-summary.json"):
        mp = work / meta_name
        if mp.exists():
            mp.unlink()

    exact_idx, skel_idx, lower_idx, _ = _build_knowledge_base(platform)

    # 先校验全部分片、建立不可变初译快照，并统计本平台同英文的所有译法供一致性预检
    part_baselines: dict[str, dict] = {}
    part_translations: dict[str, dict] = {}
    same_en_variants: dict[str, list[str]] = {}

    reused_path = work / "translated.reused.json"
    if reused_path.exists():
        reused_data = json.loads(reused_path.read_text(encoding="utf-8"))
        for k, entry in reused_data.items():
            en = full_merged.get(k, {}).get("en")
            zh = entry.get("final") if isinstance(entry, dict) else None
            if en and zh:
                bucket = same_en_variants.setdefault(en, [])
                if zh not in bucket:
                    bucket.append(zh)

    total_keys = 0
    for p_in in part_inputs:
        part_baseline = json.loads(p_in.read_text(encoding="utf-8"))
        trans_name = p_in.name.replace("to-translate.", "translated.")
        trans_path = work / trans_name
        part_trans = json.loads(trans_path.read_text(encoding="utf-8"))
        problems = validate(part_baseline, part_trans)
        if problems:
            raise SystemExit(f"{trans_name} 存在 {len(problems)} 个初译校验问题，请先修复后再导出二审包。")
        part_baselines[p_in.name] = part_baseline
        part_translations[trans_name] = part_trans
        total_keys += len(part_baseline)
        # 留存本轮二审前的不可变初译快照，确保补丁可反复幂等重放与回滚
        shutil.copy2(trans_path, work / trans_name.replace("translated.", "translated-draft."))
        for k, entry in part_trans.items():
            en = part_baseline[k]["en"]
            zh = entry["final"]
            if en and zh:
                bucket = same_en_variants.setdefault(en, [])
                if zh not in bucket:
                    bucket.append(zh)

    member_units = 0
    skipped_fast_adopt = 0
    flagged_units = 0
    review_groups: dict[tuple, dict] = {}
    review_order: list[tuple] = []

    for p_in in part_inputs:
        part_baseline = part_baselines[p_in.name]
        trans_name = p_in.name.replace("to-translate.", "translated.")
        part_trans = part_translations[trans_name]
        groups = _load_compact_meta_items(
            work, p_in, platform, part_baseline, full_merged, memory, exact_idx, skel_idx, lower_idx
        )

        for grp in groups:
            cands = grp.get("candidates") or []
            exact_cands = {c["zh"] for c in cands if c.get("match", "exact") == "exact"}
            for member in grp["members"]:
                member_units += 1
                rep_key = member["key"]
                keys = member["keys"]
                t_entry = part_trans[rep_key]
                en = grp["en"]
                draft_zh = t_entry["final"]
                flags = _lint_draft(en, draft_zh, same_en_variants)

                is_fast_exact_adopt = (
                    member.get("tier", grp.get("tier")) == "fast"
                    and "previous_en" not in grp
                    and t_entry.get("source") == "adopt"
                    and draft_zh in exact_cands
                    and not flags
                )
                if is_fast_exact_adopt:
                    skipped_fast_adopt += 1
                    continue

                rsig = (
                    en,
                    draft_zh,
                    t_entry["source"],
                    grp.get("one_en", ""),
                    grp.get("previous_en", ""),
                    grp.get("previous_zh", ""),
                    t_entry.get("note", ""),
                    tuple(flags),
                )
                if rsig not in review_groups:
                    review_groups[rsig] = {
                        "en": en,
                        "zh": draft_zh,
                        "source": t_entry["source"],
                        "flags": flags,
                        "targets": [],
                    }
                    for opt in ("one_en", "previous_en", "previous_zh"):
                        if opt in grp:
                            review_groups[rsig][opt] = grp[opt]
                    if "note" in t_entry:
                        review_groups[rsig]["note"] = t_entry["note"]
                    review_order.append(rsig)
                review_groups[rsig]["targets"].append({
                    "part_file": trans_name,
                    "rep_key": rep_key,
                    "keys": keys,
                })

    queue: list[dict] = []
    for rsig in review_order:
        entry = review_groups[rsig]
        entry["targets"].sort(key=lambda t: t["rep_key"])
        if entry["flags"]:
            flagged_units += 1
        queue.append(entry)
    # 带预检标记的条目优先排在前部，便于二审集中审阅，同组内按代表 key 排序
    queue.sort(key=lambda q: (0 if q["flags"] else 1, q["targets"][0]["rep_key"]))

    _write_prompts(work)
    total_rparts = (len(queue) + review_chunk - 1) // review_chunk if queue else 0
    pwidth = max(2, len(str(total_rparts)))
    r_id_width = max(3, len(str(len(queue))))
    review_files: list[str] = []

    for idx in range(total_rparts):
        chunk_slice = queue[idx * review_chunk : (idx + 1) * review_chunk]
        ai_items: dict[str, dict] = {}
        meta_items: dict[str, dict] = {}
        for offset, entry in enumerate(chunk_slice):
            rid = f"R{idx * review_chunk + offset + 1:0{r_id_width}d}"
            rep_keys = [t["rep_key"] for t in entry["targets"]]
            ai_obj: dict = {
                "k": rep_keys[0] if len(rep_keys) == 1 else rep_keys,
                "en": entry["en"],
                "zh": entry["zh"],
            }
            if "one_en" in entry:
                ai_obj["one"] = entry["one_en"]
            if "previous_en" in entry:
                ai_obj["p_en"] = entry["previous_en"]
            if "previous_zh" in entry:
                ai_obj["p_zh"] = entry["previous_zh"]
            if "note" in entry:
                ai_obj["note"] = entry["note"]
            if entry["flags"]:
                ai_obj["flags"] = entry["flags"]
            ai_items[rid] = ai_obj
            meta_items[rid] = entry

        rname = f"review.part{idx + 1:0{pwidth}d}.json"
        mname = f"review.part{idx + 1:0{pwidth}d}.meta.json"
        (work / rname).write_text(
            _dump_compact_json({"platform": platform, "part": idx + 1, "count": len(ai_items), "items": ai_items}),
            encoding="utf-8",
        )
        (work / mname).write_text(
            json.dumps({"platform": platform, "part": idx + 1, "items": meta_items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        review_files.append(rname)

    parts_covered = sorted(part_translations.keys())
    plan = {
        "platform": platform,
        "total_keys": total_keys,
        "member_units": member_units,
        "skipped_fast_adopt": skipped_fast_adopt,
        "reviewed_units": len(queue),
        "flagged_units": flagged_units,
        "parts_covered": parts_covered,
        "review_parts": review_files,
    }
    plan_path = work / "review-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not queue:
        summary_path = work / "review-summary.json"
        summary_path.write_text(
            json.dumps({**plan, "patched_units": 0, "patches": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"本轮全部 {member_units} 组均为无风险常规精确复用，免除二审 → {summary_path.relative_to(root)}")
    else:
        print(
            f"导出二审包 {total_rparts} 片（待复核 {len(queue)} 组，其中预检提示 {flagged_units} 组；"
            f"免二审精确复用 {skipped_fast_adopt} 组） → {plan_path.relative_to(root)}"
        )


def main(
    platform: str,
    chunk: int | None = None,
    entries: dict | None = None,
    *,
    fast_chunk: int = 350,
    deep_chunk: int = 120,
    repack: bool = False,
    review: bool = False,
    review_chunk: int = 350,
) -> None:
    if review:
        export_review(platform, review_chunk)
        return

    if chunk is not None:
        if chunk <= 0:
            raise SystemExit("--chunk 必须为正整数")
        deep_chunk = chunk
        fast_chunk = max(chunk, chunk * 3)
    if fast_chunk <= 0 or deep_chunk <= 0:
        raise SystemExit("分片大小必须为正整数")

    dirs = platform_dirs(platform)
    work = dirs["work"]
    root = dirs["raw"].parent.parent.parent
    merged_path = work / "merged.json"
    if not merged_path.exists():
        raise SystemExit(f"missing {merged_path}. 先跑 merge.py")

    full_merged = json.loads(merged_path.read_text(encoding="utf-8"))
    memory_path = work / "translation-memory.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.exists() else {}
    reused_path = work / "translated.reused.json"

    if entries is not None:
        raw_pending = entries
    elif reused_path.exists():
        reused_keys = set(json.loads(reused_path.read_text(encoding="utf-8")).keys())
        existing_tt_path = work / "to-translate.json"
        existing_tt = json.loads(existing_tt_path.read_text(encoding="utf-8")) if existing_tt_path.exists() else {}
        raw_pending = {}
        for k in sorted(full_merged.keys() - reused_keys):
            item = {"en": full_merged[k]["en"]}
            prev_en = existing_tt.get(k, {}).get("previous_en") or memory.get(k, {}).get("en")
            if prev_en and prev_en != item["en"]:
                item["previous_en"] = prev_en
            raw_pending[k] = item
    else:
        raw_pending = full_merged

    all_pending = {
        key: {name: entry[name] for name in ("en", "previous_en") if name in entry}
        for key, entry in raw_pending.items()
    }

    existing_translated_parts = sorted(work.glob("translated.part*.json"))
    completed_baseline: dict[str, dict] = {}
    completed_translated: dict[str, dict] = {}
    if existing_translated_parts:
        if not repack:
            raise SystemExit("已有审校分片。增量更新请先运行 prepare_update.py；续跑旧分片请加 --repack。")
        for tp in existing_translated_parts:
            bp = work / tp.name.replace("translated.", "to-translate.")
            if not bp.exists():
                raise SystemExit(f"缺少已完成分片对应的输入基准: {bp.name}")
            bdata = json.loads(bp.read_text(encoding="utf-8"))
            tdata = json.loads(tp.read_text(encoding="utf-8"))
            problems = validate(bdata, tdata)
            if problems:
                raise SystemExit(f"拒绝 --repack：{tp.name} 存在 {len(problems)} 个校验问题，请先修复。")
            completed_baseline.update(bdata)
            completed_translated.update(tdata)

    stale_patterns = (
        "to-translate.part*.json",
        "translated.part*.json",
        "translated-draft.part*.json",
        "compact.part*.json",
        "compact.part*.meta.json",
        "reply.part*.json",
        "validation.part*.json",
        "review.part*.json",
        "review.part*.meta.json",
        "review-patch.part*.json",
    )
    for pat in stale_patterns:
        for stale in work.glob(pat):
            stale.unlink()
    for meta_name in ("compact-manifest.json", "review-plan.json", "review-summary.json"):
        mp = work / meta_name
        if mp.exists():
            mp.unlink()

    out = work / "to-translate.json"
    out.write_text(json.dumps(all_pending, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"写入 {out.relative_to(root)}  ({len(all_pending)} keys)")

    slice_pending = {k: v for k, v in all_pending.items() if k not in completed_translated}
    exact_idx, skel_idx, lower_idx, prefix_neighbors = _build_knowledge_base(platform)
    # 若 --repack 已有完成部分，将其同步纳入精确、骨架与大小写候选池及前缀邻居
    for k, t_entry in sorted(completed_translated.items()):
        en = full_merged.get(k, {}).get("en", "")
        zh = t_entry.get("final", "")
        if en and zh:
            _index_pair(en, zh, f"{platform}:{k}", exact_idx, skel_idx, lower_idx, prepend=True)
            pref = key_prefix(platform, k)
            if len(prefix_neighbors.get(pref, ())) < 3:
                prefix_neighbors.setdefault(pref, []).append((k, en, zh))

    groups, plural_saved, same_en_saved = _fold_and_group(
        platform, slice_pending, full_merged, memory, exact_idx, skel_idx, lower_idx
    )

    slices: list[tuple[str, list[dict]]] = []
    if groups:
        if len(groups) <= deep_chunk:
            overall_tier = "deep" if any(g["tier"] == "deep" for g in groups) else "fast"
            slices.append((overall_tier, groups))
        else:
            fast_groups = [g for g in groups if g["tier"] == "fast"]
            deep_groups = [g for g in groups if g["tier"] == "deep"]
            for i in range(0, len(fast_groups), fast_chunk):
                slices.append(("fast", fast_groups[i : i + fast_chunk]))
            for i in range(0, len(deep_groups), deep_chunk):
                slices.append(("deep", deep_groups[i : i + deep_chunk]))

    offset_part = 1 if completed_translated else 0
    total_parts = offset_part + len(slices)
    pwidth = max(2, len(str(max(total_parts, 1))))

    completed_part_nums: list[int] = []
    if completed_translated:
        s1 = f"{1:0{pwidth}d}"
        (work / f"to-translate.part{s1}.json").write_text(
            json.dumps(completed_baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (work / f"translated.part{s1}.json").write_text(
            json.dumps(completed_translated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (work / f"validation.part{s1}.json").write_text(
            json.dumps(
                {"total_merged": len(completed_baseline), "total_translated": len(completed_translated), "problem_count": 0, "problems": []},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        completed_part_nums.append(1)

    fast_parts: list[int] = []
    deep_parts: list[int] = []
    for idx, (tier, part_groups) in enumerate(slices, start=offset_part + 1):
        ps = f"{idx:0{pwidth}d}"
        if tier == "fast":
            fast_parts.append(idx)
        else:
            deep_parts.append(idx)

        raw_part: dict[str, dict] = {}
        ai_items: dict[str, dict] = {}
        meta_items: dict[str, dict] = {}
        prefs: set[str] = set()
        id_width = max(3, len(str(len(part_groups))))

        for gidx, g in enumerate(part_groups, start=1):
            cid = f"{gidx:0{id_width}d}"
            rep_keys = [m["key"] for m in g["members"]]
            ai_obj: dict = {
                "k": rep_keys[0] if len(rep_keys) == 1 else rep_keys,
                "en": g["en"],
            }
            if g["has_plural"]:
                ai_obj["p"] = 1
            if "one_en" in g:
                ai_obj["one"] = g["one_en"]
            if "previous_en" in g:
                ai_obj["p_en"] = g["previous_en"]
            if "previous_zh" in g:
                ai_obj["p_zh"] = g["previous_zh"]
            if g["candidates"]:
                ai_obj["c"] = [_format_candidate_hint(c) for c in g["candidates"]]
            ai_items[cid] = ai_obj

            meta_obj: dict = {
                "tier": g["tier"],
                "en": g["en"],
                "candidates": g["candidates"],
                "members": g["members"],
            }
            for opt in ("one_en", "previous_en", "previous_zh"):
                if opt in g:
                    meta_obj[opt] = g[opt]
            meta_items[cid] = meta_obj

            for m in g["members"]:
                for k in m["keys"]:
                    raw_part[k] = slice_pending[k]
                    prefs.add(key_prefix(platform, k))

        ctx_block: dict[str, dict[str, list[str]]] = {}
        for pr in sorted(prefs):
            if pr in prefix_neighbors:
                ctx_block[pr] = {nk: [nen, nzh] for nk, nen, nzh in prefix_neighbors[pr]}

        compact_payload: dict = {
            "platform": platform,
            "part": idx,
            "tier": tier,
            "count": len(ai_items),
        }
        if ctx_block:
            compact_payload["context"] = ctx_block
        compact_payload["items"] = ai_items

        meta_payload = {
            "platform": platform,
            "part": idx,
            "tier": tier,
            "raw_key_count": len(raw_part),
            "items": meta_items,
        }

        (work / f"to-translate.part{ps}.json").write_text(
            json.dumps(raw_part, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (work / f"compact.part{ps}.json").write_text(_dump_compact_json(compact_payload), encoding="utf-8")
        (work / f"compact.part{ps}.meta.json").write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    candidate_hits = sum(1 for g in groups if g["candidates"])
    manifest = {
        "platform": platform,
        "total_pending_keys": len(all_pending),
        "completed_keys": len(completed_translated),
        "remaining_raw_keys": len(slice_pending),
        "compact_units": len(groups),
        "plural_collapsed_saved": plural_saved,
        "same_en_grouped_saved": same_en_saved,
        "candidate_hit_units": candidate_hits,
        "completed_parts": completed_part_nums,
        "fast_parts": fast_parts,
        "deep_parts": deep_parts,
    }
    manifest_path = work / "compact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _write_prompts(work)
    print(
        f"分层导出完成：待译 {len(slice_pending)} keys → 复数折叠 -{plural_saved}，同英文聚合 -{same_en_saved}，"
        f"共 {len(groups)} 组（命中候选 {candidate_hits} 组），切分 fast={fast_parts} deep={deep_parts}"
        + (f"，保留已译 part={completed_part_nums}" if completed_part_nums else "")
    )
    print(f"派发清单 → {manifest_path.relative_to(root)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("--chunk", type=int, default=None, help="兼容参数：指定 deep 分片上限（fast 自动取 3 倍）")
    parser.add_argument("--fast-chunk", type=int, default=350, help="常规片最大组数（默认 350）")
    parser.add_argument("--deep-chunk", type=int, default=120, help="疑难片最大组数（默认 120）")
    parser.add_argument("--repack", action="store_true", help="保留已通过校验的分片为 part01，将剩余条目重切为紧凑分片")
    parser.add_argument("--review", action="store_true", help="导出二审差量复核包")
    parser.add_argument("--review-chunk", type=int, default=350, help="二审包每片最大组数（默认 350）")
    args = parser.parse_args()
    main(
        args.platform,
        args.chunk,
        fast_chunk=args.fast_chunk,
        deep_chunk=args.deep_chunk,
        repack=args.repack,
        review=args.review,
        review_chunk=args.review_chunk,
    )
