> 当前结论以 [full-scan-report.md](full-scan-report.md) 为准。下面早期阶段的待读数量与完成描述属于历史进展。

# 本轮发现与验证

基线：`36e6ff76e3f5d3a28aa34c48962240f3a50ac678`。2026-10-04 暂停，2026-10-05 按 CHECKPOINT.md 续接；审查仍进行中。

## 已修复

| 项目 | 触发与影响 | 修复 | 验证 |
| --- | --- | --- | --- |
| 头文件重复定义 | 两个编译单元包含 `Misc.h`，非内联函数产生重复符号 | `GetLeveledActorBase` 改为 inline | 实际头文件，两独立 TU，`-O0`；修复前链接失败，修复后通过 |
| 脚本属性缺失崩溃 | UI 属性不存在或对象为空，解引用空 Variable | 读取返回默认值、写入不执行，并记录错误 | 提取生产属性函数；修复前 SIGSEGV，修复后缺失/空对象/正常值通过 |
| 种族位污染性别 | 生物种族编码的 bit 4 被当成人类 Futa 标志，影响性别查询与评分 | 仅 Human fragment 解读 Futa 位 | 生产枚举与 GetSex；63 种编码 × 男/女，另含人类 Futa；修复前断言失败 |
| 哈希解码分组错误 | 十进制或省略前导零的二进制组合哈希未按 11 位分组 | 恢复 55 位布局，拒绝负数、越界和非法二进制 | 实际 CLI 对比十进制、短二进制和固定宽度输出，并验证错误返回 |
| Native 空 actor | `SetNextPermutation` / `UpdatePlacement` 传 None 进入要求非空的实现 | 在入口拒绝 None 并 TraceStack | 生产入口函数与严格替身；修复前违反非空契约，修复后正常/None/缺失实例通过 |
| 阶段加权选择额外分配 | 原实现按每个匹配标签重复保存阶段索引，空间随权重总和增长 | 每个相邻阶段只保存一个 uint64 累积边界，按原随机票号选中阶段 | 512 组权重逐票比较旧算法，验证相同选择；极大权重不按分值分配内存 |
| 高潮参与者索引 | 原生返回稀疏场景位置如 `[2]`，脚本却检查列表序号 0 | 使用 `orgP[n]` 访问参与者、alias 和结果 | 稀疏位置、重复位置及性别/开关组合；修复前错误返回位置 0 |
| 回退阶段历史 | 回到第 2 阶段却保留零个前序阶段，返回历史长度为 1 | 保留 `ToStage - 1` 条前序历史 | 5 阶段回退到 2/3/4；重复ID边界已在续接补核查中修复 |
| 阶段计时器索引 | 首阶段取第二个计时；单元素自定义计时访问 -1 | 阶段号转换为零基下标，单值用于全部阶段 | 单值、首段、中段、超过数组、高潮尾值；修复前负下标失败 |
| 拒绝场景切换的恢复 | 无效场景切换注销更新后直接返回，且提前记经验 | 失败恢复原更新；成功后再累计旧场景经验 | 注入 SetActiveScene 失败，验证恢复与不记经验 |
| 标签过滤错误放行 | require-all 缺失标签和 require-any 无匹配仍返回 true | 按全部/任一/排除语义返回 | 空、单、多标签 × require-all × suppress 真值组合 |
| 寻路设置忽略参数 | SetPathing 对旧字段而非新参数做 clamp | clamp 传入参数 | 禁用/默认/强制/两侧越界；修复前字段不变 |
| 坐标数组边界 | 只有三组数组同时尺寸错误才返回，单组错误继续越界 | 任意一组错误即拒绝 | 分别缩短输出/中心/偏移数组，另测有效旋转偏移 |
| 场景控制提前停更 | 取消移动仍注销更新；随机场景入口在 reset 节流前提前注销 | 确认移动后才停更；reset 统一拥有停更逻辑 | 取消移动执行测试；随机场景入口与 reset 调用链源码核查 |
| 旧版最短线段公式 | 相交线段被算出非零距离；截断端点后未重新求另一端 | 修正投影公式及端点截断后的重算 | 修复前交叉用例失败；修复后 1000 随机样本检验对称与条件最优性，含平行/点 |

