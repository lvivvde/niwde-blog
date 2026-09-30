---
title: "CS336 学习记录与复盘：第四天"
description: "斯坦福 CS336 第四天的学习记录。"
pubDate: 2026-09-30
tags: ["CS336", "学习记录", "复盘"]
draft: false
---

## 2026-09-30

### GPU 编程优化与 FlashAttention

今天主要学习了 GPU 的执行方式和优化思路，并在这些基础上理解 FlashAttention。下面按照知识之间的依赖关系重新整理。

#### 1. GPU 与 CPU 的设计目标

CPU 通常使用较少但更复杂的核心，追求单个任务的低延迟，并配有较强的缓存、分支预测和乱序执行能力。GPU 则把更多硬件资源用于并行计算，追求大量相似任务的总体吞吐量。

矩阵乘法包含大量结构相同、彼此可以并行的乘加运算，因此很适合 GPU。NVIDIA GPU 通常把 32 个线程组成一个 warp，让它们共同执行指令。如果同一 warp 内的线程因为数据不同而进入不同的 `if/else` 分支，GPU 需要分别执行各条路径，并暂时屏蔽不走当前路径的线程，这称为分支发散。

这里需要修正的是：并非所有 `if/else` 都会拖慢 GPU。只要同一 warp 内的线程作出相同判断，就不会产生这种分支发散；不同 warp 走不同路径也可以独立执行。

#### 2. 从显存访问到合并读取

GPU 的矩阵计算很快，但数据必须先从显存搬到计算单元附近。显存容量大、访问相对较慢；共享内存和寄存器容量小，却更接近计算单元、速度也更快。因此，GPU 优化的重要目标之一，是减少较慢的显存读写，并让搬进来的数据得到更多次利用。

如果同一 warp 中的相邻线程读取相邻地址，GPU 可以把多个请求合并成较少的内存事务；如果这些线程访问的位置很分散，就可能触发更多次读取。这比单纯要求起始地址“对齐”更完整，通常称为合并内存访问。

#### 3. 矩阵分块与部分结果累加

接下来是矩阵分块。以 `4×4` 矩阵为例，可以把它拆成四个 `2×2` 小块，再以小块为单位搬运和计算。重点不只是一次取得四个数据，而是把输入块搬进共享内存后，让多个线程在许多乘加运算中反复使用它。

对于矩阵乘法 `C = AB`，结果中的一个块需要沿公共维度累加多个输入块的乘积：

```text
Cᵢⱼ += AᵢₖBₖⱼ
```

GPU 会尽量把 `Cᵢⱼ` 的部分和保存在寄存器或共享内存中。每读入一组新的 `Aᵢₖ` 和 `Bₖⱼ`，就把乘积累加到原来的部分和，最后再把完成的结果写回显存。课程所说的“原地构建矩阵”，更准确地理解为复用高速存储中的累加器，并不一定是每一步都直接修改显存里的最终矩阵。

#### 4. 矩阵形状、Tile Quantization 与 Wave Quantization

分块之后，矩阵的行列长度、token 数、batch size 和隐藏维度都会影响硬件利用率。GPU kernel 会把输出划分为固定大小的 tile。如果某个维度不能被 tile 大小整除，边缘仍可能启动一个完整计算块，其中一部分位置没有有效数据，这称为 **tile quantization**。

因此，处理更多数据不一定更慢。把矩阵尺寸调整到更适合 tile 的形状后，原本空闲的位置得到利用，每个 token 的平均成本可能下降，整体吞吐量反而提高。课程中增加几百个 token 后效率提高约 25%，应当理解为特定矩阵形状、kernel 和硬件共同产生的结果。

我最初把对齐简单理解成矩阵长度最好采用 16 或 32 的倍数。实际上没有一套适用于所有情况的固定数字：它取决于数据类型、GPU 架构、Tensor Core 指令、内存布局和 kernel。FP16 矩阵维度通常以 8 个元素的倍数更高效，而具体 kernel 的 tile 可能是 `128×128`、`256×128` 等更大的形状。

