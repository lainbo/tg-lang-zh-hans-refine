# 02 · 完整操作流程

## 日常增量维护

### 1. 导出官方英文

在已登录浏览器中，导出 Android、iOS、TDesktop 或 macOS 原生客户端的英文；安卓为 `.xml`，其他平台为 `.strings`，详见 [SOURCES.md](SOURCES.md)。保留下载文件原名，交给下一步记录版本与校验和。官方简中和社区包按具体疑点查阅本地存档，需要最新官方简中时再单独下载。

### 2. 备份并准备增量

保留旧 `merged.json`、`translated.json` 和 raw 源文件，使用实际下载路径：

```bash
python3 scripts/prepare_update.py ios \
  --en ~/Downloads/ios_en_VERSION.strings \
  --chunk 100
```

输出：

- `history/<时间>/`：旧 raw、parsed、work 文件与 dist 的完整归档。
- `merged.json`：当前全量英文。
- `update.json`：英文来源文件名、SHA-256、备份位置、新增/变化/删除 key 与复用数量。
- `translated.reused.json`：原文未变的已校验译文。
- `translation-memory.json`：上一轮英文与精修译文的配对记录，供初译后按需核对。
- `to-translate.json` 与 `to-translate.partNN.json`：本轮待审校英文，变化条目包含 `previous_en`。
- `PROMPT.md`：包含共用术语表的审校合约。

当前全量译文不完整时，脚本会停止，先完成当前轮再启动下一轮。

### 3. 理解原文、翻译与复核

翻译 AI 先读 `PROMPT.md` 和共用术语表，以英文、key、同功能上下文确定含义。分片外的相关英文可在 `merged.json` 中查找；有歧义时查看客户端界面或官方源码。

按相关 key 查 `translation-memory.json` 中成对的旧英文与精修译文，核对术语和表达。跨平台可查阅当前精修主文件及其英文基准；用途、参数角色和格式适用时直接复用，其余内容改写或新译。相同英文可合并审阅，并逐个核对不同 key 的用途。遇到具体疑点才查官方简中或社区包；在备注中写明来源和判断依据。参考译文不能单独证明功能含义。

初译完成后，单独再做一遍复核：逐条对照当前英文检查主体、对象、条件、否定、范围、后果和参数角色，再检查同功能、各平台和复数分支的一致性。可以由同一 AI 在独立步骤完成，也可在新会话中审校。模型版本变化不减少复核要求。

输出结构：

```json
{
  "<key>": {
    "final": "最终译文",
    "source": "fresh",
    "note": "需要记录时，说明语义判断、术语例外或上下文依据。"
  }
}
```

英文独立翻译使用 `fresh`。实际采用或改写已有译文时，如实使用 `adopt`、`rewrite_ref` 或 `rewrite_official` 并记录来源，详见 [数据格式](04-data-format.md)。每片保存为对应的 `translated.partNN.json` 后执行：

```bash
python3 scripts/import_from_ai.py ios --part 1
```

每片问题数须为 0。在 `work/<平台>/review.md` 记录实际复核范围、术语决策、歧义依据和未决项；影响含义的疑点解决后再完成审校。首次聊天模式由维护者保存该记录。

英文未变的译文默认保留。发现既有错误、语境变化或术语冲突时，定向列入审校：将该 key 的英文加入待译总表与对应分片，从 `translated.reused.json` 移出，在 `update.json` 的 `reviewed_existing` 记录，并更新 `reused_count`。输出 key 应与对应输入分片一致。不要仅因模型升级全量重译。

### 4. 合并、规范化、校验与打包

```bash
python3 scripts/merge_parts.py ios
python3 scripts/normalize.py ios
# 查看 normalize-report.md；有命中且全部符合上下文时：
python3 scripts/normalize.py ios --apply
python3 scripts/import_from_ai.py ios
python3 scripts/diff_report.py ios --update
python3 scripts/diff_report.py ios
python3 scripts/build_strings.py ios
```

合并后以 `translated.json` 为主文件。`normalize` 直接修改它，并创建 `translated.json.bak`。后续人工修订也修改主文件，然后重新校验、生成报告并打包；不要重新合并旧片覆盖这些修改。

结构校验和语义审校均完成后，最终文件为 `dist/ios/zh-Hans-custom.strings`。本轮报告 `update-report.html` 按新增、英文变化和既有修订分组，展示当前英文、变化前英文、旧精修译文和最终译文；全量审查打开 `report.html`。

### 5. 人工上传

1. 进入自定义语言包对应平台页面，先导出当前线上包作为备份。
2. 点击 **Import phrases**，选择对应 `dist/<platform>/zh-Hans-custom.strings`。
3. 核对识别结果，点击 **EDIT PHRASES → EDIT ALL** 提交，观察剩余数量。
4. 若只保存了一部分后停住，刷新页面继续提交；需要重新选文件时，重传同一份成品。每轮记录剩余 key，有新增写入就继续。
5. 同一批 key 连续两次刷新重试均无变化，且导出也无新增写入时，停止批量重传，按 [上传停滞与残留判断](05-troubleshooting.md#上传停滞反复提交与停止条件) 核对平台保护、建议未采用或没有可编辑条目等情况。
6. 导出更新后的线上包，与本地成品逐条对比，保存实际写入数、残留清单和查证依据。网站显示 `100%` 也要完成此核验。
7. 在客户端打开语言包 Sharing Link 并检查实际显示。

上传可能需要多轮；临时停滞的原因应根据网站提示判断。固定残留不必靠反复重传追求归零，本地校验也不能替代线上导出与客户端验收。

Android、TDesktop 和 macOS 原生客户端按同样步骤独立更新，命令中的 `ios` 改为 `android`、`tdesktop` 或 `macos`，下载文件也必须属于对应平台。安卓构建成品为 `dist/android/zh-Hans-custom.xml`。

## 首次初始化

从零开始时，只需将英文放入 `data/<platform>/raw/en.strings`（安卓为 `en.xml`），然后：

```bash
python3 scripts/parse_strings.py ios
python3 scripts/merge.py ios
python3 scripts/export_for_ai.py ios --chunk 100
```

已有官方简中和参考包可以保留，默认输入只导出英文。首次没有本项目翻译记忆，按上述第 3～5 步完成全量翻译和审校；以后使用 `prepare_update.py` 增量维护。

## 恢复备份

单次规范化可复制 `translated.json.bak` 回 `translated.json` 后重新校验和打包。

整轮回滚时，先另存当前状态，再将 `update.json` 所指归档内的 raw、parsed、work、dist 分别恢复到对应平台目录。不要混用不同轮次的英文基准和最终译文。