| 生物性别位掩码 | creature 使用 0x24、female creature 使用 0x16，错误包含人类性别位 | 分别改为 0x18 和 0x10，保留原接口拼写 | 六个 helper × 32 标志组合；旧代码在 Futa 输入误判 |
| 导航占位符数字溢出 | navtext 中超长数字经 stoul 抛出未捕获异常 | from_chars 无异常解析，越界索引同普通无效索引显示 {} | 普通、空、非数字、前导零、空 actor、超长数字；旧代码 SIGABRT |
| 进度条宽度 clamp | 宽屏与小缩放使下限大于上限，违反标准库前置条件 | 显式 min/max，保持缩放后的最大宽度约束 | 4 宽度 × 3 高度 × 3 缩放；旧代码前置条件断言失败 |
| 场景图丢失实例 | Begin 后实例不存在直接 return，漏 End 导致 UI 栈失衡 | 在 Begin 前检查实例，关闭过期窗口 | 源码路径核查；尚未做真实 ImGui 集成测试 |
| BaseObject 标签边界 | 空列表声称包含任意非空标签，空标签可添加，删除返回错误 | 明确非空标签与 Find 结果条件 | 空/重复/缺失标签及添加删除控制流回归 |
| BaseObject 启用设置 | _SetEnabled 只读取字段，不写入参数 | 写入 aSet | 执行实际函数翻译，验证状态变化 |
| 床类型及占用筛选 | 单人/双人判断相反；IgnoreUsed=true 反而接受已占床 | 修正类型映射与忽略已占床的布尔条件 | 四种床类型；允许/排除占用床，针对性测试通过 |

### 2026-10-05 续接修复

| 项目 | 触发与影响 | 修复 | 验证 |
| --- | --- | --- | --- |
| 表达式随机与稀疏过滤 | RandomInt 含 Length；共用输入/输出索引丢失稀疏结果 | 上界 Length-1、独立索引、实际候选随机选择 | 空/末项选择、稀疏 bool 与 alias 间隙 |
| 表达式/声音注册 | FindEmpty 跳过首个空槽；失败路径绑定无效对象；新 ID 重排后返回错误槽 | 查空槽、失败不绑定、SyncBackend 后返回实际 alias | native失败、容量耗尽、ID重排、锁释放；有限翻译，未验证 VM 并发 |
| 声音保存查询 | FindSaved 将 voice 对象传字符串 ID 接口；压缩 Registry 索引不等于 raw alias | GetSavedVoice ID，直接查 alias | 保存 ID 参数、稀疏注册 alias 用例 |
| legacy 动画数据 | 阶段边界反向、整数当stage ID、计时不推进、四坐标展开覆盖 | 一基Stage转ID、最长路径计时、按 stage/actor 展开 | 阶段边界/空路径、3阶段×2角色坐标、路径计时；事件传参源码核查 |
| 动画 race/tag | Find 的0/-1当bool；不可删基础标签却返回成功 | 显式 Find、只删annotation | race 首项/缺失；annotation调用契约源码核查 |
| 左右手卸装 | 右手结果推入未赋值LeftHand；左手存储写RightHand | 正确对象和手位 | 双手返回/卸装调用/手位存储 |
| 生物筛选与角色排序 | 固定男性数量重复扣除；男女优先反向、同类不稳定 | 正确扣除可选位数、稳定优先排序；HasRaceKey接纳首项 | 0..3位全部M/F/either/human组合×请求数；五性别全部排列 |
| 表情单位及边界 | 超32数组写越界、Mood ID被乘100、Phase<=0负索引、modifier无效 | 限32、ID原值、非法gender/phase拒绝、应用modifier | 长度0..40、Mood及量值、无效phase、强度缩放 |
| legacy 属性与关系 | Victims/BedStatus无return；空positions访问0 | 返回数据，空/None关系返回0 | 真实getter体、空/单/多角色关系比较 |
| 清除性别覆盖/效果缓存 | creature代码3/4当Faction rank；String缓存调用UnsetIntValue | 使用局部性别码0/1；UnsetStringValue | 性别0..4转换；效果存储类型源码对账，未跑StorageUtil |
| Lovense时长 | float配置用整数入口读取 | GetSettingFlt | 与设置定义和相邻duration读取源码对账，未跑外部插件 |
| Framework返回与启动清理 | 三个声音包装无return；动画首页0无效；旧StartSex添加失败漏释放 | 返回native结果、首页1、失败EndAnimation | 三包装返回、添加失败释放；首页调用契约源码核查 |
| 配置表情编辑器 | phoneme/modifier字段错位；末组_high残留/空数组访问 | 0..15音素、16..29修饰器；每次清高阶段、禁用列零值、空profile早退 | 实际函数翻译：末组空高段、字段对应、空profile |
| 组合热键及hook容量 | 构造R_M_S但解析M_S_R；hook满128仍返回添加成功 | 统一M/S/R顺序；满数组拒绝 | 八种前缀组合；hook容量与PushThreadHook契约源码核查 |

