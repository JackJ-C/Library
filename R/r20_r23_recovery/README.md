# R20–R23 恢复版 v2

中断的冻结实验已完整运行；两批稳定递归与校准促进后继门槛均未通过，主观体验未识别。阅读 `../docs/R20_R23_RECOVERY_REPORT.md` 和 `../docs/R23_RECOVERY_AUDIT.md`。

从R目录运行，均仅需标准库：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest r20_r23_recovery.tests -v
PYTHONDONTWRITEBYTECODE=1 python -m r20_r23_recovery.run A
PYTHONDONTWRITEBYTECODE=1 python -m r20_r23_recovery.run B
```

每条原始输出内容寻址保留。为适应单次工具时限，可分段运行 `python tools/resume_r23.py A 27100 27101`；已有普通结果会拒绝覆盖，`python -O tools/resume_r23.py A 27100` 真正重算并核对旧摘要。汇总为 `python tools/resume_r23.py A --aggregate`，B同理。

完整包内已有16份原档，可以先运行 `python tools/verify_r23_delivery.py` 校验摘要及逐条独立重放。这个新增工具不修改被冻结的选择程序或原核验器。

`tools/audit_r23_candidates.py A` 和B是事后全候选机会审查，不能将其oracle最小值当作Queen表现。所有新增审查记录与正式结果分开标明。

本目录是原冻结恢复版，不替代原R20合同；未完成的其他R注册不据编号宣告完成。数据位置/覆盖见 `results/r20_r23_recovery/PUBLICATION.json`。
