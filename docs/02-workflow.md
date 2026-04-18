# 02 · 完整操作流程

从 0 到上线的一条命令链，以 **iOS** 为主线。macOS 在末尾给 delta。

---

## 前置准备

需要 Telegram 账号登录 [translations.telegram.org](https://translations.telegram.org)，并创建一个自定义语言包（可参考 `docs/05-troubleshooting.md#创建语言包参数建议`）。

---

## Step 1 · 下载三件套

详见 `docs/SOURCES.md`。把以下文件放到 `data/ios/raw/`：

| 文件 | 来源 |
|---|---|
| `en.strings` | https://translations.telegram.org/en/ios/ → Export |
| `official-zh.strings` | https://translations.telegram.org/zh-hans/ios/ → Export |
| `zhcncc.strings` | https://translations.telegram.org/zhcncc/ios/ → Export（可能要先 fork） |

> 可选：更多参考源命名为 `ref-<name>.strings` 放入同目录，`merge.py` 自动识别。

---

## Step 2 · 解析 + 对齐 + 分片

```bash
cd /Users/owen/Projects/Self/tg-lang-refine

python3 scripts/parse_strings.py ios          # .strings → JSON
python3 scripts/merge.py ios                  # 对齐三源 → merged.json
python3 scripts/export_for_ai.py ios --chunk 500   # 切 30 片 + PROMPT.md
```

产物：
- `work/ios/merged.json`（全量对齐视图）
- `work/ios/to-translate.partNN.json`（30 片，喂给 AI）
- `work/ios/PROMPT.md`（翻译 AI 任务说明）

---

## Step 3 · 喂给翻译 AI

两条路径二选一，详见 `docs/05-troubleshooting.md#喂-ai-的两种模式`。

**核心交付合约**：AI 必须输出符合下列结构的 JSON：

```json
{
  "<key>": {
    "final": "<最终译文>",
    "source": "adopt | rewrite_ref | rewrite_official | fresh",
    "note": "<可选备注>"
  }
}
```

**单片校验必须跑**（AI 每完成一片必做）：
```bash
python3 scripts/import_from_ai.py ios --part N
```
问题数必须为 0。

---

## Step 4 · 合并 + 全局规则统一

```bash
python3 scripts/merge_parts.py ios            # 30 片 → translated.json
python3 scripts/normalize.py ios              # dry-run, 看影响面
python3 scripts/normalize.py ios --apply      # 真改, 自动备份 .bak
```

`normalize` 当前规则：
- `您` → `你`
- `...` / `....` → `…`
- `。。。` → `…`

`--apply` 会在 `work/ios/translated.partNN.json.bak` 留备份，回滚：
```bash
for f in work/ios/translated.part*.json.bak; do mv "$f" "${f%.bak}"; done
python3 scripts/merge_parts.py ios   # 重新合并
```

---

## Step 5 · 全量校验 + 审核报告 + 打包

```bash
python3 scripts/import_from_ai.py ios         # 全量校验 → validation.json
python3 scripts/diff_report.py ios            # HTML 审核报告
python3 scripts/build_strings.py ios          # 最终 .strings
```

产物：
- `work/ios/validation.json`（问题清单，理想 0 问题）
- `work/ios/report.html`（浏览器打开，按 source 分组审核）
- `dist/ios/zh-Hans-custom.strings`（**上传用的最终文件**）

---

## Step 6 · 上传到 Telegram

1. 打开 [translations.telegram.org](https://translations.telegram.org) → 自己的自定义语言包
2. 进入 **iOS 平台页面**（点击 iOS 图标或左侧 iOS 入口）
3. 点 **Import phrases** → 上传 `dist/ios/zh-Hans-custom.strings`
4. 等待识别完成，页面下方会显示 `Modified Phrases` 数量
5. 点击右上角 **EDIT PHRASES** 把翻译真正入库（**关键一步**，不点等于白传）
6. iPhone Telegram 打开 Sharing Link（形如 `https://t.me/setlanguage/<short-name>`）
7. 点击确认切换到自定义语言包

**已知限制**：
- 单次批量入库 ~1000 条后需刷新再继续，属 Telegram 平台节流
- 约 54 条安全/法律敏感 key 会被平台拒收，返回 `affected_cnt: 0`，详见 `docs/05-troubleshooting.md#安全保留-key-白名单`

---

## macOS 流程 Delta

Telegram macOS 是**独立字符串集**，要单独跑一遍，把上面所有命令的 `ios` 替换为 `macos`：

```bash
# Step 1: 下载 data/macos/raw/ 三件套 (地址把 /ios/ 改成 /macos/)
python3 scripts/parse_strings.py macos

# Step 1.5 (推荐): 把 iOS 精修结果注入为 macOS 额外参考源
# 以英文原文为对齐维度, 实测能预填 ~49% (iOS 14923 条 → macOS 命中 4731 条)
python3 scripts/seed_ios_ref.py
python3 scripts/parse_strings.py macos     # 重跑以识别新生成的 ref-ios-refined

python3 scripts/merge.py macos             # 输出会多一行 "ios-refined 覆盖: N/M"
python3 scripts/export_for_ai.py macos --chunk 500
# Step 3-5: 同 iOS (AI 看到 refs.ios-refined 会大量 adopt)
python3 scripts/merge_parts.py macos
python3 scripts/normalize.py macos --apply
python3 scripts/import_from_ai.py macos
python3 scripts/diff_report.py macos
python3 scripts/build_strings.py macos
# Step 6: 上传到同一语言包的 macOS 平台页面
```

TDesktop 也是**独立字符串集**，流程与 iOS 基本相同，不需要 `seed_ios_ref.py` 这类跨平台复用步骤，直接跑：

```bash
# Step 1: 下载 data/tdesktop/raw/ 三件套 (地址把 /ios/ 改成 /tdesktop/)
python3 scripts/parse_strings.py tdesktop
python3 scripts/merge.py tdesktop
python3 scripts/export_for_ai.py tdesktop --chunk 500
# Step 3: 用外部 AI / 子代理逐片翻译 translated.partNN.json
python3 scripts/merge_parts.py tdesktop
python3 scripts/normalize.py tdesktop              # dry-run, 看影响面
python3 scripts/normalize.py tdesktop --apply      # 真改, 自动备份 .bak
python3 scripts/import_from_ai.py tdesktop
python3 scripts/diff_report.py tdesktop
python3 scripts/build_strings.py tdesktop
# Step 6: 上传到 translations.telegram.org 的 tdesktop 平台页面
```

---

## 迭代维护

日常用 Telegram 攒"不顺眼"的条目 → 在 `work/ios/translated.json` 里改对应 key 的 `final` 字段 → 重跑 `build_strings.py` → 上传新 `.strings` → 再点一次 `EDIT PHRASES`。Telegram 客户端会周期性拉取更新，不用重新点 Sharing Link。