### 2026-10-05 调用链及边界补核查

| 项目 | 触发与影响 | 修复 | 证据与边界 |
| --- | --- | --- | --- |
| native 生物匹配 | Dog先占Canine位置，Wolf无位，错误拒绝Canine/Dog可行分配 | 预计算输入种族、增广匹配；可选dummy填未约束位置 | 完整生产函数+替身对照144组合；输入顺序、无效/None、人类及重复生物 |
| legacy 交互 | vagina limb记录自身；graph bool读取失败时使用未初始化值 | 记录partner，初始化并检查graph读取成功 | 生产函数伙伴及graph缺失/false/true回归 |
| 模型参数非finite | bias/legacy系数只拒绝NaN，Inf/float溢出污染预测 | bias、legacy与cluster统一要求finite | 实际Initialize针对NaN、±Inf及溢出输入 |
| kissing缺失节点 | 无mouth采样仍生成描述 | 双方mouth anchor守卫 | 四种可用组合；不执行无数据的DescribeMotion |
| actor重排及quick reset | 脚本alias顺序、旧识别sex快照未随native assign变化 | 同步回调刷新别名/位置；quick reset强制刷新；scene/perm变更使两种识别实例失效重建 | alias逻辑执行；快照取消顺序源码检查。真实VM/识别线程未测 |
| 偏移面板缓存 | 重排后旧positionIndex读到其他角色位置 | 按actor重算下标，变更清基线/拖拽 | 实际RefreshValues交换两角色回归；ImGui未测 |
| 重复stage ID回退 | same-stage native早退不追加history，截断后历史少一项 | 重对齐保留，但仍追加返回history | 循环A/B/A、不同ID、非法ID、空历史；RealignActors忽略返回值的调用方核查 |
| 相似阶段/跳转 | 数组身份比较；跳过第3阶段；把静态阶段列表下标当history序号 | 逐标签比较、从索引2搜索、按stage ID跳转；无匹配恢复timer | 身份数组替身、3阶段匹配、无匹配和direct-ID跳转；实际clip同步未测 |
| 声音分页/稀疏过滤 | raw alias下标与注册序号混用，漏尾部、空洞；页数整除多一页 | 只按registered序号分页/过滤；clamp perpage；最多100候选用部分Fisher-Yates | 空/整除/越界页、gap、128选100唯一值、不改输入mask |
| 后端缩减 | expression/voice native列表变短，尾部旧ID继续绑定 | 遍历全部alias并清除超出列表的Registry | 缩减+gap回归；nativeID与alias并发更改仍未测 |
| 性别覆盖及空actor计数 | GetTrans返回原生而非配置性别；None被计为male | 按ignoreOverwrite契约读取；计数跳None并守卫值域 | 男女互换、futa/creature、None及非法值 |
| legacy hook初始化 | 子类OnInit覆盖父类，锁数组未初始化 | Parent.OnInit后运行旧加载路径 | 父子调用契约源码检查；VM初始化未测 |
| 最后一层贴图 | SetIntValue返回新值时，到maxLayer直接return，最后一层永不应用 | 按写前previousLayer判定是否已满，正常写入后应用 | maxLayer=0/1/3，最后一层路径及重复调用；外部StorageUtil/渲染未测 |
| 相机忙等 | 相机不切换时无yield的无限循环 | 最多50次请求、每次Wait(0.02)，movement复用 | 永不切换及已切换控制流；VR和实际相机调度未测 |
| SLR bool对象表示 | 将任意输入字节直接读入C++ bool，非法表示有UB | uint8读取、只接受0/1后赋bool | 256字节值+ASan/UBSan；Scene allowBed/isPrivate接入 |
| 批量旧统计 | 21字段逐个获取ActorStats，重复复制自定义map和锁读取 | 整批共用一次快照；单值共用相同转换实现 | 快照调用21→1、逐字段等价、None不读取；未测FPS |
| 向量旋转单位 | vector setter直接把度当弧度，和scalar setter/脚本文档不符 | 场景及stage vector入口度→弧度 | 0/±90/180/360度、所有stage/单stage、短数组；生产内无vector setter调用方 |
| 长路径旧调整数组 | path×actor×4超过Papyrus128容量，循环仍写全部 | 明确cap128，只写完整四坐标组，写满停止 | 100段×2角色回归；旧数组接口最多返回前128值 |
| 失活默认动画数据 | 两个5P定义把A5的4个事件写入a4 | 改为a5 | 执行定义体替身，各角色均4stage；未启用已禁用入口/工厂 |
| 匹配器部分法术 | 只看第一项就早退，漏补其他项；空数组访问0 | 逐项核对、跳None、只修改实际不符项 | 部分缺失、删除、空数组 |
| 安装界面等待 | 缺要求/安装不完成一直Wait | 检查要求，最多120×0.5秒；只成功后重绘 | 失败/不完成/三次完成/已完成；新游戏延迟安装需重新打开菜单查看 |
| 遗留诊断输入 | 负RunTest次数持续递减；Loops=0除零；动画页0、数量超返回数组、线程固定15 | Benchmark参数守卫；nth>0；诊断页1、实际数组长度/线程数 | 三个RunTest负/零输入及invalid参数执行；诊断调用契约源码检查 |

