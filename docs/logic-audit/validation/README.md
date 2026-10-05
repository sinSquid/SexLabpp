# 当前本轮验证结果

以 `full-scan-portable.log` 为本轮最终完整便携回归（exit 0）；下文 `portable.log` 和早期阶段的覆盖数量属于历史记录，不当作当前全链证明。

新增 `full-scan-asan-motion.log`、`full-scan-asan-preparation.log`、`full-scan-asan-graph-locks.log`、`full-scan-asan-ui-voice.log`、`full-scan-asan-hud.log` 均为实际生产函数/头文件加替身的ASan+UBSan，exit 0。Papyrus翻译、引擎对象替身不代表DLL、VM或游戏已通过。

`full-scan-baseline-motion.log`、`full-scan-baseline-preparation.log` 是对HEAD的回归失败复现，**预期非零退出**，不是当前代码测试失败。日志记录assert及SIGABRT；当前代码相同用例通过。基线复现是在修复后补做，未宣称所有问题都先跑失败再编辑。

---

# 本地验证证据（2026-10-05）

- `portable.log`：最终当前代码的 `tests/run.py`，退出码0。
- `asan-audit.log`：`CXX=work/clang-sanitized python tests/systematic_audit.py`，退出码0。
- `asan-native.log`：同wrapper运行 `tests/systematic_native.py`，退出码0。
- `asan-statistics.log`：同wrapper运行 `tests/full_sixth_persistence.py`，退出码0。
- `asan-decode.log`：同wrapper以C++20/O1编译 `tests/decode_bounds.cpp` 后运行，退出码0；含256个bool字节。

wrapper：`clang++ -fsanitize=address,undefined -fno-omit-frame-pointer`，其余flags由各测试传入。

日志中的“production”表示测试提取实际生产函数或包含实际头文件。引擎类型与调用为替身；Papyrus为有限语句翻译。日志中的PASS不能代替MSVC DLL/Papyrus编译或真实VM、游戏/VR、ImGui、SKSE cosave、设备/插件验证。

## 剩余契约续接证据

- `asan-contracts.log`：`CXX=work/clang-sanitized python tests/contract_boundaries.py`，8组退出0。
- `build-contracts.log`：`XMAKE_DEPEND_SOURCE=work/xmake-source/depend.lua python tests/build_contracts.py`，lupa2.8；上游源码固定xmake2.9.5，SHA256 `90fb3cbbb347b81c1b7b4f927a6ad786f425c0c8c67ee754eb257336a56a0804`。编译器、target和文件系统为替身，依赖判定函数是上游实际代码。
- 下载来源：[xmake2.9.5 depend.lua](https://github.com/xmake-io/xmake/blob/v2.9.5/xmake/modules/core/project/depend.lua)。测试无自动下载，先取得该文件再设置环境变量。
- `portable.log`已替换为包含新增8组的最终当前代码完整套件。
- 早期`asan-audit/native/statistics/decode.log`属于前一次续接证据；本轮新增边界由`asan-contracts.log`覆盖，新增NUL由刷新后的`asan-decode.log`覆盖。

## 新全覆盖审查第一批（整体审查仍进行中）

- full-scan-portable.log：包含新增5个测试文件的完整tests/run.py，退出0。
- full-scan-asan-partners.log：scene_partners.py，实际3个查询入口＋RequiredMatching，退出0。
- full-scan-asan-furniture.log：家具可达性实际lambda，退出0。
- full-scan-asan-theme.log：主题编辑实际入口，退出0。
- 上述日志比portable.log新；原portable.log只是上一续接阶段结果，不再称为最终当前diff日志。


## 定点处理补充

`closure-portable.log`：完整tests/run.py退出0。随后native入口世代获取位置调整另运行world_revert.py退出0，见`closure-world.log`。`closure-asan-controller.log`、`closure-asan-foot-ik.log`、`closure-asan-world.log`为实际函数/分派片段加引擎替身的ASan+UBSan回归，无检测错误；不表示真实ABI、VM、游戏或完整DLL认证。


## 44ae5487之后的新轮

`round-portable.log`为当前完整便携回归；`round-targeted.log`为最新测试辅助调整后的新增用例；`round-asan.log`和`round-asan-motion.log`为针对性ASan+UBSan。`round-baseline-{finalize,profile,scene,script,motion}.log`是相同实际源码测试对基线执行的预期行为失败。基线复现在修复后补跑，不是编辑前全部先复现。完整DLL/PEX、真实ABI/VM/游戏未验证；导入finite guard仅人工源码证据。
