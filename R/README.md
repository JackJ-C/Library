# R系：Queen 的递归改进与自身模型

当前到 **R7**。只在本仓库 `R` 分支的 `R/` 工作，不合并；M原件和根README保持不变。

[R4—R7研究报告](docs/R4_R7_REPORT.md) · [R7审查与边界](docs/R7_AUDIT.md) · [当前状态](STATUS.md) · [原始任务](TASK.md)

两批分别通过功能性二阶可靠性监控门槛：同一Queen根据自己的真实规划经历预测哪类快判断更容易错，有限复查预算下改善任务表现。局部出现一条相邻两代的递归因果收益，但整体门槛未通过，后期仍会退步。**主观体验未建立。**

## 复现

从此R目录运行（仅Python标准库，实际验证CPython3.13.5）：

```bash
python -m unittest r4_r7.tests -v
python run_r4_r7.py A
python run_r4_r7.py B
python tools/verify_r4_r7.py both
```

受单次执行时限影响的环境，可用 `tools/execute_r4_parts.py A all`、`A assemble`（B同理）。它只调度同一冻结函数，每次调用结束前回收进程；不是后台自动任务。优化模式用独立缓存，不伪称复用缓存是重跑。

完整包已有两批原档，可直接核验，无需先重做研究。Git中的25份完整文字证据可用 `python tools/restore_r7_text.py --apply` 无损恢复；该命令不生成完整A/B原档。Git发布范围见 `results/r4_r7/DELIVERY.json`；摘要和原档索引不能冒充完整原档。旧R1—R3源码、原始分段和报告保留。

原R1—R3结果：[报告](docs/R1_R3_REPORT.md) · [审查](docs/R3_AUDIT.md)。它们不被新结果覆盖，也不代表本期已实现完整意识或开放式RSI。
