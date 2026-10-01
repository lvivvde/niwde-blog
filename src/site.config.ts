import { siteConfig as deployment } from '../site.config.mjs';

export const siteConfig = {
	title: 'Niwde',
	description: '游戏后端、AI 开发、项目实验与学习笔记。',
	origin: deployment.origin,
	github: 'https://github.com/lvivvde',
	navigation: [
		{ label: '首页', href: '/' },
		{ label: '文章', href: '/blog/' },
		{ label: '分类', href: '/categories/' },
		{ label: '项目', href: '/projects/' },
		{ label: '资料', href: '/resources/' },
		{ label: '关于', href: '/about/' },
	],
} as const;
