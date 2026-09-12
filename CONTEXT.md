# Niwde Technical Blog

This context defines the shared language for Niwde's Chinese technical blog. The blog contains long-form engineering articles and may also host focused learning artifacts such as the AI programming course site.

## Language

**技术博客（Technical Blog）**:
面向研发读者发布可复现工程经验、技术推导与实验结果的中文静态网站；文章按主题栏目组织。
_Avoid_: AI 编程课程网站、个人动态页、在线学习平台

**游戏后端栏目（Game Backend Category）**:
技术博客中记录游戏服务端设计、算法与工程实践的文章集合。
_Avoid_: 单个游戏项目、客户端玩法攻略

**AI 编程课程（AI Programming Course）**:
一门面向公司研发同事的 90 分钟现场课程，帮助学员建立可重复的 AI 辅助软件开发方法。
_Avoid_: AI 科普课、提示词技巧合集

**研发学员（Engineering Learner）**:
具备 Git、测试和 Code Review 基础，但 AI 编程熟练度可能不同的公司研发同事。
_Avoid_: 普通用户、零基础学员

**课程网站（Course Site）**:
技术博客承载的独立学习页面，用于现场投屏教学、同时可供课后查阅；保留英文标准术语和资料原名，并支持离线打开。
_Avoid_: 常规博客文章、纯幻灯片、在线学习平台

**反馈循环工程（Feedback Loop Engineering）**:
通过短而可信的验证回路，让 AI 的每次修改都能被测试、检查和评审快速证伪或确认的开发方法。
_Avoid_: 循环语句、工作流编排、只写测试

**无关禁止指令（Irrelevant Prohibition）**:
与当前目标和必要约束无关、却把不希望出现的概念引入 AI 上下文的否定性提示内容。
_Avoid_: 必要约束、安全护栏、兼容性要求

**AI 编程工作流（AI Programming Workflow）**:
课程采用的端到端协作主线：需求对齐、表达目标、获取上下文、设计验证、TDD 实现、集成验证与 Code Review。
_Avoid_: AI 工具清单、提示词技巧合集

**目标简报（Goal Brief）**:
人和 AI 在编码前共同确认的任务依据，只描述目标、可观察的成功标准、必须保持的约束、范围边界与当前未知项。
_Avoid_: 逐文件修改清单、逐行实现方案、一次性聊天提示词

**验证计划（Verification Plan）**:
把 Goal Brief 的成功标准映射为测试、构建、静态检查、真实边界验证和人工观察证据的共同工作件。
_Avoid_: 固定测试比例、传统 QA 长文、只追求覆盖率

**交付证据链（Delivery Evidence Chain）**:
由 Goal Brief、验证计划和 Code Review 依次形成的连续记录，用目标、验证方法和实际证据共同判断 AI 代码是否可交付。
_Avoid_: 三个互不相关的提示词、测试全绿即自动批准

**课程检查点（Course Checkpoint）**:
AI 编程工作流中的七个连续阶段：需求对齐、表达目标、获取上下文、设计验证、TDD 实现、集成验证和 Code Review。
_Avoid_: 彼此独立的工具章节、必须由学员现场操作的实验步骤

**五拍讲解（Five-beat Teaching Pattern）**:
每个知识点依次采用“一句话观点、常见误区、贯穿示例、操作原则、来源与边界”的固定讲解节拍。
_Avoid_: 资料堆砌、只有结论没有示例、长篇论文解读

**证据卡（Evidence Card）**:
课程主屏中把一个核心论点连接到经典来源的简短入口；详细摘要、证据等级和适用边界收纳在折叠区。
_Avoid_: 论文综述、无来源权威断言、只列链接不说明用途

**我的实际做法（My Practice Card）**:
在课程检查点中呈现讲师本人已确认工作方法的第一人称卡片；没有真实经历支持的故事不得虚构。
_Avoid_: 通用建议冒充个人经历、虚构事故复盘

**讲师备注（Speaker Notes）**:
辅助现场表达的“关键句、3–5 个提示点、过渡句与证据边界”，不是要求照读的完整逐字稿。
_Avoid_: 主屏正文、完整演讲脚本、未经限定的研究结论

**内容裁剪等级（Content Priority）**:
课程内容的 `Core` 或 `Optional` 标记；现场超时时只能优先裁剪 Optional，不得破坏端到端工作流的核心论点。
_Avoid_: 临场随意跳过核心步骤、所有资料同等重要

**贯穿示例（Through-line Example）**:
以“活动奖励领取”为主题、用于串联需求、上下文、测试、模块设计与评审环节的游戏后端通用场景；使用语言无关的伪代码和测试表格。
_Avoid_: TypeScript 教程、生产代码复刻、彼此无关的代码片段

**活动奖励领取（Event Reward Claim）**:
贯穿示例中的业务能力：满足活动资格的玩家对同一活动只能成功领取一次奖励，并可在重复请求后获得明确且一致的结果。
_Avoid_: 完整奖励平台、活动配置系统、背包系统教程

**已领取（Claimed）**:
活动奖励领取已经完成的稳定最终结果；重复或并发请求返回同一个结果与奖励引用。
_Avoid_: 重复领取错误、每次请求生成的新结果

**不具备资格（Ineligible）**:
权威资格来源判定玩家当前不能领取，并附带可解释原因的最终结果。
_Avoid_: 系统失败、结果未知

**稍后重试（RetryLater）**:
领取结果暂时无法确认、但调用方可以安全重试的非最终结果。
_Avoid_: 已失败、重新发放奖励

**安全重试（Safe Retry）**:
在结果未知或请求重复时再次发起领取，最终仍收敛到同一个结果且不会重复发放奖励。
_Avoid_: 盲目重放、重复发奖

**讲师引导互动（Instructor-led Interaction）**:
由讲师操作课程网站，通过口头选择、讨论和问答让学员参与，但不要求学员编码、安装工具或修改文件。
_Avoid_: 上机实验、现场结对编程、课后作业平台
