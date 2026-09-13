# R系当前状态：R31正式交付、补充资料及完整备份已归档

统一入口：[R31_HANDOFF.md](R31_HANDOFF.md)。正式报告：[R28—R31完整报告](docs/R28_R31_REPORT.md)；正式摘要：[PUBLIC_SUMMARY.json](results/r28_r31/PUBLIC_SUMMARY.json)；逐轨迹成绩：[TRAJECTORY_SCORES.tsv](results/r28_r31/TRAJECTORY_SCORES.tsv)；原档清单：[ARCHIVE_MANIFEST.tsv](results/r28_r31/ARCHIVE_MANIFEST.tsv)。

补充入口：[重复执行与辨认瓶颈](docs/R31_REPLAY_SUPPLEMENT.md)；[补充审查](docs/R31_AUDIT.md)；[补充摘要](results/r28_r31/REPLAY_SUMMARY.json)；[匹配消融](results/r28_r31/MATCHED_ABLATIONS.json)。

## 断点与原研究结果

断点HEAD为61e94edafb6f501b2a805d8e3e4ffb6409943083，冻结提交f7204df9c713b428e22b6106ef8d6569e3bc20aa保持；原恢复登记dc92fafd97e1de35240a28bed43d44f7b8a8a918。14项冻结内容恢复核对，按A=43100—43107、B=44100—44107完成，不换种子、不调正式算法。

R28编入统一模型、反例与消融；R29/R30将有限干预响应空间接到持续Queen的候选选择与程序绑定；R31两批三条持续路线共48轨迹、288代。space主路线16轨迹96代，9次组合更新，测试6次更好、1次更差、2次打平；严格非初代递归环节0、相邻严格链0/16。空间收益与有限递归门槛双批未通过。

原正式交付记录35项冻结测试、12项另一套只读核验测试、48份算术及关联复核和16条普通JSON路线。报告提交5d37a9c143738dd829fbfe6dd3d2b14e6dd032f2；原工具、摘要、清单及更新记录发布至c1dfa0031557f57840fa52ca4847af310e3e35de。保持这些材料原样，不把它们与另一次重复执行合并计算样本。

## 本次补充整合

用户授权将上一恢复会话的补充材料上传并整合到R。本次读取的R基线为bf6ad1c6fed49a7ec227274c8a73268db6404b09，main为15dd68540c17753b6faf2c26f6278d314037fe0b。未直接应用旧补丁覆写较新STATUS，而是保留上述正式进展并增加本节。

补充主报告首先提交于4b5874c38005bec79a7d7935e4ad384d62463593。本次另外补入R31_AUDIT.md、5份原版工具和3份补充结果文件。两份报告中上次“没有写入／待发布”的文字保留为历史事实，当前可得范围以本STATUS与R31_HANDOFF为准。

上一恢复执行的48份原档与正式清单逐字节一致；其35项冻结测试、18项R28构造诊断、10项新增核验覆盖测试在补充报告分别登记。10项不能与原正式交付的另一套12项混称同一测试套件。本次上传操作只重新检查文件完整性，没有新增科研实验或样本。

## 完整备份已上传并归位

完整文件：[Library_R31_full_backup.zip](delivery/Library_R31_full_backup.zip)，位于R分支的`R/delivery/`。2665933字节、147个文件，包含全部48份XZ、两批完整SUMMARY、逐档审查回执、事后诊断明细和原R28材料。原上传准备时，包内146项字节清单、14项冻结哈希及48份XZ/原始JSON双摘要均已核对一致。

用户上传提交`e1cd20b07c0d728da613f0faf792e0d144f9bb6f`最初将ZIP放在R分支根目录。现按用户“能调整一下吗”的要求，仅将该ZIP移动到`R/delivery/`并同步导航及交付清单。原路径与目标路径引用同一Git blob `bc395268514dac95177f45d4de1105e43a57fc56`；本次重新计算的本地原包大小、Git blob与SHA-256一致，ZIP的147项成员CRC通过。未重新压缩或修改包内文件，旧上传提交仍保留。

完整ZIP已在Git中，不再处于待上传状态。详见[交付包说明](delivery/README.md)及[机器可读登记](delivery/R31_REPLAY_PACKAGE.json)。不需要重新上传，也不要将旧补丁再应用到当前R。包内历史STATUS不覆盖本文件；归档内容未全铺到原生路径，复现应隔离解压完整包。

## 科学边界与接手点

空间仍为有限模拟干预响应伪度量，不是开放式因果世界；几何构造器与语法由研究者提供。总体风险证书UNKNOWN，经验性采用不是认证定理成功。主观体验未测量。旧R27缺失源码／数据及中断开发v0/v1档案未借本次补称完整。

研究编号止于R31，不登记或启动R32。唯一仓库JackJ-C/Library，唯一写分支R。此次路径整理的唯一R/目录外变化为移除根目录的Library_R31_full_backup.zip，其完整内容移至R/delivery/；其余变动仅为R/内交付导航和登记。不改M/main/根README/冻结源码，不建PR、不并回main、不强推、不启用自动工作流或付费算力。
