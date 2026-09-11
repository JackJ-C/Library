# 一条真实发生的连续链：确认批C，种子3000

来源：原始记录 `617292656e389179eb5831d661fec2f0742a2b630af60683c1d51b74d0f50083` 中同一Queen的32窗口轨迹。事件真值只在评分器，下面为事后解释，不是发给Queen的答案。

| 窗口 | 之前的解释 | 实际诊断与修订位置 | 下一段实际任务结果 |
| --- | --- | --- | --- |
| 0 | 环境 [-1, 1]；Worker [-2, 0, 2]/[-2, 0, 2] | environment_model；读取/探测证据 [3, 4, 5, 6] | apple→1：正确；apple→1：正确 |
| 4 | 环境 [1]；Worker [0]/[0] | environment_model；读取/探测证据 [98, 103, 104, 105] | apple→0：正确；apple→4：正确 |
| 9 | 环境 [-1]；Worker [0]/[0] | queen_judge, worker1, environment_model；读取/探测证据 [210, 224, 225, 226, 227] | apple→1：正确；teacup→0：正确 |
| 17 | 环境 [1]；Worker [0]/[0] | worker0；读取/探测证据 [413, 418, 419, 420, 421] | apple→2：正确；teacup→2：正确 |
| 24 | 环境 [1]；Worker [0]/[0] | queen_judge；读取/探测证据 [575, 584, 585, 586, 587] | teacup→1：正确；apple→2：正确 |
| 29 | 环境 [1]；Worker [0]/[0] | queen_judge；读取/探测证据 [697, 706, 707, 708, 709] | teacup→2：正确；teacup→4：正确 |

窗口0是启动校准，不算后来一次自我进化；其余五次有非空修订，同一个实例、账本和历史保留。每次按实际证据重开解释，不是按事件类型通知直接选择修法。

## 后来怎样重新评价过去的自己

**changed**：窗口8回访窗口1；当时修订版1、当前2。公开视图为 `[{"commands": [1]}, {"commands": [4]}]`，输出 `[0.0, 1.0]`。
**identical**：窗口8回访窗口3；当时修订版1、当前2。公开视图为 `[{"commands": [3]}, {"commands": [3]}]`，输出 `[0.5, 0.5]`。
**merge**：窗口8回访窗口3；当时修订版1、当前2。公开视图为 `[{}, {}]`，输出 `[0.5, 0.5]`。

changed案例以实际旧命令与当前同输入重放不同为准；identical中另一控制者确实执行相同命令；merge中不同路径最终状态合流，最小归属通道没有前驱命令，保持各半。归属不是拿当前程序相似度去强行否认旧自己。

## 后续错误与依据撤回

同一存续Queen在主轨迹后接受一个仅对茶杯出错的候选，未来实际出错后自动回退。其后又撤回一项标定依据，四个任务入口全部停止，再取证恢复。对应布尔检查为：

```json
{
  "all_four_entries_blocked": true,
  "automatic_rollback": true,
  "bad_candidate_rejected": true,
  "latent_false_confidence_before_counterexample": true,
  "later_error_observed": true,
  "revalidated_future_restored": true,
  "same_lived_queen": true,
  "tentative_accepted": true,
  "withdrawal_reproof_future_correct": true,
  "withdrawn_support_blocks_four_entries": true,
  "withdrawn_support_closes_permission": true
}
```

这些压力检查中的“true”包含实际失败被观察到，不等于没有错误。原始完整切片在运行包；`trace_3000.json`是摘录，不能当作完整轨迹。
