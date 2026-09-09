# 上下文工程与 Code Review Graph MCP：资料核验与课程定位

> 核验日期：2026-09-10。本文优先引用项目维护者的仓库、包元数据、协议文档和 Git 官方文档。工具版本与功能变化较快，授课前应复查链接和安装命令。

## 结论先行

1. 课程中所说的 “Code Review Graph MCP” 最可能指开源项目和 PyPI 包 [`code-review-graph`](https://pypi.org/project/code-review-graph/)，维护仓库为 [`tirth8205/code-review-graph`](https://github.com/tirth8205/code-review-graph)。项目正式名称是小写连字符形式 **`code-review-graph`**，MCP server 配置名也是 `code-review-graph`；“Code Review Graph MCP”适合作为口语称呼，不应暗示它是 MCP 官方或某家模型厂商的官方产品。
2. 它的价值不是“把整个仓库塞给 AI”，而是把当前代码解析成可查询的结构图，先找出调用者、依赖、相关测试和受影响执行流，再让 AI 只读取完成任务所需的源文件。这与上下文工程“选择最小的高信号上下文”的原则一致。
3. 它应被讲成**上下文发现与缩小范围的工具案例**，不是事实裁判。图谱是基于 Tree-sitter 的静态、启发式索引；结论仍需回到实际源码、编译器/LSP、可执行测试以及 Git/ADR/Issue/PR 历史核实。
4. 不建议在课程中复述未经限定的“65 倍节省”或“100% 召回”。项目自己说明：token 基线是“读取整个语料库”，不是熟练的 agentic grep；其 1.0 recall 使用由同一图生成的 ground truth，存在循环性，只能视为上界。

## 一、产品身份：能确认什么，哪里仍有歧义

### 最强匹配

以下一手信息共同指向 `tirth8205/code-review-graph`：

- PyPI 的正式包名是 [`code-review-graph`](https://pypi.org/project/code-review-graph/)，项目链接回到 `tirth8205/code-review-graph`，维护者为 `tirth8205`；截至核验日，PyPI 最新版本为 2.3.8，标记为 Beta、MIT License、要求 Python 3.10 以上。
- 仓库自己的 [`.mcp.json`](https://github.com/tirth8205/code-review-graph/blob/main/.mcp.json) 把 MCP server 命名为 `code-review-graph`，通过 `uvx code-review-graph serve` 启动。
- 项目 [`pyproject.toml`](https://github.com/tirth8205/code-review-graph/blob/main/pyproject.toml) 将包描述为“通过 MCP 与 CLI 提供 token-efficient code review 的 local-first knowledge graph”，并把 Homepage、Documentation、Repository 和 Issues 指向同一维护链路。

因此，课程页面应使用：

> **code-review-graph（一个通过 MCP/CLI 暴露的本地代码结构图工具）**

而不是：

> “官方 Code Review Graph MCP”或“上下文工程 MCP”。

### 名称歧义

公开网络上至少还有两个容易混淆的同名或近名项目：

- [`n24q02m/better-code-review-graph`](https://github.com/n24q02m/better-code-review-graph) 明确自称是上游 `code-review-graph` 的 fork，包名、命令、许可证和能力已有分化。
- [`Echelon-X/code-review-graph`](https://github.com/Echelon-X/code-review-graph) 使用同名代码和相同安装文案，但 PyPI 的项目链接及包元数据并不指向它。

若讲师实际安装的是 `better-code-review-graph` 或其他 fork，应按它自己的文档改名并重新核验；不要把不同 fork 的能力、benchmark 或安装命令混在一起。

## 二、它实际做什么

项目的 [README](https://github.com/tirth8205/code-review-graph#how-it-works) 描述的核心管线是：

```text
仓库源码
  → Tree-sitter / 定向解析
  → 本地 SQLite 结构图
  → 调用、导入、继承、测试等关系查询
  → 影响范围 / review context
  → AI 再读取被选中的真实源码
```

主要能力可以按课程问题来讲：

| 课程中的问题 | 工具提供的结构信号 | 对应接口示例 |
| --- | --- | --- |
| “改这里会波及哪里？” | 调用者、依赖者、相关测试、受影响执行流 | `get_impact_radius_tool`、`detect_changes_tool` |
| “谁调用它？它又调用谁？” | caller/callee 与可限制深度的图遍历 | `query_graph_tool`、`traverse_graph_tool` |
| “应该先读哪些文件？” | 压缩后的最小上下文和 review context | `get_minimal_context_tool`、`get_review_context_tool` |
| “哪些测试可能相关？” | `TESTED_BY` 等解析或约定推断出的关系 | `query_graph(pattern="tests_for")` |
| “整体模块结构和风险热点？” | community、hub、bridge、耦合和执行流 | architecture/community/hub/bridge 系列工具 |

完整的 MCP 工具清单和 CLI 命令以项目 [README 的工具表](https://github.com/tirth8205/code-review-graph#30-mcp-tools)与[使用指南](https://github.com/tirth8205/code-review-graph/blob/main/docs/USAGE.md)为准。

### 它与 MCP 的关系

[Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) 是把 AI 应用连接到外部工具和数据源的开放协议。`code-review-graph` 是一个第三方 MCP server 实现：MCP 负责“让 agent 调用这些图查询工具”，代码图的构建、存储和查询逻辑来自该项目本身。MCP 不是图算法，也不会自动保证返回内容正确。

## 三、访问方式、数据边界与维护成本

### 使用与授权模型

- **核心是免费开源、本地运行**：MIT License；通过 PyPI 安装，核心工作流不要求 SaaS 账号或 API key。参见 [PyPI 项目页](https://pypi.org/project/code-review-graph/)与[项目安全模型](https://github.com/tirth8205/code-review-graph/blob/main/SECURITY.md#security-model)。
- **安装入口**：`pip install code-review-graph`（或 `pipx`），再运行 `code-review-graph install` 和 `code-review-graph build`。官方使用指南列出了 Codex、Claude Code、Cursor、Qoder 等不同客户端的配置位置；不要把某一客户端的配置复制给所有人。参见 [Installation](https://github.com/tirth8205/code-review-graph/blob/main/docs/USAGE.md#installation)。
- **本地数据**：默认图数据库位于仓库 `.code-review-graph/graph.db`；常规 build/review/search/MCP 流程不发起网络请求，server 通过 stdio 或绑定 localhost 的 HTTP 工作。参见 [Security Policy](https://github.com/tirth8205/code-review-graph/blob/main/SECURITY.md#threat-surface)。
- **可选网络外传**：本地 embedding 首次会下载模型；显式配置云 embedding 时会把用于 embedding 的文本发给提供商。当前 README 说明该文本包含标识符、签名、结构上下文和有限的文档摘要，不包含函数体；企业环境仍应按代码敏感级别和具体版本重新审批。参见 [README 的 embedding 说明](https://github.com/tirth8205/code-review-graph#configuration)。
- **成熟度**：截至核验日，PyPI 将 2.3.8 标为 Beta；应把它当作快速演进的工程工具，而非稳定标准。

### 运维前提

图不是一次构建后永久可信。代码变化后要通过 hooks、watch mode 或 `update` 增量更新；若怀疑过期，可用 `code-review-graph status` 和 `code-review-graph update --brief` 检查。官方 [FAQ 的验证步骤](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md#how-do-i-verify-it-is-working)给出了状态、变更检测和 MCP 连接的检查方法。

## 四、能力边界：哪些话可以讲，哪些话不能讲

### 1. 图谱是索引，不是源代码事实本身

项目基于 Tree-sitter AST 与启发式解析跨语言关系，并非每种语言的编译器前端。其维护者明确说明：动态派发、元编程和 duck typing 会产生推断或歧义边；若要单一语言内语义精确、近乎完备的定义/引用关系，LSP 更合适。参见 [官方 FAQ：CRG 与 LSP](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md#how-is-this-different-from-lsp-and-language-servers)。

课程表述建议：

> 图谱先告诉 AI “值得读哪里”；AI 再以源码、类型系统和运行结果确认“实际发生什么”。

### 2. “找到相关测试”不等于“已有充分覆盖”

`tests_for` 使用解析出的关系加命名约定映射测试，并可以把相关测试加入变更上下文；这是**候选测试发现**。它没有因此证明断言正确、边界齐全或测试真实通过。后两者必须由阅读测试与实际执行测试完成。这是根据[官方 FAQ 对 `tests_for` 的实现描述](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md#why-not-just-grep)作出的范围推论。

### 3. 不替代 Git 历史与决策记录

`detect-changes` 可以把某个 Git diff 映射到结构影响，graph snapshot 也可比较结构变化；但当前官方工具清单没有把“为什么这样设计”、讨论过程或 ADR/Issue/PR 结论建模为一等事实。因此：

- 用 [`git log`](https://git-scm.com/docs/git-log) 按路径、提交范围或文本变化查演化；
- 用 [`git blame`](https://git-scm.com/docs/git-blame.html) 找到某行最后一次变更，再回到对应提交理解上下文；
- 用仓库内 ADR、Issue、PR 和设计文档查“为什么”。

不要把 `git blame` 教成“找责任人”；应把它教成“找到相关提交的入口”。Git 官方文档也提醒，blame 只标注当前存在的行，删除或替换过的内容要结合 diff/log 搜索。

### 4. benchmark 不能当成普遍承诺

项目 [README 的 Limitations](https://github.com/tirth8205/code-review-graph#limitations-and-known-weaknesses)主动列出：

- 1.0 impact recall 使用 graph-derived ground truth，循环地依赖同一图，只是上界；
- 小型单文件变更时，结构元数据可能比直接读取源码更贵；
- 搜索排序与部分语言的 flow detection 有已知弱点；
- 保守的影响分析会带来 false positive。

官方 [FAQ](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md#why-not-just-grep)还说明，约 65 倍的 token reduction 是“全仓语料”与图查询的比较，而不是与熟练的 grep + 定向读取比较。适合课程的严谨说法是：

> 在大仓库和多跳影响分析中，结构图有机会显著减少重复检索和无关上下文；收益取决于仓库、语言、问题形状和索引新鲜度，应现场测量。

### 5. 有些场景直接搜索更简单

官方 [When should I not use it?](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md#when-should-i-not-use-it) 不建议把它当万能入口：几百文件以下的小仓库、单文件琐碎修改、一次性问题，直接 grep/文件导航的成本可能更低；当前 JS/Go 的执行流检测也有明确限制。

## 五、放回“上下文工程”的通用框架

Anthropic 的一手文章 [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 给出了适合课程的总原则：上下文工程不是只写一段 prompt，而是持续选择和维护推理时进入窗口的全部信息；好的上下文应是“足够完整的最小高信号集合”。文章还推荐 just-in-time retrieval：先保留文件路径、查询和链接等轻量引用，再按任务逐步载入材料。

据此，代码任务的上下文不应等同于“代码文件越多越好”，而应分层组合：

| 层次 | 要回答的问题 | 常见来源 | CRG 的角色 |
| --- | --- | --- | --- |
| 目标上下文 | 为什么做、什么算成功、边界是什么？ | Goal Brief、Issue/Spec、验收标准 | 不提供；必须由人和任务资料给出 |
| 结构上下文 | 改动点与哪些调用者、依赖、测试、流程相连？ | 代码图、LSP、grep、目录结构 | 强项：快速生成候选阅读范围 |
| 行为上下文 | 代码当前真实做什么？ | 源码、配置、schema、运行日志 | 只提供导航/片段；最终读源码和运行系统 |
| 验证上下文 | 怎样证伪或确认修改？ | 单元测试、集成测试、类型检查、监控 | 找候选测试和 gap；不代替执行与判断 |
| 历史/决策上下文 | 为什么形成当前结构？哪些约束仍有效？ | Git log/blame、ADR、Issue、PR、团队文档 | 当前不是完整解决方案；需要并行检索 |

这张表应成为上下文工程章节的核心：**工具只覆盖其中一层或几层；上下文工程是选择、验证、组合这些层。**

## 六、推荐的授课呈现

### 核心论点

建议把本节标题写成：

> **上下文工程：不是把仓库全给 AI，而是让它逐层找到最相关的证据**

三句话完成概念与案例的分离：

1. 通用原则：上下文是有限的注意力预算，目标是最小但充分的高信号证据。
2. 工具案例：`code-review-graph` 预计算结构关系，擅长为多跳问题缩小候选阅读范围。
3. 必要护栏：回读源码、运行测试、核对历史；索引过期或关系不精确时切换 LSP/grep/Git。

### 适合投屏的演示流程

用语言无关的“活动奖励领取”需求，只展示决策过程，不要求学员编码：

```text
Goal Brief：重复请求不能重复发奖
      ↓
图查询：领取入口 → 幂等模块 → 存储调用 → 调用者 → 相关测试
      ↓
选择 3–6 个高信号文件，而不是打开整个仓库
      ↓
回读源码与配置，确认图中的边
      ↓
Git / ADR / Issue：为什么幂等键由这一层负责？
      ↓
运行单元 + 集成测试，形成可交付证据
```

现场互动可以让同事在三个候选集合中判断“下一步应该加载哪些上下文”，而不是安装工具或写代码。

### 一页“何时用 / 何时不用”

**优先尝试图查询**：大型或陌生仓库、跨模块改动、需要 callers-of-callers、依赖影响、测试关联、PR 风险扫描。

**优先用其他方法**：

- 精确符号语义、重载/动态分派判断 → 编译器或 LSP；
- 小仓库、单跳定义、一次性问题 → grep / 文件导航；
- 真实业务行为 → 源码、运行日志和可执行测试；
- 设计动机与约束 → Git、ADR、Issue、PR；
- 图过期 → 先 update/status，不能直接相信旧结果。

## 七、可直接放进 HTML 的资料卡

1. **[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)**  
   支撑观点：上下文工程是持续策划完整上下文状态；目标是最小、充分、高信号，并按需逐步检索。

2. **[`code-review-graph` 官方仓库](https://github.com/tirth8205/code-review-graph)**  
   支撑观点：用 Tree-sitter 建立持久结构图，通过调用、依赖、测试和影响范围缩小 AI 需要读取的代码。

3. **[`code-review-graph` Usage](https://github.com/tirth8205/code-review-graph/blob/main/docs/USAGE.md)**  
   支撑观点：安装方式、客户端支持、日常 review 流程、索引内容与更新方法。

4. **[`code-review-graph` FAQ](https://github.com/tirth8205/code-review-graph/blob/main/docs/FAQ.md)**  
   支撑观点：与 LSP、grep、RAG 的边界；适用/不适用场景；隐私与 benchmark 的限定。

5. **[`code-review-graph` Security Policy](https://github.com/tirth8205/code-review-graph/blob/main/SECURITY.md)**  
   支撑观点：默认 local-first 的运行与存储边界，以及可选网络调用的风险面。

6. **[Model Context Protocol：Introduction](https://modelcontextprotocol.io/docs/getting-started/intro)**  
   支撑观点：MCP 是 AI 应用连接外部工具和数据源的协议；它与具体代码图产品不是同一个概念。

7. **[`git log` 官方文档](https://git-scm.com/docs/git-log)** 与 **[`git blame` 官方文档](https://git-scm.com/docs/git-blame.html)**  
   支撑观点：结构关系之外，还需从提交和行演化追溯代码历史；blame 是定位相关提交的入口，不是完整因果解释。

## 八、最终建议

将 `code-review-graph` 保留为课程中的重点演示工具，但给它一个明确、有限的承诺：

> 它帮助 AI 更快回答“我接下来应该读什么”，尤其适合大仓库的多跳结构问题；它不替你回答“代码一定怎么运行”“测试一定够不够”或“当初为什么这么设计”。

这样既能呈现讲师真实使用的工具，也能让课程在工具改名、fork 分化、语言支持变化或团队无法安装 MCP 时依然成立：学员带走的是“按目标逐层发现、验证并压缩上下文”的方法，而不是对单一产品的依赖。
