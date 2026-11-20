# 05 · 故障排查与上传经验

---

## 上传停滞、反复提交与停止条件

上传可能需要分几轮完成：文件已识别，点击 **EDIT PHRASES → EDIT ALL** 后先保存几百条，随后 `Processing` 停住；刷新页面后再次提交，有时还能继续写入。每轮可保存的数量不固定。可能涉及临时限流、请求中断或服务端批次处理，页面没有明确错误时，只记录实际现象，不直接认定原因。

### 遇到停滞时怎么做

1. 上传前先用 **Import/Export → EXPORT FILE** 导出当前线上包，解析为 key/value JSON 保存可回滚备份，记录来源版本和 SHA-256。
2. 上传 `build_strings.py` 生成的上传文件（`dist/<platform>/zh-Hans-custom.upload.strings`，安卓为 `.upload.xml`），记录 `Modified Phrases` 的数量，点击 **EDIT PHRASES → EDIT ALL**。文件上传完成只代表已解析，最终还要确认译文已经保存。
3. 只要剩余数量仍在下降，就让当前提交继续。数量持续不变时刷新页面；页面仍保留待修改列表时，直接再次提交；列表消失或要求选文件时，重新上传**同一份成品**再提交。
4. 每轮记录剩余数量与 key。仍有新增写入就继续；如网站明确提示限流或等待时间，按提示等待后再试。
5. **同一批 key 连续两次刷新重试都没有变化，且重新导出的线上包也没有新增写入时，停止批量重传，转为核对残留。** 不以固定条数或必须归零为停止标准。

### 上传文件只保留中文使用的复数分支

