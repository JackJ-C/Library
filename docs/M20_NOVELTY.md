# M20：原创性查核与贡献边界

## 结论

**全球原创性尚未建立，而且若干宽泛的“首创”表述已有直接先例，不能使用。** “能改自己的代码”“修改元修改程序”“读取全部旧轨迹”“让群体共享经验”“用证书限制自改”都不是本项目可独占的新方向。[1–6,9–11]

本轮源码是为Library独立编写的参考实现，没有复制外部仓库。但是独立编写、独立想到、工程新组合和全球学术优先权是不同命题。用新名字组织已知机制不能直接交付一套全球新理论。

核对截至2026-09-10可访问的原始论文或作者/机构资料。检索围绕元代理自修改、自写验证器、历史执行轨迹、群体演化、语法引导合成和证书有效性展开。多篇2026资料是预印本，不将作者报告的结果提升为已获独立复现的事实。没有访问外部GitHub仓库，没有运行其代码；没有跨方法相同基准的性能比较。

## 直接相邻工作

| 原始工作 | 已有相关内容 | 对Library主张的影响 | 本轮阅读范围 |
| --- | --- | --- | --- |
| Darwin Gödel Machine [1] | 在代码中提出自修改，用经验评价积累候选档案 | 自改代码及保留演化档案不能称为首创 | 摘要、方法、安全和限制相关正文 |
| Hyperagents [2] | 任务代理与元代理置于可编辑程序，元修改过程亦可编辑 | “元机制也能改”已有直接先例；本轮复制恢复比它的可编辑范围更窄 | 摘要、引言、方法、评估设置 |
| Meta-Harness [3] | 通过文件系统访问旧候选源码、成绩与执行轨迹，提出新的完整程序 | “历史不仅存总分，而是可再进入原始证据”已有直接交集 | 摘要、引言、方法 |
| Self-Authored Verification Is Unreliable [4] | 检验自写验证与实际部署间的差距，使用封闭外部接受边界 | 不能将“不让自己给自己无条件发证”说成新原理 | 摘要、引言、机制相关正文 |
| Meta^n [5] | 固定元操作反复读取它的产物与轨迹，形成更高层过程 | 递归观察并不必然消除固定基础；相关做法已有先例 | 摘要及递归机制正文 |
| Group-Evolving Agents [6] | 以群体为演化单位共享经历，报告框架错误恢复 | 群体支持改进和故障恢复是已有方向；不等同本轮多数协议 | 摘要、方法相关正文 |
| Syntax-Guided Synthesis [7] | 明确语法与约束共同界定程序合成 | M18属于已知程序合成范式，不是新数学 | 原作者机构发表页与摘要 |
| The Sybil Attack [8] | 多个身份不代表多个独立实体 | 复制日志/伪造名字不能扩充可靠票数的风险已有先例 | 原作者机构摘要 |
| Self-Modifying Lean Proof Agents [9] | 可变工作区置于固定可信运行时，证明在外部规则下检查 | 小可信核加大可改范围并非全新总架构 | 原始摘要 |
| Self-Evolving Agents with Anytime-Valid Certificates [10] | 版本化执行框架与固定风险预算的可审计门禁 | 版本证书与有条件风险不是本轮独有 | 原始摘要 |
| WebWorld [11] | 以真实浏览器执行检验改变及旧能力保持 | “修复目标+旧成功不退化”的验收思路已有相邻应用 | 原始摘要 |

[2]的原始摘要页记载首次提交为2026-03-19；当前可访问HTML正文还显示2026-08-24的内部日期。本报告按摘要页列首发日期，并以当前可见v1正文核对机制，不据此臆测未显示的版本历史。

## 与最接近的三项区分

Hyperagents已经明确讨论修改产生未来改进的程序。本实验恢复损坏的`generate`和`audit`，但使用同伴已有实现，没有合成更好的元算法；两者不能视为同一能力。Hyperagents的主实验也保留某些固定外层机制，例如方法部分明确说明主实验父代选择规则固定。[2] 这并不使我们的类似边界变成原创，只说明比较必须逐层注明可改范围。

