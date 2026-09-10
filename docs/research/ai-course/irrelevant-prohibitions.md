# “无关禁止指令”的证据边界与课程表述

> 研究问题：把与任务无关的否定性概念写进提示词，是否会提高该概念的显著性，或使模型输出向被禁止的概念偏移？“J-space”是不是可采用的科学术语？
>
> 检索与核验日期：2026-09-10

## 结论先行

课程可以讲这条实践原则，但不能讲成一条普适的模型定律：

> **先直接说明你希望 AI 达成的目标、成功标准和输出形态。不要用一长串与任务无关的“不要……”来描摹结果；它们会给上下文增加噪声，还可能让被点名的概念变得更显著。真正重要的安全、兼容性和数据边界仍要明确保留，并尽可能补上希望 AI 采取的替代行为。**

目前最贴近该主张的证据来自四条彼此不同、不能混为一谈的线索：

1. Anthropic 在 Claude 模型内部定义并测量了 **J-space**。在其思想抑制实验中，仅仅点名某概念就会使它进入 J-space；“不要想 X”对这种激活的抑制很弱，而把 X 明确标记为“与任务无关”更有效。但实验中的模型仍能正确抄写规定文本，因此该研究证明的是**内部表征的显著性**，不是“最终输出必然被污染”。[^gurnee]
2. 一个尚未同行评审的跨模型预印本在九个开放模型上发现，`do not mention X` 可能提高 X 的后续 token 概率；效应随模型和上下文负载变化，且 GPT-OSS-20B 是明显反例。研究只测了合成英文提示中的单 token 概率，而非真实对话中的完整生成。[^mann]
3. 同行评审研究已经可靠证明：**无关上下文本身会干扰 LLM**；但同一研究也发现，明确要求模型忽略无关信息能缓解干扰。这反驳了“所有否定式指令都不该用”的绝对说法。[^shi]
4. 同样重要的反证来自 2025 年 *Nature*：在阻止模型执行作弊请求的六种护栏中，放在用户提示末尾的、强而具体的任务相关禁止项最有效。这说明**关键护栏不能为了追求“全正向措辞”而删除**。[^kobis]

所以，课堂上应把它讲成“减少无关负向概念、优先正向描述目标”的**稳健实践**，而不是“AI 像人一样，听到不要想橘子就一定会画出橘子味的苹果”的已证实机制。

## “J-space”到底是什么

`J-space` 是一个真实、有精确定义、但很新的术语。它由 Anthropic 研究者在 2026 年的 *Verbalizable Representations Form a Global Workspace in Language Models* 中提出，指由 Jacobian lens（J-lens）向量构成的模型表征空间子成分；这些向量刻画某个内部激活对模型未来说出某个 token 的平均线性影响。作者把这些向量的集合称为 J-space，并论证它具有可报告、可定向调节、参与内部推理、可灵活复用和容量有限等“全局工作空间”式功能。[^gurnee]

准确边界是：

- 可以说：**“Anthropic 的研究团队在其测试的 Claude 4.5/4.6 模型中，用 J-lens 识别出一个被称为 J-space 的内部表征子空间。”** 论文默认在 Claude Sonnet 4.5 上实验，并用 Haiku 4.5、Opus 4.5 和部分 Opus 4.6 实验交叉验证关键结果。[^gurnee]
- 不应说：**“所有 AI 都有同一种 J-space。”** 这篇研究主要考察同一模型家族；J-lens 本身也只能近似、且不完整地读取内部表征，尤其受限于单 token 概念。[^gurnee]
- 不应把 J-space 当成 `latent space`（潜在空间）的同义词。前者是一个按特定 Jacobian 方法定义出来的子空间，后者是泛指模型内部高维表征的宽泛术语。
- 这是一篇公开的第一方原始研究与可复现实验，不是长期形成的教科书共识；截至本次检索，论文没有声明经过同行评审。课程页面宜标注“2026 年新研究”。

### 与本课最相关的 J-space 实验

研究者让模型一边抄写一段无关句子，一边接受不同的概念指令，然后读取抄写过程中的 J-space：

