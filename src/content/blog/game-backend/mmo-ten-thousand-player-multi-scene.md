---
title: "万人同屏 MMO 的一种服务端拆分方案"
description: "用多逻辑场景、权威实体与镜像体拆分万人战场，并讨论 Linux 多进程、入场均衡、共享状态、ECS/OOP 和故障接管。"
pubDate: 2026-08-25
tags: ["MMO", "游戏后端", "C++", "ECS", "Linux", "共享内存"]
draft: false
---

万人同屏最难处理的并不是“服务器里能不能放下一万个角色对象”，而是一万人集中活动时，谁负责运行这些角色、场景之间怎样交换状态、一个进程出问题后怎样接管，以及随着并行度提高，镜像和通信成本会不会反过来拖慢系统。

这篇文章记录一套仍待实现和压测的设计：一张战场由多个逻辑 Scene 共同运行，每个玩家只有一个权威实体，同时在其他 Scene 中保留轻量镜像。Scene 部署在同一台 Linux 机器上，以多进程隔离故障，通过共享内存交换公共状态。正常游玩期间不因为负载迁移角色，均衡主要发生在玩家或团体入场时。

本文讨论服务端场景架构，不讨论客户端万人渲染，也不展开 QUIC 协议和技能系统的具体实现。

## 从单场景拆成多个逻辑 Scene

假设一张战场运行十个 Scene。一万个玩家被均匀分配后，每个 Scene 大约拥有一千个权威实体，同时保存另外九千人的镜像：

```text
Scene 0
├── 约 1,000 个权威实体
└── 约 9,000 个镜像体

Scene 1
├── 约 1,000 个权威实体
└── 约 9,000 个镜像体

...
```

权威实体负责完整状态：输入、属性、HP、MP、技能、Buff、死亡、任务和私有数据。镜像只保存本地空间查询和公共表现需要的数据，例如位置、朝向、动作、阵营、公共血量和可选中状态。

玩家 A 的权威实体位于 Scene 0 时，其他 Scene 里的 A 都是镜像。玩家 B 属于 Scene 1，A 对 B 产生交互时，Scene 0 可以先用 B 的镜像完成目标选择和表现，最终状态仍由 Scene 1 中的 B 权威实体提交。

镜像不能成为另一个写入者。每个实体在任何时刻只能有一个权威归属：

```text
entityId
ownerSceneId
ownerEpoch
```

`ownerEpoch` 用来隔离迁移前后的旧消息。旧 Scene 即使恢复运行，也不能覆盖新权威实体的状态。

## 同机多进程，而不是一个进程十个线程

每个 Scene 可以使用一个独立进程，进程内保留一个常驻模拟线程，并将它绑定到独立物理核心：

```text
Battle Host
├── Supervisor / Entity Router
├── Gateway
├── Scene Process 0
├── Scene Process 1
├── ...
├── Scene Process 9
└── Shared Public State
```

同机共享内存的通信成本低于跨机器网络，同时多进程能隔离单个 Scene 的非法内存访问、死循环和进程退出。Gateway 独立保持玩家连接；Scene 崩溃后，Gateway 只需切换实体路由，不必让玩家重新建立连接。

多进程并不能解决整机故障。共享内存被错误写坏、主机 OOM 或机器宕机仍然会影响整张战场。这套设计先处理 Scene 进程级故障；如果需要整机容灾，还要向另一台机器复制检查点和命令日志。

Linux 上可以用 `pthread_setaffinity_np` 固定模拟线程，用 cgroup v2 限制 CPU 和内存。双路 CPU 还要注意 NUMA：如果 Scene 频繁跨 NUMA 节点读取镜像，共享内存很可能先变成内存互联瓶颈。一个战场应尽量放在同一个 NUMA 节点，或者明确分成两个低频互通的 Scene 组。

## Scene 数量存在性能拐点

增加 Scene 会降低单 Scene 的权威实体数量，却会增加镜像数量。设：

```text
P   玩家数量
S   Scene 数量
Ca  一个权威实体的平均成本
Cm  一个镜像的平均成本
C0  一个 Scene 的固定成本
```

全局成本可以粗略写成：

```text
Ctotal(P,S) = P*Ca + P*(S-1)*Cm + S*C0 + Ccross
```

它不是生产环境的容量公式，只用于说明趋势：权威实体总数始终是 P，镜像总数却是 `P*(S-1)`。Scene 增加到一定数量后，Dirty 消费、空间索引、缓存失效和内存带宽会抵消并行收益。

因此“一万人开十个 Scene”只能作为待验证配置。最终应对不同玩家数和 Scene 数运行压测，观察逻辑帧 P99、队列年龄、共享内存读写、LLC Cache Miss 和内存带宽，找到曲线最低点。

## 均衡发生在入场，而不是游玩过程中

