> 历史轮次：其两项修改仍未提交；后续最新轮见[round-ten-report.md](round-ten-report.md)。round-full-scan.json现为最新轮清单，前轮起始源码指纹已保存在round-ten-renumbering.json。

# 04e77305 后的全量结构扫描与两项修复

日期：2026-10-05；仓库 `/Users/sin/code/mine/SexLabpp`，master。开始时工作区干净，基线 `04e77305`；本轮未提交、未推送。

全量结构/风险语法扫描覆盖222个自有生产文件、58,960行、4,924个提取条目；62个辅助源码/CI/审查工具文件单独枚举并检查Python语法。两个第三方文件及外部CommonLib依赖沿用既定排除范围。287个native名称及参数数量匹配，没有缺项或无法提取项；不代表完整类型映射/ABI验证。每文件SHA和风险位置见round-full-scan.json，执行日志validation/round-nine-scan.log。

“全量”指所有范围内文件经过上述自动扫描及完整便携回归。人工复核集中于数值计算、碰撞恢复、排队任务及循环退出路径，完整阅读两个改动生产文件、核对消费者；**不是本轮人工重新读完全部4,924个函数，也不证明所有源码问题已穷尽**。扫描列出的246处数值转换、76处脚本等待、68处front/back/at调用、19处文件写入口、11处AddTask及7处无限循环语法只是风险候选；没有detached线程命中。并非每个候选都完成了新鲜的逐项调用链证明。

| 编号 | 修复及触发 | 验证 |
| --- | --- | --- |
| NEW-38 | 有限正数缩放经GiantSpider倍率可溢出为Inf，经Chaurus倍率可下溢为0；原逻辑先添加scale mode/移除既有scale，再拒绝结果。现在倍率后重新校验目标，并在初始base异常时提前返回，两个接口版本都不触碰既有transform | 实际SetScale函数＋Legacy/modern接口替身，验证FLT_MAX、最小subnormal、NaN/Inf/非正base、正常比例及后续分母校验；基线发生行为断言失败。针对性ASan/UBSan通过 |
| NEW-39 | 两个finite表情端点可在float差值/外插中产生Inf/NaN。现在使用double中间运算，结果饱和在float有限范围，再保留mood取整；未新增[0,1]限制 | 实际GetData函数＋profile/logger替身，覆盖±FLT_MAX中点/端点、四种曲线、正负极端强度、正常插值/外插及legacy行为；基线中点断言失败。针对性ASan/UBSan通过 |

性能收益只限异常请求提前退出，省去无效SKEE修改调用；没有FPS或整体性能提升测量。double插值为数值正确性修复，没有声称它减少计算量。

最终当前源代码的完整tests/run.py退出0：validation/round-nine-portable.log。Lua测试执行实际生产规则及xmake2.9.5 depend.lua，编译器/文件系统为替身：validation/round-nine-build.log。两项sanitizer日志为round-nine-asan-expression.log、round-nine-asan-scale.log；两项编辑前基线行为失败日志为round-nine-baseline-expression.log、round-nine-baseline-scale.log。新增测试加入默认完整套件；增强缩放测试同时计数scale mode/移除调用，避免只检查最终scale写入而漏掉前面的破坏性修改。

累计阅读记录仍为4,924条，call_chain_closed全部保持false。14条不变本体按文件、名称、SHA及所属函数匹配平移，两个改变函数分别补核，证据round-nine-renumbering.json。没有将自动扫描输出批量标为新鲜人工验证。11个解析诊断文件指纹/定义对账仍有效。

开放边界：

- SKEE移除原scale后的base可能依然异常，现有后置校验只阻止继续写入，不保证完整事务回滚；Legacy接口没有声明可调用的旧值查询。本轮修复只覆盖修改前可检测的无效目标/初始base。
- rigid-body快照按Actor FormID保存。不同Actor是否共享同一个body、同Actor body替换的实际引擎契约尚无证据；controller/Foot IK共享所有权测试不能代替此项。没有凭条件性怀疑扩展生产状态模型。
- 真实Windows DLL/MSVC、PEX、VM/Revert互斥、引擎内部锁、UI线程、private Foot IK ABI、瞬时controller状态机及游戏/VR未验证。实机步骤沿用runtime-validation.md、closure-report.md，并补充以下验收点。

实机补充：使用实际Legacy/modern SKEE版本，已有scale时提交异常缩放，检查节点及override记录保留；移除自有scale后仍由其他插件/骨架产生异常base时，记录前后override和恢复行为。观察角色controller/body在卸载、换骨架、加载存档时是否替换或共享，并检验移除/恢复后mass和gravity。表情验收采用正常资源和极端finite配置，确认输出无Inf/NaN、正常mood/强度行为兼容；有限范围输出不保证Facial/VM接受任意极大强度或mood ID。
