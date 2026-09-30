# 05 · 故障排查与上传经验

---

## 上传停滞、反复提交与停止条件

上传可能需要分几轮完成：文件已识别，点击 **EDIT PHRASES → EDIT ALL** 后先保存几百条，随后 `Processing` 停住；刷新页面后再次提交，有时还能继续写入。每轮可保存的数量不固定。可能涉及临时限流、请求中断或服务端批次处理，页面没有明确错误时，只记录实际现象，不直接认定原因。

### 遇到停滞时怎么做

1. 上传前先用 **Import/Export → EXPORT FILE** 导出当前线上包，保留可回滚备份。
2. 上传对应平台的 `.strings` 或 Android `.xml`，记录 `Modified Phrases` 的数量，点击 **EDIT PHRASES → EDIT ALL**。文件上传完成只代表已解析，最终还要确认译文已经保存。
3. 只要剩余数量仍在下降，就让当前提交继续。数量持续不变时刷新页面；页面仍保留待修改列表时，直接再次提交；列表消失或要求选文件时，重新上传**同一份成品**再提交。
4. 每轮记录剩余数量与 key。仍有新增写入就继续；如网站明确提示限流或等待时间，按提示等待后再试。
5. **同一批 key 连续两次刷新重试都没有变化，且重新导出的线上包也没有新增写入时，停止批量重传，转为核对残留。** 不以固定条数或必须归零为停止标准。

### 最后剩下的条目可能是什么

| 现象 | 可能原因或已知依据 | 处理 |
|---|---|---|
| 安全提示、反诈、权限确认、语言切换或固定链接持续无法写入 | 可能受平台保护；部分条目在详情中标记 `CRITICAL` | 对照历史记录，抽查少量代表条目；确认建议未被采用、导出也未改变后，记录为平台残留并停止重复提交 |
| 单条提交后能看到自己的译文，但导出里仍没有 | 可能只保存为翻译建议，尚未成为实际采用的译文 | 以重新导出结果为准，不把建议提交成功计为已发布 |
| 导出仍为英文，导入列表却不包含它，按完整 key 搜索显示 `No phrases found` | 网站当前可能没有可编辑条目，或该条目由平台固定处理；仅凭此现象无法确定具体机制 | 记录 key、英文内容和查询结果，保留本地译文，不反复重传整包 |
| 普通界面文案残留，且不符合以上情形 | 仍需排查平台选错、源版本变化、占位符或格式问题 | 对照当前英文、本地校验与网站具体报错，定向修复；不要直接归入平台限制 |

历史残留常见类别与示例：

- 登录与安全：`AUTH_REGION`、`PUSH_AUTH_*`、`Login.ResetAccountProtected.*`、`AuthCode.Alert`。
- 反诈与权限：`Conversation.ScamWarning`、`UserInfo.FakeUserWarning`、`Conversation.ShareBot*`。
- 隐私、付款和语言切换：`Checkout.LiabilityAlert`、`Passport.AcceptHelp`、`ApplyLanguage.*`、`Settings.AppLanguage`。
- 固定链接与平台声明：`Settings.PrivacyPolicy_URL`、`WebApp.TermsOfUse_URL`、`Chat.PsaTooltip.psa`。

这些示例用于定位问题，具体 key 和数量会随版本变化。客户端对受限或缺失条目的回退显示需另行验收，不能从上传页直接确认。

### 验收与记录

保存上传前后导出，按 key 对比本地成品，将结果分成：实际新增或修改并保存、已有且一致、未导出、已导出但仍不同。英文与简中文件包含的复数分支可能不同，不能直接用英文总 key 数减去简中导出总数判断漏传；结合当前简中 key 集合与导入预览核对。

**以实际导出核验为准。** 导出弹窗的 `100%`、侧栏“未译”数量、导入剩余数量可能采用不同口径。记录每轮剩余 key、最终差异、抽查依据和文件 SHA-256，明确哪些已发布、哪些仍未写入。原始导出与详细差异放在 `work/maintenance/`，该目录被 Git 忽略；可复用经验应写入本文档。

### 2026-09-28 实测，供以后快速对照

| 平台 | 导入识别变更 | 实际保存变更 | 刷新重试后的固定残留 | 导出中与本地一致 | 导出中仍不同 |
|---|---:|---:|---:|---:|---:|
| iOS | 414 | 341 | 73 | 11,874 | 5 |
| TDesktop | 336 | 299 | 37 | 8,287 | 0 |
| macOS | 3,391 | 3,350 | 42 | 8,287 | 2 |

本次刷新后再次提交，固定残留未减少。浏览器未显示明确限流原因。抽查 iOS `AUTH_REGION`，页面标记 `CRITICAL`；单条提交后显示为翻译建议，重新导出仍未包含该 key。

