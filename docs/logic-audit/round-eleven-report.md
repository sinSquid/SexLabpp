> 历史轮次：改动仍未提交；最新轮见[round-twelve-report.md](round-twelve-report.md)。round-full-scan.json已更新，前轮结束指纹保存于round-twelve-renumbering.json。

# 继承未提交工作区的全量结构扫描与脚本桥接修复

日期：2026-10-05；仓库 `/Users/sin/code/mine/SexLabpp`，master，HEAD `04e77305`。本轮从包含round-nine/round-ten五项未提交修复/优化的工作区继续，保留全部既有修改；没有提交或推送。起始222个生产文件的SHA保存于round-eleven-renumbering.json。

全量自动结构/风险语法扫描覆盖222生产文件、59,010行、4,925个提取条目；66辅助源码/CI/审查工具文件单独枚举及Python语法检查。两个第三方文件和外部CommonLib沿用既定排除范围。287 native名称与参数数量匹配，没有缺项/无法提取项，不代替完整类型/SDK ABI。当前文件指纹及候选位置见round-full-scan.json，执行日志validation/round-eleven-scan.log。

全量指范围内所有文件均经自动扫描和完整portable回归；**不是本轮逐函数人工重读，也不保证源码问题已穷尽**。人工复核集中于Decode/Script/World/Transform工具、VM属性读取消费者、脚本对象创建和回调入口。新增生产改动仅Script.h两个函数；未将全量风险语法命中逐项包装为新鲜调用链闭环。

| 编号 | 修复 | 本地证据与可达性 |
| --- | --- | --- |
| NEW-43 属性数值转换 | GetTrivialProperty先拒绝float源NaN/Inf并返回既有默认值；float转非bool整数前按截断值检查最低值及精确2^digits独占上界，避免越界转换。正常float、bool、int源和合法截断行为保留 | tests/script_property_boundaries.py property组编译实际helper，属性/对象为替身。覆盖NaN/±Inf、32位上下界、64位上界、有限bool、负小数及普通值。基线在非finite默认值断言失败。UI菜单/文字倍率通过GetThreadProperty<float>读取该helper，Scale setter原先直接接收值，CtrlPanel clamp也不排除NaN；新错误返回0会进入现有默认/范围处理。int32 GetThreadProperty虽显式实例化，当前自有源码未找到直接消费调用，不声称复现了实际游戏整数崩溃 |
| NEW-44 对象创建失败 | GetScriptObject对null form/class及空class在VM查找前返回空；CreateObject2未产出对象时不再调用BindObject绑定空对象 | 同文件object组编译实际helper/VM替身，验证失败创建、输入保护、有效创建及不创建查询；基线在BindObject的非空契约断言失败。当前自有调用方没有启用a_create=true，属于helper潜在路径修复；不是已观察到游戏绑定崩溃 |

完整最终tests/run.py退出0：validation/round-eleven-portable.log；本轮两个测试组默认都会执行，上一轮未提交的五项改动也保留在完整suite内。针对性ASan/UBSan两组通过：round-eleven-asan-script.log。编辑前行为失败：round-eleven-baseline-property.log、round-eleven-baseline-object.log。最初测试替身enum初始化写错导致编译失败，已修正测试后重跑基线；留存的基线日志都是实际运行时断言失败，未把fixture编译失败当作产品缺陷证据。

Lua构建依赖检测再次通过：round-eleven-build.log（实际生产Lua+xmake2.9.5 depend.lua；编译器/文件系统是替身）。git diff --check通过。没有确认新的热路径性能优化；仅异常参数提前退出，省去无效VM查询/绑定。没有FPS或总体速度提升测量，不为凑数修改算法。

累计4,925条source_reviewed，call_chain_closed仍全部false。7条不变本体按文件、名字、本体SHA及所属函数平移，两个改动本体分别核查登记：round-eleven-renumbering.json。11个解析诊断文件保持指纹/定义对账有效；Script.h没有新增解析诊断。自动扫描不自动关闭真实调用链或VM契约。

仍开放：真实VM singleton可用时序、handle存活、CreateObject2/BindObject实际语义、dispatch参数所有权及回调异常契约没有完整SDK/运行证据。此前SKEE移除scale后的失败回滚、rigid-body共享/替换、Revert/VM互斥、UI/引擎内部锁、Foot IK私有ABI、controller瞬时状态机等事项继续保留。未执行Windows DLL/MSVC、PEX编译、真实VM/游戏/VR测试。

实机补充：正常菜单/文字倍率、bool控件及各原有脚本属性读写；损坏配置或测试脚本产生NaN/Inf时确认错误日志及默认倍率，UI仍可关闭恢复。如果启用脚本对象创建API，验证真实失败返回和绑定结果；本地替身不能证明真实handle/对象生命期。
