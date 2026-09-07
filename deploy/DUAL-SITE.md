# 双域名部署

| 域名 | 用途 | 构建目录 | 搜索收录 |
| --- | --- | --- | --- |
| `yangjiexin.com` | 简历作品集及技术文章 | `dist/portfolio` | HTML noindex + Caddy X-Robots-Tag |
| `niwde.com` | Niwde 公开博客 | `dist/blog` | 允许，独立 sitemap / RSS / canonical |

## 本地验证

`npm run build` 构建两个站点并执行输出检查。`npm run dev` 预览作品集；`npm run dev:blog` 预览公开博客。

## 首次上线顺序

1. 确认拥有 `niwde.com`，并将其接入 Cloudflare。为根域名和 `www` 配置当前 Tunnel 的 DNS 路由。
2. 暂停生产部署（仓库变量 `DEPLOY_ENABLED=false`），保存当前 Caddy、Tunnel 和发布激活脚本的备份，以及 `current` 指向的版本。
3. 将新的 `activate-release.sh` 安装到现有激活脚本的位置，保留现有 root 所有者和执行权限。新版本要求 `portfolio/index.html` 和 `blog/index.html` 同时存在。
4. 通过原有签名发布流程上传双站构建。切换 `current` 后立即安装新的 Caddy 配置；这两个操作应安排在同一维护窗口，否则旧配置会短暂找不到首页。
5. 使用 `caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` 验证配置后 reload。更新现有 cloudflared 配置并验证 ingress，再重启对应 Tunnel 服务。
6. 检查四个域名的 HTTPS 访问。`www` 只重定向到各自根域名，不跨站跳转。姓名站的首页、文章和 RSS 均应返回 `X-Robots-Tag: noindex`；公开博客不应带此头。
7. 验证姓名站项目链接、两站搜索、公开博客 RSS 和 sitemap。全部通过后恢复 `DEPLOY_ENABLED=true`，并设置 `BLOG_DOMAIN_ENABLED=true` 启用新域名线上检查。

## 回滚

将 `current` 恢复到备份的旧版本，并同步恢复旧 Caddy 配置和旧激活脚本，再 reload Caddy。首次迁移的旧版本是单站目录，不能仅切换版本链接而保留双站 Caddy 配置。Tunnel 的新增域名路由也应恢复到备份状态。

## 隐私边界

公开博客构建不得包含姓名域名；凭据、登录笔记和私钥不得进入源码或构建目录。公开仓库仍可能通过配置与历史记录关联两站，两个站点中的相同文章与 GitHub 链接也能形成关联。noindex 是搜索引擎指令，不是访问控制，已存在的收录不会立即消失。
