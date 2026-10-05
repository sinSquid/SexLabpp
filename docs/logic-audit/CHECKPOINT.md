# 全量本体阅读及剩余疑点定点处理完成；外部契约待验收

更新时间：2026-10-05。仓库 `/Users/sin/code/mine/SexLabpp`，HEAD/master `36e6ff76e3f5d3a28aa34c48962240f3a50ac678`。

- 222个生产文件本体已读，后续改动段补核；当前58,891行、4,920条源码阅读结论，pending=0，call_chain_closed仍false。
- 累计32组修复。本次新增Foot IK原值与共享owner/锁序、Revert跨存档清理与任务世代、controller四持久控制位原值恢复。详见[closure-report.md](closure-report.md)。
- 218同名同本体记录迁移、29新/改条目分别登记，证据closure-renumbering.json；11解析诊断文件已对账。枚举/阅读标志不是全链验证。
- 当前完整portable退出0；最后native世代捕获位置调整另经world测试通过；三组针对性ASan+UBSan通过，diff/scope检查通过。
- 瞬时controller支撑/状态机、引擎内部锁、私有Foot IK ABI、已执行VM调用与Revert互斥、UI框架线程和Ending真实事件时序仍缺外部契约。逐项实机步骤已记录，不再泛称“继续观察”。
- 59个辅助源/CI/审查工具文件枚举和语法检查；没有声称全部人工逐函数核验。
- 既有修改全部保留，未提交、未推送。本轮没有完整DLL/PEX或游戏验证。

续接从closure-report.md的具体待验证契约开始，不重复把222个文件再读一遍当作新的验证。台账以文件/函数SHA绑定，用Python3.12与已锁定解析器重建；scratch工具根 `/Users/sin/Documents/Codex/2026-10-04/users-sin-code-mine-sexlabpp/work`。

---

# 上一次续接记录（历史状态，已被本轮范围校正取代）

更新时间：2026-10-05。已完成“按 CHECKPOINT.md 继续”，随后按用户要求逐项处理剩余可本地验证契约；实机部分由用户后续自行打包验证。

## 当前准确状态

- 仓库：`/Users/sin/code/mine/sexlabpp`（实际路径大小写为 `SexLabpp`）。
- 基线/HEAD：`36e6ff76e3f5d3a28aa34c48962240f3a50ac678`；master，本轮开始时干净。
- 本轮所有生产修改、测试和审查文档仍在工作区，**未提交、未推送**。本次续接没有提交/推送授权。
- 清单：221 个自有生产文件，58,290 行，4,899 个实现/事件/lambda/Papyrus native 声明条目。
- `source_reviewed=4899`，`pending=0`。改动导致位置变化的相同本体已按同文件 SHA 人工续接记录；新/修改本体另核查、登记。
- 11 个 C++ 解析诊断文件全部人工对账。当前没有发现遗漏的函数定义；`parser-reconciliation.json` 绑定文件 SHA、诊断、函数范围与 SHA，文件变化会使对账失效。
- C++ 前置/纯 virtual 声明及 ABI 已作为调用契约阅读，不计函数实现分母；第三方 `Premutation.h` 排除生产分母，调用方在范围内。
- **源码覆盖完成不等于全部逻辑/调用链验证完成**。台账 `call_chain_closed` 仍为 false，以下开放事项不能称为已通过。

## 本次续接处理

补读了全部余下脚本，包括 ActorLibrary、Stats、VoiceSlots、Framework、Utility、SystemConfig、ConfigMenu、SexLabUtil、遗留诊断及四个 Defaults 文件。默认动画/表达式加载入口失活的事实单独登记，未启用旧工厂，也不把替身执行定义当成真实资源加载。

全部修复、触发和证据见 `findings.md`；其中包含 Oct4 的已有修改，以及 Oct5 注册/分页、legacy 数据、表达式、卸装、配置编辑器等修复。后续调用链回查处理了：

- native 生物匹配的贪心漏解、输入种族重复解析；legacy 交互伙伴错误、未初始化 graph bool。
- 模型非finite参数、缺失mouth的kissing描述。
- actor换位及quick reset后的别名/位置刷新、识别实例旧sex快照、偏移面板位置缓存。
- 重复stage ID回退历史、相似stage逐标签比较及直接ID跳转。
- 稀疏声音分页/筛选、后端列表缩减清空旧alias、候选抽样及分页边界。
- GetTrans强制性别方向、None计数、legacy hook父类初始化。
- 覆盖层最后一层贴图、相机无界忙等、SLR非法bool字节。
- 批量旧统计共用快照（21次→1次），vector setter角度→弧度。
- 长路径调整数组128容量，两组失活5P定义A5事件写错位置。
- 匹配器部分法术、安装界面有限等待、旧Benchmark负输入/除零及诊断页号/实际数量。