- `think about X`：目标概念经常进入 J-space；
- 只在提示中 `mention X`：在类别和算术任务中，激活率已经接近 `think about X`；
- `whatever you do, do not think about X`：目标概念仍大致停留在单纯提及时的水平；
- `X is irrelevant to this task`：比单纯提及和 `don't think` 更能压低目标概念的 J-space 激活。

这项结果直接支持一个很窄的说法：**点名一个被禁止概念，本身就可能使该概念进入模型可报告、可用于推理的内部表征。** 它不支持下面这些扩大解释：

- 被激活的概念一定会出现在最终文本；
- 被激活的概念一定会使生成物在语义或风格上向它偏移；
- 所有模型、语言、任务和提示长度都有同样的效应。

事实上，在论文的思想抑制实验里，基础模型和后训练模型都把指定句子抄写正确，表面文本在各条件间完全一致。研究者还明确说 J-lens 是不完整的近似工具。[^gurnee]

同一论文还有一个容易被忽略的反向因果结果：当上下文已经暗示了某个概念，而任务要求模型不要说出它时，消融早期 J-space 中该概念的方向，反而使回避失败率提高约五倍。作者据此推断，模型可能需要先在早期 J-space 表示这个概念，才能主动抑制它。[^gurnee] 因此，“被禁止概念出现在内部表征中”本身既可能是干扰，也可能是成功执行禁令所需的一步；只看激活不能判断最终效果。

## 四类证据必须分开讲

### 1. LLM 的直接行为证据

#### 禁止词在完整生成之外的“可控性”有限

OpenAI 等研究者在 2026 年发布 CoT-Control：把 13,000 多个推理任务与“推理时不要使用某个任务相关关键词”等指令配对，测试 13 个推理模型。当前前沿模型控制其 chain of thought 的成功率为 0.1%–15.4%；论文给出的一个对比是 Claude Sonnet 4.5 对 CoT 的控制率为 2.7%，对最终输出的控制率为 61.9%。[^cot]

这说明“禁止提及任务所需概念”很难约束模型的中间推理，但它研究的是**推理轨迹的可监控性**，不是普通提示词的最终回答质量。它也再次提醒：内部过程和最终输出不能当成同一个测量对象。

#### `do not mention X` 的 token 概率可能反弹，但现有证据仍是初步的

Mann 等人的 ReboundBench 用 5,000 个合成英文提示测试九个开放模型。在 `do not mention X` 后插入不同长度和类型的干扰文本，再比较 X 的 token 概率。多数模型出现不同程度的“反弹”，但强度与持续时间因模型而异，GPT-OSS-20B 几乎没有或呈负反弹。[^mann]

这项结果和课程论点方向一致，却不足以支持普遍结论，因为：

- 它是 arXiv v1 预印本，未显示同行评审；
- 提示是合成模板，只有英文和单 token 目标；
- 核心测量是下一 token 的 log-probability，而非完整文本生成；
- 模型间差异大，且存在反例；
- 作者自己要求未来在自然对话、多词目标和完整生成上复验。

#### 无关上下文确实会干扰，但“忽略它”有时有效

Shi 等人在 ICML 2023 的同行评审论文中构建 GSM-IC，在小学数学题里加入无关信息，发现多种 LLM 会被干扰；在原本能答对的题目中，不超过 18% 能在各种无关信息条件下持续答对。作者也发现，加入“忽略无关信息”的指令可以缓解这一问题。[^shi]

它直接支持“不要塞入无关信息”，却不支持“不要使用任何否定句”。相反，它表明**与任务直接相关、作用清楚的排除指令**可能有帮助。

#### 任务相关的强禁止项可以成为有效护栏

Köbis 等人在 *Nature* 2025 的同行评审研究中，让 GPT-4、GPT-4o、Claude 3.5 Sonnet 和 Llama 3.3 面对作弊请求，并比较六种通用、任务具体和明确禁止式护栏。跨模型总体最有效的是追加在用户提示末尾的强任务禁止项（例如绝不允许错误报告掷骰结果）；它显著降低了模型服从作弊请求的概率，尽管并未在所有模型上完全消除违规。[^kobis]

这是一条重要反证：本课原则绝不能简化成“不要对 AI 说不要”。更准确的切分是：

- **无关、堆砌、只描摹坏结果的禁令**：删掉或改写；
- **直接决定正确性、安全、隐私和兼容性的硬边界**：保留、写具体、给出替代行为，并用测试验证。

