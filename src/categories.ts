export const BLOG_CATEGORIES = [
	{
		name: '游戏后端',
		slug: 'game-backend',
		description: 'C++、Lua、网络、并发与游戏服务端架构。',
	},
	{
		name: 'AI 开发',
		slug: 'ai-development',
		description: 'AI 编码工作流、提示设计、审查与测试实践。',
	},
	{
		name: '项目实验',
		slug: 'project-lab',
		description: 'RealmMesh 等真实项目的设计、实现与验证记录。',
	},
	{
		name: '随笔复盘',
		slug: 'retrospectives',
		description: '开发过程中的判断、失败、取舍与阶段性复盘。',
	},
] as const;

export const BLOG_CATEGORY_NAMES = BLOG_CATEGORIES.map((category) => category.name) as [
	(typeof BLOG_CATEGORIES)[number]['name'],
	...(typeof BLOG_CATEGORIES)[number]['name'][],
];

export type BlogCategoryName = (typeof BLOG_CATEGORIES)[number]['name'];

export function getCategoryPath(name: BlogCategoryName) {
	const category = BLOG_CATEGORIES.find((item) => item.name === name);
	if (!category) throw new Error(`Unknown blog category: ${name}`);
	return `/categories/${category.slug}/`;
}
