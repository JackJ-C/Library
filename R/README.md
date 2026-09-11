# R系：Queen的递归改进与功能性自身模型

本目录与`R`分支隔离工作；不修改M系文件、不并回main。

**R0—R3的首轮结果：功能性自身输出模型与有界元改进通过；严格递归改进门槛未通过；没有据此建立主观意识。**

阅读顺序：[任务原文与边界](TASK.md) → [当前状态](STATUS.md) → [R1—R3研究报告](docs/R1_R3_REPORT.md) → [证据与局限审查](docs/R3_AUDIT.md)。正式验证在源码摘要登记后进行，A/B两批分开保留。

代码复用冻结M54 Queen、实际执行/观察路径、编译器和M8账本；副本放在本目录`vendor/`，原文件不改。本期重点是控制自身发令的功能性模型和诊断取证策略，不是复跑M54的全部复杂条件世界。

```bash
cd R
python3 tools/restore_raw.py
python3 -m unittest discover -s tests -v
python3 tools/verify.py
# 重新运行正式两批；不会改变冻结源文件：
python3 run.py A
python3 run.py B
```

实际运行环境为CPython 3.13.5，只有标准库。原始JSON完整无损保存在`results/raw_parts/`；还原器写回本目录的`results/`，不联网、不执行归档中的代码、不覆盖不同内容。配套ZIP也包含展开后的原档。本轮没有需要用户另行上传的正式原档欠账。

根目录README仍为`2026912.`；所有本期操作只在本目录内。
