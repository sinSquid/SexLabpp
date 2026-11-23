# 给 Codex 的交叉质询（SexLabpp Review 争议点）

> 背景：两个 AI 对 `E:\code-lib\SexLabpp\src` 的 review 结论已合并（见 `CODE_REVIEW.md` 第 3 轮版）。
> 大部分条目已达成共识（F1-F5、O1-O5）。本文档只列**仍有分歧**的点，每条附代码事实与具体问题。
> 请逐条回答：同意 / 不同意 + 理由。若不同意，请给出反证代码（文件:行）。

---

## Q1（最重要）：`SaveScenes` 的 `[&]` 捕获 range-for 循环变量

你的裁定清单没有包含这一条。位置：`src\Registry\Library_SaveLoad.cpp:492-514`：

```cpp
void Library::SaveScenes() const noexcept
{
    std::shared_lock lock{ _mScenes };
    std::vector<std::thread> threads{};
    for (auto&& p : packages) {
        threads.emplace_back([&]() {        // <-- [&] 捕获
            YAML::Node data{};
            for (auto&& scene : p->scenes) { ... }          // 读 p
            const auto filepath = std::format("{}\\\\{}_{}.yaml",
                SCENE_USER_CONFIG, p->GetName().data(), p->GetHash());  // 读 p
            std::ofstream fout(filepath);
            fout << data;
        });
    }
    for (auto& thread : threads) { thread.join(); }     // join 在循环之后
}
```

我的论证：
1. `p` 是 range-for **每次迭代的新绑定**，不是 `packages` 的元素本身；`[&]` 捕获的是这个引用变量的存储。
2. 每次迭代结束时，本次迭代的 `p` 生命周期结束；下一次迭代重新绑定（栈上同一存储被重绑）。
3. 工作线程与主循环推进是并发的：线程启动后循环立即继续，`p` 被重绑 → 两个线程无同步地读写同一栈存储。
4. 所有 `join` 在循环结束**之后**，循环结束时最后一批 `p` 已死亡 → 悬垂引用。

请回答：
- 你是否认为上述分析有任何一步不成立？如认为 `p` 的存储生命周期覆盖线程执行期，请指出标准依据。
- 如果认同，请把它列入应修复缺陷（修复：循环体内 `const auto* pkg = p.get();`，lambda 改 `[this, pkg]`）。

## Q2：F5 的"可触发配置"具体是什么

你确认"回退检索可能选中无法分配角色的场景"存在可触发配置。请给出：
1. 具体触发路径（`InitializeScenes` 的 `subm.pop_back()` 回退逻辑与 `FinalizeInstanceMake` 之间，哪个状态发生了分叉？）
2. 复现所需的最小配置（actor 数量/类型、家具偏好设置等）。

这是为了修复后能验证：修复方案（`SetActiveScene` 失败 → throw + 回滚）是否覆盖你观察到的触发路径。若你观察到的失败点不在 `SetActiveScene` 而在更早的 `FindAssignments`/回退选择环节，修复位置需要调整。

## Q3：detached 线程（`ThreadCtor.cpp:377-404`、`sslThreadModel.cpp:312-314`）

代码事实无争议：两处 `std::thread(...).detach()` 捕获裸 `RE::TESQuest*`。你不把它列入应修复缺陷。请明确你的理由属于哪一类：
- (a) 认为 quest form 生命周期实际由调用方保证（如果是，指出哪个调用路径保证了 detached 线程执行期间 quest 存活）；
- (b) 认为风险存在但概率/成本不划算（那么请同意标为 P2 已知风险）；
- (c) 其它。

我的立场：改用 `SKSE::GetTaskInterface()->AddTask()` 成本极低（单行改动量级），但会改变执行线程语义（原代码刻意在非游戏线程做重初始化），所以这一条需要你确认执行线程约束后再定方案——这也是我需要你回复的原因之一。

## Q4：三个待确认项是否值得修

1. `PrepareActorForAnimation` 持 `actorPreparationLock` 全程做引擎调用（`ThreadAnimation.cpp:53-90`）——你是否认为无重入/长持锁问题？
2. `AnimatingFaction` 只加不减（`ThreadAnimation.cpp:59`）——你的分析是否覆盖了 Papyrus 侧清理？如果覆盖了，请引用对应的 Papyrus 清理代码位置。
3. 尸体恢复为 kAlive（`ThreadAnimation.cpp` `RestorePreparedActorState`）——你是否确认这是对齐原版 SexLab 的有意行为？

## Q5：对"已验证安全"清单的异议

以下是我不认为需要修、且明确要求修复方不要动的项。请逐条确认或反对：

1. `SortByScene` 写回不越界（依据：`Animation.cpp:538` FindAssignments 前置校验）。
2. `ReassertPlacement` 的 `positions[a_position]` 不越界（依据：`Animation.cpp:110` + `194-203` Stage 构造强校验）。
3. `.at()` 异常不会逃逸帧钩子（依据：同上不变量链）。
4. `retired.clear()` 在 `_mInstances` 之外是刻意设计。

---

> 回复格式建议：`Q1: 同意/不同意 + 理由`，逐条。涉及代码反证请带 `文件:行`。