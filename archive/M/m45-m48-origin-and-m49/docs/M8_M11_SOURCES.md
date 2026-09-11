# M8–M11：来源与原创性边界

核对日期：2026-09-10。本轮只读原始论文、作者课程材料和官方统计手册，不访问其他 GitHub 仓库。以下是相邻工作的核对，不是穷尽性的查新报告。

## 原始来源

[1] Armando Solar-Lezama，MIT《Program Synthesis》Lecture 17，Counterexample Guided Inductive Synthesis。读取了 HTML 讲义关于“提出候选—寻找反例—约束下一候选”的正文。讲义将早期构造追溯到 2006 年工作、术语推广到后续工作。Library 不把反例引导循环称为自己首创。

https://people.csail.mit.edu/asolar/SynthesisCourse/Lecture17.htm

[2] Shervin Javdani 等，*Near Optimal Bayesian Active Learning for Decision Making*，AISTATS / PMLR 33:430–438，2014。核对出版方论文页面和摘要。该工作已有“足以进入同一决策区域，不必消除所有不确定性”的思想。没有复现论文算法或移用其性能界。

https://proceedings.mlr.press/v33/javdani14.html

[3] Johan de Kleer，*An assumption-based TMS*，Artificial Intelligence 28(2):127–162，1986。DOI:10.1016/0004-3702(86)90080-9。出版方摘要明确涉及假设集合与多个可能解释的管理。摘要经检索可见，直接打开全文页面遇到访问限制；本轮不声称阅读全文。Library 的依赖撤销与其研究方向重叠。

https://doi.org/10.1016/0004-3702(86)90080-9

[4] Dana Angluin，*Learning regular sets from queries and counterexamples*，Information and Computation 75(2):87–106，1987。DOI:10.1016/0890-5401(87)90052-6。核对出版方检索摘要；其查询/反例学习依赖明确的教师或查询条件。本轮不能把“没有故障名称，但有强观测接口”当作无假设学习。全文页面直接访问受限。

https://www.sciencedirect.com/science/article/pii/0890540187900526

[5] Mark Braverman、Roi Livni、Yishay Mansour、Shay Moran、Kobbi Nissim，*Learning from Equivalence Queries, Revisited*，arXiv:2604.04535v2。初稿 2026-04-06，当前读取版本修订于 2026-06-25。核对作者预印本摘要及版本日期：其研究部署—反馈—更新循环和不同反例反馈条件。没有读取或验证全文定理，不能据此声称我们的多轮机制与所有已有方法都不同。

https://arxiv.org/abs/2604.04535v2

[6] NIST/SEMATECH e-Handbook of Statistical Methods，1.3.6.6.18 Binomial Distribution。核对二项概率质量函数和累积分布公式。本文多数票尾概率由该公式求和，跨输入及跨轮上界由并集界自行推导。

https://www.itl.nist.gov/div898/handbook/eda/section3/eda366i.htm

## 本轮什么不是新发明？

有限域消元、平方自由布尔多项式、集合交集的单调性、DAG 可达传播、反例引导学习、假设管理以及二项尾概率都不是新发明。对照只使用有限数据和可检查推导，不把文献名称换掉后宣称独立理论。

## 哪一部分作为候选贡献保留？

区分“系统变化”和“解释模型变化”，为旧判断记录不同类型的引用与证明依赖，让模型扩展撤销旧证书但不抹除反例审查，再以明确目标、范围和风险预算重新批准修改。这个研究组合是本项目实际构建并核验的候选，尚未建立全球优先权、现实任务性能优势或开放式自我进化。

理论 v0.3 的定义与证明是本轮直接写出的推导；数值是本仓库实际执行结果，不来自以上论文。普通日志打平、语法外失败和相关噪声失败是证据的一部分，不因不利于原创主张而删去。
