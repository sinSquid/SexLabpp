> 后续定点处理已新增三组修复，当前状态及外部契约以 [closure-report.md](closure-report.md) 为准。以下为追加处理前的全量阅读报告（29组、4910条、56辅助文件），保留历史证据。

# 全量生产源码本体扫描与本地修复（2026-10-05）

本轮已完整分段读取 **222/222 个自有生产源码文件**，累计 58,675 行；函数清单提取 4,910 个函数、事件、lambda 和 native 声明。此前在 96/222 时结束回复是执行错误，不能称为完成；本记录替换此前的部分进展数字。

**完整读取不等于所有调用链闭环，更不等于问题已经穷尽。** 本轮修复 29 组已确认问题。测试、CI、审查工具另列 56 个辅助文件，第三方实现排除 2 个文件及 CommonLib 子模块；辅助范围已枚举，Python AST 检查无错误，但没有宣称全部辅助实现都逐函数人工复核。

## 覆盖证据

- `full-scan-scope.json`：重新按 Git 跟踪及非忽略新增文件枚举，生产范围无函数清单漏项。
- `full-scan-progress.json`：每个完整读取文件的当前 SHA、读取说明、修复和源码开放问题；生产待读文件为空。
- `inventory.json`：所有 4,910 条目都处于已读文件本体内，`body_read_this_pass` 是根据文件指纹派生的阅读证据，不能解释为逐函数行为验证。
- 逐函数阅读结论已对账：`source_reviewed=4910`、`pending=0`。原1,314条失配中，1,226条按同路径、同函数名、同本体SHA且检查说明一致迁移旧记录，证据在 `decision-renumbering.json`；其余88条改动/新增函数逐项登记本轮检查及对应测试限制。没有用整文件阅读派生“已验证”结论，所有条目仍明确 `call_chain_closed=false`。
- 11/11 个 C++ 解析诊断文件已对账：诊断保留，未发现函数定义漏提取；宏及 ABI 扩展的解析成功不代表编译成功。

## 本轮修复

| 编号 | 修复或优化 |
| --- | --- |
| NEW-1 | 翻译工具TODO空行崩溃、BOM漏键、目标截断及缺失目标处理 |
| NEW-2 | 动画伙伴查询错误预筛选Human，漏掉生物候选；先距离过滤再做昂贵有效性校验（fixture中2次→1次） |
| NEW-3 | Actor/Bed搜索NaN与Inf半径绕过检查，浮点半径平方溢出 |
| NEW-4 | 家具可达性射线重复对象/连续穿透导致无界循环 |
| NEW-5 | 主题编辑器绕过已有Validate，非法值进入实时主题 |
| NEW-6 | 默认BedRoll角度180度未经转换传入弧度坐标 |
| NEW-7 | Actor查询/排序拒绝重复、None、超量输入；未知actor构造异常安全失败；Ex排序构造碎片从每候选一次减为每请求一次。 |
| NEW-8 | 偏移native拒绝非finite；Transform YAML先解析验证再发布，失败保留原偏移；家具YAML过滤非finite。 |
| NEW-9 | ObjectBound有效性检查覆盖local/world/rotation非finite，阻止NaN进入SAT与位置判定。 |
| NEW-10 | Creature计数native/helper相加前范围检查，拒绝负数及int极值溢出。 |
| NEW-11 | Collision massInv/gravity保存原值、解除后恢复；保留刚体引用并在缓存锁外释放，Revert仅丢弃旧世界引用。 |
| NEW-12 | CreateProxyArray过滤查询reserve按实际场景数约束，不因外部UINT32_MAX请求过量分配。 |
| NEW-13 | Binary识别hysteresis在NaN预测下保留旧active，Inf可开启；非finite预测现在清空active/timeActive。 |
| NEW-14 | 七个识别除数配置参数不再接受零，避免距离/速度/持续时间特征除零。 |
| NEW-15 | UI偏移浮点转整数使用double舍入并钳制到int范围，避免有限大数转换未定义行为。 |
| NEW-16 | 声音导出拒绝路径分隔符/驱动器前缀，目录与文件名使用path拼接；序列索引使用size_t避免2^24处float递增停滞。 |
| NEW-17 | 公开线程ID访问拒绝越界；Hook读写检查None/ID范围，写入前初始化锁数组。 |
| NEW-18 | 动画分页空/整页数量多算一页及非法perpage；GetList先同步并收集实际候选、有限次抽样，跳过稀疏别名空项。 |
| NEW-19 | Legacy动画运行时间把毫秒当秒；场景旋转增量把弧度当度。现在显式换算并检查无效axis/actor索引。 |
| NEW-20 | ReleaseAnimations将graph锁去重并按std::less固定顺序获取，避免共享manager重复锁和跨实例获取顺序相反。 |
| NEW-21 | Legacy expression、offset、gender计数及FindNext公开输入边界保护；空phase返回0、偏移数组长度限制128。 |
| NEW-22 | MoveScene稳定等待限20次，每次latent返回检查StartupRequest/场景状态，终止后旧调用不再锁Actor或重定位。 |
| NEW-23 | ActorAlias在SetActor时捕获原始graph变量，避免Native恢复前已改写导致脚本清理覆盖原值。 |
| NEW-24 | HUD初始化被拒绝时不隐藏游戏HUD、不误记打开；只关闭当前线程持有的HUD，新增native所有权查询。 |
| NEW-25 | IsAggressive setter正确取反映射到consent；GetNthPosition拒绝越界。 |
| NEW-26 | NiMotion显式保存anchor存在性，原点合法；非finite及缺失样本隔断轨迹，PCA/描述量仅使用最新连续有效窗口。 |
| NEW-27 | Native清理保留已恢复/新发生的死亡状态；仅恢复自己修改过的Variable05基础值，重复准备不覆盖原值。 |
| NEW-28 | Ending等待累计最多200次，失败记录超时并安排既有恢复入口；空Alias跳过，latent恢复后拒绝过期请求；MoveScene在CenterOnObject返回后同样检查请求。 |
| NEW-29 | 死亡Alias清理临时取消essential后恢复原值，避免永久修改共享ActorBase。 |

