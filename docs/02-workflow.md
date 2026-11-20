# 02 · 完整操作流程

## 日常增量维护（标准流程）

多平台同时更新时，建议按待译规模由小到大**单平台串行**执行（如 `ios` → `tdesktop` → `android` → `macos`）。前序平台合并出新的 `translated.json` 后，下一平台运行导出脚本时会自动把刚产出的译文纳入跨端候选池，避免四端重复新译同一功能。

### 1. 导出官方英文

在已登录浏览器中，导出 Android、iOS、TDesktop 或 macOS 原生客户端的英文；安卓为 `.xml`，其他平台为 `.strings`，详见 [SOURCES.md](SOURCES.md)。保留下载文件原名，交给下一步记录版本与校验和。

### 2. 备份并导出分层紧凑分片

保留旧 `merged.json`、`translated.json`、parsed 数据与成品，传入实际下载路径：

```bash
python3 scripts/prepare_update.py ios \
  --en ~/Downloads/ios_en_VERSION.strings
```

若工作区此前已跑过 `prepare_update.py`，需要生成或重新切分紧凑分片：
- 尚无已译分片：`python3 scripts/export_for_ai.py ios`
- 已有部分校验通过的旧分片需续跑：`python3 scripts/export_for_ai.py ios --repack`（脚本将已完成分片合并保留为 `part01`，仅把剩余未译条目重切为紧凑分片）

输出产物：
- `history/<时间>/`：旧 raw、parsed、work 文件与 dist 的归档；其中的下载原件及复制件在任务结束时清理。
- `merged.json`：当前全量英文基准。
- `update.json`：英文来源文件名、SHA-256、备份位置、新增/变化/删除 key 与复用数量。
- `translated.reused.json`：原文未变的已校验译文。
- `translation-memory.json`：上一轮英文与精修译文的配对记录。
- `to-translate.json` 与 `to-translate.partNN.json`：本轮待审校原始 key 账本与各分片原始基准。
- `compact-manifest.json`：分片派发清单，列出复数折叠数、同英文聚合数、候选命中数、`fast_parts` 与 `deep_parts`。
- `compact.partNN.json` 与 `compact.partNN.meta.json`：前者为单行紧凑结构的 AI 输入分片（已折叠复数、聚合相同英文，并预注入四端候选 `c`、变更旧译 `p_en`/`p_zh` 与同前缀邻居 `context`，默认 `fast` ≤350 组/片，`deep` ≤120 组/片）；后者仅供脚本展开和二审筛选使用，AI 无需读取。
- `PROMPT.md`、`PROMPT.fast.md`、`PROMPT.deep.md`、`PROMPT.review.md`：总合约、常规片指令、疑难片指令与二审指令。

### 3. 独立子代理初译与单片展开校验

主会话读取 `work/ios/compact-manifest.json` 查看 `fast_parts` 与 `deep_parts`，不在主会话通读 `merged.json` 或 `translation-memory.json`，也不在同一个长会话里连续处理大量分片。

针对每个待译 `compact.partNN.json` 派发一个干净的独立子代理：
1. 子代理首轮**并行**读取对应档位的指令文件（`tier == "fast"` 读 `work/ios/PROMPT.fast.md`；`tier == "deep"` 读 `work/ios/PROMPT.deep.md`）和 `work/ios/compact.partNN.json`（不读 `.meta.json`）。
2. 全程使用用户选定的同一主力翻译模型；若宿主子代理支持调节思考强度，`fast` 片设为低/中档、`deep` 片设为高档；若宿主仅支持选模型，直接用同一模型派发。
3. 依据片内已内联的 `context`、`c` 和 `p_zh` 完成判断，直接写出纯 JSON 文件 `work/ios/reply.partNN.json` 后结束子会话（仅当 `deep` 片内信息仍无法确认参数内容或功能含义时，才定向查阅客户端源码或本端最小必要上下文）：

```json
{
  "001": "=",
  "002": "=1",
  "003": "=prev",
  "004": "已向 **%d** 位用户发送邀请。",
  "005": ["此礼物已移至你的个人资料。", "rewrite_ref", "rewrite:ios:Gift.MoveToWallet.Success 调整目标位置"],
  "006": {"*": "名称", "Checkout.Name": "姓名"}
}
```

短编号取值约定：
- `"="` 或 `"=0"`、 `"=1"`：核对 key 所属业务模块与参数角色一致后，采用对应下标的候选 `c`；脚本自动展开为完整译文、`"source": "adopt"` 及 `"adopt:<platform>:<key>"` 备注。
- `"=prev"`：仅用于英文微调条目，确认旧译 `p_zh` 在新英文下仍完全准确且占位符一致时沿用。
- `"最终译文"`：独立新译（默认展开为 `"source": "fresh"`）。
- `["最终译文", "source", "note"]`：基于候选/参考包改写（`rewrite_ref` / `rewrite_official`）或需要附加备注时使用（第 3 项备注可选）。
- `{"*": "默认译文", "特殊Key": "特殊译文"}`：当 `k` 为多个共享相同英文的 key 列表且个别 key 存在语境差异时，按 key 分别指定译文（对象值同样支持 `"="`、数组或字符串）。

每片回传完成后，在主会话执行展开与结构校验：

```bash
python3 scripts/import_from_ai.py ios --part 1
```

脚本会将短编号、同英文聚合组及折叠的复数分支自动展开写入标准 `translated.part01.json`，并对照 `to-translate.part01.json` 校验 100% 原始 key 覆盖与占位符一致性，问题数须为 0。

