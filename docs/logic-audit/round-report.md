> 历史轮次：本报告修复已提交并推送为04e77305。后续最新轮见[round-nine-report.md](round-nine-report.md)，本文数字/未提交状态为当时记录。

# 44ae5487 后的全量结构扫描与定点修复

日期：2026-10-05。基线 `44ae5487`。本轮扫描222个自有生产源码文件，覆盖58,943行；另外枚举61个辅助源码/CI/审查工具文件并检查Python语法。排除的两个第三方文件与CommonLib子模块仍按既有范围处理。

这里的“全量”指每个范围内文件都经过结构/风险位置扫描、清单和指纹检查，以及全量便携回归；**没有声称本轮重新人工读完全部4,924个函数条目**。人工复核集中于队列/恢复/持久化/采样调用链和七个改动生产文件。风险语法位置只是候选，不能自动判为错误或证明其调用链安全。

可重现扫描：`python docs/logic-audit/round_scan.py`（Python3.12及已锁定tree-sitter依赖）。输出`round-full-scan.json`包含每个生产文件的指纹、风险语法位置和解析诊断。287个native声明与注册名称一一匹配，287个参数数量检查没有缺项、无法提取项或数量不一致；该检查不代替完整类型映射或ABI验证。

| 修复 | 触发及现在的行为 | 本地证据 |
| --- | --- | --- |
| NEW-33 家具选择异步完成 | 旧路径继续启动detached线程，可能在Revert后访问旧Quest；改为game task，在registry锁内先核对world generation。不存在pending request时日志不再解引用Quest | 实际FinalizeCenterRefSelection＋任务/实例替身；检查执行线程、同Quest/request跨存档、成功/构造失败/排队失败。基线在任务队列/线程归属断言失败 |
| NEW-34 导出路径和批量异常隔离 | 表情ID、包名/hash可把路径分隔符带入文件名。拒绝非法表情ID；Scene检查拼接后的最终name_hash.yaml，保留空显示名/尾句点包名的正常导出；filesystem组合根目录和单文件名。一个坏表情不再阻止其他合法表情保存 | 实际CreateExpression、Expression::Save、SaveExpressions、SaveScenes及file-stem helper＋YAML/queue替身；非法路径、正常中文/空格/点、合法空包名/尾标点及相邻合法记录。基线创建非法ID及Scene导出断言失败。非法包元数据需修正才能导出其设置 |
| NEW-35 非finite表情值 | YAML/legacy导入和编辑拒绝NaN/Inf；编辑失败前不resize/copy，原值和dirty保持 | 实际UpdateValues覆盖NaN/±Inf及正常扩容；YAML/legacy导入guard为人工源码核对，没有执行真实yaml-cpp/glaze导入集成 |
| NEW-36 表情更新判断和查询开销 | 同强度但不同mood ID原先可能不更新；现在ID或强度不同时更新，同ID同强度省去重复override，mouth-open策略保留。复用已有读数，native mood查询从3–4次降到2次，并补None/不足32值保护 | 有限Papyrus翻译执行实际函数，覆盖同ID/异ID、同强度/异强度、mouth-open、None和短数组；基线在no-op更新行为断言失败。未编译PEX或执行真实VM |
| NEW-37 派生坐标的有效性 | 无效头部位置/方向被清成零占位后，原先可能产生“有效”喉部/嘴部。现在throat须head位置与Z有效，mouth须throat与Y有效 | 实际NiMotion/PCA＋向量/node替身；NaN头部位置、Y/Z矩阵列、正常原点、环形轨迹。基线在派生anchor缺失断言失败 |

完整`tests/run.py`通过。新增回归和NiMotion针对性ASan+UBSan通过，详见`validation/round-*`日志。四项基线行为复现及Motion复现是修复后补跑的证据，不声称全部问题都在编辑前跑过失败测试。新增导入finite guard只记录源码证据，不把编辑接口的回归包装成完整导入验证。

测试翻译器原先错误处理同一函数调用中的多个`as int`，本轮修正括号算术表达式转换并由新回归检验。这是测试辅助改动，不计生产修复。全量native参数检查也是扫描工具，不计应用功能优化。没有FPS测量；性能结论仅为省去重复查询/无变化写入。

累计阅读清单更新为4,924条，仍全部`call_chain_closed=false`。本轮110条同路径/同名/同本体旧阅读记录平移，16个新/改条目分别登记；兼容性补核另平移2条并核查2个改动本体，证据`round-renumbering.json`。11个解析诊断文件对账；Library_SaveLoad保持23个定义、三个MSVC成员函数指针诊断位置未变。累计阅读记录不等于本轮新鲜全函数人工验证。

真实DLL/MSVC、PEX、VM加载暂停、UI/引擎内部锁、私有Foot IK ABI、瞬时controller状态机及游戏/VR仍未验证。具体实机步骤保留在`closure-report.md`；家具选择完成排队阶段也应加入跨存档验收。本轮修改尚未提交或推送。