正常玩家不因负载被迁到另一个 Scene。这样可以减少状态转移、输入重放和手感波动，但分配一旦完成，就只能等待玩家自然离开来修正不均衡。

Scene 生命周期可以设计成：

```text
Starting
  → Warming
  → CatchingUp
  → Open
  → SoftClosed
  → Draining
  → Retired
```

Scene 达到高水位后进入 `SoftClosed`，停止接收新团体，已有玩家继续运行；负载自然下降到低水位后再重新 `Open`。故障接管是在线角色迁移的例外。

入场调度可以借鉴 Kubernetes 调度器的 [Filter、Score、Reserve、Bind](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/) 流程：先过滤不健康或容量不足的 Scene，再评分，原子预留容量，最后创建权威实体。预留失败时必须幂等撤销，避免多个团体同时看到同一个“最空 Scene”并造成超卖。

调度单位不应只是单个玩家，而应是一次活动里的队伍、团队或公会 Cohort。第一个成员入场时创建 Group Placement Lease，为后续成员预留容量。整个公会通常过大，需要按照活动队伍拆分，不能硬塞进同一个 Scene。

## 把长会话团体分散开

只看当前人数会留下一个问题：短时玩家陆续离开后，几个长时间活动团体可能集中留在同一个 Scene。

每个入场团体至少需要两个估计值：

```text
瞬时成本 Cg：人数、活动强度、角色计算成本
留存成本 Hg：Cg * 预计时长权重
```

初期不必建立复杂预测模型，可以按活动类型将时长分为 Short、Medium、Long 和 VeryLong，并设置有上限的权重。公会攻城可能是长时间、高强度，挂机活动则是长时间、低强度；两者不能用同一个“在线人数”代表。

长会话团体的分布可以借鉴 Kubernetes [Topology Spread 的 maxSkew](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/) 思路。这里的拓扑域就是 Scene，比较的是加权后的 LongLoad Token，而不是团体个数。大型长会话团体可以使用硬约束，普通团体则只在评分中增加集中惩罚。

第一版调度策略应保持简单：

```text
1. 过滤非 Open、容量不足或逻辑帧超预算的 Scene
2. 优先降低长会话 Token 的倾斜
3. 再选择权威实体预留量较低的 Scene
4. 分数相同时使用稳定哈希决定
```

由于在线角色不做常规迁移，活动开始前的容量预测比运行中扩容更重要。新 Scene 即使启动，也只能接收后续入场玩家，无法立刻分担已在运行的长会话团体。

## ECS 保存状态，OOP 表达行为

混合 ECS 和 OOP 是可行的，但两者不能同时拥有同一份权威状态。

ECS 适合保存位置、移动、HP、MP、属性和公共状态。技能与 Buff 的规则可以使用 OOP 表达，运行时数据仍应保持可序列化：

```text
ECS：状态平面
  Transform、Attribute、Resource、PublicCombat

OOP：行为平面
  SkillDefinition、BuffDefinition、复杂规则

Effect / Modifier：两者之间的接口
```

技能和 Buff 规则只决定“应该发生什么”，通过 EffectCommand 和 ModifierCommand 提交修改，不能长期保存 ECS 内部指针，也不能绕过属性模块直接修改最终属性。

镜像实体只安装公共 ECS 数据。提升为权威实体时，再从对象池加载完整属性、技能和 Buff 运行时；降级时移除权威部分，保留稳定的实体槽和公共状态。

## 当前状态表加可覆盖的 Dirty Journal

场景间同步公共状态可以采用“状态表 + 变更日志”：

```text
SharedWorld
├── EntityDirectory
├── TransformTable
├── CombatTable
├── AppearanceTable
├── SceneChangeJournal[SceneCount]
└── SnapshotChunkPool
```

状态表保存每个实体的最新公共状态，是最终数据来源。Dirty Journal 只保存 `entityIndex`、`generation`、字段掩码和版本，用于通知其他 Scene 哪些槽发生了变化。消费者落后导致 Journal 被覆盖时，不要求生产者重放全部历史，而是重新扫描版本并读取当前状态。

这一组合可以参考几类成熟设计：