课程中还有一个尺寸略微增加、耗时却接近翻倍的例子。我一开始误以为它使用了第二张 GPU，实际讲的是同一张 GPU 上出现了第二个计算 wave：

- 矩阵尺寸为 1792 时，按照 `256×128` 分块，共产生 98 个 tile；
- 尺寸增加到 1793 后，需要 120 个 tile；
- 一张 A100 有 108 个 SM，第一轮无法完成全部 120 个 tile；
- 剩余 12 个 tile 必须在同一张 GPU 上再运行一轮。

第二轮虽然工作很少，却仍增加了一轮执行时间，而且大部分 SM 都处于空闲状态。这称为 **wave quantization**，不涉及第二张显卡，也没有跨 GPU 通信。

真正使用第二张 GPU 是另一种情况。如果模型参数、优化器状态、梯度或激活值无法放进单卡显存，或者希望用更多算力加速训练，才需要进行多卡切分。这时会产生 NVLink、PCIe 等互连上的通信和同步成本。

#### 5. 算子融合与 FlashAttention

普通 Attention 会依次进行矩阵乘法、缩放、Softmax 和另一轮矩阵乘法。如果每一步都作为独立 kernel 执行，中间结果就可能反复写回显存，再由下一步重新读取。算子融合可以把多个步骤放进同一个 kernel，减少 kernel 启动和中间数据搬运。

FlashAttention 综合使用了分块、数据复用和算子融合。它把 Q、K、V 的小块搬入片上高速内存，在块内计算 Attention，并避免把完整的注意力分数矩阵写入显存。它计算的仍是数学上等价的完整 Attention，主要减少的是 HBM 与片上 SRAM 之间的读写。

#### 6. Online Softmax

FlashAttention 逐块计算 Attention 时，不能先保存完整分数矩阵再统一执行 Softmax，因此需要使用 Online Softmax。

我的初步理解是：处理新块时，如果出现了更大的分数，就要更新之前的归一化结果。这看起来可能更慢，因为似乎需要重新寻找并修改所有旧数据。

实际并不会重新遍历旧分数。Online Softmax 只维护当前最大值、指数和以及加权输出等少量汇总状态。新块出现更大值时，它用一个缩放系数修正旧的汇总值，再把新块的数据加入，不需要回头读取所有旧分数。

这种方法增加了少量指数、缩放和乘加运算，却省去了大型中间矩阵的写入和读取。Attention 经常受显存带宽限制，因此多做少量计算，通常比反复搬运大量数据更快。

#### 今天的整体理解

这节课的知识可以串成一条完整路线：GPU 追求并行吞吐量，所以要减少分支发散；计算速度远高于数据搬运速度，所以要合并读取并利用内存层级；为了复用数据，需要进行矩阵分块；分块又要求关注矩阵形状、tile 和 wave；最后，FlashAttention 把分块、融合和 Online Softmax 组合起来，用更少的显存读写完成完整 Attention。

#### 参考资料

- [NVIDIA CUDA Programming Guide：SIMT 与分支发散](https://docs.nvidia.com/cuda/cuda-programming-guide/03-advanced/advanced-kernel-programming.html)
- [NVIDIA CUDA Programming Guide：合并全局内存访问](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/writing-cuda-kernels.html)
- [NVIDIA Matrix Multiplication Background：矩阵分块、维度对齐与量化效应](https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html)
- [Stanford CS336 Lecture 5：GPU、Tiling 与 Wave Quantization](https://cs336.stanford.edu/spring2025-lectures/nonexecutable/2025%20Lecture%205%20-%20GPUs.pdf)
- [FlashAttention：具有 IO 感知能力的快速、节省显存的精确 Attention](https://arxiv.org/abs/2205.14135)
