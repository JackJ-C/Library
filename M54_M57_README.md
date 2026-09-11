# M54–M57：条件发现与跨经历迁移

先读 [M0–M57总览](LIBRARY_M0_M57_TOTAL.md)，本期细节见 [报告](docs/M54_M57_REPORT.md) 与 [仓库审查](docs/M57_REPO_AUDIT.md)。

两批冻结验证通过操作性联合门槛；不宣称完整意识、任意机制发现或开放式RSI。与本期对应的实际实例是library_m54.queen.Queen，旧M0–M53文件不修改。

```bash
python3 -m unittest library_m54.tests -v
python3 tools/verify_m57_supplement.py both
# 需要从头复现时：
python3 run_m54_m57.py A
python3 run_m54_m57.py B
```

标准库，实测CPython3.13.5。包中已有原始A/B标准XZ，可直接核验。原冻结verify_m54_m57.py误将查表占位模型当作真实程序，失败记录保留；请使用上面的补充核验器，它不训练、不改原档。

freeze.json禁止覆写；再次运行相同实验不增加独立样本。模型只覆盖非零条件增益×命令的模7先验，条件树深度和搜索预算有界。相同信息JSON打平，无历史对照在主变化实验更省，稳定缓存恢复中旧历史可减少新探测，详见分项结果。

发布状态：当前只在会话工作区完成，没有新的远端Git提交。补丁只新增本期内容，不含旧源码修改。详细原档批注在docs/M57_DELIVERY_STATUS.md。