回归入口：`tests/systematic_audit.py`、`tests/systematic_native.py`、`tests/systematic_scripts.py`，均纳入 `tests/run.py`。统计及decode回归扩充了原测试。引擎类型为替身、Papyrus为有限语句翻译，不代表DLL/VM/游戏执行。

性能结论限于算法和调用次数：阶段选择额外存储降至O(阶段数)；输入种族每请求只解析一次；批量旧统计快照21次降至1次；声音抽样有界、长路径legacy数组写满停止。未测游戏帧率。

## 2026-10-05：剩余可本地验证契约的逐项处理

按用户要求逐项验证并修复，实机项目移交用户打包验收。具体逐项结论、兼容策略、输入边界及验收步骤见 `runtime-validation.md`。

- **RaceKey/RaceID**：枚举合法范围、空Actor/Race/图路径及sex索引保护；有效Human数组`[0]`与错误空数组分开，种族只构造一次；整数映射在转uint8前检查范围。标量历史`0`错误返回兼容保留，脚本文档纠正此前宣称`-1`的错误。
- **种族/标签契约**：评分Canine排除Fox，与头文件、索引Split和RaceKey契约一致。基础tag命名空间优先保留，明确`HasAnnotation`独立查询，真实函数回归固定已有行为。
- **SLR语义边界**：race/sex/extra/正scale、非负duration、家具mask及All哨兵；家具和position数据改为读整数后构造EnumSet，避免对象表示覆写；文本拒绝内嵌NUL。四版本的climax非0为true和strip全部8位含预留位保留，未任意收紧。
- **配置/主题**：新增SettingsValidation，接入YAML/INI/native设置入口，验证float、float数组及菜单整数域；保留百分比原有double归一化。Theme全部float字段校验，无效字段回默认；HUD异常享受值回0。
- **SKEE**：target、删除旧override后base及倍率finite/正值保护；旧、新路径都不传递除零/溢出倍率。实际API布局未在本机认证。
- **Actor缓存**：享受值改存Actor对象而非全局名字；低值backup清旧值，未备份/时间回退不恢复。旧名字缓存不迁移，避免错误分配；临时缓存时效60秒。
- **评分溢出**：单项累计64位，int32返回饱和；分配总分及递归累计64位，极大正/负权重排序回归通过。
- **射线**：错误线程检测后立即返回，空filter跳过；不再记录错误后继续调用Havok。实际线程、重入及ABI仍需实机。
- **构建**：Papyrus跟踪include PSC/flags、工具、文件集合及稳定选项值，缺PEX强制重建并创建输出目录；Spriggit跟踪排序资源集合/工具，新增、删除文件改变depvalues。使用上游xmake2.9.5实际依赖检测Lua验证。安装顺序已按上游调度源码核对，生成/复制发生在common install前，无代码改动。