iOS 另有 5 个 key 在导出中保持英文，官方简中导出也同样为英文：`AppUpgrade.Running`、`Login.PhonePaidEmailText`、`PUSH_CHAT_PHOTO_EDITED`、`PUSH_CHAT_TITLE_EDITED`、`ProfileLevelInfo.MyDescriptionToday_1`。前两个按完整 key 搜索显示 `No phrases found`。这 5 条不在导入页的 73 条待修改清单中，需单独记录。

当时两个平台的导出弹窗均显示 `100%`，侧栏分别还有 75、38 条未译。上述表格由实际导出逐条比较得到，不能把 73／37 当成以后版本的固定上限。原始记录位于本地 `work/maintenance/upload-2026-09-28/`，包含上传前后导出、`verification.json` 和可重复核验的 `verify_upload.py`；本节保留了无需本地工件也能使用的判断依据。

macOS 实际新增 361 条、更新 2,989 条。最后 42 条经过连续两次刷新重试，key 集合和线上导出均保持不变；抽查 `ChannelInfo.ScamWarning` 标记为 `CRITICAL`，表单只有提交建议的 `SUBMIT`。导出弹窗显示 `100%`，侧栏仍显示 44 条未译。原始导出、残留清单和核验脚本位于 `work/maintenance/upload-macos-2026-09-28/`。

macOS 还遇到两类需要单条处理的导入差异：

- **同名普通字符串与复数词条同时存在**：官方英文导出同时含 `Star.Auction.Preview.TopBidders` 的完整旧句和 `_other` 等复数分支；网页当前编辑的是 `top %d bidders`。上传文件省略无后缀旧句，单独应用 `_other` 的译文后，导出已正确包含中文。无后缀旧句在官方简中和自定义包中仍保留英文。
- **空译文被批量导入忽略**：`Chat.Title.Topics_other` 的当前英文为空，批量上传后仍导出已有的“话题”。在详情中清空译文并点击 `SUBMIT AND APPLY`，导出才与本地空值一致。这次单条修正不计入最初的 3,391 条导入变更。

另一条仍为英文的导出项是 `StoryPrivacy.GrayList_Main`，按完整 key 搜索显示 `No phrases found`，官方简中导出也保持英文。两条英文导出差异均已单独记录，不能和 42 条导入残留混算。

### 2026-09-30 Android 首次上传

在现有自定义包 `zhcn1ainbo` 中启用 Android，基础语言为 `Chinese (Simplified) (zh)`，仅启用 `other` 复数类别。初始自定义翻译数量为 0；上传前导出仍包含基础简中的回退译文，不能把导出已有中文计为自定义包已保存。

本地 XML 含 14,809 个资源，去掉中文不用的 3,535 个非 `other` 复数分支后，恰为平台识别的 11,274 个词条。四轮保存后的剩余数量依次为 8,238、4,987、1,812、72；最后 72 条经过连续两次刷新重试，key 集合不变，重试前后导出逐字节相同。

| 核验项 | 数量 |
|---|---:|
| 实际采用的自定义词条 | 11,202 |
| 中文使用的资源中，导出与成品一致 | 11,228 |
| 固定残留中，基础语言回退与成品一致 | 26 |
| 固定残留中，基础语言回退与成品不同 | 46 |
| 中文使用的资源缺失 | 0 |

抽查 `AreYouSureShareMyContactInfo` 和 `GiftOfferAmountLowerHint2`，均标记为 `CRITICAL`，表单只有 `SUBMIT`。前者单条提交后显示为建议，最终导出仍为基础语言译文。全部 46 条有效资源差异都属于这 72 条残留，内容与上传前回退相同。导出弹窗显示 `100%`，侧栏仍为 72 条未译，验收以实际导出差异为准。

导出包含全部 14,809 个资源；其中 132 个非 `other` 复数分支与本地不同，均等于线上对应的 `other` 译文，单独记录为中文不用的分支差异。本次在仍显示 `Processing` 的导入页切换导出时出现 `Import id required`，刷新 Android 概览后可正常导出。

原始导出、每轮数量、残留 key、受限条目详情及可重复核验脚本保存于本地 `work/maintenance/upload-android-2026-09-30/`。本地成品 SHA-256 为 `2ce724a27529a2b51776385ab62ab061736285553594fff4d3cefdf3d862f5f3`；最终线上导出为 `37162e6d6844fbd927cd48d9b5c74d36bd432fc345019d69531f85a2518c3a7c`。应用链接为 `https://t.me/setlanguage/zhcn1ainbo`，安卓真机显示仍待验收。

---

### 2026-09-30 iOS 增量发布

