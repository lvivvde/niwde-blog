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

export type BlogCategoryName = (typeof BLOG_CATEGORIES)[number]['name'];

function getEntrySegments(entryId: string) {
	return entryId.replaceAll('\\', '/').split('/').filter(Boolean);
}

export function getCategoryFromEntryId(entryId: string) {
	const [folder] = getEntrySegments(entryId);
	const category = BLOG_CATEGORIES.find((item) => item.slug === folder);
	if (!category) throw new Error(`Blog post is not inside a known category folder: ${entryId}`);
	return category;
}

export function getPostSlug(entryId: string) {
	const segments = getEntrySegments(entryId);
	const filename = segments.at(-1);
	if (!filename || segments.length < 2) {
		throw new Error(`Blog post must be inside a category folder: ${entryId}`);
	}
	return filename.replace(/\.(md|mdx)$/i, '');
}

export function getCategoryPath(name: BlogCategoryName) {
	const category = BLOG_CATEGORIES.find((item) => item.name === name);
	if (!category) throw new Error(`Unknown blog category: ${name}`);
	return `/categories/${category.slug}/`;
}
