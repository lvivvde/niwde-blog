// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = 'Niwde';
import { siteConfig } from '../site.config.mjs';
export const IS_PORTFOLIO = siteConfig.variant === 'portfolio';
export const SITE_DESCRIPTION = IS_PORTFOLIO
	? '游戏后端开发者的项目作品与技术实践：C++、Lua、服务端架构与 AI 辅助开发。'
	: '一个游戏后端开发者的 AI 实践与技术笔记。';
export const SITE_URL = siteConfig.origin;
export const GITHUB_URL = 'https://github.com/lvivvde';
export const REALMMESH_URL = 'https://github.com/lvivvde/RealmMesh';
