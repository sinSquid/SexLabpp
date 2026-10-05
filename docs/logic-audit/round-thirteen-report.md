# 第十三轮：全量自有源码本体复核、修复与验证

日期：2026-10-05。仓库 `/Users/sin/code/mine/SexLabpp`，master，HEAD `04e77305`。起始工作区包括第九至十二轮未提交改动，全部保留；本轮没有提交或推送。

## 范围与完成证据

本轮重新阅读全部 **222 个自有生产源码文件、59,037 行**，包括全部 C++ 实现/头文件、47 个 Papyrus 文件、Python、Lua、宏配置；另重新阅读 **71 个测试、审查工具和 CI 文件**，总计 **293/293 文件**，当前指纹对应的本体阅读待办为 0。本轮独立台账 `full-thirteen-progress.json` 保存逐文件 SHA、阅读状态及证据，与 `full-scan-scope.json` 全部路径逐项一致。历史 source_reviewed 标记、文件枚举和模式扫描没有替代本轮本体阅读。

第三方 `src/Util/Premutation.h`、`lib/ImGui/SKSEMenuFramework.h` 及外部 CommonLibSSE-NG 实现不计自有源码分母；自有调用方在范围内。资源二进制、翻译文本、数据和普通说明文档不是可执行源码；未声称逐条验证游戏资源存在性。

生产提取条目为 **4,926**（包括 lambda、事件及 native 声明）；逐函数台账指向本轮文件阅读证据，call_chain_closed 仍 false。8 个新增或改变本体逐项登记、33 个不变记录按路径/名称/SHA/所属函数平移；7 个重复且本体相同的 lambda 因匹配不唯一而重新登记，未冒充语义改动。11 个解析诊断文件的源码、定义及诊断指纹对账有效。287 个 native 名称/参数数量对账通过；不是完整类型或 SDK ABI 认证。

## 本轮修复

| 编号 | 修复及边界 | 验证 |
| --- | --- | --- |
| NEW-46 | Voice 导出的 exists 检查后若别的写入方先创建文件，原先 AtomicWrite 会覆盖它。增加 overwrite=false 发布模式；Windows 不带 REPLACE_EXISTING，POSIX 原子创建硬链接。原有默认覆盖保存保持兼容。 | 实际 SaveToFile 函数、真实文件系统及 SaveQueue.h；YAML/声音数据替身。竞争发布基线失败，修复后及 ASan/UBSan 通过。Windows 分支未运行。 |
| NEW-47 | Papyrus project XML 的路径和 flags 遇到 & 等字符生成非法 XML。动态属性和节点文本统一转义。 | Lupa 执行实际完整生成器，xmake I/O 替身；XML 解析及还原路径通过，原输出解析失败。 |
| NEW-48 | GetTimersRunTime 把 native GetFixedLength 已返回的秒再除以 1000，低估固定时长。保持秒单位，保留动态计时回退。 | 实际 Papyrus 函数有限翻译，原生接口按秒模拟；基线断言失败，修复后通过。同步纠正 animation_slot_boundaries 和 systematic_scripts 的旧毫秒替身。未运行真实 VM。 |
| NEW-49 | UI 的“ · ”为四字节，只复制三字节导致后半空格丢失。修正长度并验证缓冲边界；同时把 VarUI_EnjInterText 配置读取从各 actor 循环移至每次 Render 一次。 | 实际 UpdateSlider，普通文本及 0–511 长度分隔符输入、ASan/UBSan 通过。属性读取优化是调用次数证据，没有 FPS 测量或真实 ImGui 验证。 |
| NEW-50 | RemoveTag(self) 在遍历自己的 extra tags 时删除同一 vector，迭代器失效并可能残留标签。self 路径直接清空 extra tags；基标签按原语义清除，annotations 保留。 | 实际 TagData 函数及头文件，原实现三标签自删除断言失败，修复后及 ASan/UBSan 通过。没有发现自有代码调用这一重载，不声称游戏崩溃已复现。 |

Voice 发布测试使用独立临时目录，避免固定临时目录清理影响其他运行。新增四个回归文件全部接入 tests/run.py。

## 未确认的疑点与验证限制

MCM 全部动画选项用显示文字传 package 名，沿实际 CreateProxyArray 调用链核查后，未知包名会回退全部包，没有证实查询遗漏，因此撤回最初疑点且不修改。旧 Defaults 注册入口立即 return，失活目录函数也已读完，不启用过时工厂。forceSchlong 空 TODO 是尚未实现的功能，不在此轮擅自新增。

本轮完整 tests/run.py **退出 0**：`validation/full-thirteen-portable-final.log`。三个针对性 ASan/UBSan、实际 Lua 依赖检测器与生成器替身、全范围结构和 Python 语法检查通过；`git diff --check` 通过。完整回归覆盖之前保留的未提交修复。替身及有限脚本翻译的证据不替代 Windows DLL、Papyrus 编译、真实 VM 或游戏运行。

本轮已完成声明范围内的源码本体复核及确认错误处理，**不证明所有逻辑问题穷尽**。SKEE 移除后异常 base 的回滚、rigid body 共享/替换、Revert 与已执行 VM 调用交错、引擎内部锁及 Foot IK 私有 ABI 等外部契约仍开放，详见既有 runtime-validation.md。没有把这些项目登记为通过。

用户后续打包实机验收另需检查：Windows 上竞争/既有 Voice 文件不被覆盖，正常 Voice 导出重载；含 & 等字符的实际工程路径；固定时长与动态时长混合的 legacy 总时长；UI 分隔符显示及配置切换。无需为了标签 self helper 人为宣称已有游戏入口。
