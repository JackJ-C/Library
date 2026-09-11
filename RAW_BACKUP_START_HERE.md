# 原始档案：只需上传一个 ZIP

## 当前状态

**代码、M54–M57报告与M0–M57总览已经在本分支。完整原始备份包已经整理、从新目录解压并逐文件核验，但备份ZIP尚未上传。** 此说明不把“已打包”改写成“已在GitHub”。

最新M54–M57待传清单19份，以及此前M37–M48待传清单13份，全部32份原档都在备份包中，合计10,912,094字节。还保留本会话实际取得的九份原始研究运行包，内部668份文件逐个核对SHA-256。原运行包字节不变，未重新运行研究来替代原始数据。

## 最简单的上传方式

1. 从当前ChatGPT会话保存 `Library_available_evidence_backup_20260912.zip`。**不要先解压。**
2. [点这里打开本分支的上传页面](https://github.com/JackJ-C/Library/upload/delivery/m54-m57-verified-20260911)，把这一份ZIP拖进去。
3. 提交说明可写 `backup: preserve available Library raw evidence`，选择提交到当前交付分支，再点页面上的提交按钮。不要合并其他研究分支，也不必修改仓库可见性。

若直接上传链接未打开，先[进入这个已经选好的交付分支](https://github.com/JackJ-C/Library/tree/delivery/m54-m57-verified-20260911)，点 **Add file → Upload files**。

GitHub官方说明：网页单文件上限25MiB。本备份为13.94MiB，在该限制之内，不需要因为这份包引入Git LFS。
参考：https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository

## 备份校验信息

- 文件名：`Library_available_evidence_backup_20260912.zip`
- 文件大小：14,612,661字节（约13.94MiB）
- SHA-256：`7e6e6f4570ef576561620d012de21d889714c4a82964412061ef5dd511d34fcc`
- 九份原始运行包完整保留，内部668份文件核验通过。
- 外层包内 `BACKUP_MANIFEST.json` 列出每份原包、内部文件及32份待传原档的大小和SHA-256。
- 外层包内 `verify_backup.py` 是离线校验程序，不联网、不执行研究代码、不改变研究结果。

## 保留范围与限制

保存的原包为M8–M11、M12–M15、M16–M20、M25–M28、M29–M32、主线M33–M37、研究分支M37–M44、M45–M48、M54–M57。

这不是全部M0–M57所有分支的完整镜像：当前会话未取得M21–M24独立ZIP；M0–M7和其他仅在远端的历史文件没有自动复制进本包。两份已知待传清单的32份原档完整在内，不等于所有历史版本均无遗漏。

上传这个ZIP后，原档会作为**完整归档内容**保存在GitHub，不会自动出现在各自原生 `results/...` 路径。需要运行旧阶段时，使用对应原包，避免不同分支同名模块互相覆盖。

此前 `delivery/m57/raw_backlog.json` 与 `delivery/20260911/raw_backlog.json` 保留为历史清单。只有在远端实际看到并核对本ZIP后，才应另行登记其上传完成状态。
