# SexLabpp Code Review 报告（Cursor 与 Codex 复核合并版）

> 审查对象：`E:\code-lib\SexLabpp\src`（C++ / CommonLibSSE 风格 Skyrim 插件）
> 来源：Cursor 审查、Codex 源码复核及 Cursor「sexlab plus」会话中的 Q1～Q5 交叉核对。复核基线为 `fork/origin` 的 `6ebf61b0`。
> 阅读顺序建议：先"一、双方一致确认的缺陷"（直接修），再看"二、争议项对照"（有证据，供复核），最后"三、性能优化"。

---

## 一、双方一致确认的缺陷（可直接修）

### F1. 动画调速缺少 `activeGraph` 上界检查 【P0，双方一致】

- **位置**：`src\Thread\ThreadAnimation.cpp:841-843`
- **事实**：同文件 424、574、634 行的三处访问均有 `runtime.activeGraph >= graphManager->graphs.size()` 防护，唯独此处拿到 `updateLock` 后直接 `graphMgr->graphs[activeGraph].get()`。
- **后果**：`activeGraph` 失效时（动画图切换期间）vector 越界读 → Release 下 CTD。
- **修复**：补与其它三处一致的边界检查（不满足则 continue）。

### F2. `noexcept` 函数内创建 `std::thread`，失败即 terminate 【P0，双方一致】

- **位置**：`src\Registry\Library_SaveLoad.cpp:23`（`Initialize()`）、`492`（`SaveScenes()`）及内部 `std::thread` 创建点
- **事实**：`std::thread` 构造在资源耗尽时抛 `std::system_error`；函数签名 `noexcept` → `std::terminate`。
- **修复**：去掉 `noexcept`，或 try/catch 包裹线程创建；已有工作线程的异常路径需保证收尾（join 已创建的线程，不留游离线程）。

### F3. 家具菜单打开失败后，已发布的 pending 实例不回滚 【P1，双方一致，措辞已修正】

- **位置**：`src\Thread\Thread.cpp:47-82`（`CreateInstance`）
- **事实**：`OpenCenterRefMenu()` 在实例已 move 进 `pendingInstances` 之后调用。若它抛异常，外层 catch 只 log + dispatch(false)，半初始化实例留在列表中。
- **修正说明**（采纳 Codex）：原报告"setup ticket 已被消费、阻塞重试"的表述不准确——`setupRequests` 会被下一次 `ReserveSetupTicket` 覆盖，ticket 不构成永久阻塞。**真正的阻塞点是 `GetPendingInstance` 命中旧实例**：后续 `CreateInstance` 走"already exists"分支直接 dispatch(false) 返回。另外若失败回调 `DispatchContinueSetup(false)` 本身也送达失败，Papyrus 侧将永久等待。
- **修复**：`OpenCenterRefMenu` 失败时把实例从 `pendingInstances` 移除并走完整销毁路径，确保失败回调必达（或重试）。

### F4. 保存路径不检查文件打开/写入结果，失败仍记录"Saved" 【P1，双方一致】

- **位置**：`src\Registry\Library_SaveLoad.cpp:504-506`（SaveScenes）、`540`、`558`（SaveVoices）
- **事实**：`std::ofstream fout(filepath); fout << data;`——`is_open()`、写入状态、`close()` 结果均未检查；目录缺失/文件被占用时静默丢数据，且函数尾部无条件 log "Saved scenes/voices"。路径分隔符硬编码 `\\`（503 行）。
- **修复**：检查 `fout.is_open()` 与写入流状态，失败时 log error 并调整返回语义；用 `fs::path` 拼接路径。

### F5. `SetActiveScene` 失败后 Release 仍可能发布不完整实例 【静态确认可达】

- **实际路径**：`ThreadCtor.cpp:77` 对传入场景做完整分配校验，但 Primary 为空后的 `LookupScenes()` 只按片段哈希、启用状态和标签返回候选。`subm.pop_back()` 只移除一个角色的 submissive 标记，参与人数不变。`ThreadCtor.cpp:49` 最终调用 `SetActiveScene()`，后者按原始片段和权重做完整分配。Release 的 `assert(success)` 消失，失败实例仍可发布，后续使用未初始化的场景状态可能崩溃。
- **源码可推导的最小配置**：单角色、唯一开启的同类单人场景、无需家具。角色与场景的其他片段标记相同，身高倍率差超过 `fScaleTolerance`，其余权重保留默认值，将 `iScoreAcceptThreshold` 设为 `145`。哈希不含身高倍率，因此回退能返回该场景。完整分配得分为 `140`，低于阈值。此案例未在游戏内运行，默认配置的触发率未知。
- **修复方向**：`SetActiveScene()` 返回失败时走已有失败处理，阻止发布。回退候选采用与最终分配一致的片段和约束。