Meta-Harness通过原始历史帮助程序改进，直接碰到图书馆的核心直觉。本轮可以独立贡献一个有源代码、故障注入和失败记录的细粒度测试，但没有证明这种历史组织优于该工作，也没有比较相同的信息和资源预算。[3]

自写验证器研究讨论“自己测试通过，部署仍失败”。我们在有限函数上给出同样性质的可执行反例，并保留错误安装器和错误参照。这有助于说明我们的失败范围，但不是抢占其研究主题的优先权。[4]

## 当前候选贡献逐项判定

| 候选表述 | 判定 | 理由 |
| --- | --- | --- |
| “第一套可改自身元程序的代理” | 不支持，已有直接先例 | Hyperagents等明确包含该机制 |
| “第一套用完整历史修复自己的代理” | 不支持，已有直接交集 | DGM档案、Meta-Harness原始轨迹等 |
| “递归语法使未知机制都能修复” | 本实验反例否定强表述 | 未测分支和预算失败仍存在 |
| “四单元和版本化票决证明整个Queen无需可信基础” | 本实现直接不支持 | 固定probe/recover/quorum/安装器仍存在 |
| “六个可损真实函数槽的504个故障组合及恢复后96次合成流程” | 本轮新增工程证据 | 可复现具体基准；未证明这是首个此类组合 |
| “切片复制不增加独立支持、旧版本支持不自动延续的统一验收记录” | 有用的组织与检验约定 | 与身份认证、版本一致性和证据维护存在重叠；尚无独立优势证明 |

此时最稳妥的研究定位是**已知思想基础上的有界实验框架与反例集**。未来真正需要证明的新贡献，应是此前方法未覆盖的条件结论、算法改善或同预算下独立实验增益；不是继续增加编号或扩大“自己”的命名范围。

## 原始资料

1. Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, Jeff Clune. *Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents*. 首发2025-05-29；可见v3为2026-03-12。https://arxiv.org/abs/2505.22954 ；方法阅读：https://arxiv.org/html/2505.22954v3
2. Jenny Zhang et al. *Hyperagents*. arXiv:2603.19461，首发2026-03-19。https://arxiv.org/abs/2603.19461 ；https://arxiv.org/html/2603.19461v1
3. Yoonho Lee, Roshen Nair, Qizheng Zhang, Kangwook Lee, Omar Khattab, Chelsea Finn. *Meta-Harness: End-to-End Optimization of Model Harnesses*. 2026-03-30。https://arxiv.org/html/2603.28052v1
4. Diandian Guo et al. *Self-Authored Verification Is Unreliable in Heuristic Self-Improving Agents*. 2026-07-27。https://arxiv.org/abs/2607.24300 ；https://arxiv.org/html/2607.24300v1
5. Zae Myung Kim, Young-Jun Lee, Seungyeon Jwa, Dongyeop Kang. *Meta^n: Recursive Self-Improvement through Emergent Depth*. 2026-08-25。https://arxiv.org/abs/2608.24735 ；https://arxiv.org/html/2608.24735v1
6. Zhaotian Weng et al. *Group-Evolving Agents: Open-Ended Self-Improvement via Experience Sharing*. 2026-02-04。https://arxiv.org/abs/2602.04837 ；https://arxiv.org/html/2602.04837v1
7. Rajeev Alur et al. *Syntax-Guided Synthesis*. FMCAD 2013。https://www.microsoft.com/en-us/research/publication/syntax-guided-synthesis-2/
8. John R. Douceur. *The Sybil Attack*. IPTPS 2002。https://www.microsoft.com/en-us/research/publication/the-sybil-attack/
9. Yuqing Li, Zeguan Wu, Yu Gan, Junyu Liu. *Self-Modifying Lean Proof Agents with Verifier-Grounded Benchmark Coevolution*. 2026-07-19。https://arxiv.org/abs/2607.17352
10. Biswa Sengupta. *Self-Evolving Agents with Anytime-Valid Certificates*. 2026-07-01。https://arxiv.org/abs/2607.00871
11. Jiajun Wu et al. *WebWorld: The Browser as a World Model for Self-Improving Web Code*. 2026-08-31。https://arxiv.org/abs/2608.30530

本报告不是专利检索、法律意见、全球穷尽文献审查或同行评审结论。只列使用的原始资料，不把检索未命中当成原创性证据。