### 4. 本地规则预检与差量二审（只输出修改补丁）

全部初译分片校验通过后，导出二审差量复核包：

```bash
python3 scripts/export_for_ai.py ios --review
```

- 脚本先为所有已校验初译分片留存不可变快照 `translated-draft.partNN.json`，并对术语表高确定性专名、称呼/省略号、首尾空白、长度比例与本端同英文多译差异做静态预检（命中项附 `flags` 置顶排序）。
- 常规片（`fast`）中精确复用四端候选、非原文变更且未命中任何预检提示的词条自动豁免二审；其余所有新译、改写、投影/模糊候选复用、疑难词条及预检提示项导出为 `work/ios/review.partNN.json`（默认 ≤350 组/片，脚本映射存于 `.meta.json`）。若本轮全部词条均属豁免范围，脚本直接生成 `review-summary.json`。
- 对每个 `review.partNN.json` 派发独立复核子代理，首轮并行读取 `work/ios/PROMPT.review.md` 与 `work/ios/review.partNN.json`，优先核查带 `flags` 的条目，再逐条核对主体、否定、条件边界、参数角色与术语一致性。
- **差量输出 `work/ios/review-patch.partNN.json`**：确认无误的词条一律不输出；整片无问题直接输出 `{}`；仅对需修正项输出补丁（多 key 组支持只列出需要改动的 key）：

```json
{
  "R004": "修正后的最终译文",
  "R012": ["修正后的最终译文", "fresh", "修正原因说明"],
  "R019": {"Checkout.Name": "姓名"}
}
```

所有二审分片补丁生成后，应用补丁并自动复检全部分片：

```bash
python3 scripts/import_from_ai.py ios --review
```

脚本始终基于 `translated-draft.partNN.json` 幂等重放全部补丁（不改动 `reply.partNN.json`，修改或删除某条补丁后重跑即可完整回退）。参考生成的 `work/ios/review-summary.json`，在 `work/ios/review.md` 记录实际复核范围（含复数折叠、同英文聚合、预检提示数、精确复用免审数、二审复核数与修正数）、术语决策、歧义查证依据及客户端待验收项。

英文未变的既有译文默认保留。发现既有错误、语境变化或术语冲突需定向修订时，将该 key 从 `translated.reused.json` 移出，在 `update.json` 的 `reviewed_existing` 中记录并更新 `reused_count`，再运行 `python3 scripts/export_for_ai.py ios`（已有部分完成分片时加 `--repack`）。

### 5. 合并、规范化、校验与打包

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

`merge_parts.py` 会检查二审完成状态（`review-summary.json`）及全部分片覆盖与占位符门禁。合并后以 `translated.json` 为唯一主文件；后续人工微调直接改 `translated.json`，再重新校验、生成报告并打包，不要重新合并分片覆盖主文件修改。

完整成品为 `dist/ios/zh-Hans-custom.strings`，上传文件为 `dist/ios/zh-Hans-custom.upload.strings`（安卓分别为 `.xml` 与 `.upload.xml`）。本轮报告 `update-report.html` 按新增、英文变化和既有修订分组展示。

### 6. 人工上传

1. 进入自定义语言包对应平台页面，先导出当前线上包，解析为 key/value JSON 保存可回滚备份，并记录导出版本与 SHA-256。
2. 点击 **Import phrases**，选择打包生成的上传文件 `dist/<platform>/zh-Hans-custom.upload.strings`（安卓为 `.upload.xml`），详见 [上传文件只保留中文使用的复数分支](05-troubleshooting.md#上传文件只保留中文使用的复数分支)。
3. 核对识别结果，点击 **EDIT PHRASES → EDIT ALL** 提交，观察剩余数量。
4. 若保存一部分后停住，刷新页面继续提交；需要重新选文件时，重传同一份上传文件。每轮记录剩余 key，有新增写入就继续。
5. 同一批 key 连续两次刷新重试均无变化，且重新导出也无新增写入时，停止批量重传，按 [上传停滞与残留判断](05-troubleshooting.md#上传停滞反复提交与停止条件) 核对平台限制。
6. 导出更新后的线上包，与本地成品逐条对比，保存实际写入数、残留清单和查证依据。网站显示 `100%` 也要完成此核验。
7. 在客户端打开语言包 Sharing Link 并检查实际显示。

### 7. 清理下载资源

每次任务结束都执行 [下载资源清理规则](../AGENTS.md#维护铁律)，包括仅检查更新且没有新增或变化的情况。确认来源记录、英文基准、所需参考数据、译文及回滚备份已保存后，删除下载原件和项目、历史归档中的复制件，再核对清理结果。

## 首次初始化

从零开始时，将英文放入 `data/<platform>/raw/en.strings`（安卓为 `en.xml`），然后运行：

```bash
python3 scripts/parse_strings.py ios
python3 scripts/merge.py ios
python3 scripts/export_for_ai.py ios
```

随后按上述第 3～7 步完成子代理分片初译、差量二审、合并打包、上传与资源清理；后续更新统一使用 `prepare_update.py`。

## 恢复备份

单次规范化可复制 `translated.json.bak` 回 `translated.json` 后重新校验和打包。

整轮回滚时，先另存当前状态，再将 `update.json` 所指归档内的 parsed、work、dist 分别恢复到对应平台目录。raw 中的下载资源已在任务结束时清理，英文基准以归档的 `parsed/en.json` 与 `work/merged.json` 为准。不要混用不同轮次的英文基准和最终译文。