## 验证证据与限制

最终当前代码完整便携套件结果见 `validation/full-scan-portable.log`。C++ 测试提取实际生产函数/包含实际头文件，所需引擎对象为替身；Papyrus 是有限控制流翻译，不是 Papyrus 编译器或真实 VM。翻译工具测试使用临时真实文件，不修改真实翻译资产。通过范围仅限各测试实际执行的路径。

本轮新增 sanitizer 日志包括伙伴查询、家具、主题、Actor 查询、偏移转换、几何界限、生物计数、碰撞原物理值、识别迟滞、graph 锁、UI/Voice、NiMotion 和原生 Actor 恢复。`full-scan-asan-*.log` 为 ASan+UBSan；自定义 allocator 的 Proxy 测试未混用 sanitizer。

`full-scan-baseline-motion.log` 与 `full-scan-baseline-preparation.log` 对已提交 HEAD 执行相同实际源码回归，分别在原点存在性和原值恢复断言失败，当前代码通过。这是修复后补做的基线复现，不冒称所有 29 组都先跑失败测试再编辑。其他组的证据边界见 `findings.md` 和各测试源码。

Variable05 基础值读取接口对照仓库锁定 CommonLib commit d61bca4de789428aa7d98a770b1323ddf1bb855c 的 [ActorValueOwner 声明](https://raw.githubusercontent.com/alandtse/CommonLibSSE-NG/d61bca4de789428aa7d98a770b1323ddf1bb855c/include/RE/A/ActorValueOwner.h)；没有据此宣称真实 DLL ABI 已通过。

## 保留的开放项

- Collision controller flags/context与Foot IK恢复当前仍采用默认值，是否应保留原值、哪些瞬时字段应重新求值，尚无可靠引擎生命周期契约；这是源码开放项，未归为仅游戏验收。
- Collision缓存锁内获取graph锁及movement hook更新controller的跨模块锁顺序/并发写入契约未闭环；ReleaseAnimations的内部重复/逆序graph锁已修复，但不能证明引擎外部锁序。
- ActorPreparation保存raw Actor指针；跨存档Revert、异步animation恢复、scale/collision/HUD所有权生命周期需实际SDK/调度验证。
- Ending清理超时采用既有game-time Initialize恢复入口，真实VM中事件积压、菜单暂停、原死亡/essential actor复原的时序尚未验证。
- 辅助测试/CI/审查工具56文件列入范围与AST检查；不声称本轮逐函数人工审查全部辅助实现。
- 全部4910条目有源码阅读结论；1226条仅名称/本体SHA不变后迁移旧结论，88条改动/新增逐项登记检查和测试限制。所有阅读标志仍不代表完整调用链或真实VM证明。

必须在 Windows 完整构建 DLL、Papyrus/PEX、Spriggit 产物并按 `runtime-validation.md` 验证游戏/VR、跨存档和真实 VM。新增 `IsSceneHUDActiveImpl` native 查询要求 DLL 与脚本一起打包，不能只替换 PEX。

所有之前及本轮的本地改动保留；本轮未提交、未推送。本报告不提供“其他源码问题全部不存在”的保证。
