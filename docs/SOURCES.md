# 源文件下载指引

所有下载都需要 Telegram 账号登录 translations.telegram.org。本项目不代下, 请手动放入 `data/<platform>/raw/`。

## iOS 平台

### 1. 官方英文 baseline → `en.strings`

地址: https://translations.telegram.org/en/ios/

登录后右上角 **Export** → 选 `.strings` 格式 → 下载全部字符串。
重命名为 `en.strings`, 放到 `data/ios/raw/en.strings`。

### 2. 官方简中 (新出的机翻版) → `official-zh.strings`

地址: https://translations.telegram.org/zh-hans/ios/ 
(或 zh-hant 看你要改哪个)

同样 **Export** → `.strings`。重命名为 `official-zh.strings`。

### 3. 社区参考包 @zhcncc → `zhcncc.strings`

地址: https://translations.telegram.org/zhcncc/ios/

注意: @zhcncc 是自定义语言包。如果该包 owner 允许公开导出, 在页面上能看到 Export 按钮; 否则你需要:
- 方案 A: 把该包 fork 到自己账号下 (页面上有 fork 选项), fork 后自己的副本可以 Export
- 方案 B: 联系 owner 申请权限

落地为 `data/ios/raw/zhcncc.strings`。

## macOS 平台

同上三步, 地址里 `/ios/` 替换成 `/macos/`:
- https://translations.telegram.org/en/macos/
- https://translations.telegram.org/zh-hans/macos/
- https://translations.telegram.org/zhcncc/macos/

落地到 `data/macos/raw/`。

## 增加更多参考源 (可选)

如果想多挂几个社区包做交叉参考, 命名为 `ref-<name>.strings` 放进 raw 目录, `merge.py` 会自动识别 `ref-*` 前缀纳入 refs。

## 上传回写

审校完产出 `dist/<platform>/zh-Hans-custom.strings` 后:
1. 在 translations.telegram.org 创建或选择你自己的自定义语言包
2. 页面上有 **Import** 功能, 上传 .strings 文件
3. 生成 `tg://setlanguage?lang=<你的包名>` 链接
4. 在客户端打开链接应用
