# tg-lang-refine

Telegram 简体中文语言包精修工具链。以 **官方英文** 为基准，**官方简中 + 历史精修包 + 冻结社区参考包（@zhcncc 等）** 为翻译记忆，交给外部翻译 AI 审校，本地打包后上传到 translations.telegram.org。

## 底层逻辑

```
官方英文 (baseline)
   ├── 官方简中 (机翻味重, 待改版)
   ├── 当前精修包 (增量维护的主要参考源)
   └── @zhcncc 等冻结社区包 (首次翻译参考源)
              ↓
       按 key 对齐合并 (merge.py)
              ↓
       导出给翻译 AI 审校 (export_for_ai.py)
              ↓
       [外部翻译 AI 工作]
              ↓
       导入 AI 输出 (import_from_ai.py)
              ↓
       生成 .strings 最终产物
              ↓
       手动上传 translations.telegram.org
```

## 目录结构

```
tg-lang-refine/
├── data/
│   ├── ios/
│   │   ├── raw/          # 原始下载文件 (.strings)
│   │   │   ├── en.strings           ← 官方英文 baseline
│   │   │   ├── official-zh.strings  ← 官方简中 (机翻版)
│   │   │   ├── ref-current-refined.strings ← 当前精修包, 增量维护参考
│   │   │   └── zhcncc.strings       ← @zhcncc 冻结历史参考包
│   │   └── parsed/       # 解析后的 JSON (scripts 产出)
│   └── macos/            # 历史产物, 已停止维护
├── work/
│   ├── ios/
│   │   ├── merged.json       ← 多源对齐
│   │   ├── to-translate.json ← 喂给翻译 AI
│   │   ├── translated.json   ← 翻译 AI 回写
│   │   └── report.html       ← 审核对比视图
├── dist/
│   └── ios/
│       └── zh-Hans-custom.strings  ← 上传用的最终产物
├── scripts/   # Python 脚本, 无第三方依赖
└── docs/
    └── SOURCES.md   # 如何下载三个源文件
```

## 使用流程 (iOS)

### 1. 下载源文件
详见 `docs/SOURCES.md`。增量维护时把两个官方 .strings 文件放到 `data/ios/raw/`:
- `en.strings` (官方英文)
- `official-zh.strings` (官方新出的简中, 你要替换掉的那版)

`zhcncc.strings` 只作为首次翻译时留下的冻结参考源，后续不再要求下载新版。每次增量前先把当前精修包保存成参考源：

```bash
cp dist/ios/zh-Hans-custom.strings data/ios/raw/ref-current-refined.strings
```

### 2. 解析成 JSON
```bash
python3 scripts/parse_strings.py ios
```

### 3. 对齐合并
```bash
python3 scripts/merge.py ios
```
产出 `work/ios/merged.json`, 每个 key 带 `{en, official_zh, refs: {"current-refined": "...", "zhcncc": "..."}}`。

### 4. 导出给翻译 AI
```bash
python3 scripts/export_for_ai.py ios
```
产出 `work/ios/to-translate.json` 和 `work/ios/PROMPT.md` (建议的翻译 AI prompt)。

### 5. 翻译 AI 工作 (外部)
你把 `to-translate.json` + `PROMPT.md` 丢给你的翻译 AI, 得到 `translated.json`, 放回 `work/ios/`。

格式约定:
```json
{
  "lng_chat_typing": {
    "final": "对方正在输入…",
    "source": "rewrite_ref",    // 采用/改写/重写, 便于审核
    "note": ""                  // 可选, 改写原因
  }
}
```

### 6. 生成审核报告
```bash
python3 scripts/diff_report.py ios
```
产出 `work/ios/report.html`, 浏览器打开, 按 source 分类高亮, 重点看 `改写/重写` 的条目。

### 7. 打包
```bash
python3 scripts/build_strings.py ios
```
产出 `dist/ios/zh-Hans-custom.strings`, 上传到你自己的 Telegram 自定义语言包。

## 平台维护状态

- iOS：继续维护。
- TDesktop：继续维护，和 iOS 是独立字符串集，需要单独跑。
- macOS：停止维护，保留历史产物，不再下载和上传。

## 设计原则

- **零外部依赖**: 纯 Python 标准库, `python3` 直接跑。
- **可审可回滚**: 每一步都产出中间文件, 出问题能定位到条目。
- **翻译与流水线解耦**: 本项目不做翻译, 只做数据搬运和审核辅助。