证据：最终`validation/portable.log`退出0；新增8组`contract_boundaries.py`全部通过，ASan/UBSan日志`validation/asan-contracts.log`退出0；`validation/build-contracts.log`通过实际Lua+上游依赖检测测试。测试包含固定域穷举、四SLR版本合成scene、异常数值、缓存隔离及极端评分排序；不等同DLL、VM或插件ABI认证。

本轮生产清单为221文件/58,290行/4,899条目，新增及改动的40条本体单独核查，360条相同文件/本体SHA记录因行号移动续接；11解析诊断文件按当前指纹对账。

## 剩余实机与集成验证

上一停点所列本地可验证契约已逐项处理。下列证据依赖用户的Windows构建、资源、VM及游戏环境，没有标记为通过：

- Windows/MSVC完整DLL、Papyrus编译、真实Spriggit、实际install/打包产物、external plugin及设备的ABI/返回值/回调契约。
- scene reset、换位、固定时长和过期回调、camera/VR、覆盖层最后一层及真实ImGui渲染。
- 跨存档/Revert的旧实例、准备actor、排队工作生命周期；Settings直接读取与写入的实际同步；射线线程归属、共享collector重入及Havok ABI。
- 真实SLR包的行为事件/HKX、声音、贴图和骨架存在性，以及新增校验对实际旧版本包的兼容验收。

兼容约定已明确保留：旧标量RaceID无法单凭0区分Human/错误；基础tag名称不由同名annotation覆盖。这两项不再作为本轮未核查源码事项；若以后要改变外部行为，应单独设计API兼容变更。

源码覆盖与本轮限定契约的本地验证已完成；台账`call_chain_closed=false`仍表示完整集成链未经真实环境认证，不宣称问题穷尽。下一停点见`CHECKPOINT.md`，实际验收勾选项见`runtime-validation.md`。

## 2026-10-05 新全覆盖审查第一批修复（整体审查尚未完成）

1. **NEW-1 翻译工具**：TODO后空行触发IndexError；BOM使首键漏读；目标更新先截断再查找fallback。改为按marker键识别TODO、去除BOM参与解析、先构建结果并同目录replace，支持目标缺失；main加导入保护。`translation_regressions.py`以临时UTF16文件验证空行、BOM、幂等、缺失目标及replace失败时原文件不变；未运行真实翻译目录。
2. **NEW-2 生物候选漏失**：FindAnimationPartnersImpl原调用FindAvailableActors(empty race)只保留Human。改为遍历有效process候选，由Scene位置匹配种族；保持公开FindAvailableActors空race=Human的既有契约；先按距离筛选再做昂贵有效性校验，fixture中两候选只对范围内一名做有效性检查（2次→1次），不声称FPS收益。`scene_partners.py`提取实际两个finder和FindBeds并执行真实RequiredMatching，混合种族/必选/重复/距离回归通过；引擎、RaceKey数据查询为替身。
3. **NEW-3 查询半径边界**：FindAvailableActors/FindBeds的 `<0` 不拒绝NaN/Inf，筛选失效。拒绝非finite半径和非finite床Z限制；有限负Z仍表示不限制。actor距离拒绝非finite，半径平方使用double避免float溢出。同一真实函数回归先失败后通过。
4. **NEW-4 家具可达性无界射线循环**：ThreadCtor的独立路径用do/while(true)，缺重复命中与次数上限。改为最多64次穿透，重复对象立即终止。`furniture_reachability.py`实际lambda验证重复障碍、连续唯一障碍64次上限、直接可达；旧代码在测试超过100次后失败。
5. **NEW-5 实时主题编辑绕过校验**：DrawThemeFields直接写live data，而既有Validate只覆盖加载/Save副本，非法值能在渲染前进入live主题。改为编辑candidate、Validate后赋回；`theme_editor.py`实际RenderThemeEditor入口验证非法输入回退/合法输入保留/隐藏时不写。UI及validator在入口测试中为替身；实际Validate全float域由原contract_boundaries.py独立覆盖。
6. **NEW-6 默认BedRoll角度单位**：Coordinate保存弧度，默认BedRoll却直接填180.0；YAML家具分支正确用radians，这个默认分支漏转。改为pi弧度；`default_bedroll.py`编译实际默认初始化与实际Coordinate构造器，验证半转三角值及高度7.5不变。

