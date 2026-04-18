# tg-lang-refine

Telegram 简体中文语言包精修工具链。以 **官方英文** 为基准，**官方简中 + 社区参考包（@zhcncc 等）** 为翻译记忆，交给外部翻译 AI 审校，本地打包后上传到 translations.telegram.org。

## 底层逻辑

```
官方英文 (baseline)
   ├── 官方简中 (机翻味重, 待改版)
   └── @zhcncc 等社区包 (参考源)
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
│   │   │   └── zhcncc.strings       ← @zhcncc 社区参考包
│   │   └── parsed/       # 解析后的 JSON (scripts 产出)
│   └── macos/            # 同构, 处理 macOS 包
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
详见 `docs/SOURCES.md`。把三个 .strings 文件放到 `data/ios/raw/`:
- `en.strings` (官方英文)
- `official-zh.strings` (官方新出的简中, 你要替换掉的那版)
- `zhcncc.strings` (参考包, @zhcncc)

### 2. 解析成 JSON
```bash
python3 scripts/parse_strings.py ios
```

### 3. 对齐合并
```bash
python3 scripts/merge.py ios
```
产出 `work/ios/merged.json`, 每个 key 带 `{en, official_zh, refs: {zhcncc: "..."}}`。

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
    "source": "zhcncc",         // 采用/改写/重写, 便于审核
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

## macOS 流程

把 iOS 换成 `macos` 或 `tdesktop` 即可。它们都是独立字符串集, 需要各自单独跑一遍。

## 设计原则

- **零外部依赖**: 纯 Python 标准库, `python3` 直接跑。
- **可审可回滚**: 每一步都产出中间文件, 出问题能定位到条目。
- **翻译与流水线解耦**: 本项目不做翻译, 只做数据搬运和审核辅助。