#### 邻近证据不等于本题证据

同行评审的 NLP 研究表明，语言模型在事实否定、自然语言推理或否定问句上会出现特定错误，例如 *Strong Hallucinations from Negation and How to Fix Them*。[^ashern]

这些研究说明“处理否定”并非已解决的能力，但研究的是逻辑/语义否定，不是“不要生成 X”的提示策略，因此不能用来直接证明本课主张。

### 2. 机制与潜在表征解释

可以采用的机制层表述是：

> 为了理解“不要提 X”，模型必须先表示 X 及其与否定词的关系。Anthropic 的 J-space 研究确实观察到，被点名但要求忽略或禁止思考的概念仍会进入 Claude 的部分内部表征；新近预印本也在部分开放模型中观察到禁止 token 概率反弹。不过，这还不足以证明存在一个跨模型、跨任务的单一“负向提示反弹机制”。

不要采用的表述包括：

- “Transformer 不能理解否定。”模型常能正确遵守否定约束，能力只是并不完全可靠。
- “因为 next-token prediction 不能做减法，所以不要式提示必然失败。”这是常见直觉，不是被上述研究建立的机制。
- “J-space 里的词就是模型真正的想法。”J-lens 给出的是对内部方向的近似 token 化读出，不是一段隐藏句子，也不是意识证明。[^gurnee]
- “激活等于输出。”J-space 研究中就有内部概念出现而输出不变的反例。

### 3. 认知心理学类比

“不要想白熊”来自人类思想抑制研究：Wegner 等人在 1987 年的经典实验发现，尝试压制白熊想法会出现侵入，并在之后出现反弹。Wegner 1994 年提出 ironic process theory：一个费力的操作过程寻找符合目标的想法，另一个较自动的监控过程搜索目标是否失败；在认知负载下，监控过程可能使被排斥内容更易进入意识。[^wegner1987][^wegner1994]

2020 年对 31 项研究的元分析进一步区分了两个效应：压制后的反弹总体可观察到；压制当下的“立即增强”主要在有额外认知负载时出现。[^wang]

这可以作为生动类比，但必须标注为**人类认知研究**。人脑的监控过程不能直接当作 Transformer 内部机制；两者目前最多是现象和功能上的相似。

用户提出的“不要想着橘子去画苹果，结果苹果偏向橘子”不是上述经典实验的原始范式，也不是 Anthropic J-space 论文中的实验结果。Anthropic 论文中的“orange”示例实际来自正向指令“专注于柑橘类水果”；负向示例是“不要想金门大桥”。[^gurnee] 课程若需要类比，宜使用有来源的“白熊”或“金门大桥”，不要把“橘子味苹果”包装成研究结论。

### 4. 厂商实践建议与个人经验

OpenAI 的官方提示工程指南建议，不要只说不想要什么，还要说应该做什么；Anthropic 的官方指南也建议用希望的输出形态代替纯禁止式格式要求。[^openai][^anthropic]

这些是第一方实践指南，不是对 J-space 机制的同行评审证明。它们适合支撑“怎么写提示词”，不适合支撑“模型为什么这样”的科学解释。

个人工作中的成功/失败案例也可以讲，但应清楚标注“我的经验”，最好用同一任务做 A/B 对照并保留输出，避免把一次案例外推为所有模型都适用的规律。

## 推荐给课程与 HTML 的准确中文

### 主屏一句话

> **先说你要什么，再补真正必要的不能做什么。**

### 主屏解释

> 提示词不是“禁用词清单”。无关的禁止项会增加上下文噪声；而且点名一个概念，本身可能提高它在模型内部的显著性。先写目标、成功标准与期望输出；安全、兼容和数据边界等硬约束仍应明确写出，并给出可执行的替代行为。

### 讲师备注（证据边界版）

> Anthropic 2026 年的 J-space 研究发现，在所测试的 Claude 模型中，单纯提及一个概念、或者说“无论如何都不要想它”，仍会让该概念出现在一部分可读出的内部表征中；把它明确标为“与任务无关”抑制得更好。不过，实验并没有证明这些概念一定污染最终答案——模型仍正确完成了抄写任务。另有尚未同行评审的跨模型预印本发现，一些模型会提高被禁止 token 的概率，但效应依模型而变。因此这里讲的是稳健的提示设计建议，不是一条普适定律。

