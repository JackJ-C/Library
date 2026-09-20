# R36—R37接续包阅读入口

先读 ../../R37_HANDOFF.md（包内路径R/R37_HANDOFF.md），其次是THEORY_RECOVERY.md与FAMILY_THEOREM_SUPPLEMENT.md。原缺失6份文件没有伪造替代到旧路径。所有新恢复实现与说明均在本目录。

结果在R/results/r32_r37_recovery/：PUBLIC_SUMMARY.json、TRAJECTORY_SCORES.tsv、R37_ACCEPTANCE.json、ARCHIVE_MANIFEST.json、VERIFICATION_SUMMARY.json、SEQUENCE_STREAM_CHECKS.json、FAMILY_THEOREM_CHECKS.json、POST_HOC_DISTANCE_DIAGNOSTIC.json。A/B是192份完整XZ原档及回执，audit是192份核验和32份顺序距离。

标准库、实测CPython3.13.5。进入R后运行 `python -m r32_r37.recovery.tests_recovery` 或 `python -m r32_r37.recovery.verify_recovery results/r32_r37_recovery/A/73100_measured.json.xz`。完整重新计算用独立副本与空A/B结果目录，不覆盖本证据包。原旧run()要求缺失原件，保持其失败语义；请使用本恢复协议的run_recovery或resume_chunks。

冻结前材料由RECOVERY_FROZEN.json绑定；工具时限导致的操作层协调器单独由ORCHESTRATION_RECEIPT.json登记；事后分析由R37_SUPPLEMENT_MANIFEST.json登记。它们不是一批全部事前冻结的材料，不能混称。旧FROZEN.json和12份原执行源码未改变。

本地交付完成；远端写入因工具安全检查被拦截，没有绕过或发布。本包不是完整Library仓库镜像，不包含缺失的R27、旧A/B原档或完整M历史。所有包内项目文件仅在R/。
