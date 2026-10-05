# 剩余契约定点核查结果（2026-10-05）

在已有222文件本体阅读上核查剩余疑点，没有重复一遍完整读取。新增三组修复，累计32组；当前58,891行、4,920条源码阅读结论。阅读覆盖和本地回归通过不表示全调用链或所有问题已经证明收敛。

| 原开放项 | 本次处理与证据 | 仍需的证据及验收步骤 |
| --- | --- | --- |
| Foot IK默认恢复、共享driver | 保存原disabled和quaternion，去重graph并计数共享owner，最后owner退出才恢复；保留driver/graph引用；`collision_foot_ik.py`执行实际函数 | 私有hkb字段偏移/真实引用生命周期需要各支持游戏版本及VR核验；预设禁用IK、双Actor共享/切换graph后退出，确认原状态及无崩溃 |
| controller默认恢复 | 保存四个持久控制位NoGravityOnGround/NoSim/NotPushablePermanent/PossiblePathObstacle；捕获替换controller，共享owner计数；退出只还原这四位，引用锁外释放；16组合及替换/共享/Revert实际helper回归 | Support/CheckSupport、Swimming→OnGround、速度和support manifold属于瞬时状态，SDK声明不包含重初始化契约；在斜坡、楼梯、空中、水中分别进入/退出，确认退出后的支撑、重力及行走。不能以还原旧位置/速度代替该验证 |
| cache/graph锁序及controller并发写 | Add/Remove先释放cache锁再进入Foot IK；Foot IK按graph→cache获取；movement hook独占cache锁，原callback在锁外。实际函数替身断言锁序 | SetLinearVelocityImpl等引擎虚函数内部锁/reentry不在仓库，不能证明全引擎锁序；在多Actor碰撞切换和graph卸载时使用调试DLL跟踪等待/重入及卡死 |
| raw Actor跨存档残留及异步任务 | Revert取消creating/active/pending，清双Ni registry、ActorPreparation、HUD/selection菜单；清理不向旧Actor写回；native创建改game task，创建/selection/撤销任务按世代过滤；中心初始化在game thread直接执行，避免排队等待自己。实际Revert、队列、分派片段及菜单reset测试通过 | 原子世代不能保护已开始执行的VM/native/UI调用。缺SKSE加载时VM暂停与回调线程、UI render与Revert互斥契约；在创建排队、选择菜单、active、Ending各阶段连续A→B→A读档，确认无旧实例/HUD/准备记录、旧任务不访问旧Actor；后台VM负载与菜单打开状态都测试 |
| Ending/死亡/essential事件时序 | 先前的有限超时和原值恢复修复保留；未把已有有限Papyrus翻译测试升级为真实VM证明 | 真实VM事件积压、菜单暂停和game-time推进契约不可在本机替身证明；死亡及原essential Actor在启动/结束/超时/读档时核对复原，匹配DLL和PEX |
| 辅助范围/阅读台账 | 范围检查222生产、59辅助、2第三方排除，无遗漏或Python语法错误；218同名同本体记录迁移、29新/改条目逐项登记；11解析诊断文件对账 | 辅助文件枚举与语法检查不表示59文件全部人工逐函数审查；4,920条`source_reviewed`也不是调用链认证。没有新增人工验证承诺或包装清零 |

HUD先前已有generation+owner过滤，因此保留，不另计修复。native入口在读取VM属性前捕获世代，排队创建的回调在使用Quest/Actor前检查世代；这减少旧任务问题，但不代替真实加载暂停契约。

本地验证：完整`tests/run.py`退出0（`validation/closure-portable.log`）；native入口世代捕获位置的最后调整另外运行`world_revert.py`退出0（`closure-world.log`）；Foot IK、controller及world清理针对性ASan+UBSan通过。`git diff --check`及scope检查通过。测试使用实际函数或明确限定的源码片段与引擎替身；没有完整DLL/PEX构建、真实VM/游戏/VR执行，没有FPS改善测量。

所有修改保留在工作区，未提交、未推送。下一次续接应从上述具体外部契约/验收步骤开始；不要把再次读取所有文件当作新的验证。
