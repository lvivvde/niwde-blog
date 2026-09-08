# 发布现有站点

站点保持单站结构，`npm run build` 生成 `dist/index.html`、文章和搜索索引。服务器继续从 `/srv/niwde-blog/current` 提供文件，沿用现有 Caddy、Cloudflare Tunnel 与签名发布流程。

## 发布

1. 本地执行 `npm ci` 和 `npm run build`，确认输出检查通过。
2. 提交并推送到 `main`。GitHub Actions 会构建站点。
3. 仓库变量 `DEPLOY_ENABLED=true` 时，工作流签名、上传并激活该版本；为 `false` 时只构建。
4. 已提交的版本也可以从 Actions 的 `Build and deploy` 页面手动运行。
5. 确认构建与发布均成功，再检查线上首页、文章、图片、RSS 和搜索。

文章页面包含 `noindex`，robots.txt 允许搜索引擎读取这一指令。它不是访问控制，已有收录也不会立即消失。

## 回滚

发布脚本保留最近三个版本。出现问题时，通过管理员将 `/srv/niwde-blog/current` 原子切回上一个已验证版本，并检查页面与搜索。不要关闭签名校验或 SSH 主机密钥校验。

登录信息、私钥及 Tunnel 凭据仅保存在本地私有目录或 GitHub Secrets 中，不加入源码。
