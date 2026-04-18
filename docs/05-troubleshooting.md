# 05 · 踩坑、白名单、FAQ

---

## 安全保留 Key 白名单（54 条左右）

**现象**：上传 `.strings` 后 `Modified Phrases` 识别全量成功，但点 EDIT PHRASES 入库时剩余几十条死活入不进去，服务端返回：
```json
{"lang_keys":[],"repeat_lang_keys":[],"affected_cnt":0}
```
前端无限重试也不会成功。

**原因**：Telegram 的 **anti-malicious-translation 机制**。涉及账号安全、反诈、法律条款的字符串被平台锁定，**任何自定义语言包都改不了，包括 API 方式**。

**已知被锁定的类别**（通过 iOS 实战确认）：

| 类别 | 示例 key | 为什么锁 |
|---|---|---|
| 登录/账号安全 | `AUTH_REGION`, `Login.ResetAccountProtected.*`, `PUSH_AUTH_*`, `AuthCode.Alert` | 验证码/账号重置钓鱼攻击面 |
| Scam/Fake 警告 | `Conversation.ScamWarning`, `ChannelInfo.FakeChannelWarning`, `UserInfo.ScamUserWarning` | 反诈提示被篡改 → 帮骗子洗白 |
| 机器人权限 | `Conversation.ShareBot*`, `Conversation.SecretChatContextBotAlert` | 骗用户授权恶意 bot |
| PSA 公告 | `Chat.PsaTooltip.psa`, `ChatList.PsaAlert.psa`, `Message.ForwardedPsa.psa` | CEO 官方声明立场 |
| 支付免责 | `Checkout.LiabilityAlert`, `Checkout.PaymentLiabilityAlert` | 法律文本责任归属 |
| 语言包元操作 | `ApplyLanguage.*`, `Settings.AppLanguage` | 切换语言包提示被篡改 → 诱导装恶意包 |
| 端到端加密 | `EncryptionKey.Description` | 安全机制说明不能歪曲 |
| 数据导入/Passport | `Passport.AcceptHelp`, `Conversation.ImportedMessageHint` | 隐私数据流向 |
| 会话设备关联 | `AuthSessions.AddDevice*` | 账号被盗高危点 |
| 礼物打赏敏感 | `Chat.GiftPurchaseOffer.*`, `Notification.StarGiftOffer.Offer` | 资金损失风险 |

**处理**：放弃。这些会 fallback 到 base language 显示官方译文。

**覆盖率上限**：iOS 实测 **11417/11471 ≈ 99.53%**。

---

## 1000 条限流

**现象**：Import 时每提交 ~1000 条需刷新页面才能继续。

**原因**：Telegram 平台对单次 batch import 有节流。不是 bug 也不是本项目的问题。

**处理**：刷新页面继续，反复几次直到剩余一批卡住（通常就是上面那 54 条安全白名单），关掉页面。

---

## Base Language 选择

**必须选 Simplified Chinese (zh-hans)，不要选 English**。原因：

1. **Fallback 行为**：Telegram 周期性新增字符串，你的静态包会有缺口
   - base=zh-hans → 新字符串显示官方简中（体面）
   - base=en → 新字符串显示英文（难看）
2. **复数规则**：中文只有 `other` 一种形式，英文有 `one/other` 两种
   - base=zh-hans → 期待 `_other` 后缀 key（本项目数据对齐这个）
   - base=en → 期待 `_one` + `_other`，数据对不上会出 bug
3. **安全白名单 fallback**：上面那 54 条锁定 key 会 fallback 到 base，选 zh-hans 显示官方简中，体验顺滑

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
# 全量回滚
for f in work/ios/translated.part*.json.bak; do mv "$f" "${f%.bak}"; done
python3 scripts/merge_parts.py ios

# 调整 normalize.py:normalize() 规则，跳过特定场景
# 重跑 dry-run 看 diff
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
python3 scripts/export_for_ai.py tdesktop --chunk 500
```

**如果旧翻译已经做了很多，不要推倒重来：**
1. 备份旧的 `translated.json`
2. 重新切分新版 `to-translate.partNN.json`
3. 把旧 `translated.json` 作为 seed 灌回各片已有 key
4. 只补新增出来的缺失 key

---

## 喂 AI 的两种模式

### 模式 A：AI 有文件系统权限（另一个 Claude Code / Cursor / Cline）

最省事。贴这段启动：

```
我在当前目录跑 Telegram 简中语言包精修任务, 你负责翻译审校。
1. 先读 work/ios/PROMPT.md 吸收任务规则
2. 依次读取 work/ios/to-translate.part01.json ~ part30.json
3. 每读完一片, 按规则产出并写入 work/ios/translated.part01.json ~ part30.json
4. 每片完成后跑 python3 scripts/import_from_ai.py ios --part N, 问题数 0 才算完成
5. 30 片全部完成后告诉我
```

### 模式 B：AI 只有聊天界面

**开场**：贴 `PROMPT.md` 全文 + 下面这段：
```
接下来分 30 批发 JSON 分片 part01 ~ part30, 每批约 500 条。
每批只输出一个纯 JSON 对象, 顶层 key 完全一致, 不要 markdown 代码块包裹。
被截断时回"继续", 从中断处补完。
```

**每批**：
```
part01:
<粘贴 to-translate.part01.json 全文>
```

AI 回复保存为 `work/ios/translated.part01.json`（去掉首尾可能的 ```json 代码块）。

---

## 增量迭代（发布后的 feedback 回流）

用 Telegram 几天后攒了"不顺眼"的条目，定向修复：

1. 在 `work/ios/translated.json` 里找到对应 key，改 `final` 字段
2. 重跑 `build_strings.py ios`
3. 上传新 `.strings` → 点 EDIT PHRASES
4. 客户端会周期性拉取更新，无需重新切换语言包

**如果要同时同步 part 文件**（避免下次 merge_parts 时被旧 part 覆盖）：
- 改完 `translated.json` 后也要改对应 `translated.partNN.json`
- 或者直接从 `translated.json` 重新切片回去（可以写个 `split.py`，当前未实现）

---

## macOS 数据对不上 iOS

macOS 是独立字符串集，**key 空间与 iOS 不同**：
- 有些 key 只在 iOS 存在（如 `AccessDenied.Camera`）
- 有些 key 只在 macOS 存在（macOS 特有 UI）
- 重叠的 key 译文可以共享，但脚本层面是两套独立流水线

**不要**手动把 iOS 的 `.strings` 上传到 macOS 平台，会导致大量无效 key + 缺失覆盖。
