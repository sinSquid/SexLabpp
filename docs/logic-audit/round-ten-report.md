> 历史轮次：改动仍未提交。最新轮见[round-eleven-report.md](round-eleven-report.md)；round-full-scan.json已更新，前轮结束/本轮起始指纹保存在round-eleven-renumbering.json。

# 继续未提交工作区的全量结构扫描及三组修复/优化

日期：2026-10-05，仓库 `/Users/sin/code/mine/SexLabpp`，master，HEAD `04e77305`。本轮从包含上一轮两项未提交修复的工作区继续；没有重置或提交这些修改。本轮新增修改也未提交/推送。起始222个生产文件的SHA保存在round-ten-renumbering.json，避免把HEAD误当作干净工作区基线。

扫描覆盖222个自有生产文件、58,987行、4,925个函数/事件/lambda/native声明提取条目；65个辅助源码/CI/审查工具另行枚举及Python语法检查。排除范围沿用两个第三方文件和外部CommonLib。287个native注册/声明名称及参数数量全部匹配，不代替完整类型映射及ABI。逐文件扫描结果是round-full-scan.json，日志validation/round-ten-scan.log。

全量指范围内每个文件均经过自动结构/风险位置扫描，并执行完整portable suite；**没有声称本轮重新人工读完4,925个函数或穷尽所有逻辑问题**。本轮人工复核集中在通用工具、native表情/数组入口、Ni初始化/读取路径及两项既有开放契约；新增生产改动仅StringUtil.h、SharedSnapshot.h、NiInstance.cpp的相关本体。自动风险候选位置不能自动证明调用链正确。

| 编号 | 改动与触发 | 本地证据/限制 |
| --- | --- | --- |
| NEW-40 保留设备名 | 原stem校验允许CON/NUL.txt等，追加.yaml也不能成为普通Windows文件。按首个点前的名称补大小写无关设备名检查，拒绝CON/PRN/AUX/NUL、COM/LPT 1–9及UTF-8上标1/2/3；普通名字及带hash的合法Scene文件名保持 | tests/windows_file_stems.py执行实际predicate，基线行为断言失败；完整suite同时执行实际CreateExpression/Save/SaveScenes既有路径回归。规则依据[微软Win32文件命名文档](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)。没有执行真实Windows文件I/O，也不声称校验覆盖所有路径长度/编码限制 |
| NEW-41 旧快照析构 | SharedSnapshot::store原先在mutex内赋值并释放旧值；最后一个旧owner析构回调调用slot.load会死锁。现在锁内swap发布新值，旧值在离开锁作用域后释放 | tests/shared_snapshot_release.py编译实际header，析构回调重读slot并检查新值，另验证reader持有旧对象不受reset影响。基线2秒超时退出10，修复后返回成功。真实Ni对象析构及引擎内部锁仍未验证 |
| NEW-42 状态容量 | NiInstance构造包含self pair，实际创建n²条状态，却仅reserve n(n−1)。改为预留n²，保持配对顺序和数量 | tests/interaction_state_capacity.py执行实际构造函数，Actor/Scene为替身、仅state vector使用计数allocator；验证0–5角色全部ordered/self pair及状态存储分配次数。基线在2角色时出现第二次分配，修复后1–5角色均一次。没有宣称整个引擎构造过程只分配一次 |

完整最终tests/run.py退出0：validation/round-ten-portable-final.log，包含上一轮未提交两项修复及本轮三个新增测试。validation/round-ten-portable.log是第三项改动前的中间回归记录，不能代替最终日志。三项ASan/UBSan退出0：round-ten-asan-snapshot.log、round-ten-asan-stems.log、round-ten-asan-capacity.log。三个baseline日志分别记录编辑前的行为失败。Lua构建依赖检测再次通过：round-ten-build.log（实际生产Lua+xmake2.9.5 depend.lua，编译器/文件系统仍为替身）。git diff --check通过。

性能结论限于：快照旧对象析构不再占用slot锁；2–5角色构造时state vector省去一次扩容及已有元素搬移。没有FPS、帧耗时或总初始化耗时测量。

台账累计4,925条source_reviewed，call_chain_closed仍全部false。本轮28条不变本体按文件、名字、SHA及所属函数平移，4条改变/新增本体分别登记（含文件名比较lambda）；证据round-ten-renumbering.json。SharedSnapshot模板构造的既有parser恢复诊断仍在同位置，ctor/load/store三个定义完整，按当前文件/定义SHA重新对账；全部11个诊断文件指纹有效。

开放边界未自动关闭：上一轮记录的SKEE移除已有scale后异常base的完整回滚、rigid-body共享/替换契约仍需实际接口/引擎证据。真实Windows DLL/MSVC、PEX、VM/Revert暂停契约、UI线程、引擎内部锁、Foot IK私有ABI、controller瞬时状态机和游戏/VR未测试。实机清单保留runtime-validation.md、closure-report.md及round-nine-report.md补充步骤。

本轮实机补充：正常名字和既有中文资源保存/重载；设备保留名输入被明确拒绝且不会生成待写任务；Ni对象reset/Revert/换位时检查析构与读取是否卡顿，确认真实引用和引擎锁契约。设备名限制可能使原先已加载、但在Windows不能正常保存的profile需改名；没有自动迁移用户资源。
