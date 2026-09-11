# M12–M15 独立运行包

对应 GitHub：JackJ-C/Library，main 提交 1d496a4688515127b84458cc664314cf1e4de220。

这是本轮研究文件与最小旧阶段依赖的运行包，不是整个仓库历史的复制。README 中早期阶段文档链接应在仓库中阅读。本轮全文、合同、代码、两个完整原始结果及实际执行日志均包含。

在解压目录运行：
python3 tools/verify_m12_m15.py
python3 -m unittest library_m12.tests -v
python3 run_m12_m15.py

只有标准库。交付时提高了原 JSON 的 xz 压缩级别，未改变解压后内容或实验摘要。新完整运行会重复使用相同内容地址的原档。

原 M8 类保留；使用新撤销策略需显式使用 library_m12.guard.RevocableReader。固定元审查核、任务规范、可信记录和有限程序族仍是明确假设。