完整成品 `dist/<platform>/zh-Hans-custom.strings` 保留官方英文的全部复数分支，网站上的简中语言包每个复数词条只启用一个分支：Android 与 macOS 为 `_other`，iOS 为 `_any`，TDesktop 为 `#other`。`build_strings.py` 每次打包时同时生成 `zh-Hans-custom.upload.strings`（安卓为 `.upload.xml`），删除中文不用的分支，macOS 另外省略无后缀的 `Star.Auction.Preview.TopBidders`。上传时只选这份文件，删除规则见 [`build_strings.py`](03-scripts.md#build_stringspy)。

2026-11-15 直接导入完整成品时，Android 预览识别 881 条修改，iOS 识别 1,175 条。多出的约 700 条都是中文使用的复数分支：左侧为线上精修译文，右侧为 `<no value>`，提交会清空这些译文。用 Android 单个词条测试，只含 `ChatsSelected_other` 的文件提示 `All phrases are synchronized`；含全部六个分支的文件显示 `other` 变为 `<no value>`。改用过滤后的文件后，Android、iOS 分别识别 170、456 条，均为预期修改。预览出现大量 `<no value>` 时，取消 **EDIT ALL** 确认框，先检查上传文件的复数分支。

### 最后剩下的条目可能是什么

| 现象 | 可能原因或已知依据 | 处理 |
|---|---|---|
| 安全提示、反诈、权限确认、语言切换或固定链接持续无法写入 | 可能受平台保护；部分条目在详情中标记 `CRITICAL` | 对照历史记录，抽查少量代表条目；确认建议未被采用、导出也未改变后，记录为平台残留并停止重复提交 |
| 单条提交后能看到自己的译文，但导出里仍没有 | 可能只保存为翻译建议，尚未成为实际采用的译文 | 以重新导出结果为准，不把建议提交成功计为已发布 |
| 旧译文显示 `APPLIED`，新译文反复无法替换 | 该词条当前可能受 `CRITICAL` 保护；历史上曾采用译文不代表现在仍可直接修改 | 打开详情核对当前标记和表单。若只有 `SUBMIT`，按建议处理；导出仍为旧译时记录为未生效 |
| 导出仍为英文，导入列表却不包含它，按完整 key 搜索显示 `No phrases found` | 网站当前可能没有可编辑条目，或该条目由平台固定处理；仅凭此现象无法确定具体机制 | 记录 key、英文内容和查询结果，保留本地译文，不反复重传整包 |
| 普通界面文案残留，且不符合以上情形 | 仍需排查平台选错、源版本变化、占位符或格式问题 | 对照当前英文、本地校验与网站具体报错，定向修复；不要直接归入平台限制 |

历史残留常见类别与示例：

- 登录与安全：`AUTH_REGION`、`PUSH_AUTH_*`、`Login.ResetAccountProtected.*`、`AuthCode.Alert`。
- 反诈与权限：`Conversation.ScamWarning`、`UserInfo.FakeUserWarning`、`Conversation.ShareBot*`。
- 隐私、付款和语言切换：`Checkout.LiabilityAlert`、`Passport.AcceptHelp`、`ApplyLanguage.*`、`Settings.AppLanguage`。
- 固定链接与平台声明：`Settings.PrivacyPolicy_URL`、`WebApp.TermsOfUse_URL`、`Chat.PsaTooltip.psa`。

这些示例用于定位问题，具体 key 和数量会随版本变化。客户端对受限或缺失条目的回退显示需另行验收，不能从上传页直接确认。

### 验收与记录

核验期间暂存上传前后导出，按 key 对比本地成品，将结果分成：实际新增或修改并保存、已有且一致、未导出、已导出但仍不同。核验结束后按 [下载资源清理规则](../AGENTS.md#维护铁律) 删除下载原件及复制件，保留解析后的回滚备份与核验结论。英文与简中文件包含的复数分支可能不同，不能直接用英文总 key 数减去简中导出总数判断漏传；结合当前简中 key 集合与导入预览核对。

**以实际导出核验为准。** 导出弹窗的 `100%`、侧栏“未译”数量、导入剩余数量可能采用不同口径。核验期间记录每轮剩余 key、最终差异、抽查依据和文件 SHA-256，明确哪些已发布、哪些仍未写入。结束后将发布结果、未生效条目和可复用经验写入文档，清理核验专用脚本、报告、截图和下载副本。

从仍在 `Processing` 的导入页切换到概览再打开导出，可能出现 `Import id required`。此时完整刷新对应平台的概览页，再打开 **Import/Export**；不要在报错弹窗上反复点击导出。下载完成后先检查文件存在、能按平台格式解析，再将其作为备份或验收依据。

上传保存后立即导出，可能仍拿到上传前的文件：文件名版本号不变，SHA-256 与上传前备份相同，即使导出弹窗已显示 `100%`、侧栏未译数已经下降。这时不要据此判断上传失败；等几分钟后刷新概览页重新导出，文件名出现新版本号后再核验。

线上导出与本地成品比较时，除完整差异外，还要按**本轮修订清单**单独统计已生效、仍为旧值和未导出的条目。历史残留与本轮修订可能重叠，不能因剩余数量接近历史值就认定本轮全部发布成功。Android 导出会将部分中文不用的复数分支映射为 `other` 内容；应验证映射关系并单独记录，不将其计为中文有效词条漏传。

### 2026-09-28 实测，供以后快速对照

| 平台 | 导入识别变更 | 实际保存变更 | 刷新重试后的固定残留 | 导出中与本地一致 | 导出中仍不同 |
|---|---:|---:|---:|---:|---:|
| iOS | 414 | 341 | 73 | 11,874 | 5 |
| TDesktop | 336 | 299 | 37 | 8,287 | 0 |
| macOS | 3,391 | 3,350 | 42 | 8,287 | 2 |

本次刷新后再次提交，固定残留未减少。浏览器未显示明确限流原因。抽查 iOS `AUTH_REGION`，页面标记 `CRITICAL`；单条提交后显示为翻译建议，重新导出仍未包含该 key。

iOS 另有 5 个 key 在导出中保持英文，官方简中导出也同样为英文：`AppUpgrade.Running`、`Login.PhonePaidEmailText`、`PUSH_CHAT_PHOTO_EDITED`、`PUSH_CHAT_TITLE_EDITED`、`ProfileLevelInfo.MyDescriptionToday_1`。前两个按完整 key 搜索显示 `No phrases found`。这 5 条不在导入页的 73 条待修改清单中，需单独记录。

当时两个平台的导出弹窗均显示 `100%`，侧栏分别还有 75、38 条未译。上述表格由实际导出逐条比较得到，不能把 73／37 当成以后版本的固定上限。本节保留了残留类型、抽查结果与停止重试的判断依据。

macOS 实际新增 361 条、更新 2,989 条。最后 42 条经过连续两次刷新重试，key 集合和线上导出均保持不变；抽查 `ChannelInfo.ScamWarning` 标记为 `CRITICAL`，表单只有提交建议的 `SUBMIT`。导出弹窗显示 `100%`，侧栏仍显示 44 条未译。

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

本地成品 SHA-256 为 `2ce724a27529a2b51776385ab62ab061736285553594fff4d3cefdf3d862f5f3`；最终线上导出为 `37162e6d6844fbd927cd48d9b5c74d36bd432fc345019d69531f85a2518c3a7c`。应用链接为 `https://t.me/setlanguage/zhcn1ainbo`，安卓真机显示仍待验收。

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

本地成品 SHA-256 为 `6d65873ce20f89429e3c0a8758d1d0f5b901fbb6778ea504acff199725c9121c`；线上导出为 `22039353bcc88a800abd3b6ffbe88235d6e36343b252e47651f539a8c8bfd204`。iOS 真机界面仍待验收。

---

### 2026-10-02 四平台增量发布

四平台均重新导出官方英文并完成本地校验，再备份线上包、上传并重新导出逐条核验。

| 平台 | 本轮审校字符串 | 实际新增或修改并保存 | 固定导入残留 |
|---|---:|---:|---:|
| Android | 5 | 4 | 72 |
| iOS | 131 | 121 | 73 |
| TDesktop | 2 | 0 | 37 |
| macOS | 1 | 0 | 42 |

Android 修正 3 条实时位置共享提示的参数含义，以及代理自动切换等待时间说明；生日提示的新英文适用原译。iOS 审校新增 124 条、英文变化 7 条，含两组六分支复数，中文实际使用 121 个词条；线上新增 114 条、修改 7 条。主要内容为钱包备份、助记词、转账提示及资金锁定，助记词长度更新为 12 或 24 个单词。TDesktop 的生日与礼物附言提示、macOS 的生日提示均适用原译，详情页确认仍为 `APPLIED`，重传前后导出未变。

各平台残留清单连续两次刷新重试均保持不变，重新导出也没有额外写入；残留 key 与各平台上一轮记录一致。本轮中文有效词条全部与本地成品一致，其他既有译文及导出差异保持不变。Android 仍有 46 条中文有效资源采用基础语言回退，另有 132 个中文不用的复数分支差异；iOS 的 5 条英文导出差异与 macOS 的 2 条历史导出差异均未变。macOS 上传继续按上文处理同名普通字符串与复数词条冲突。

最终线上版本：Android `v61077352`、iOS `v22144899`、TDesktop `v5894414`、macOS `v2300944`。应用链接仍为 `https://t.me/setlanguage/zhcn1ainbo`，四平台实际客户端显示待验收。

---

### 2026-10-02 四平台语义审校发布

本轮本地修订 1,012 个资源，按中文实际使用的复数分支计为 847 个有效词条。上传前冻结成品并导出线上备份；上传后重新导出逐条对比。

| 平台 | 本地修订资源（含复数） | 本轮中文有效词条 | 实际保存 | 本轮未生效 | 固定导入残留 |
|---|---:|---:|---:|---:|---:|
| iOS | 558 | 478 | 470 | 8 | 75 |
| TDesktop | 442 | 362 | 360 | 2 | 37 |
| Android | 10 | 5 | 5 | 0 | 72 |
| macOS | 2 | 2 | 2 | 0 | 42 |

实际保存共 837 个中文有效词条。每个平台的残留清单经过连续两次刷新重试均未改变，随后两次导出内容相同；可发布的本轮译文全部与成品一致。未审校的既有译文保持原样，导出没有新增缺失。

本轮未生效的修订须继续保留在本地成品：

- iOS 未导出 6 条：`CancelResetAccount.TextSMS`、`EncryptionKey.Description`、`Notification.NewAuthDetected`、`Conversation.ShareBotContactConfirmation`、`Conversation.ShareMyPhoneNumberConfirmation`、`Chat.GiftPurchaseOffer.AcceptConfirmation.BadValue`。它们均在历史导入残留中。
- iOS 仍采用旧译 2 条：`Chat.GiftPurchaseOffer.RejectConfirmation.Text`、`Chat.GiftPurchaseOffer.RejectConfirmation.Title`。详情均标记 `CRITICAL`，旧译显示 `APPLIED`；前者展开编辑后只有 `SUBMIT`。因此本轮残留由 73 条增加为 75 条。
- TDesktop 未导出 2 条：`lng_payments_warning_body`、`lng_bot_share_phone`，均在历史导入残留中。

Android 的 `RemoveManyMasksCount_one` 导出为对应 `other` 译文，本地保留官方英文单数分支对应的译文；中文有效分支正确。macOS 上传文件继续省略已知冲突的无后缀 `Star.Auction.Preview.TopBidders`，既有复数修正与空译文均保持正确。

最终线上版本为 iOS `v22145842`、TDesktop `v5898498`、Android `v61078267`、macOS `v2328824`。语义审校范围、修订原因和源码依据记录在各平台的 `work/<platform>/review.md` 与本轮审校记录中。应用链接仍为 `https://t.me/setlanguage/zhcn1ainbo`，实际客户端显示待验收。

---

### 2026-10-07 Android、iOS 增量发布

已将本轮成品上传至现有自定义包 `zhcn1ainbo`。上传前导出线上包并保存可回滚的 key/value 业务备份，上传后重新导出逐条比较。

| 平台 | 本轮审校词条 | 导入识别修改 | 实际保存 | 本轮已有且一致 | 保存后导入残留 |
|---|---:|---:|---:|---:|---:|
| Android | 2 | 74 | 2 | 0 | 72 |
| iOS | 28 | 102 | 27 | 1 | 75 |

Android 两条 Web 代理文案已采用精修译文；上传前导出已有基础语言回退，前后导出比较计为修改 2 条。iOS 新增并导出 20 条、修改 7 条；`Wallet.Recipient.NoResultsText` 已与本地一致，继续保留。两端本轮全部词条均与本地成品一致，本轮未生效 0 条。

前后导出比较确认，本轮之外的既有资源没有变化，也没有新增缺失。Android 保留历史 46 条中文有效资源差异，以及 132 个映射为 `other` 内容的非中文复数分支差异；iOS 保留历史 5 条英文导出差异和 2 条礼物出价拒绝确认旧译。页面剩余 72／75 条均属此前记录的导入残留，本轮词条已全部退出待修改清单。

最终线上版本为 Android `v61158863`、iOS `v22190975`。上传前版本分别为 `v61078267`、`v22145842`，业务备份保存在本轮各平台历史归档的 `online-before-upload.json`；可通过 `_common.dump_resource()` 恢复相应平台资源格式。

最终导出 SHA-256：

- Android：`9e533468344cfae1b9a2eb876405347677ecbc70d93e0ffea27e5653ed647f46`。
- iOS：`586cbe41f9de6e4069a0915ae1ec7a5b2e947d6d624da5f625747771727018c2`。

应用链接：[简体中文（精修版）](https://t.me/setlanguage/zhcn1ainbo)。本轮已完成线上导出验收，实际客户端显示仍待验收。上传前后四份下载原件均已清理，线上业务备份及发布结论已保留。

---

### 2026-10-19 四平台增量发布

官方英文版本为 Android `v61343911`、iOS `v22279764`、TDesktop `v5949089`、macOS `v2383494`。本轮审校新增 1,730 个资源、原文变化 45 个，按中文实际使用的复数分支计为 1,650 个有效词条。四平台成品均已上传至 `zhcn1ainbo`，上传前导出线上包作为回滚备份，上传后重新导出核验。

| 平台 | 本轮审校资源（含复数） | 本轮中文有效词条 | 导入识别修改 | 实际保存 | 本轮已有且一致 | 保存后导入残留 |
|---|---:|---:|---:|---:|---:|---:|
| Android | 420 | 400 | 467 | 395 | 5 | 72 |
| iOS | 121 | 116 | 187 | 112 | 4 | 75 |
| TDesktop | 454 | 399 | 434 | 397 | 2 | 37 |
| macOS | 780 | 735 | 772 | 730 | 5 | 42 |

四平台上传后的导出均恰好等于“上传前导出加本轮中文有效词条的本地译文”：本轮有效词条全部与本地成品一致，本轮未生效 0 条；本轮之外的既有资源没有变化，也没有新增缺失。iOS 新增 93 条、修改 19 条；TDesktop 新增 391 条、修改 6 条；macOS 新增 730 条。Android 上传前导出已含基础语言回退，302 条由回退改为精修译文，另有 93 条回退内容与精修译文相同、本轮作为自定义译文保存。

“本轮已有且一致”均为英文只做了拼写、标点或措辞微调，本地沿用原译的条目，例如 `Cancelled` → `Canceled`、`View in Blockchain Explorer` → `View in Explorer`。导入不把它们计为修改，导出包含原译，但网站侧栏仍将其列为未译。各平台侧栏未译数为 Android 78、iOS 80、TDesktop 42、macOS 50，减去导入残留后，剩余均为本轮或此前轮次的这类条目；iOS 两条礼物出价拒绝确认旧译属于导入残留，但不在未译列表中。

Android 和 iOS 的残留清单经过两次刷新重试均未改变。TDesktop 与 macOS 首轮保存后剩余 37／42 条，数量与此前记录一致，且不含本轮词条，导出核验已确认本轮内容全部生效。Android 历史 46 条中文有效资源差异与 132 个映射为 `other` 内容的非中文复数分支差异未变；iOS 的 5 条英文导出差异和 2 条礼物出价拒绝确认旧译未变。macOS 上传文件继续省略无后缀的 `Star.Auction.Preview.TopBidders`。

| 平台 | 上传前版本 | 最终线上版本 | 最终导出 SHA-256 |
|---|---|---|---|
| Android | `v61160319` | `v61363780` | `3211017a0aab2f186651dca183f6aa53022b2f91b4f092aa2e5240e806b8393b` |
| iOS | `v22202254` | `v22280261` | `c228079aad97ee7cd8b320d315ccc3329383aab7eae0f2fc6cab99647c2d61ed` |
| TDesktop | `v5898498` | `v5959242` | `70e4a632efd75be115307bee197f38a568dbacabec1be7bb2400b7e6051c24cc` |
| macOS | `v2328824` | `v2391307` | `b329eb660e5d70dcac8a5beade9039ddcf4cb66b5b9a07fe49d9c53b40995c61` |

业务备份保存在本轮各平台历史归档的 `online-before-upload.json`。应用链接仍为 [简体中文（精修版）](https://t.me/setlanguage/zhcn1ainbo)，实际客户端显示仍待验收。上传前后的下载原件均已清理。

---

### 2026-11-15 四平台增量发布

官方英文版本为 Android `v61669501`、iOS `v22594704`、TDesktop `v6047144`、macOS `v2433756`。本轮审校新增 1,693 个资源、原文变化 42 个，按中文实际使用的复数分支计为 1,489 个有效词条；Android 另有 1 个资源已从官方英文移除。上传前复核修正 5 条：iOS 2 条法币估值括号改为全角，macOS 3 条无障碍朗读标签改为与同组一致的写法。

四平台均按 [上传文件只保留中文使用的复数分支](#上传文件只保留中文使用的复数分支) 生成上传文件。上传前导出线上包作为回滚备份，上传后重新导出逐条核验。

| 平台 | 本轮审校资源（含复数） | 本轮中文有效词条 | 导入识别修改 | 实际保存 | 本轮已有且一致 | 保存后导入残留 |
|---|---:|---:|---:|---:|---:|---:|
| Android | 113 | 103 | 170 | 98 | 5 | 72 |
| iOS | 457 | 382 | 456 | 381 | 1 | 75 |
| TDesktop | 239 | 189 | 221 | 184 | 5 | 37 |
| macOS | 926 | 815 | 856 | 814 | 1 | 42 |

本轮中文有效词条全部与本地成品一致，未生效 0 条；本轮之外的既有资源没有变化，也没有新增缺失。iOS 新增 374 条、修改 7 条；TDesktop 新增 177 条、修改 7 条；macOS 新增 808 条、修改 6 条。Android 上传前导出已含基础语言回退：66 条导出内容改为本轮译文，32 条回退内容与精修译文相同、本轮作为自定义译文保存。`StoryPrivacyGroupAddContacts`、`StoryPrivacyGroupNonContacts` 的 10 个非 `other` 分支随之导出为新的 `other` 译文；导出中全部非 `other` 分支均等于对应的 `other` 译文。

各平台残留清单经过两次刷新重试均未改变，数量与上一轮相同。Android 46 条中文有效资源差异未变。iOS 导出中仍不同的 6 条为 4 条英文导出（`AppUpgrade.Running`、`Login.PhonePaidEmailText`、`PUSH_CHAT_PHOTO_EDITED`、`PUSH_CHAT_TITLE_EDITED`）和 2 条礼物出价拒绝确认旧译；上传文件不含中文不用的分支，`ProfileLevelInfo.MyDescriptionToday_1` 不再计入比较。macOS 仍有 `StoryPrivacy.GrayList_Main` 导出为英文；TDesktop 上传文件中已导出的词条全部一致。侧栏未译数为 Android 85、iOS 82、TDesktop 47、macOS 52，与导入残留口径不同，验收以导出逐条比较为准。

| 平台 | 上传前版本 | 上传前导出 SHA-256 | 最终线上版本 | 最终导出 SHA-256 |
|---|---|---|---|---|
| Android | `v61638730` | `5a22625a6305e4442cd203a470b4810715e39daa774d3f719cbdd881d06da55d` | `v61837157` | `3e35e19cc873d8545732fdbba49d28555f97df8be487084b8100416bc0b13837` |
| iOS | `v22594703` | `9eefbd8f6318e51b7097e61abebdf3df1fb9e54545a47e58078bcfa29486da54` | `v22612066` | `6edfdc34cc38d7aadffb10fcd36fd8fe3d0df7f3b6f1f2bd46f3e4519eaf98d0` |
| TDesktop | `v5959242` | `760f6daed8dc38a53f5495f9c3bfa17df69db509d9c5899a3b5829ee37234417` | `v6161776` | `5c3485f74629959dd4e2caf2fddf1459a6ec27c38dd366cde74465f88113fa4f` |
| macOS | `v2391307` | `88409831480c32a6b2caabb112738a6ab65346eb94dfb445f1048f21bf9e56a3` | `v2440866` | `bf185efe5aa5049355a787279272bb7fedcfd4e688ef7bc0d8d03d2459740de6` |

业务备份保存在本轮各平台历史归档的 `online-before-upload.json`。macOS `VoiceOver.Common.Live`（“实况”）的使用场景尚未确认，需在客户端核对。应用链接仍为 [简体中文（精修版）](https://t.me/setlanguage/zhcn1ainbo)，实际客户端显示仍待验收。上传前后的下载原件均已清理。

---

### 2026-11-20 Android、iOS、macOS 增量发布

官方英文版本为 Android `v62007995`、iOS `v22661645`、macOS `v2470821`。本轮审校新增 4,255 个资源，英文变化 0 个，按中文实际使用的复数分支计为 3,615 个有效词条。TDesktop 本轮未处理，网站侧栏未译数仍为 47，与上一轮相同。三个平台均上传 `build_strings.py` 生成的上传文件。上传前导出线上包作为回滚备份，上传后重新导出逐条核验。

| 平台 | 本轮审校资源（含复数） | 本轮中文有效词条 | 导入识别修改 | 实际保存 | 本轮已有且一致 | 保存后导入残留 |
|---|---:|---:|---:|---:|---:|---:|
| Android | 261 | 256 | 328 | 256 | 0 | 72 |
| iOS | 50 | 45 | 120 | 45 | 0 | 75 |
| macOS | 3,944 | 3,314 | 3,356 | 3,314 | 0 | 42 |

本轮中文有效词条全部与本地成品一致，未生效 0 条；本轮之外的既有资源没有变化，也没有新增缺失。iOS、macOS 本轮均为新增。Android 上传前导出已含基础语言回退：253 条导出内容改为本轮译文，3 条回退内容与精修译文相同（`FpnvConsentSimSlotValue`、`GiftOnchainErrorTitle`、`GiftOnchainGramAmount`），本轮作为自定义译文保存。`BotInviteDoneMany` 的 5 个非 `other` 分支随之导出为新的 `other` 译文；导出中全部 3,570 个非 `other` 分支均等于对应的 `other` 译文。

macOS 首次提交保存到剩余 1,439 条后停住，刷新页面再次提交后继续写入，降到 42 条。各平台残留清单经过两次刷新重试均未改变，数量与上一轮相同，对应 key 在上传前导出中就已缺失或不同，且不含本轮词条。Android 46 条中文有效资源差异未变；iOS 导出中仍不同的 6 条与上一轮相同；macOS 仍有 `StoryPrivacy.GrayList_Main` 导出为英文。侧栏未译数为 Android 85、iOS 82、macOS 52，与上一轮相同。

iOS 提交后约 3 分钟内导出三次，得到的仍是上传前文件：版本号为 `v22612066`，SHA-256 与上传前备份相同。当时页面已显示 `100%`，翻译数增加 45 条。提交约 6 分钟后重新导出，才得到新版本，核验结果见上。

| 平台 | 上传前版本 | 上传前导出 SHA-256 | 最终线上版本 | 最终导出 SHA-256 |
|---|---|---|---|---|
| Android | `v61837157` | `0a863623e6d1b036048527c5648ca055bbfbc05f14085920619aacc1ccdab8f6` | `v62029095` | `06488ed02c778e920ddc64dbe7052ee126570287c1f434cedbd7341a756da2f5` |
| iOS | `v22612066` | `23df5727ffdd6f3c83125402403aed973d8f235e86898a1925bdbe1283a2266d` | `v22666453` | `fc1a66d1c5182cd2ca410c5148d5c7930ad8f38a6e5a696b9ad6844521a5af3b` |
| macOS | `v2440866` | `efcf116f943ba26d3cd04417934f3b9395f19760d2eccb104cf52a7ff363ffd4` | `v2482028` | `0d7ac70285c0f57876a43c1c93d42752685c00b27d643cd6d36f0ef02523600a` |

业务备份保存在本轮各平台历史归档的 `online-before-upload.json`。应用链接仍为 [简体中文（精修版）](https://t.me/setlanguage/zhcn1ainbo)，实际客户端显示仍待验收。上传前后的下载原件均已清理。

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

## AI 跳片或半截旧分片续跑

**现象 1**：分片跑了一部分中断，缺少若干 `translated.partNN.json`。

**处理**：
- 若工作区已是紧凑分片（存在 `compact.partNN.json`），仅为缺失的分片单独启动一次性子代理写出 `reply.partNN.json`，再运行：
  ```bash
  python3 scripts/import_from_ai.py ios --part 11
  ```
- 若工作区保留了部分旧版分片（无 `compact.part*.json`），运行：
  ```bash
  python3 scripts/export_for_ai.py ios --repack
  ```
  脚本会先校验并合并已完成分片保留为 `part01`，再将剩余未译条目重切为紧凑分级分片 `part02..partNN`。

**预防**：严格按“每片一个独立一次性子代理”派发，不在同一长会话中连续处理多个分片。

---

## 占位符误伤

**现象**：`import_from_ai.py` 报 `placeholder_mismatch` 或 `placeholder_order_mismatch`。

**常见原因**：
- AI 把 `%@` 翻译成了中文（如 "用户"）
- 无编号百分号占位符（如两个 `%@`）调换了次序
- 占位符出现次数变化（如 `{bot}` 用了两次超出原文）

**修法**：
1. 查看 `validation.partNN.json`（或全量 `validation.json`）中的 `en_placeholders` 与 `zh_placeholders` 差异
2. 单片阶段修正对应 `reply.partNN.json` 中的短编号译文，重跑 `python3 scripts/import_from_ai.py ios --part N` 重新展开验证；合并后阶段直接修正 `translated.json` 并重跑 `python3 scripts/import_from_ai.py ios`

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
python3 scripts/export_for_ai.py tdesktop
```

**如果旧翻译已经做了很多，不要推倒重来：**
1. 备份旧的 `translated.json`
2. 重新切分新版 `to-translate.partNN.json`
3. 把旧 `translated.json` 作为 seed 灌回各片已有 key
4. 只补新增出来的缺失 key

---

## 向 AI 提供任务的两种模式

### 模式 A：AI 有文件系统权限（Claude Code / Codex / Pi / Cursor）

直接让 AI 读取仓库根目录的 `AGENTS.md` 按标准流程执行：

```
请按 AGENTS.md 的《分层增量审校标准流程》完成 ios 语言包更新：
1. 若尚未生成紧凑分片，运行 export_for_ai.py ios（有半截旧分片时加 --repack），读取 work/ios/compact-manifest.json
2. 对每个待译 compact.partNN.json 派发独立子代理：首轮并行读取对应的 PROMPT.fast.md 或 PROMPT.deep.md 与该紧凑分片（不读 .meta.json，不检索外部大文件），直接写出 reply.partNN.json，随后运行 import_from_ai.py ios --part N 展开校验
3. 初译全部通过后运行 export_for_ai.py ios --review，按 review.partNN.json 派发独立复核子代理并行读取 PROMPT.review.md 与复核分片，重点核查带 flags 项并输出差量补丁 review-patch.partNN.json（无修改输出 {}），运行 import_from_ai.py ios --review 应用补丁并更新 review.md
4. 依次完成 merge_parts.py、normalize.py、import_from_ai.py、diff_report.py --update 与 build_strings.py
```

### 模式 B：AI 只有聊天界面

1. **初译每批**：每次新开干净对话，按分片顶层 `tier` 贴入 `PROMPT.fast.md` 或 `PROMPT.deep.md` 全文，随后贴入 `compact.partNN.json` 全文。将 AI 返回的纯 JSON 保存为 `work/ios/reply.partNN.json`，运行 `python3 scripts/import_from_ai.py ios --part N`。
2. **差量二审**：运行 `python3 scripts/export_for_ai.py ios --review`。新开干净对话贴入 `PROMPT.review.md` 与 `review.partNN.json`，将返回的差量补丁 JSON（无修改为 `{}`）保存为 `work/ios/review-patch.partNN.json`，运行 `python3 scripts/import_from_ai.py ios --review`，并将复核说明写入 `work/ios/review.md`。

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