官方英文更新至 `ios_en_v22121554.strings`，本地成品共 15,811 个字符串。本轮审校新增 285 条、原文变化 1 条，稳定复用 15,525 条；新增内容主要为 Gram 钱包、转账、助记词与备份、表情回应通知。`Settings.MyTon` 由“我的 Gram”更新为“Gram 收益”。全量结构校验、成品构建再解析和 `.strings` 语法检查通过。

本轮 286 个字符串包含两组六分支复数，中文仅使用 `_any` 分支，因此实际需发布 276 个词条。批量导入共识别 349 条修改，首轮保存 276 条，剩余 73 条经过连续两次刷新重试，key 集合均未改变。

| 核验项 | 数量 |
|---|---:|
| 本轮新增并导出为精修译文 | 275 |
| 本轮更新并导出为精修译文 | 1 |
| 本轮中文有效词条未保存 | 0 |
| 最终导出中与本地一致 | 12,149 |
| 最终导出中仍不同 | 5 |
| 固定导入残留 | 73 |

最终线上包为 `ios_zhcn1ainbo_v22121921.strings`。73 条固定残留和 5 条英文导出差异均与 9 月 28 日记录一致，本轮之外的既有导出译文保持不变。核对残留时，页面使用复数词条名 `Chat.GiftPurchaseOffer.AcceptConfirmation.Text.Stars`，旧导出核验清单使用其中文分支 `_any`，比较时须对应到同一词条。导出弹窗显示 `100%`，侧栏仍为 75 条未译，验收以实际导出为准。

发布前后导出、残留 key、各轮进度及可重复执行的 `verify_upload.py` 保存在本地 `work/maintenance/upload-ios-2026-09-30/`；本轮语义复核和成品验证分别保存在 `work/ios/review.md`、`work/ios/release-verification.json`。本地成品 SHA-256 为 `6d65873ce20f89429e3c0a8758d1d0f5b901fbb6778ea504acff199725c9121c`；线上导出为 `22039353bcc88a800abd3b6ffbe88235d6e36343b252e47651f539a8c8bfd204`。iOS 真机界面仍待验收。

---

## Base Language 选择

**必须选 Simplified Chinese (zh-hans)，不要选 English**。原因：

1. **Fallback 行为**：Telegram 周期性新增字符串，你的静态包会有缺口
   - base=zh-hans → 新字符串显示官方简中（体面）
   - base=en → 新字符串显示英文（难看）
2. **复数规则**：中文只有 `other` 一种形式，英文有 `one/other` 两种
   - base=zh-hans → 期待 `_other` 后缀 key（本项目数据对齐这个）
   - base=en → 期待 `_one` + `_other`，数据对不上会出 bug
3. **缺失或受限文案回退**：选择 zh-hans 作为回退语言；具体条目的客户端显示需实际验收，不以历史固定数量判断覆盖率

---

## 创建语言包参数建议

在 translations.telegram.org 创建自定义语言包时：

| 字段 | 建议值 | 说明 |
|---|---|---|
| Short Name | `zhcn-<你的标识>` | 5+ 字符、小写字母/数字/连字符、全局唯一；生成的 Sharing Link 是 `https://t.me/setlanguage/<short-name>` |
| Name | `Simplified Chinese (Refined)` | 英文显示名 |
| Native Name | `简体中文（精修版）` | 中文显示名，客户端里会看到 |
| Base Language | **Simplified Chinese** | 见上节 |

---

## AI 跳片（连续缺失）

**现象**：翻译 AI 跑了 30 片，但中间连续缺 5-6 片（比如 part11~15）。

**原因**：AI 对话上下文过长导致中段"失忆"，或批处理时跳过了一段。

**处理**：对着缺失的 partNN 单独重跑：
```bash
# 让 AI 重读对应 to-translate.partNN.json, 回填 translated.partNN.json
# 然后单片校验
python3 scripts/import_from_ai.py ios --part 11
```

**预防**：AI 跑到第 10 片开始格式不稳时，重开一个会话重新贴 PROMPT.md。

---

## 占位符误伤

**现象**：`import_from_ai.py` 报 `placeholder_mismatch`。

**常见原因**：
- AI 把 `%@` 翻译成了中文（如 "用户"）
- 占位符 `%1$@` 和 `%2$@` 顺序调换但数量没变（这个其实不报错，因为 sorted 后一致）
- 占位符出现次数变了（如 `{bot}` 用了两次超出原文）

**修法**：
1. 看 `validation.json` 里的 `en_placeholders` 和 `zh_placeholders` diff
2. 手动修正对应 `translated.partNN.json` 的 `final` 字段
3. 重跑 `import_from_ai.py ios --part N` 验证

---

