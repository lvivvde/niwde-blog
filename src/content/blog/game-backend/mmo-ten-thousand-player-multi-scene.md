---
title: "万人同屏 MMO 的一种服务端拆分方案"
description: "用多逻辑场景、权威实体与镜像体拆分万人战场，并讨论 Linux 多进程、入场均衡、共享状态、ECS/OOP 和故障接管。"
pubDate: 2026-08-25
tags: ["MMO", "游戏后端", "C++", "ECS", "Linux", "共享内存"]
draft: false
---

万人集中活动时，系统需要同时处理角色运行归属、跨场景状态交换、进程故障接管，以及并行度提高后不断增长的镜像和通信成本。

这篇文章记录一套仍待实现和压测的设计：一张战场由多个逻辑 Scene 共同运行，每个玩家只有一个权威实体，同时在其他 Scene 中保留轻量镜像。Scene 部署在同一台 Linux 机器上，以多进程隔离故障，通过共享内存交换公共状态。正常游玩期间不因为负载迁移角色，均衡主要发生在玩家或团体入场时。

本文讨论服务端场景架构，不讨论客户端万人渲染，也不展开 QUIC 协议和技能系统的具体实现。

## 设计基线和开放项

这篇文章将方案分成三种状态，后续详细设计不能把暂定项当成已经验证的结论。

| 状态 | 内容 |
|---|---|
| 已确定 | 单权威写入、只读镜像、同机 Linux 多进程、常规均衡只发生在入场阶段、共享状态表配合 Dirty Journal、不同语义的数据使用独立通道 |
| 暂定 | 一个 Scene 对应一个进程和一个模拟线程、完整热备按实体分散、入场调度采用 Filter/Score/Reserve/Bind、跨 Scene 效果使用异步批次提交 |
| 待压测 | 单机玩家上限、Scene 数量、镜像字段集合、Ring 容量、完整热备频率、调度权重、各阶段延迟预算 |
| 延后设计 | 技能规则语言、QUIC Stream 分配、跨机器战场容灾和客户端万人渲染 |

无论实现怎样变化，都要保持三条不变量：同一实体在同一 `ownerEpoch` 下只有一个权威写入者；镜像不能直接提交最终状态；奖励和所有权变更不能依赖可覆盖的瞬时队列。

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

## 模块职责和最小接口

进程拆分以后，还要限制每个模块向外暴露的接口。Gateway 不理解战斗规则，Scene 不管理客户端连接，Supervisor 不进入每帧模拟。调用方只提交意图，顺序、版本校验、背压和恢复由接收模块处理。

| 模块 | 持有的状态 | 对外接口 |
|---|---|---|
| Gateway | QUIC 连接、会话、已确认输入序号、实体路由缓存 | `ForwardInput`、`InstallRoute`、`PublishClientEvent` |
| Supervisor | Scene 生命周期、租约、健康状态、接管事务 | `AdmitCohort`、`ChangeOwner`、`ReportSceneHealth` |
| Entity Router | `entityId → ownerSceneId + ownerEpoch` | `ResolveOwner`、`CommitOwner`、`WatchOwnerChange` |
| Scene Runtime | 权威实体、镜像、本地空间索引、逻辑帧和命令队列 | `SubmitInput`、`SubmitEffectBatch`、`PrepareTakeover` |
| Shared World | 公共状态槽、Directory、Dirty Journal、快照 Chunk | `ReadPublicState`、`PublishPublicState`、`PollDirty` |
| Durable Writer | 奖励、货币、物品和任务事务 | `CommitReward`、`QueryTransaction` |

这些名称表示逻辑模块，不要求每个模块都对应独立进程。Entity Router 可以由 Supervisor 管理，Shared World 也可以由各 Scene 映射同一块共享内存。接口还包括调用方必须遵守的约束：命令是否允许重复、是否要求顺序、满队列时怎样处理，以及结果能否晚到。

Gateway 只缓存路由，不成为所有权真源。发现 `ownerEpoch` 过期时，它重新查询 Entity Router，再更新本地缓存。Scene 之间也不能永久缓存目标归属；跨 Scene 命令携带发送方看到的目标 `ownerEpoch`，接收方用当前 Directory 拒绝旧路由。

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

