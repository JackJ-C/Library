# 原始证据位置

`summary.json` 与 `verification.json` 是本轮实际运行的摘要和独立核验结果。

`kernel_trace.json.xz` 是标准XZ压缩的核发现、三代接力及调用轨迹；`audit/audit.json.xz` 是标准XZ压缩的完整审查JSON，列出实际命令、缺失范围、源码摘要和漏洞复现。可用Python标准库 `lzma.decompress` 读取，不需要专有生成器。

完整实验原始JSON（包括2048条组合流程）、其XZ压缩、首轮和中间版本原档/源码快照，以及审查JSON所引用的各个运行日志，保存在交付文件 `Library_M29_M32_v0.8.zip`。没有将完整实验原档或全部日志同步到Git；不要把这里的摘要误认成全部证据。

Git-only复现顺序：

```bash
python3 run_m29_m32.py
python3 tools/verify_m29_m32.py
python3 tools/audit_library.py
```

最终原始JSON SHA-256：`02162b0a0436fe7cbbb7c91b3c9a564dcf3fbdadc4feb9b56b06f039f76e70a9`。

审查程序会生成明文JSON和运行日志。只使用独立运行包时，历史源码执行覆盖仍是27/46份，不是完整仓库镜像；报告列出的其余19份在远端存在但未进入这次执行副本。

有限实验通过，最终“全部高层规则自主创造”仍未通过验收，两者分别记载。
