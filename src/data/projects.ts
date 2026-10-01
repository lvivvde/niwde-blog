export const projects = [
	{
		name: 'RealmMesh',
		description: '帧驱动的 C++ / Lua 游戏服务端，记录架构、实现与验证过程。',
		href: '/blog/building-realmmesh-with-ai/',
		source: 'https://github.com/lvivvde/RealmMesh',
		stack: 'C++ / Lua',
		details: [
			'网络 I/O 与帧逻辑之间的有界队列、服务发现、C++ / Lua 调用边界与热更新。',
			'生产代码与测试代码由 AI 生成，我负责需求、架构边界、审查和最终验收。',
			'持续迭代中，关注断线、超时、队列满和依赖失败时的行为。',
		],
	},
	{
		name: '游戏设计知识 MCP',
		description: '将 Word、Excel 与文档图片组织成可查询、可定位的项目资料。',
		href: '/blog/game-design-knowledge-mcp/',
		stack: 'MCP / SQLite FTS5',
		details: [
			'原始资料作为事实来源，SQLite FTS5 作为可重建索引，查询结果回到章节与单元格。',
			'明确返回未找到、歧义和过期状态，通过计划与确认两步导入资料，建库成功后再原子发布。',
		],
	},
];
