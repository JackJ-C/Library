# R31结果与原始证据位置

研究已完成，两个收益门槛均未通过；详见[完整报告](../../docs/R28_R31_REPORT.md)。

PUBLIC_SUMMARY.json保留两批预定指标与成本；TRAJECTORY_SCORES.tsv列48条完整路线；ADOPTION_EVENTS.json列9次space主路线采用；ARCHIVE_MANIFEST.tsv列48份XZ大小、压缩文件SHA-256及解压后原始JSON的SHA-256。

这些表不是原档。完整原档位于本会话交付包Library_R28_R31_完整交付_20260913.zip中的R/results/r28_r31/A与B目录。Git本次不含48份XZ；源码与冻结身份已在R分支，可以用r28_r31.run重新计算。直接运行采用默认结果路径时不覆盖现存文件。

交付包还含两批原SUMMARY、14项来源复原记录、35项冻结测试日志、12项补充测试、48份关联核验回执、16条普通JSON完整重跑回执及排序见证反例。原runner算术核验在保存前执行；补充关联核验的--linkage-only明确复用已验SHA的原算术回执，不伪称新科学样本。

所有工具均为只读离线检查；运行命令见完整报告。包是当前实验的可运行子集，不是Library全部分支镜像。