调度请求至少包含以下信息：

```text
AdmissionRequest
  requestId
  activityId
  cohortId
  memberCount
  affinityKeys[]      // 队伍、家族、公会活动组
  estimatedCost
  durationClass
  requiredFeatures
```

队伍是不可拆分的硬约束。公会和家族属于亲和性来源，可以拆成多个活动 Cohort；调度器优先让同一 Cohort 聚合，再把高 `LongLoad Token` 的 Cohort 分散到不同 Scene。这样可以同时保留组队体验和长期负载离散度。

评分先使用可解释的线性模型：

```text
Score(scene, group)
  = Wframe    * FrameHeadroom
  + Wmemory   * MemoryHeadroom
  + Waffinity * AffinityGain
  - Wlong     * ProjectedLongLoadSkew
  - Wqueue    * QueueAgePenalty
  - Whotspot  * SpatialHotspotPenalty
```

第一版不需要猜出精确权重。Filter 负责挡住超出硬容量、帧预算或功能约束的 Scene；Score 只在合格候选中排序。相同输入、相同策略版本应得到稳定结果，分数相同时使用 `hash(cohortId, activityId)` 打散。

Reserve 创建带过期时间的 `PlacementLease`，原子增加预计人数、内存和 LongLoad Token。Bind 成功后将预留转成实际占用；超时、断线和重试使用同一个 `requestId`，撤销操作也必须幂等。每次决策记录候选集合、过滤原因、各维度分数、租约结果和策略版本，后续才能离线重放调度算法。

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

## 跨 Scene 交互提交有序效果批次

技能系统可以后置，场景架构仍需先定义一条稳定的交互接口。权威实体不接受“替我调用某个技能对象”这种远程调用，只接受可序列化、可校验的 `EffectBatch`：

```text
EffectBatch
  commandId
  sourceEntityId
  sourceOwnerEpoch
  skillCastId
  sourceTick
  deadlineTick
  targets[]
    targetEntityId
    expectedOwnerEpoch
    orderedEffects[]
      stageIndex
      effectType
      payload
```

`orderedEffects` 可以表达单目标、多目标和多阶段效果，例如“先加状态、再造成伤害、最后刷新另一个 Buff”。它只描述已经由施法者权威实体解析出的效果，不把技能对象、ECS 指针或脚本运行时传到另一个进程。

一次跨 Scene 交互按以下顺序执行：

```text
客户端输入
  → Gateway 根据路由发给施法者 Authority
  → 施法者 Authority 校验输入、资源、冷却和目标镜像
  → 按目标 ownerSceneId 拆分 EffectBatch
  → 目标 Authority 校验 ownerEpoch、免疫、死亡和本地状态
  → 在一个逻辑帧内按 stageIndex 提交效果
  → 写入公共状态并发布 Dirty
  → 异步返回 EffectResult
  → Gateway 向客户端确认或纠正表现
```

多目标技能不会获得跨多个 Scene 的全局原子性。每个目标由自己的 Authority 独立提交，结果可能部分成功。`commandId + targetEntityId` 构成幂等键，重试不能让同一目标重复受击；结果中保留成功、拒绝、过期和所有权已变化等状态。确实要求全局一致的玩法要进入单独的协调流程，不能占用普通战斗热路径。

目标 `ownerEpoch` 已变化时，接收方返回 `OwnerMoved`。发送方只在 `deadlineTick` 前根据新路由重试，过期后丢弃普通表现和位置相关效果；奖励或所有权变化转入不可丢失的事务通道。

## 延迟预算来自队列年龄和逻辑帧

跨进程通信不能采用“发送请求后阻塞等待目标 Scene 返回”的调用方式。每个 Scene 在固定阶段批量消费输入和 Effect Inbox，提交后继续当前帧，结果通过异步 Outbox 返回。共享内存降低传输时间，排队和错过帧阶段仍可能增加一个或多个逻辑帧。

端到端时间可以拆成：

```text
Ttotal
  = Tgateway
  + Qsource + Tsource
  + Troute
  + Qtarget + Ttarget
  + Tpublish
  + Toutbound
```

