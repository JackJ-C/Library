# R41正式运行前冻结登记：根修改与后续部署的四臂因果检验

本轮恢复基线R=bba1c11d65ca9f4ca73f40588bc7b6528fb30912；main=15dd68540c17753b6faf2c26f6278d314037fe0b。已经读取远端R40结果与ERRATA，但原R39冻结源码和322份原档未恢复。R41是独立补充，不是原R39复现，不重写旧冻结，也不将历史汇总当本轮验证。

完整本地FROZEN.json（21项新旧文件）的SHA-256：

```
129fafd9c9e1e04b18f30967be8422dce5a17f783100942b9f3a7e70982f8d4d
```

运行标签日期2026-09-21；实际运行时钟冻结时间2026-09-20T17:38:55.690674+00:00，两者分开登记。当前尚未运行正式A/B/辅助数据。开发0、1、2、3及辅助4；24项测试在普通Python和-O下通过，开发失败另留原件。

## 新实验和主判据

每origin从原INITIAL至多六轮，取原采用规则第一次接受的allocator AST+scale为根；无根保留。完整部署前状态由实验者复制，实际执行四臂：keep_update、keep_frozen、remove_update、remove_frozen。前两者部署根子、后两者保留父机制；update允许后续三轮部署新allocator，frozen仍做候选/取证/排序/采用判断但禁止新allocator安装。各臂任务程序仍依当前allocator选择。另逐根实际重跑restore和annotation-only三轮。

共同外部随机输入按seed/phase/index/role命名，不含arm；因干预而变化的候选、任务及历史保留为合法中介。使用不变R37 SpaceQueen/R3/M54/M8和原算法；八候选、六任务、12内测、3pilot块、至多2额外完整候选检查、4新采用块、>.002采用阈值，风险证书UNKNOWN。

端点由16个共同外部slate审计，测试allocator选择任务程序后的损失Y(a,g)，不是R39的donor产物assay或完整Queen通用能力。G1=Y(1,0)-Y(1,1)，G0=Y(0,0)-Y(0,1)，C=G1-G0，T=Y(0,1)-Y(1,1)，T0=Y(0,0)-Y(1,0)，并有C=T-T0。C正可只是从坏起点追赶；T正可只是根直接收益，不能单凭其中一个宣称RSI。

A=95100—95163，B=96100—96163，各64origin，两批不调参、不合并挽救。无根效应记0，条件根另列。每批5000次origin bootstrap为描述性区间。重复优势门槛：两批分别G1、C、T均>.002且各描述区间下端>0。另列独立生成器理想化下6项比较总alpha=.05 Hoeffding界。局部生产性候选需该origin G1/C/T均>1e-12、keep_update有后续真实更新且终点不同于根子，仍不等于稳定RSI。

## 辅助取证

97100—97115共16世界，各fixed/active；明示研究者提供有限World族先验后最多14学习格，另各自4802格外部全审计，费用分列。97100另有两臂command2单格域外控制，不能从command1学习资料认证该格。辅助不并入RSI样本。

## 源身份和独立核验

experiment.py SHA256=915603ee6518ff73ce539d19a9eadb2791bd54d86cb70c401b5ebb42b6434f64
verify.py SHA256=f1497f14eca05f030871ef68f2ea01d2142315b6a884c33f3b19dbb6aa5c27d2
PROTOCOL.md SHA256=45138081098e1f03a568e15d71df3b1e22cfbe96884226ab1b73fef542854e25
THEORY.md SHA256=7189a5c1097ec365a69f4bab20b282a31212af80e397595eba6d4521a65858a9

12份继承执行依赖逐项匹配原R37冻结值；原ZIP身份和686项CRC重新核对。verify独立重写问题/候选生成、两类解释器、求解、race、距离、选择、采用、审计、lineage和费用，不导入原Queen/学习器。独立是代码路径，不是独立团队。证明依赖撤销不等于删除因果祖先；两者分别实际检验。

本登记只写R分支R/，不改M/main/根README/旧冻结，不PR/合并/强推/工作流/付费计算/密钥/后台任务。前台离线执行；遇写入阻止不绕过。完整冻结源码检查点已生成，后续原档逐origin保存；本文件不是正式结果或完整原档已上传的声明。