完整回归日志：`validation/full-scan-portable.log`。targeted ASan/UBSan：`full-scan-asan-partners.log`、`full-scan-asan-furniture.log`、`full-scan-asan-theme.log`。不声称FPS提升；射线修复给出单路径64次确定工作量上限。未执行完整DLL/Papyrus/游戏验证。

**开放源码问题仍在**：未知/重复actor如何跨Native/ActorFragment安全失败、Coordinate/Transform偏移非finite及YAML加载事务、Collision状态原值恢复/锁顺序。还未完成本轮重读的126文件见full-scan-progress.json。没有将其全部归为实机问题。

## 本轮继续核查（NEW-7—NEW-10，2026-10-05）

- NEW-7：`MakeFragmentList` 统一拒绝 None、重复演员、超过 5 人和无法构造的演员数据，查询及 legacy 排序使用此入口；`CanFillPosition` 对无效候选安全返回 false。`SortBySceneEx/ExA` 在候选循环前构造一次演员信息。`actor_query_boundaries.py` 提取真实函数：重复输入修复前失败，修复后通过；3 个候选/2 名演员构造次数为 2。引擎构造替身模拟 runtime_error，不证明真实 Actor/VM ABI。
- NEW-8：Transform 的 3 个 native 消费 setter 拒绝非有限数据；YAML 使用候选副本，在转换和有限性检查全部成功后提交，转换失败不留下部分偏移；家具 YAML 不登记非有限坐标。`transform_boundaries.py` 提取实际 setter、loader、IsFinite，YAML 为转换替身。测试 NaN、正负 Inf、第二分量转换失败、合法度/弧度契约；不证明整个 Scene/YAML 文件事务性。
- NEW-9：ObjectBound::IsValid 原来仅比较局部盒尺寸，忽略世界坐标及旋转的非有限数；SAT/IsPointInside 消费此结果。现检查所有五个 vec3，测试实际谓词 45 种非有限组合，以及旋转后的世界对角无需按轴排序。未验证 Havok 地址偏移/真实形状。
- NEW-10：生物计数 native/helper 在范围检查前做 signed int 相加，极值可溢出。现拒绝负数和超出人数的组合，再做差值约束。`creature_count_boundaries.py` 提取真实 native/helper，49 组含 INT_MIN/MAX 输入，非法输入不进入场景遍历，合法 1/0 查询保留。ASan/UBSan 通过。

新增源码疑问：CreateProxyArray 过滤分支的外部 returnsize 直接 reserve；Voice 大序列使用 float 循环索引及输出 ID 的路径约束。碰撞状态恢复仍为源码开放项；本轮仍未完成全部文件重读，不能据这些测试称为全覆盖完成。

