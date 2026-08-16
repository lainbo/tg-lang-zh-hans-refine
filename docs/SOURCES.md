# 源文件下载指引

所有下载都需要 Telegram 账号登录 translations.telegram.org。本项目不代下, 请手动放入 `data/<platform>/raw/`。

## 平台维护状态

- iOS：继续维护。
- TDesktop：继续维护，和 iOS 独立更新。
- macOS：停止维护，保留历史产物，不再要求下载新源文件。

## iOS 平台

### 增量维护必下

#### 1. 官方英文 baseline → `en.strings`

地址: https://translations.telegram.org/en/ios/

登录后右上角 **Export** → 选 `.strings` 格式 → 下载全部字符串。
重命名为 `en.strings`, 放到 `data/ios/raw/en.strings`。

#### 2. 官方简中 (新出的机翻版) → `official-zh.strings`

地址: https://translations.telegram.org/zh-hans/ios/ 
(或 zh-hant 看你要改哪个)

同样 **Export** → `.strings`。重命名为 `official-zh.strings`。

### 冻结参考源，不再更新

#### 社区参考包 @zhcncc → `zhcncc.strings`

地址: https://translations.telegram.org/zhcncc/ios/

@zhcncc 只作为首次翻译时的历史参考源。后续 Telegram 新增文案它不会继续覆盖，因此增量维护时**不要再要求下载新版 zhcncc**；保留仓库里已有的 `data/ios/raw/zhcncc.strings` 参与参考即可。

如果需要从零初始化，@zhcncc 是自定义语言包。如果该包 owner 允许公开导出, 在页面上能看到 Export 按钮; 否则你需要:
- 方案 A: 把该包 fork 到自己账号下 (页面上有 fork 选项), fork 后自己的副本可以 Export
- 方案 B: 联系 owner 申请权限

落地为 `data/ios/raw/zhcncc.strings`。

## macOS 平台

macOS 已停止维护。保留已有 `data/macos/`、`work/macos/`、`dist/macos/` 作为历史记录，不再下载新源文件，不再上传新包。

## TDesktop 平台

TDesktop 同理, 地址替换成 `/tdesktop/`:
- https://translations.telegram.org/en/tdesktop/
- https://translations.telegram.org/zh-hans/tdesktop/

落地到 `data/tdesktop/raw/`:
- `en.strings`
- `official-zh.strings`

`zhcncc.strings` 同 iOS，仅作为历史参考源保留；增量维护不要求下载新版。

## 增加更多参考源 (可选)

如果想多挂几个社区包做交叉参考, 命名为 `ref-<name>.strings` 放进 raw 目录, `merge.py` 会自动识别 `ref-*` 前缀纳入 refs。

## 上传回写

审校完产出 `dist/<platform>/zh-Hans-custom.strings` 后:
1. 在 translations.telegram.org 创建或选择你自己的自定义语言包
2. 页面上有 **Import** 功能, 上传 .strings 文件
3. 生成 `tg://setlanguage?lang=<你的包名>` 链接
4. 在客户端打开链接应用
