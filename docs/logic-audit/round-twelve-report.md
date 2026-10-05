# 继承未提交工作区的全量结构扫描及声音ID修复

日期：2026-10-05，仓库 `/Users/sin/code/mine/SexLabpp`，master，HEAD `04e77305`。继承round-nine/ten/eleven共七组未提交改动，本轮也未提交或推送。起始222个生产文件的指纹见round-twelve-renumbering.json，不以HEAD冒充干净工作区基线。

全量自动结构/风险位置扫描覆盖222生产文件、59,015行、4,925个提取条目；67辅助源码/CI/审查工具另行枚举并检查Python语法。两个第三方文件及外部CommonLib沿用既定排除范围。287个native名称/参数数量匹配，没有缺项或无法提取项；不是完整类型/SDK ABI验证。逐文件SHA及候选位置见round-full-scan.json，日志validation/round-twelve-scan.log。

全量指范围内所有文件均经过自动扫描及完整便携回归；**不是本轮重新逐函数人工读完，也不证明问题穷尽**。人工复核集中于DirtyFlag/SaveQueue、资源保存入口、Voice导出及调用方边界。没有确认保存重试策略的新错误，不因候选命中修改策略。

本轮一组修复NEW-45，涉及两个生产函数：

- Library::CreateVoice原先只检查重复ID，允许空值、非法文件字符和设备保留名。现在在加锁/插入之前先empty短路，再调用共享IsSafeFileStem；失败返回false，不产生不可导出的新profile。
- Voice::SaveToFile原先先用GetId().data()构造string_view，再检查empty；若空BSFixedString提供null指针，该构造就不安全。此外它仅拒绝/、反斜线和冒号，没有继承共享校验中的问号、星号、控制字符、引号、尖括号、管道及设备名规则。现在先保存ID所有权、检查empty和共享predicate，之后才构造view/path。

已有从资源加载的Voice没有被删除或自动改名；若其ID不能作为合法文件名，导出入口明确拒绝，WriteVoiceToFile既有异常日志路径处理。正常中文、空格、尾点/尾空格的现有stem策略与重复创建行为保持一致。不声称file-stem校验覆盖所有Windows编码、长度或文件I/O限制。

验证证据：

- tests/voice_creation_boundaries.py执行实际CreateVoice函数和共享predicate，BSFixedString/Voice/容器为替身。检查空/路径/非法字符/设备名ID不插入，正常及重复创建。编辑前基线在拒绝空ID断言失败：round-twelve-baseline-create.log。
- tests/ui_voice_boundaries.py增强实际SaveToFile的pre-I/O路径块，ID替身为空时c_str/data返回null；检查拒绝非法/保留名和正常中文文件路径。原函数基线在拒绝行为断言失败：round-twelve-baseline-export.log；不是实际游戏崩溃证明。只执行路径块，未执行完整YAML序列化/声音资源写入；原有大sequence循环和UI整数转换回归继续保留。
- 两项针对性ASan/UBSan通过：round-twelve-asan-create.log、round-twelve-asan-export.log。
- 最终完整tests/run.py退出0：round-twelve-portable.log，涵盖所有既有未提交修复。Lua依赖检测通过：round-twelve-build.log，实际生产Lua+xmake2.9.5 depend.lua，编译器/文件系统为替身。git diff --check通过。

本轮未确认新的热路径性能优化；异常创建提前拒绝，只省去无效锁/插入及失败导出工作，没有FPS或总体速度测量。

累计4,925条source_reviewed，call_chain_closed仍全部false。40条不变本体按文件、名称、SHA及所属函数平移，两处改动分别补核：round-twelve-renumbering.json。11个解析诊断文件保持指纹/定义对账有效。全量扫描没有自动关闭真实调用链。

完整Windows DLL/MSVC、PEX、VM、YAML/声音实际写入及游戏/VR未测试；此前SKEE失败回滚、rigid-body共享/替换、Revert与VM暂停、UI/引擎内部锁、Foot IK ABI等契约仍开放。Voice导出既有文件检查后的并发发布行为没有本轮运行证据，不能将路径块测试包装成整个导出链的并发认证。

实机补充：通过现有脚本入口尝试空ID、设备名和禁用字符，确认创建返回false且不会出现不可导出profile；正常中文Voice创建、保存及重载；已有不合法Name资源保持可加载时，其导出明确失败并有日志，可由用户自行修正元数据。真实BSFixedString编码及Windows落盘需实机验收。