- [Linux Seqcount](https://docs.kernel.org/locking/seqlock.html) 的单写者版本校验适合保护无指针、可平凡复制的公共槽；
- [LMAX Disruptor](https://github.com/LMAX-Exchange/disruptor/blob/master/src/docs/asciidoc/en/disruptor.adoc) 的预分配 Ring、单调 Sequence 和批量消费适合 Dirty 通知；
- [Aeron IPC](https://github.com/aeron-io/aeron/wiki/Transport-Protocol-Specification) 的共享内存帧提交方式可以识别写到一半的记录；
- [Eclipse iceoryx](https://github.com/eclipse-iceoryx/iceoryx/wiki/Eclipse-iceoryx%E2%84%A2-in-1000-words) 的 Loan/Publish/Take 模式适合万人初始化快照和其他大型不可变批次。

这里不必完整引入所有框架。高频小型 Dirty 可以使用自定义单生产者广播 Ring，大型低频快照再使用共享内存 Chunk Pool。

新 Scene 启动时，先记录 Journal Tail，批量扫描当前状态表并建立本地空间索引，再消费扫描期间产生的 Dirty。追上当前 Tail 后才能从 `CatchingUp` 进入 `Open`。如果追赶期间发生 Ring 覆盖，则重新扫描，而不是带着不完整镜像开始接收玩家。

## 奖励、状态和位置不能走同一条数据路径

MMO 数据同时具有正确性和实时性两个维度。奖励比位置重要，但奖励晚几百毫秒通常可以接受；位置晚几百毫秒即使到达也已失去价值。

可以按语义分为五级：

| 等级 | 数据 | 处理方式 |
|---|---|---|
| 持久事实 | 奖励、货币、物品、任务完成 | 持久日志、幂等事务，不允许丢失或重复生效 |
| 权威事实 | 死亡、复活、所有权变化 | 热备日志和输入重放，不允许静默丢失 |
| 可收敛状态 | HP、MP、属性、动作 | 中间版本可以合并，最终读取权威状态表 |
| 瞬时状态 | 位置、速度、朝向 | 旧版本可丢，只保留最新值 |
| 表现事件 | 普通特效、声音、次要动作 | 过期后直接丢弃 |

这些等级不能只是在同一个队列中增加优先级字段。奖励队列、权威日志、状态 Journal、位置 Journal 和表现 Arena 应拥有独立容量及过载策略，否则位置更新可能先占满内存，让后来的奖励消息无处写入。

奖励还需要唯一事务 ID。系统允许 RewardIntent 重试，但持久化模块只能让同一个事务生效一次。位置则采用相反策略：不补发旧值，下一次绝对位置负责收敛。

## 避免构造、拷贝和分配成为主耗时

万人同屏会放大每一处小对象成本。高频路径应遵循几条约束：

- 战场启动时预分配实体槽、镜像槽、Ring 和对象池；
- Transform、公共战斗状态和 Dirty Record 使用无指针 POD；
- 高频数据按冷热拆分，位置变化不能复制整份角色状态；
- 同一实体一帧内多次变化只进入一次 Dirty List；
- 临时查询结果和批次使用 Frame Arena，在帧结束后整体回收；
- 跨进程引用使用共享内存 Offset 和 Generation，不能传原始指针；
- 公共数据批次只构建一次，按 Handle 和 Slice 交给后续模块；
- 高频消息使用枚举加定长 Payload，不为每条消息 `new` 一个多态对象。

目标不是宣传“完全零拷贝”，而是让每次变化只做必要写入，后续通过稳定槽、共享视图和批量 Handle 传播。迁移是低频操作，完整状态复制可以接受，不应为了消除一次迁移拷贝而拖慢所有逻辑帧。

## 镜像接管需要完整热备

普通镜像只有公共状态，不能在 Scene 崩溃后直接恢复技能冷却、Buff、未完成命令和私有数据。因此每个权威实体还需要一个完整热备影子：

```text
1 个 Authority
1 个 Hot Shadow
S-2 个普通 Mirror
```

热备不应集中在一个 Scene。某个 Scene 拥有的一千个实体，可以将热备分散到其他九个 Scene，避免故障后由单个进程瞬间接管全部负载。

接管流程是：Supervisor 停止旧路由、递增 `ownerEpoch`、热备补齐尚未提交的输入、本地镜像升级为权威实体，最后由 Gateway 将后续输入送到新 Scene。普通负载均衡不迁移在线角色，但故障接管必须保留这条路径。

## 先留下多维负载数据，再谈精确权重

现在没有真实活动数据，不能假设一组精确权重。第一版应保留多维原始向量：

```text
权威实体数、镜像数、团体数、长会话 Token
逻辑帧 P50/P95/P99
移动、属性、战斗、镜像、复制各阶段耗时
Dirty 数量、跨 Scene 消息量
队列深度和最旧消息年龄
进程内存、共享内存读写和热备落后帧数
```

初期用硬容量、权威实体数和长会话 Spread 做保守分配。上线后记录每次 Admission 的候选 Scene、过滤原因、最终选择和策略版本，再用真实的活动时长及运行成本离线重放其他策略。

未来策略可以先以影子模式运行：生产仍采用旧策略，新策略只记录“如果由我决定会选择哪个 Scene”。数据足够后再调整权重和 `Open/SoftClosed` 阈值。埋点和决策日志必须第一版就存在，具体模型可以后续校准。

这套方案最终依赖压测回答两个问题：单机在目标玩法下能承载多少权威计算，以及 Scene 增加到多少个之后，镜像和内存成本开始超过并行收益。在得到这些数据以前，它是一套可实现、可验证的架构设计，还不是已经证明的万人容量结论。