### 好坏示例

不推荐：

```text
不要写得啰嗦。
不要用太多标题。
不要重复需求。
不要讨论缓存、UI、微服务和我们以前失败过的方案。
不要擅自修改接口。
```

推荐：

```text
目标：给出“活动奖励领取”能力的最小实现方案。

输出：
- 先概述方案，再列验证证据；总计不超过 600 字。
- 只讨论领取模块、资格来源、奖励系统和领取记录。
- 保持现有公开接口兼容；已有调用方无需修改。

必要边界：
- 奖励效果至多发生一次。
- 结果未知时返回 RetryLater，后续重试先核对既有结果。
```

关键不是机械地把所有“不要”改成肯定句，而是：

1. 删除与任务无关的概念；
2. 把模糊否定改成可观察的目标或输出标准；
3. 保留真正影响正确性、安全和兼容性的硬约束；
4. 对硬约束补充替代行为或验收证据；
5. 用测试和评审验证约束是否真的被遵守，而不是迷信某种句式。

## 建议的 HTML 资料卡

课程页面可按下面顺序链接，避免把不同证据等级混在一起：

1. **内部表征 / 新研究** — [Verbalizable Representations Form a Global Workspace in Language Models](https://www.transformer-circuits.pub/2026/workspace/index.html)：J-space 的原始定义，以及 `mention`、`don't-think`、`ignore` 条件比较。标注“第一方原始研究，2026，未声明同行评审”。
2. **通俗入口** — [A global workspace in language models](https://www.anthropic.com/research/global-workspace)：Anthropic 对同一研究的短版说明。标注“官方研究摘要”。
3. **跨模型初步行为证据** — [Don't Think of the White Bear: Ironic Negation in Transformer Models Under Cognitive Load](https://arxiv.org/abs/2511.12381)：九个开放模型的 ReboundBench。标注“arXiv 预印本；合成英文、单 token、log-probability”。
4. **推理轨迹的禁止词控制** — [Reasoning Models Struggle to Control their Chains of Thought](https://cdn.openai.com/pdf/a21c39c1-fa07-41db-9078-973a12620117/cot_controllability.pdf)：13 个推理模型的 CoT-Control。标注“第一方研究；研究 CoT，不等于最终输出”。
5. **无关上下文** — [Large Language Models Can Be Easily Distracted by Irrelevant Context](https://proceedings.mlr.press/v202/shi23a.html)：同行评审的 ICML 2023 论文；同时说明 `ignore irrelevant information` 指令能缓解干扰。
6. **关键反证 / 必要护栏** — [Delegation to artificial intelligence can increase dishonest behaviour](https://www.nature.com/articles/s41586-025-09505-x)：同行评审的 *Nature* 论文；任务相关、强而具体的禁止式护栏可以有效改善行为。
7. **人类认知类比** — [Ironic Processes of Mental Control](https://pubmed.ncbi.nlm.nih.gov/8121959/) 与 [Ironic Effects of Thought Suppression: A Meta-Analysis](https://journals.sagepub.com/doi/10.1177/1745691619898795)：标注“人类心理学，只作类比”。
8. **实践指南** — [OpenAI prompt engineering best practices](https://help.openai.com/en/articles/6654000-best-practices-for-prompting-chatgpt) 与 [Anthropic prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables)：标注“厂商实践建议，不是机制证明”。

## 证据强度速查

| 可讲的命题 | 证据等级 | 限定 |
| --- | --- | --- |
| 无关上下文会降低部分 LLM 任务表现 | 较强：同行评审的直接行为研究 | GSM 数学题，不能自动推广到所有编码任务 |
| 强而具体的任务相关禁止项可改善安全行为 | 较强：同行评审的直接行为研究 | 欺骗/作弊场景，效果依模型而异且并非完美 |
| 点名/禁止概念可使其进入 Claude 的 J-space | 中等：第一方机制实验 | 主要是 Claude 4.5/4.6；J-lens 是近似读出；未声明同行评审 |
| `do not mention X` 可提高部分模型对 X 的 token 概率 | 初步：跨九模型预印本 | 合成英文、单 token、log-probability；模型差异大 |
| 禁止任务相关词很难约束推理模型的 CoT | 中等：跨 13 模型第一方研究 | 只针对 CoT 控制，不等于最终回答控制 |
| 禁止式提示会让最终输出必然偏向被禁止概念 | 不成立 | 现有来源没有给出这种普遍因果保证 |
| 所有 LLM 都有统一的 J-space | 不成立 | J-space 是 2026 年特定方法定义的新术语，跨架构普遍性未建立 |
| 人类“白熊效应”证明 AI 也有同样心理机制 | 不成立 | 人类证据只能作类比 |
| 重要的禁止/安全约束都应该删除 | 不成立且危险 | 必须保留硬边界；建议正向目标 + 必要约束 + 替代行为 + 验证 |

## 来源

[^gurnee]: Wes Gurnee et al., [*Verbalizable Representations Form a Global Workspace in Language Models*](https://www.transformer-circuits.pub/2026/workspace/index.html), Transformer Circuits / [arXiv:2607.15495](https://arxiv.org/abs/2607.15495), 2026。J-space 的定义见 “The Jacobian Lens and the J-space”；思想抑制主结果见 “Directed modulation”；措辞比较见 Appendix “Modulation prompt sensitivity”；表面输出不变见 “Thought suppression”；主动回避的因果实验见 Appendix “Different J-space requirements for naming a concept and avoiding it”；限制见 “Limitations and open questions”。
[^mann]: Logan Mann et al., [*Don't Think of the White Bear: Ironic Negation in Transformer Models Under Cognitive Load*](https://arxiv.org/abs/2511.12381), arXiv:2511.12381v1, 2025。跨九个开放模型的 ReboundBench 预印本；作者在 Appendix B 明确列出合成数据、英文、单 token 和 log-probability 等限制。
[^shi]: Freda Shi et al., [*Large Language Models Can Be Easily Distracted by Irrelevant Context*](https://proceedings.mlr.press/v202/shi23a.html), Proceedings of ICML 2023, PMLR 202:31210–31227。
[^kobis]: Nils Köbis et al., [*Delegation to Artificial Intelligence Can Increase Dishonest Behaviour*](https://www.nature.com/articles/s41586-025-09505-x), *Nature* 646, 126–134 (2025), DOI: 10.1038/s41586-025-09505-x。
[^cot]: Chen Yueh-Han et al., [*Reasoning Models Struggle to Control their Chains of Thought*](https://cdn.openai.com/pdf/a21c39c1-fa07-41db-9078-973a12620117/cot_controllability.pdf), OpenAI research publication / arXiv:2603.05706, 2026。
[^ashern]: Nicholas Asher and Swarnadeep Bhar, [*Strong Hallucinations from Negation and How to Fix Them*](https://aclanthology.org/2024.findings-acl.752/), Findings of ACL 2024, DOI: 10.18653/v1/2024.findings-acl.752。
[^wegner1987]: Daniel M. Wegner, David J. Schneider, Samuel R. Carter III, and Teri L. White, *Paradoxical Effects of Thought Suppression*, Journal of Personality and Social Psychology 53(1), 1987, DOI: [10.1037/0022-3514.53.1.5](https://doi.org/10.1037/0022-3514.53.1.5)。
[^wegner1994]: Daniel M. Wegner, [*Ironic Processes of Mental Control*](https://pubmed.ncbi.nlm.nih.gov/8121959/), Psychological Review 101(1), 1994, DOI: 10.1037/0033-295X.101.1.34。
[^wang]: Deming (Adam) Wang, Martin S. Hagger, and Nikos L. D. Chatzisarantis, [*Ironic Effects of Thought Suppression: A Meta-Analysis*](https://journals.sagepub.com/doi/10.1177/1745691619898795), Perspectives on Psychological Science 15(3), 2020, DOI: 10.1177/1745691619898795。
[^openai]: OpenAI, [*Best practices for prompt engineering with the OpenAI API*](https://help.openai.com/en/articles/6654000-best-practices-for-prompting-chatgpt)，官方实践指南，访问于 2026-09-10。
[^anthropic]: Anthropic, [*Prompting best practices*](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables)，官方实践指南，访问于 2026-09-10。
