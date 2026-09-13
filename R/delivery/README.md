# R系交付包：只需上传一个ZIP

## 待上传的R31恢复与补充核验包

目标：`R`分支的`R/delivery/Library_R31_full_backup.zip`。

| 校验项 | 期望值 |
|---|---|
| 文件大小 | 2665933字节 |
| SHA-256 | `577892b1934b6db2935a4630ad018a6699241f704c11cf1d3f20bc357ac5d8d2` |
| ZIP内文件数 | 147 |
| 正式XZ原始数据 | 48份，A/B各24份 |

本次补交工具已成功上传文本及源码，但完整本地ZIP尚未自动传入GitHub。这个清单只是预期文件身份，不是上传成功证明。此前R31_PACKAGE.json属于另一份既有交付登记，不覆盖、不混同。

## 网页操作

1. 打开本目录，确认左上方分支显示`R`，目录路径是`Library / R / delivery`。
2. 点击`Add file`，选择`Upload files`。
3. 拖入从当前会话下载的`Library_R31_full_backup.zip`。保持ZIP，不要解压，不要上传.patch。
4. 提交说明填写`R31: upload complete replay and audit backup`。选择直接提交到`R`分支（`Commit directly to the R branch`），然后点击提交按钮。不要选main，不需要新建分支或Pull Request。

若页面出现保护规则或权限错误，应停止并保留具体提示，不改选main、不强推。

上传单个ZIP不会覆写其中的旧STATUS或源码，它只新增一个归档文件。该归档保存147个文件的完整内容；仓库内原生A/B原档目录仍可能不存在。需要运行时，将ZIP解压到隔离目录，再在包内R目录执行`python tools/verify_r31_delivery.py`。

## 本次补交边界

只在JackJ-C/Library的R分支、R/路径内增加资料和更新导航。原M系、main、根README、冻结源码和正式原始结论不改动。未启动新实验，也没有新增R32。
