# Niwde Blog

Niwde 的个人技术博客，内容聚焦游戏后端、AI 开发、项目实验与工程复盘。

- 站点：<https://yangjiexin.com>
- 项目：[RealmMesh](https://github.com/lvivvde/RealmMesh)
- 框架：[Astro](https://astro.build/)
- 搜索：[Pagefind](https://pagefind.app/)

## 本地开发

```bash
npm install
npm run dev
```

生产构建会先生成 Astro 静态站点，再生成 Pagefind 搜索索引：

```bash
npm run build
npm run preview
```

## 写文章

按分类在下面四个目录中新建 Markdown 或 MDX 文件，目录名就是分类，不需要在文章里重复填写分类字段：

```text
src/content/blog/
├── game-backend/       # 游戏后端
├── ai-development/     # AI 开发
├── project-lab/        # 项目实验
└── retrospectives/     # 随笔复盘
```

Frontmatter 示例：

```yaml
---
title: "文章标题"
description: "文章摘要"
pubDate: 2026-08-19
tags: ["C++", "Lua"]
draft: false
---
```

## 可选环境变量

复制 `.env.example` 为 `.env`，配置 giscus 评论和 Cloudflare Web Analytics。密钥和 Token 不得提交到仓库。

## 版权

博客程序代码采用 MIT License。文章和原创图片保留所有权利，详见 `CONTENT_LICENSE.md`。
