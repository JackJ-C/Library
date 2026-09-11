# 原始备份上传核验与连接诊断

核验日期：2026-09-12。只操作 `JackJ-C/Library` 的现有交付分支；不修改研究源码、main 或其他分支。

## 已核验的备份

用户上传提交：`a76cbab85b1618ce7645af9b10a09306a0a0e124`。

- 远端路径：`Library_available_evidence_backup_20260912.zip`
- 远端字节数：14,612,661
- 远端 Git blob SHA-1：`aa6a2714d264e8e2ee034051eede6a8fc019e07c`
- 本会话本地原包字节数：14,612,661
- 本地按 Git blob 格式计算的 SHA-1：`aa6a2714d264e8e2ee034051eede6a8fc019e07c`
- 本地原包 SHA-256：`7e6e6f4570ef576561620d012de21d889714c4a82964412061ef5dd511d34fcc`

远端树中的大小和 Git 内容地址与本地完整原包相同。此处没有声称通过连接器重新下载了14MB远端二进制并重算SHA-256：当前fetch接口拒绝非UTF-8内容，本次使用远端Git对象哈希与本地Git对象哈希比较。

状态：这份完整备份已进入远端Git。此前两份待传清单的32份已知原档现已作为该ZIP的归档内容保存，不是自动展开到各自results路径。更早未取得的历史材料仍不在此确认范围；原清单与原报告保留，不覆写历史。

## 本次实际诊断

1. ChatGPT内GitHub专属操作权限为“Allow all actions”；这是确认策略，不等于所有运行环境自动获得Git凭据。
2. 当前会话已提供创建文件、Git对象等写入操作。本记录的成功提交可作为当前交付分支写入测试；不据此推定所有端点或其他时间均可用。
3. 本会话命令执行环境有git，但没有gh可执行文件。常见凭据环境变量GH_TOKEN、GITHUB_TOKEN、GIT_ASKPASS与SSH_AUTH_SOCK未设置；没有遍历其他凭据存储，也不推断所有凭据一定不存在。
4. 对github.com及api.github.com的DNS查询与HTTPS连接均失败，返回`[Errno -3] Temporary failure in name resolution`。阻塞发生在HTTP/GitHub授权检查之前。原因是解析配置、网络策略还是暂时DNS故障，现有观测无法进一步确定；不能把它说成用户未授权，也不能归咎于用户Mac或代理。
5. 当前连接器的fetch接口对ZIP返回“GitHub Fetch only accepts UTF-8 text”。这是此读取操作的内容类型限制，不是GitHub仓库存储限制或权限拒绝。

结论：区分GitHub授予的访问权限、ChatGPT内的操作确认策略、当前会话提供的动作、以及独立命令执行环境的网络/凭据。重新扩大用户授权不能直接修复这里复现的DNS问题。未更改任何权限设置，未请求或保存用户访问令牌。