---

## 二、争议项对照（有代码证据，供复核裁决）

### D1. `SaveScenes` 的 range-for 引用捕获 【Cursor 已撤回】

- `packages` 是 `std::vector<std::unique_ptr<AnimPackage>>`。`auto&& p` 绑定真实元素，lambda 通过该引用访问绑定对象。保存线程均在 `_mScenes` 共享锁释放前 `join`，包发布持同一锁的独占锁。迭代绑定结束无法推出原报告所称的悬垂或栈地址竞争。线程创建异常与文件写入错误分别由 F2、F4 跟踪。[C++ 草案 §13](https://eel.is/c++draft/expr.prim.lambda.capture#13)

### D2. SurfaceCache 全局缓存"数据竞争"指控 【已撤回，双方一致】

- **裁决**：撤回。缓存读写点（`SurfaceCache.cpp:85-682`）全部位于帧更新路径：`Manager::OnFrameUpdate` 仅由帧钩子调用（`Hooks.cpp:28`，游戏线程）；`Manager::Register`（`Thread.cpp:165`）只登记 Scene，不触碰 Geometry 缓存。当前实际线程模型下无竞争。
- **保留项**：线程安全靠调用约定而非机制保证，建议加一行注释声明"仅游戏线程访问"；`FindShaftAssetTopology`（123 行）每次查找构造 `std::string(a_key)`，较长键触发堆分配——改为 heterogeneous lookup（透明 hash + equal_to）可消除，已并入性能项。

### D3. detached setup 任务的读档边界 【P2 风险，静态缺口已确认】

- **位置**：`src\Thread\ThreadCtor.cpp:377-404`、`src\Papyrus\sslThreadModel.cpp:312-314`
- **原 #3 复核**：两处 detached 线程捕获 `RE::TESQuest*`。`sslThreadSlots.psc` 的 `InstallSlots()` 从 `SexLab.esm` 读取固定槽位 Quest。原报告所列的读档销毁 Quest、悬垂指针和 DLL 卸载故障均缺少运行证据。
- **可确认的缺口**：`IsCurrentSetup()` 核对原生 ticket 和脚本 `SetupRevision`。正常销毁槽位会擦除 ticket，新预约会覆盖旧 ticket。原生 `RevertCallback` 未清除 setup ticket，`kPostLoadGame` 也未处理这些请求，读档后由 Papyrus `OnPlayerLoadGame()` 调用 `StopAllOnGameLoad()`。若旧请求在清理或新预约前恢复，且新读入的槽位恰有相同 `SetupRevision`，现有检查没有存档会话标识来区分它们。旧请求是否能在实际读档时序中越过检查，仍需运行证据。
- **任务队列约束**：`InitializeCenter()` 向 SKSE 队列提交任务后调用 `future.get()`。把整个 `CreateInstance()` 搬到同一个游戏线程队列，会让中心定位任务等待当前任务让出队列。

### D4. 其余未纳入共识清单的低优先级项（保留待确认，不阻塞修复）

| 项 | 位置 | 状态 |
|---|---|---|
| `AnimatingFaction` 清理链 | `ThreadAnimation.cpp:60`、`sslActorAlias.psc:390` | 正常 Alias 清理会把阵营 rank 设为 `-1`；仅执行原生恢复且跳过 Alias 清理时，才需要进一步验证是否残留。 |
| 原 #6 `PrepareActorForAnimation` 持锁做引擎调用 | `ThreadAnimation.cpp:41`、`:400` | 维护建议。`EvaluatePackage()`、`Resurrect()` 等调用位于帧更新的临界区。两个准备入口都已持有外层 `_mSetup` 和 `_mInstances`，只缩短 `actorPreparationLock` 的持锁时间仍会保留外层阻塞。仓库可追踪的调用未发现反向取锁路径，帧耗时及引擎内部重入待验证。 |
| 死亡角色的状态恢复 | `ThreadAnimation.cpp:73`、`sslActorAlias.psc:381` | 原生准备会复活待处理角色；Alias 已记录死亡状态时，正常清理调用 `KillSilent()`。本地 P+ 2.18.1 也有死亡标记与归还逻辑。仅原生恢复时是否留下状态异常待验证。 |

---

## 三、性能优化（双方一致成立，均非必须）

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| O1 | `src\Thread\Interaction\NiSurface\SurfaceCache.cpp:123`（及同类查找） | 每次查找构造临时 `std::string`，长键堆分配 | 透明 hasher + heterogeneous lookup |
| O2 | `src\Thread\ThreadAnimation.cpp` TryStartAnimations 准备循环 | 同一 pending 对同一 actor 调两次 `GetPosition()`（线性扫描） | 缓存返回指针 |
| O3 | `src\Thread\Thread.cpp:237` `GetThreadScenes(SceneType)` | 按值返回 vector，每次调用整份拷贝 | 返回 `const&`；需同步调整调用方（非 const 调用方需单独处理） |
| O4 | `src\Papyrus\SexLabRegistry.cpp:368-424` `SortBySceneEx/ExA` | 每个候选 sceneid 重建相同的 positions vector 和 fragments | 提到循环外 |
| O5 | `src\Papyrus\sslActorStats.cpp` `GetEveryStatisticID` | `ranges::contains` 逐项线性查重 O(n²) | `unordered_set` 辅助；**保留首次出现顺序**（输出顺序是可观察行为） |

---

## 四、已核实的边界与不变量

### 关键不变量链（三轮复核建立）

1. `Scene::FindAssignments`（`Registry\Define\Animation.cpp:538`）前置校验 `a_fragments.size() != positions.size()` → assignment 长度恒等于 scene positions 数。
2. `Scene` 加载把自身 `positions.size()` 传给每个 `Stage`（`Animation.cpp:110`）；`Stage::Stage`（`Animation.cpp:194-203`）校验失败即抛 → 每个 stage 的 positions 数恒等于 scene positions 数。
3. 实例侧 fragments 由实例 `positions` 全量变换而来；非空 assignment 要求等长。

**由此推导的"非问题"（此前报告已撤销，不要"顺手加固"报成 bug）**：

- ~~SortByScene 写回越界~~：`arr.size()` 恒等于 `a_positions.size()`，不存在越界（可加防御性断言）。
- ~~ReassertPlacement 的 `activeStage->positions[a_position]` 越界~~：不变量链下索引上界恒成立。
- 帧路径的上述索引访问受同一组不变量约束。整条帧链仍有其它可能抛异常的操作，例如 `ThreadAnimation.cpp:444` 的 `vector::emplace_back()`。异常边界保留在维护项 #18。

### 其它

- **锁序一致性**：`LockState → _mInstances`、`_mSetup → _mInstances` 全部访问点一致，无死锁环。
- **`Util\Premutation.h`**：Howard Hinnant 组合数学库拷贝，算法正确；仅文件名拼写（Premutation→Permutation）与 `<iostream>` 卫生问题。
- **`InitializeCenter` 的 SKSE task + `future.get()`**：栈变量因阻塞保证存活，安全。
- **`DestroyInstance` 的 `retired.clear()` 在 `_mInstances` 之外**：刻意设计（析构注销碰撞表面），不要移回临界区。
- **`CreateInstance` 内层 `catch(...)` + rethrow**（emplace 之前失败）：逻辑正确；仅发布后路径有 F3 漏洞。

---

## 维护清单（沿用原报告编号）

| 编号 | 维护项 | 核验依据 |
|---|---|---|
| #16 | 修正 `Premutation.h` 文件名拼写并核查冗余 `<iostream>` | `src/Util/Premutation.h` 的文件名和头文件依赖 |
| #17 | 保存路径使用 `std::filesystem::path` 拼接 | `src/Registry/Library_SaveLoad.cpp:503` 手工拼接 Windows 路径分隔符 |
| #18 | 评估帧 Hook 的异常边界和失败后的状态处理 | `src/Thread/Hooks.cpp:21` 直接调用原生更新函数。异常逃逸的具体路径和实际影响待确认。 |

## 覆盖范围说明

- **已深读**：`Thread\Thread.cpp`、`ThreadAnimation.cpp`、`ThreadCtor.cpp`、`Hooks.cpp`、`Registry\Library_SaveLoad.cpp`、`Registry\Define\Animation.h`、`NiSurface\SurfaceCache.cpp`、`Util\Premutation.h`（全文件）；`Papyrus\SexLabRegistry.cpp`、`sslActorStats.cpp`、`sslThreadModel.cpp`、`Registry\Define\Animation.cpp`、`Thread\Collision\CollisionHandler.cpp`、`Util\World.h`、`NiSurface\Manager/CollisionManager.cpp`（调用点/定向扫描）。
- **未覆盖**：`Thread\Interface\` 全部 UI 文件、`NiSurface\Shaft.cpp`、`ActorState.cpp`、`ActorGeometry.cpp` 全文、`Registry\Define\Expression.cpp`、`Registry\Library.cpp`、`Registry\Stats.cpp` 全文、`API\IPluginInterface.h`。
- **待运行验证**：旧 setup 请求能否跨读档进入新会话、准备阶段的锁等待耗时，以及异常结束是否跳过 Alias 清理。
