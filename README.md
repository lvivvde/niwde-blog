# Niwde Blog

Niwde 的个人技术笔记，记录游戏后端、AI 开发、项目实验与学习过程，方便自己查阅。

- 项目：[RealmMesh](https://github.com/lvivvde/RealmMesh)
- 框架：[Astro](https://astro.build/)
- 搜索：[Pagefind](https://pagefind.app/)

## 本地开发

```bash
npm install
npm run dev
```

生产构建生成单个站点和 Pagefind 搜索索引，并检查页面链接、元数据和收录规则：

```bash
npm run build
npm run preview
```

首页按时间列出文章，并提供项目和资料入口。文章归档、分类、项目、资料、关于与课程页面统一输出到 `dist/`。页面使用 `noindex`，供持有链接的访客访问。发布步骤见 [部署说明](deploy/README.md)。

## 页面与样式

布局参考 [Astro Cactus](https://github.com/chrismwilliams/astro-theme-cactus)，字体参考 [AstroPaper](https://github.com/satnaing/astro-paper)。Google Sans Code 随站点本地提供，中文使用系统字体回退；字体许可证位于 `src/assets/fonts/google-sans-code-LICENSE.txt`。

```text
src/
├── site.config.ts          # 名称、描述、导航和个人链接
├── data/                   # 项目与资料，首页和独立页面共用
├── lib/posts.ts            # 公开文章、日期排序和重复 URL 检查
├── layouts/                # 通用文档布局与文章布局
├── components/layout/      # 导航、页脚与主题切换
├── components/blog/        # 文章列表、分类导航和目录
└── styles/                 # 主题变量、全局基础样式、正文排版
```

课程使用宽版布局，内容与交互独立于博客文章。修改主题或全局样式后，同时检查 `/ai-course/`。文章文件名决定原有 URL，目录决定分类；页面重构不改变这两个约定。

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