## normalize 规则误伤

**现象**：apply 后发现某条本不该改。

**修法**：
```bash
cp work/ios/translated.json.bak work/ios/translated.json
python3 scripts/import_from_ai.py ios
python3 scripts/normalize.py ios
```

**预防**：任何新规则先 dry-run 看影响面，再 apply。

---

## 上传后完成度明显偏低

**现象**：本地看起来已经全量翻完，但上传到 translations.telegram.org 后，完成度明显低于预期。

**先别怀疑 AI 漏翻**。优先排查是不是**解析阶段漏 key**。

**推荐排查顺序：**
1. 对比 `data/<p>/raw/en.strings` 的原始条目规模，与 `data/<p>/parsed/en.json` 的 key 数
2. 对比 `work/<p>/merged.json` 与 `work/<p>/translated.json` 的 key 数
3. 如果 `parsed/en.json` 就明显偏少，问题通常在 `parse_strings.py` / `_common.py`

**对 TDesktop 尤其要查：**
- 值里带 `https://` / `http://` 的 URL
- 值里带 `**markdown**`
- 值里带 `[a href=\"...\"]...[/a]`
- 值里出现字面量 `/* */`

**典型原因：**
- 用全局正则删除 `//` 行注释，误伤 `https://`
- 用全局正则删除 `/* */` 块注释，误伤字符串内部的字面量内容

**正确做法：**
- 只在**字符串外部**识别并剥离注释
- 修完解析器后，重跑：

```bash
python3 scripts/parse_strings.py tdesktop
python3 scripts/merge.py tdesktop
python3 scripts/export_for_ai.py tdesktop --chunk 100
```

**如果旧翻译已经做了很多，不要推倒重来：**
1. 备份旧的 `translated.json`
2. 重新切分新版 `to-translate.partNN.json`
3. 把旧 `translated.json` 作为 seed 灌回各片已有 key
4. 只补新增出来的缺失 key

---

## 向 AI 提供任务的两种模式

### 模式 A：AI 有文件系统权限（另一个 Claude Code / Cursor / Cline）

最省事。贴这段启动：

```
我在当前目录跑 Telegram 简中语言包精修任务, 你负责翻译审校。
1. 先读 work/ios/PROMPT.md，按英文、上下文与共用术语逐片初译
2. 读取 work/ios/to-translate.part01.json ~ partNN.json；相关英文可在 merged.json 中检索
3. 初译后按相关 key 查 translation-memory.json 核对精修表达；参考包只在具体疑点需要时查阅
4. 单独再做语义与一致性复核，输出对应 translated.partNN.json，并在 review.md 记录实际复核范围及疑点处理
5. 每片完成后运行 python3 scripts/import_from_ai.py ios --part N；结构校验与语义复核都完成后再汇报
```

### 模式 B：AI 只有聊天界面

**开场**：贴 `PROMPT.md` 全文 + 下面这段：
```
接下来按实际分片数分批发 JSON 分片 part01 ~ partNN, 每批默认 100 条。
先根据英文和上下文初译，需要相关英文时说明具体 key 或功能。
初译后我再按需提供精修记忆、功能资料或参考译文；完成语义与一致性复核后输出纯 JSON。
顶层 key 与该分片完全一致，不要 markdown 代码块包裹。
```

**每批**：
```
part01:
<粘贴 to-translate.part01.json 全文>
```

AI 回复保存为 `work/ios/translated.part01.json`（去掉首尾可能的 ```json 代码块），另行索取实际复核记录并保存到 `work/ios/review.md`。聊天模式按疑点提供相关资料，不必预先粘贴所有参考包。

---

## 增量迭代（发布后的 feedback 回流）

用 Telegram 几天后攒了"不顺眼"的条目，定向修复：

1. 在 `work/ios/translated.json` 里找到对应 key，改 `final` 字段
2. 重跑 `build_strings.py ios`
3. 上传新 `.strings` → 点 EDIT PHRASES
4. 客户端会周期性拉取更新，无需重新切换语言包

合并后的 `translated.json` 是主文件。分片只保留审校交付记录，不要再次合并旧片覆盖主文件修订。下一次更新使用 `prepare_update.py`，它会从当前主文件建立翻译记忆并归档旧轮次。

---

## macOS 数据对不上 iOS

macOS 是独立字符串集，**key 空间与 iOS 不同**：
- 有些 key 只在 iOS 存在（如 `AccessDenied.Camera`）
- 有些 key 只在 macOS 存在（macOS 特有 UI）
- 重叠的 key 译文可以共享，但脚本层面是两套独立流水线

**不要**手动把 iOS 的 `.strings` 上传到 macOS 平台，会导致大量无效 key + 缺失覆盖。
