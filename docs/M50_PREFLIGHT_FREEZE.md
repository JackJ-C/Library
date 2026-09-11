# M50–M53 正式验证前冻结记录

唯一仓库 JackJ-C/Library；基线 a122a5c764bb04d87d2ee8b06ae57ee4a2e89cb4。M49已有并行登记，本实验从M50开始。既有完整原档欠传清单不变；旧文字摘要不得被称为全部原始证据已上传。

完整合同 docs/M50_M53_CONTRACT.md 的 SHA-256：27a0012b33da58139a12c9606ac95e7d5433833ff7698623dfeb68a607f73ca4。该合同和源码已在本地锁定；本提交先登记内容摘要，完整文件在最终提交中按同一摘要核对。本记录不声称程序已经通过正式验证。

## 开发与确认

开发种子0–7，唯一开发条件组合为顺时针相对距离小于2、先前命令余数等于1。正式验证排除此完整组合。A种子73000–73031，B种子91000–91031；每批32个连续生命周期、五种配对方法。同一个Queen连续92次在线请求；A/B不互相调参，种子轨迹是独立单位。

## 锁定的信息、预算和门槛

反馈仅为Worker前后读数、自己的实际命令与事前预测，correct/success/作者/故障标签不进入Queen。位置域5；原字段组合150，按(3*x+7*y+11*previous+object)%5==4保留30个组合用于迁移，其余120个允许取证。每个保留组合检查5个位移。

初始模型只含command*gain。反例触发由字段、减法、绝对值、取余、比较、否定与合取生成条件AST，最多两原子组合；不预装完整作用规律答案。语法、规范、标定点0/4与受限放置装置是明确先验，不主张任意新机制或开放式RSI。

每次审查统一上限：64探测（含4次标定和1次自身判断）、12000读取、8000000读取字节、12000000定义的原子计算。程序源码载荷上限512字节；同数据查表对照参数载荷上限512字节，不等于工作内存相同。对照含普通JSON、同表达能力固定取证、屏蔽旧证据但可补测、禁止结构扩展；查表为同观测配对表示对照。

每批必须同时通过：每条至少3次启动后真实修订，至少一次条件结构扩展；同一实例/账本/历史前缀；在线完成率>=90%；重新审查后迁移>=98%；末端迁移>=98%；旧程序在当前真实机制下仍正确的组合零退化；健康组件误改、Worker原因错误和判断绑定位置不一致均0；可区分历史归属>=95%，对称案例各半，错误确定归属0；共同预算不越界，普通日志按同信息对照。撤回支持、门禁、错误候选回退与原始历史重建另由压力测试核验。

通过这项操作性目标后收束，不追加完整意识、任意机制发现和开放式RSI。若未通过则只报告实际分项结果。结束时对全部可见Library分支做分层审查，并交付M0至M53总MD，区分已验证、未验证和仅登记。

## 冻结源码 SHA-256

```json
{
  "library_m12/__init__.py": "05db86bdfab5711f479a100603b1274148c8b02ddfda7d2816e061778fc6ed11",
  "library_m12/core.py": "6d846dcf995290d3d2eb8d343afef7b578023caa0970a57bee166e7cb6d527fd",
  "library_m37/__init__.py": "f42092976363bdcced8e71cd2105e4dbd7dfc07c359324f44a2a87ea68e044e2",
  "library_m37/core.py": "e500e26f723357501c6a13f9996f44a41cb5dbf245a296bf7d2963484125fc0b",
  "library_m37/identity.py": "d63f94093b1c30af9e5c63192244556fda30890ac0a329e31867b71858307ec9",
  "library_m41/__init__.py": "18304c5d2596e5bb9efd2196273cdf87dc6145541090170c3cd0a5a6b04fbd1f",
  "library_m41/integration.py": "fa0f5f3b792aeca6033a5c8712342446e90fcc163c274e8fc93c43f538a6c8eb",
  "library_m50/__init__.py": "7a97a5fee25622b13d77f5cd1e2dc78ca2c4ea45d0af01faf0f3c5f03a30ac28",
  "library_m50/core.py": "793a42aadd80e1335ab71eac8b8d5b33aae32d42969c48807a359c6012f000bc",
  "library_m50/models.py": "015f0e3b6a56fce830b34a878b02e02da790dbc8b2391e3f94a63cdfedc30492",
  "library_m50/pressure.py": "1cf97ed7910e3f3d6bea9b740e159558dec153a8e5d3335ebc7b99c8769fe6a6",
  "library_m50/study.py": "325cdaaca4184a3b289742d588849e77eabf89a0cbe0e19c03a573a32bf8bfef",
  "library_m50/tests.py": "cde660fd635377fc36fc86de562d5915bc5b68031ab6868578a9461b5ec98169",
  "library_m50/world.py": "01d70a2acf7ab1b8d655d636905557b6281ad05a8754093c1b96a1ecba94dd43",
  "library_m8/__init__.py": "00cf93c8f78a265743ebba78034d76dbfd90da89754699b944a367166fd08775",
  "library_m8/core.py": "fc1aca53c55dd962693616ae8055e92a80ccb02d21792e5f89be55ade5051952",
  "run_m50_m53.py": "b7e161091ab127dc40bb7bb8364100d81e63ccf6a4fa99ea9b1df1084bc16c14"
}
```