- NEW-11：Collision 恢复原本将 massInv/gravityFactor 强制设 1，改变原来的物理属性。现第一次禁用时保存字段并持有刚体引用，移除时即使 Actor 已找不到也恢复被修改的原刚体，最终引用释放在缓存锁外；Revert 丢弃旧世界引用而不回写。`collision_physics_restore.py` 测实际保存/移除/Revert函数＋Havok替身，覆盖重复禁用、非1原值、缺失Actor、锁外释放，ASan/UBSan通过。控制器 flags、Foot IK 及跨模块锁顺序仍开放。字段/引用契约核对仓库锁定 CommonLib commit d61bca4：[hkpMotion](https://raw.githubusercontent.com/alandtse/CommonLibSSE-NG/d61bca4de789428aa7d98a770b1323ddf1bb855c/include/RE/H/hkpMotion.h)、[hkRefPtr](https://raw.githubusercontent.com/alandtse/CommonLibSSE-NG/d61bca4de789428aa7d98a770b1323ddf1bb855c/include/RE/H/hkRefPtr.h)。并未编译或执行真实Havok/DLL。
- NEW-12：CreateProxyArray 过滤分支按 uint32 请求 limit 直接 reserve，可产生过量分配异常。现预留量上限为实际场景数量，查询截断/排序语义保留。实际函数＋1MiB分配上限fixture在 UINT32_MAX 请求下修复前抛bad_alloc、修复后返回正确2条，1条限额及0无限保留。不会在测试中真实申请数十GiB内存。

## 本轮续接修复 NEW-13—NEW-29

- **NEW-13**：Binary识别hysteresis在NaN预测下保留旧active，Inf可开启；非finite预测现在清空active/timeActive。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-14**：七个识别除数配置参数不再接受零，避免距离/速度/持续时间特征除零。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-15**：UI偏移浮点转整数使用double舍入并钳制到int范围，避免有限大数转换未定义行为。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-16**：声音导出拒绝路径分隔符/驱动器前缀，目录与文件名使用path拼接；序列索引使用size_t避免2^24处float递增停滞。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-17**：公开线程ID访问拒绝越界；Hook读写检查None/ID范围，写入前初始化锁数组。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-18**：动画分页空/整页数量多算一页及非法perpage；GetList先同步并收集实际候选、有限次抽样，跳过稀疏别名空项。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-19**：Legacy动画运行时间把毫秒当秒；场景旋转增量把弧度当度。现在显式换算并检查无效axis/actor索引。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-20**：ReleaseAnimations将graph锁去重并按std::less固定顺序获取，避免共享manager重复锁和跨实例获取顺序相反。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-21**：Legacy expression、offset、gender计数及FindNext公开输入边界保护；空phase返回0、偏移数组长度限制128。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-22**：MoveScene稳定等待限20次，每次latent返回检查StartupRequest/场景状态，终止后旧调用不再锁Actor或重定位。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-23**：ActorAlias在SetActor时捕获原始graph变量，避免Native恢复前已改写导致脚本清理覆盖原值。 证据：对应实际源码回归，见完整套件及测试源码。
- **NEW-24**：HUD初始化被拒绝时不隐藏游戏HUD、不误记打开；只关闭当前线程持有的HUD，新增native所有权查询。 证据：tests/hud_ownership.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。
- **NEW-25**：IsAggressive setter正确取反映射到consent；GetNthPosition拒绝越界。 证据：tests/hud_ownership.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。
- **NEW-26**：NiMotion显式保存anchor存在性，原点合法；非finite及缺失样本隔断轨迹，PCA/描述量仅使用最新连续有效窗口。 证据：tests/motion_presence.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。
- **NEW-27**：Native清理保留已恢复/新发生的死亡状态；仅恢复自己修改过的Variable05基础值，重复准备不覆盖原值。 证据：tests/actor_preparation_restore.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。
- **NEW-28**：Ending等待累计最多200次，失败记录超时并安排既有恢复入口；空Alias跳过，latent恢复后拒绝过期请求；MoveScene在CenterOnObject返回后同样检查请求。 证据：tests/reposition_lifecycle.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。
- **NEW-29**：死亡Alias清理临时取消essential后恢复原值，避免永久修改共享ActorBase。 证据：tests/reposition_lifecycle.py；实际源码＋有限引擎/VM替身，不证明真实ABI/调度。

当前仍开放的源码契约见 full-scan-progress.json；本体完整读取与逐函数结论缺口明确分开，不宣称问题已穷尽。


## 定点闭环补充（2026-10-05）

NEW-30 Foot IK原值/共享owner与cache/graph锁序；NEW-31 Revert清native/准备/UI状态与跨存档排队世代过滤，game-thread中心初始化避免自阻塞；NEW-32 controller四控制位原值及共享/替换owner恢复。实际函数替身及targeted sanitizer通过，具体证据与外部契约见[closure-report.md](closure-report.md)。


## 44ae5487之后新增五组

NEW-33家具选择完成的game task/世代过滤；NEW-34表情与Scene导出路径和批量错误隔离；NEW-35表情非finite值；NEW-36mood更新判断/查询次数；NEW-37喉/嘴派生anchor有效性。触发、测试、兼容策略及仍未验证路径见[round-report.md](round-report.md)。
