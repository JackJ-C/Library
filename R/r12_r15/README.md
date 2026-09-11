# R12–R15：在线可靠性与元改进的独立实验线

报告：[R12_R15_REPORT](../docs/R12_R15_REPORT.md)。接续：[status/R12_R15](../status/R12_R15.md)。审查：[R15_AUDIT](../docs/R15_AUDIT.md)。

冻结合同先于两批运行。A/B各8个完整种子轨迹：预测适应两批通过，在线联合仅B通过，稳定递归两批未通过，主观体验未被当前协议识别。这是研究进展，不是原始两个总目标已经完成。

同分支存在并行R8开题及后续R12接口修补，不能因编号相同而合并代码或分数。本实验身份为 `R/docs/R12_R15_CONTRACT.md`、`R/results/r12_r15/FROZEN.json`，实现仅 `R/r12_r15/`。

在仓库根目录：

```bash
(cd R && PYTHONDONTWRITEBYTECODE=1 python -m unittest r12_r15.tests -v)
PYTHONDONTWRITEBYTECODE=1 python R/run_r12_r15.py A --seed 11100
PYTHONDONTWRITEBYTECODE=1 python R/tools/verify_r12_r15.py A --seed 11100
```

完整批次依次运行A的11100–11107及B的12100–12107，各条都从头实际执行；随后用 `python R/run_r12_r15.py A --summary` 与B汇总。只读补充核验为 `python R/tools/audit_r15_counters.py A --seed 11100`，不导入学习器。标准库，CPython3.13.5已实测，禁止联网研究代码或外部服务。

运行包带20份完整开发/正式JSON-XZ原档及附加开发材料。Git若只有摘要，可运行对应种子重建，再检查相同SHA-256。来源、已上传与未上传清单见 `R/results/r12_r15/DELIVERY.json`，不能以摘要代替原档。

旧R7来源在原处只读复用；本次所有新文件限R/，不得并回main或改M原件。没有后台任务。