压测必须分别记录 `Qsource`、`Qtarget` 和最旧消息年龄。只看平均 IPC 延迟会掩盖 Scene 过载造成的手感问题。每个效果还带 `sourceTick` 和 `deadlineTick`，目标 Scene 不能让已经失去玩法意义的命令继续挤占队列。

客户端可以立即播放施法前摇、动作和不改变规则的本地反馈。命中、伤害、控制、资源消耗和死亡仍以服务端结果为准。服务端拒绝或修正时，客户端通过结果序号收敛。第一版需要为施法者本地命中、同 Scene 命中和跨 Scene 命中分别统计 P50、P95、P99，确认拆分没有把跨 Scene 目标系统性推迟多个逻辑帧。

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

共享记录至少包含以下版本信息：

```text
EntityDirectoryEntry
  entityId, entityIndex, generation
  ownerSceneId, ownerEpoch
  hotShadowSceneId

PublicSlotHeader
  generation, ownerEpoch
  writeSequence, publicVersion
  dirtyMask

DirtyRecord
  entityIndex, generation
  ownerEpoch, publicVersion
  dirtyMask
```

公共槽只允许当前 Authority 写入。写入者先把 `writeSequence` 变成奇数，写入 POD 字段，再以 release 顺序发布偶数序号；读取者使用 acquire 顺序读取并重试变化中的槽。记录里不能放跨进程原始指针，变长数据使用共享 Chunk Handle，并同时校验 Offset、Generation 和长度。

每个生产 Scene 使用独立的单生产者 Journal，避免多个进程争抢同一个写游标。消费端为每个 Journal 保存自己的 Sequence。Journal 满时覆盖旧 Dirty 通知，不覆盖状态表；消费者检测到序号断层后重新扫描相关分区。奖励、所有权事务和完整热备日志不能复用这种可覆盖机制。

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

每次变化只做必要写入，后续通过稳定槽、共享视图和批量 Handle 传播。迁移是低频操作，完整状态复制可以接受，不应为了消除一次迁移拷贝而拖慢所有逻辑帧。

## 镜像接管需要完整热备

普通镜像只有公共状态，不能在 Scene 崩溃后直接恢复技能冷却、Buff、未完成命令和私有数据。因此每个权威实体还需要一个完整热备影子：

```text
1 个 Authority
1 个 Hot Shadow
S-2 个普通 Mirror
```

热备不应集中在一个 Scene。某个 Scene 拥有的一千个实体，可以将热备分散到其他九个 Scene，避免故障后由单个进程瞬间接管全部负载。

接管流程是：Supervisor 停止旧路由、递增 `ownerEpoch`、热备补齐尚未提交的输入、本地镜像升级为权威实体，最后由 Gateway 将后续输入送到新 Scene。普通负载均衡不迁移在线角色，但故障接管必须保留这条路径。

每个 Scene 中的实体副本遵循同一套状态机：

```text
Absent
  → MirrorCatchingUp
  → Mirror
  → HotShadow
  → Promoting
  → Authority
  → Demoting
  → Mirror
  → Retired
```

`MirrorCatchingUp` 完成公共快照并追上 Dirty Tail 后才能进入 `Mirror`。`HotShadow` 在公共镜像之外保存完整检查点、已确认输入序号、技能冷却、Buff 和待提交命令。进入 `Promoting` 的前提是热备落后量没有超过接管上限，并且 Supervisor 已经为新所有者取得租约。

所有权切换分成四步：冻结旧路由；确认候选热备可接管；在 Entity Directory 中原子提交新的 `ownerSceneId + ownerEpoch`；安装 Gateway 新路由。目录提交是生效点。旧 Authority 即使继续运行，它携带的旧 `ownerEpoch` 也无法写入公共槽或提交权威事务。

计划迁移可以等待旧 Authority 刷新检查点。崩溃接管无法等待旧进程，需要从最近检查点和输入日志恢复。恢复窗口内允许丢失哪些瞬时表现、必须重放哪些输入、怎样处理已经发出但尚未确认的效果，都要由数据等级决定。