## 已完成验证

1. **最终当前 diff 的完整 portable suite 已通过，退出码 0。** 日志：`validation/portable.log`。包含 33 组本轮有限翻译脚本回归、7 组 native 回归及全部原有测试。
2. ASan+UBSan 本轮 targeted 通过：`validation/asan-audit.log`、`asan-native.log`、`asan-statistics.log`、`asan-decode.log`。不是完整游戏或全部引擎路径的 sanitizer 认证。
3. `git diff --check` 通过。
4. 所有日志、证据均区分独立C++、引擎替身、有限Papyrus翻译及源码契约检查。**没有执行 Windows DLL/MSVC 完整编译、Papyrus 编译、真实 VM、ImGui、SKSE cosave、外部插件/设备或游戏/VR 验证。** 本机缺少这套构建/运行环境。
5. 原图栈测试的实现细节断言已改为验证“失效线程在 Begin/clip stack 前退出”；不是删除安全要求来放行。

性能结论只限算法空间/调用次数，不声称 FPS 提升。长路径 legacy 数组最多返回前128个float是Papyrus接口容量限制；安装等待一分钟后不再占用无限等待，未安装时保留页面，之后重新打开查看。

## 剩余本地契约处理结果

此前列出的RaceID/Canine/Fox/标签、SLR域、设置/主题、SKEE分母、名字缓存、构建依赖已逐项核查和修复或明确保留兼容策略。另修复评分及分配总分溢出、错误线程仍继续射线调用。详见`findings.md`及`runtime-validation.md`的逐项表。

- 新增`tests/contract_boundaries.py`8组真实函数/头文件及有限脚本翻译回归，加入完整portable suite；最终完整套件退出0。
- `validation/asan-contracts.log`：上述8组ASan/UBSan，退出0。
- `tests/build_contracts.py`：lupa运行实际生产Lua，配合上游xmake2.9.5 depend.lua；编译器与文件系统为替身。`validation/build-contracts.log`通过。需要`XMAKE_DEPEND_SOURCE`指定上游文件，并安装lupa，不在默认portable suite中自动下载依赖。
- 有效Human数组返回`[0]`，错误空；旧标量错误仍0，脚本文档已纠正；基标签同名annotation优先级保留。两项兼容策略已明确，不继续登记为待定源码问题。
- 改动/新增40条本体单独登记，360条相同文件+本体SHA因行号移动续接；11解析诊断文件均已按当前文件/函数指纹对账。

## 下一续接：用户实机验收

用户要求其自行后续打包验证，因此本轮到“本地验证通过+实机清单可执行”为止。清单：`runtime-validation.md`。以下尚未完成，不由portable替身结果自动关闭：

1. Windows DLL/MSVC、Papyrus、Spriggit真实构建与install/打包产物；实际外部插件版本/设备/ABI。
2. 真实状态机、reset/换位/quick reset、重复stage图、fixedlength及失效回调、VR/相机/覆盖层/ImGui。
3. 跨存档及Revert生命周期，Settings同步、射线线程及collector重入/Havok ABI。
4. 真实SLR/声音/贴图/骨架等资源存在性及本轮输入校验与旧资源兼容。

收到用户构建或游戏日志后按具体失败链继续，不重复扫描已读条目，也不把完整集成链标记为已通过。本轮没有提交/推送。

## 工具和工作目录

临时目录：`/Users/sin/Documents/Codex/2026-10-04/users-sin-code-mine-sexlabpp`。

- `work/audit-env/bin/python`：Python 3.12、tree-sitter 0.25.2；重建 `docs/logic-audit/build_inventory.py`。不要直接升级0.26，当前环境曾SIGBUS。
- `work/test-env/bin/python`：完整 portable suite 环境；运行 `tests/run.py`。
- `work/clang-sanitized`：clang++ ASan/UBSan wrapper；本轮 targeted 使用它。
- `work/read_psc.py`：保留引号和行号的脚本注释剥离阅读工具。
- `work/record_systematic.py` 旧工具可能覆盖notes，不要直接重跑；也不要未经本体/指纹核查批量标记通过。
- 当前证据已保存进仓库 `docs/logic-audit/`，续接不依赖聊天记忆或scratch日志。
