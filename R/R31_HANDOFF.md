# R31统一阅读与补交入口

## 当前阅读顺序

1. 原冻结研究的正式报告：[R28—R31报告](docs/R28_R31_REPORT.md)。
2. 同一冻结版本的重复执行与辨认瓶颈补充：[R31_REPLAY_SUPPLEMENT.md](docs/R31_REPLAY_SUPPLEMENT.md)。
3. 补充核验器的覆盖范围与限制：[R31_AUDIT.md](docs/R31_AUDIT.md)。
4. 补充摘要：[REPLAY_SUMMARY.json](results/r28_r31/REPLAY_SUMMARY.json)；匹配消融：[MATCHED_ABLATIONS.json](results/r28_r31/MATCHED_ABLATIONS.json)；10项核验覆盖回执：[AUDIT_REGRESSIONS.json](results/r28_r31/AUDIT_REGRESSIONS.json)。

本次只把已有补充材料整合到R分支，不新做研究、不占用R32，不把重复执行计作新科学样本。R27的FINAL_HANDOFF.md、原R31正式报告和全部冻结来源保留不改。研究结论仍为有限空间构造进入决策有支持，稳定空间收益和严格递归增强未建立。

## 历史发布说明与当前发布说明不能混淆

两份补充报告保留了上一次恢复执行时的原文，包括当时“没有写入”“待发布”的事实；这是历史记录，不是本次补交失败的声明。其当前发布范围以R/STATUS.md和本文件为准。

本次整合以R分支bf6ad1c6fed49a7ec227274c8a73268db6404b09为起点，补充主报告首先提交于4b5874c38005bec79a7d7935e4ad384d62463593。补充报告、5份原版只读工具和3份结果文件均以原交付包内容上传，不改历史科学结果。

## 完整原档包已上传并归位

完整备份：[Library_R31_full_backup.zip](delivery/Library_R31_full_backup.zip)。位于R分支的`R/delivery/`。它与会话中的“Library_R31_恢复与补充核验.zip”逐字节相同，仅使用英文文件名；共2665933字节，147个文件，包含48份XZ原始数据、两批完整SUMMARY、逐档审查回执、事后诊断和原R28材料。

用户在提交`e1cd20b07c0d728da613f0faf792e0d144f9bb6f`上传到R分支根目录；随后按用户要求移动到上述交付目录。移动前后直接使用同一Git blob：`bc395268514dac95177f45d4de1105e43a57fc56`，没有修改ZIP内容，原根目录路径已移除。文件大小、Git blob和SHA-256与本地原包核对一致，当前ZIP成员CRC检查通过。

不需要再次上传或应用旧补丁。详细文件指纹与使用说明见[交付包说明](delivery/README.md)。这是完整内容的归档备份，不等于147个文件已经逐个铺到原生路径；不要解压覆盖当前R目录。

## 复现

将完整ZIP解压到一个新的、隔离的目录，在包内R目录执行：

```bash
python tools/verify_r31_delivery.py
python -m r28_r31.tests
python tools/r31_supplemental_audit.py
python tools/r31_audit_regressions.py
python tools/r31_posthoc_diagnostics.py
python tools/r31_finalize_summary.py
```

上述5份补充工具已经同时保存到Git的R/tools/，均保持旧字节。verify_r31_delivery.py校验的是原交付快照的146项文件清单，必须针对隔离解压的原包运行；当前Git导航文件已更新，不应据此改写原包清单。仅克隆后仍需解压上述ZIP，才能按原包布局取得全部本期原档。

本次没有补齐旧R24—R27缺失源码及中断环境的全部开发v0/v1档案，也没有把R并入main。