| 故障 | 检测与处理 | 剩余风险 |
|---|---|---|
| Scene 进程退出 | Supervisor 发现 pidfd/心跳失效，隔离旧路由并提升分散热备 | 热备落后会增加回放量和接管时间 |
| Scene 卡死 | 逻辑帧心跳超时后 fencing，禁止旧 epoch 继续提交 | 超时阈值过短会误判长帧 |
| Dirty Journal 覆盖 | 消费者发现 Sequence 断层，重新扫描公共状态 | 重扫期间镜像延迟增大 |
| 热备落后超限 | 停止将新玩家分配给原 Scene，尝试补齐或降级玩法 | 无健康热备时无法无缝接管完整战斗状态 |
| Supervisor 重启 | 从 Directory、Scene 租约和持久日志恢复控制状态 | 恢复期间暂停所有权变更和新 Admission |
| 共享内存损坏、主机 OOM 或宕机 | 终止整张战场并从跨机检查点恢复 | 当前方案没有解决整机级无缝容灾 |

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

## 用容量工作表约束实现

成本公式还需要展开成可以填写的容量工作表。第一版原型至少测量这些输入：

```text
P             玩家数
S             Scene 数
F             逻辑帧频率
Ma            单个 Authority 常驻内存
Mm            单个 Mirror 常驻内存
Mh            单个 Hot Shadow 常驻内存
Rd            每秒发生公共变化的实体数
Bd            单条 Dirty Record 字节数
Fd            每条变化的平均消费 Scene 数
Re            每秒跨 Scene Effect 数
Be            单个 EffectBatch 平均字节数
```

内存下界可以先按下面的式子估算：

```text
Mtotal
  ≈ P*Ma
  + P*(S-1)*Mm
  + P*Mh
  + Mrings
  + Msnapshots
  + Mindexes
  + Mheadroom
```

Dirty 通知产生的最低写入流量约为 `Rd * Bd`，消费和状态读取成本还会随 `Fd` 增长。每个 Scene 的镜像空间索引包含接近 `P - P/S` 个对象，通常不能忽略。最终容量受最慢 Scene 的逻辑帧时间、内存带宽和 LLC Miss 限制，不由总 CPU 使用率单独决定。

压测矩阵至少覆盖：

- `P` 与 `S` 的组合，以及玩家在空间中均匀、局部聚集和全体聚集三种分布；
- 移动密集、技能密集、Buff 密集、奖励爆发和混合负载；
- 同 Scene 与跨 Scene 目标比例；
- 一个 Scene 崩溃、卡死、恢复和热备落后；
- Dirty Ring 覆盖、Effect Inbox 满、Reward 通道变慢和 Snapshot Pool 耗尽；
- 单 NUMA 节点与跨 NUMA 放置。

## 验收标准在压测前填写

项目可以先用符号表示尚未确定的预算，但测试开始前必须给出数值：

| 预算 | 验收条件 |
|---|---|
| `Bframe` | 满载时各 Scene 逻辑帧 P99 不超过预算，且没有持续积压 |
| `Beffect` | 跨 Scene Effect 的 P99 和最旧队列年龄不超过玩法预算 |
| `Btakeover` | 单 Scene 退出后在预算内完成 fencing、热备提升和路由切换 |
| `BshadowLag` | 正常运行时完整热备落后量保持在可回放窗口内 |
| `Bmemory` | Authority、Mirror、Hot Shadow、Ring、快照和索引总和留有故障接管余量 |
| 正确性 | 压测中没有双 Authority 写入、奖励重复、奖励丢失或旧 epoch 覆盖新状态 |
| 降级 | 瞬时通道过载时可以丢位置和表现旧值，不阻塞奖励与所有权事务 |

第一阶段原型不需要实现完整 MMO。实现移动、一个单目标效果、一个跨 Scene 多目标效果、一个可叠加 Buff、一次奖励提交和一次 Scene 崩溃接管，就可以验证主要接口。原型通过后再扩展技能规则和跨机器容灾，避免把未经验证的场景模型埋进完整玩法系统。

这套方案最终依赖压测回答两个问题：单机在目标玩法下能承载多少权威计算，以及 Scene 增加到多少个之后，镜像和内存成本开始超过并行收益。在得到这些数据以前，它是一套可实现、可验证的架构设计，还不是已经证明的万人容量结论。
