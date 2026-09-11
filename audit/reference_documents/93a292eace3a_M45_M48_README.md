# Library M45–M48：匿名作用证据、未来控制与旧历史重建

本轮为本地完成的研究交付，**未推送到GitHub**。基线是JackJ-C/Library的`a107e655e5a5c4d9dd00a3032ee8d190c8eea4a6`；保留旧分支、旧结果和PR。当前连接缺少写操作，命令行连接也失败。

先读[研究总报告](docs/M45_M48_REPORT.md)，再读[接线审查](docs/M48_INTEGRATION_AUDIT.md)。[理论笔记](docs/M45_M48_THEORY.md)区分来源确定性、动作可确定性和未知机制边界。

主A/B为各32个新种子、八方法；补充C/D为各16个新种子、五方法。两种实验分别冻结，不混计独立样本。三条匿名效果不含控制者命令/作者，自己的实际发令来自先前存入的本地记录。来源—机制相容约束进入可执行控制程序。

主方法后续任务10,100/10,240正确；重新推断后的3,840项任务全部正确。旧数据可支持新控制，但显式独立身份状态不是必要：同信息JSON和近邻边际对照打平。补充实验中，恢复缓存后主方法32次新探测，对照撤回关键旧意向后需要98次；两组未来320/320正确。模型外的位置依赖变化仍失败，开放式修复未完成。

## 运行

Python标准库；实际验证CPython3.13.5。运行包已含原始XZ，可以直接核验：

```bash
python tools/verify_m45_m48.py both
python tools/verify_m48_retrieval.py
python tools/audit_m48_claims.py
```

完整重跑：

```bash
python -m unittest library_m45.tests -v
python run_m45_m48.py A
python run_m45_m48.py B
python tools/m48_retrieval_audit.py C
python tools/m48_retrieval_audit.py D
```

原合同和源码哈希已冻结，不覆盖freeze.json。修改源代码后应另立协议和新验证，不覆盖本期原档。仓库旧套件分别在新进程运行，避免旧集成代码的模块替换影响其他测试：

```bash
python -m unittest library_m37.tests -v
python -m unittest library_m41.tests -v
```

## 对应编号

M45：自行检索同步的意向/匿名效果，无正确见证索引，三路真实来源。
M46：相容约束进入控制；配对弱化与恢复、同信息强对照。
M47：预设有限非线性族和未知状态依赖压力；不冒充开放式新语言。
M48：证据撤销和接口审查；另冻C/D验证较旧原始记录的实际效用。

## 补丁

随交付的`Library_M45_M48_additions.patch`仅新增本期文件，不修改既有程序。先在具有上述基线依赖的Library研究工作树中执行`git apply --check`，再应用。不是新远端提交，也不会自动合并既有冲突。运行包中的旧README和旧阶段原档仅作依赖和历史复现保留，以本文件为本期入口。
