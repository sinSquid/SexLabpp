# 打包后验证清单（2026-10-05）

本轮完整读取生产源码并对已确认问题做了范围有限的本地测试；Collision等源码契约仍开放，详见full-scan-report.md。下表保留必须依赖 Windows、实际资源、VM 调度或游戏环境的验收。源码阅读登记及 portable/替身测试不能替代这些验收。所有代码仍未提交、未推送。

## 本地已核查的契约

| 项目 | 处理与证据 | 验证边界 |
| --- | --- | --- |
| RaceID | 保留旧标量 Human/错误均为0的兼容行为；数组现在有效Human返回`[0]`，错误返回空；映射整数先检查0..52，避免uint8截断 | `contract_boundaries.py`真实函数，0..255及负数/大整数；演员/字符串类型为替身 |
| RaceKey | 有效值限定Human..Wolf；Actor、Race空输入及非法sex索引提前退出 | 源码核查；有效枚举穷举；真实行为图识别需游戏资源 |
| Canine/Fox | 按RaceKey头文件注释、Split索引及兼容函数已有规则移除评分中的Fox例外；Fox单独匹配 | 53×53种族评分/兼容回归；具体模组种族识别仍需实机 |
| 标签优先级 | 保留已有基础标签命名空间优先；同名annotation不会覆盖基础标签，显式`HasAnnotation`查询编辑标签；写入头文件说明 | 实际查询/添加/删除函数回归；不把此兼容策略当成未定事项 |
| SLR值域 | 检查race/sex/extra/正scale、非负fixedlength、家具mask；家具All哨兵保留；避免读取器覆写EnumSet对象表示；字符串拒绝内嵌NUL | 逐字节及四版本合成scene测试；真实HKX/事件/贴图存在性需实机 |
| SLR兼容保留 | climax保持任意非0字节为true；strip是8位掩码，保留All及预留位；offset为有限int32定点数 | 四版本×256字节测试；没有擅自把已有宽松字段改为bool严格编码 |
| 配置输入 | YAML、INI及native float/菜单int setter共用校验；数组保持长度检查；拒绝NaN/Inf/负float/极端值、非法菜单索引 | 校验头文件测试+入口源码对账；百分比仍使用原有double归一化，FLT_MAX回归保留 |
| 主题输入 | 校验全部float字段；字体及除法尺寸必须为正；不合法字段回退默认，其余自定义值保留；HUD收到非finite享受值回退0 | 全float字段异常值回归；真实ImGui绘制需实机 |
| SKEE缩放 | 校验actor/target及旧、新接口删除已有override后得到的base；拒绝无效分母和溢出倍率 | 实际生产函数两分支回归；旧接口cast用共同API替身，未认证真实vtable/布局 |
| 临时享受值 | StorageUtil改按Actor对象存储；低值backup清旧值，未backup/负时间差不restore，避免同名角色与时间回退串数据 | 有限Papyrus翻译回归；旧按名字全局缓存不迁移（无法可靠归属，缓存时效只有60秒） |
| 匹配评分 | 单项累加64位并饱和返回int32；分配总分及递归累加64位，避免极端INI权重改变排序 | 实际生产函数极端正/负权重回归+ASan/UBSan |
| 射线线程 | 发现错误线程立即返回，不再继续调用Havok；空filter引用跳过 | 源码核查；实际线程判断、共享collector重入及Havok ABI留待实机 |
| Papyrus增量 | 跟踪所有include脚本/flags、编译器、配置及文件集合；删除PEX强制重编，创建输出目录；布尔选项使用稳定字符串供xmake比较 | 实际Lua+上游xmake2.9.5依赖检测器，编译器/文件系统替身 |
| Spriggit增量 | 跟踪排序后的资源文件集合及工具；增删文件改变values；缺失产物mtime0触发构建 | 实际Lua回调及上游依赖检测源码核对；真实CLI输出待Windows |
| 自动安装顺序 | xmake2.9.5先执行target的after_build，再执行rule的after_build；现有生成/复制在common自动install前，无需改代码 | [xmake构建调度源码](https://github.com/xmake-io/xmake/blob/v2.9.5/xmake/actions/build/build.lua)，真实安装/打包内容仍需Windows |

配置边界：普通float允许0..1,000,000；菜单缩放0.1..10；概率/透明度/音量0..1；minScale与timer必须正。INI百分比使用独立原有验证和归一化。主题一般尺寸/速率上限10,000，字体0.1..1,024，nestedMenuScale0.1..10；无效字段回默认。上限是防止异常数值进入绘图、转换及运算的工程边界，不是对最佳游戏参数的推荐。

## Windows构建及产物

1. 在包含CommonLib子模块、编译器和外部Papyrus源码的Windows环境执行完整release构建。保存MSVC、Papyrus、Spriggit日志；必须零错误，不能用portable通过代替DLL/PEX编译。
2. 保留正常构建产物，再无改动构建一次：Papyrus不应全部重编。
3. 删除一个`dist/Scripts/*.pex`后构建：该PEX应恢复；修改被其他脚本引用的PSC、flags或切换optimize/anonymize后构建：依赖脚本必须重编。新增/删除include PSC也应触发。
4. 删除生成的`SexLab.esm`后构建：应恢复；增加/删除/修改Spriggit资源后应重新生成。
5. 分别测试auto_install关闭/打开；打开时确认安装目录包含本轮DLL、PEX、ESM和新生成INI，文件内容/时间一致。压缩包中亦要核对，不能只检查dist。

## 游戏/VM验证（记录“通过/失败+日志”）

| 场景 | 操作 | 预期 |
| --- | --- | --- |
| 启动和资源 | 分别测试实际支持的SLR包，尤其旧版本包、声音/表情/家具配置；观察注册日志 | 合法资源正常加载；不应新增合法包被拒绝；非法包应报错且不污染其它包 |
| actor位置/快重置 | 2P/3P/5P中交换位置、切换scene、quick reset，再调偏移 | 角色、别名、性别快照与面板一致；不沿用旧位置偏移缓存 |
| 阶段图 | A→B→A→C，回退；固定时长和相似scene阶段跳转 | 历史保持实际顺序，跳转到指定ID；无重复/过期回调推进 |
| reset失败 | 有player/无player时分别给非法scene、取消移动及快速连续切scene | 原scene继续/正确停止；计时器恢复；旧异步回调不修改新scene |
| 跨存档 | scene播放、准备actor、异步读写时读另一存档/回主菜单再加载；反复保存/读取 | 旧实例/准备actor/排队工作不再引用旧存档对象；无崩溃、悬挂或串数据 |
| Settings并发 | 场景与HUD运行时反复改MCM、保存和加载配置 | 设置/UI一致；无冻结/随机崩溃；本地输入验证不等于同步契约已证明 |
| 主题/HUD | 正常自定义主题；零/负/极大尺寸及不合法JSON；窗口开合、切屏幕分辨率 | 无效字段回退或加载错误保留有效主题；字体/轨道不消失，无绘制断言 |
| 种族与筛选 | Dog/Wolf共用Canine、Fox单独scene、未知race、Human数组查询 | Canine不吸纳Fox；未知race不当作Human；Human数组为`[0]` |
| 同名缓存 | 两个同名NPC分开备份/恢复，再测试低享受backup、60秒过期、读档后时间回退 | 两者不互相继承；低值不复用上次高值；过期/回退不恢复 |
| RaceMenu/SKEE | 支持的旧/新RaceMenu各测缩放与移除；缺插件、缺骨架、零scale；关闭/开启缩放 | 有效缩放/恢复正确；异常不写NaN/Inf；真实接口版本/布局兼容 |
| Havok/家具 | 家具搜索、多线程开始场景、不同cell及VR | 射线在正确线程运行；无错误线程警告或共享collector重入；家具筛选结果正确 |
| 外部插件 | PapyrusUtil、MfgFix、Lovense、VRIK、SKSEMenuFramework实际支持版本，以及缺插件/设备情况 | VM签名、返回值、回调顺序、设备状态符合预期；不把声明核对当ABI证明 |
| VR/摄像机/覆盖层 | VR与非VR分别测试相机切换、最后一层贴图、不同overlay数量 | 等待有限、无持续忙等；最后一层实际显示，缩放与相机正常 |
| 安装/卸装及旧hook | 新游戏、旧存档升级、部分匹配器法术、旧hook初始化、菜单一分钟超时后重开 | 不无限等待；法术逐项一致；hook父类初始化与监听正常 |

建议随结果保存：游戏/SKSE/插件版本、DLL/PEX对应commit或打包时间、具体scene和SLR文件名、SexLab日志、Papyrus日志及复现操作。失败时先保留本轮日志，再定位具体调用链。

## 本轮新增修复的实机验收

- DLL/PEX同时更新，确认 `sslThreadModel.IsSceneHUDActiveImpl` 注册成功；两个场景竞争HUD时失败方不隐藏GameHUD、不误暂停场景；所有者关闭后恢复配置。
- 角色位置处于世界原点、节点暂时丢失/重载时，识别不把原点视为缺失、不把零占位当成运动。
- 正常退出、quick reset、异常结束，以及原死亡/昏迷/essential演员退出时，生命状态、Variable05基础值、essential与graph值正确恢复。
- 移动中心过程中结束/重置场景，过期继续执行不得修改新请求；持续移动时等待有限。Alias清理异常超过200次poll时日志报超时，既有Initialize恢复入口最终释放线程；真实VM繁忙/菜单暂停时测量恢复时间。
- 共享animation graph、不同Actor排序同时启动/结束，确认内部graph锁去重排序无冻结；此项仍需追查引擎外部锁顺序，不用一次游戏通过替代同步证明。


## 定点闭环补充（2026-10-05）

NEW-30 Foot IK原值/共享owner与cache/graph锁序；NEW-31 Revert清native/准备/UI状态与跨存档排队世代过滤，game-thread中心初始化避免自阻塞；NEW-32 controller四控制位原值及共享/替换owner恢复。实际函数替身及targeted sanitizer通过，具体证据与外部契约见[closure-report.md](closure-report.md)。
