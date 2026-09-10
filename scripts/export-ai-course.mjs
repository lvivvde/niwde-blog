// 把课程页 dist/ai-course/index.html 打包成单个离线 HTML：内联全部样式、去掉站内导航与页脚、
// 去除字体与图标等外部引用（字体回退到系统字体），拷到任何电脑双击即可打开。
// 用法：npm run build && npm run export:course [-- --out <路径>]；默认输出到桌面 ai-course.html。
import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

const outIndex = process.argv.indexOf('--out');
const outPath =
	outIndex > -1 && process.argv[outIndex + 1]
		? resolve(process.argv[outIndex + 1])
		: join(homedir(), 'Desktop', 'ai-course.html');

const dist = resolve('dist');
const pagePath = join(dist, 'ai-course', 'index.html');
assert(existsSync(pagePath), '缺少 dist/ai-course/index.html，请先运行 npm run build');
let html = readFileSync(pagePath, 'utf8');

// 字体声明块同时定义了 --font-atkinson 变量；直接删掉会让 body 的整个字体栈失效，
// 所以保留变量并指向 system-ui，拉丁字符与中文都交给系统字体渲染。
const fontBlock = html.match(/<style>@font-face[\s\S]*?<\/style>/);
assert(fontBlock && fontBlock[0].includes('--font-atkinson'), '未找到字体声明样式块');
html = html.replace(fontBlock[0], '<style>:root{--font-atkinson:system-ui}</style>');

// 内联全部样式表，保持原引用顺序（后一个文件里有全局变量与基础样式，顺序不能颠倒）。
html = html.replace(/<link rel="stylesheet" href="(\/_astro\/[^"]+\.css)">/g, (_match, href) => {
	const cssPath = join(dist, href);
	assert(existsSync(cssPath), `找不到样式文件 ${href}，请先运行 npm run build`);
	return `<style>\n${readFileSync(cssPath, 'utf8')}\n</style>`;
});
assert(!html.includes('<link rel="stylesheet"'), '仍有未内联的样式表');

// 去掉离线场景无意义的外部引用：字体预加载、站点图标、RSS、canonical。
html = html.replace(/<link rel="preload"[^>]*as="font"[^>]*>/g, '');
html = html.replace(/<link rel="icon"[^>]*>/g, '');
html = html.replace(/<link rel="alternate"[^>]*>/g, '');
html = html.replace(/<link rel="canonical"[^>]*>/g, '');

// 极简页头复用原站头部的 data-astro-cid 属性，免费获得 sticky 定位、毛玻璃背景和按钮样式，
// 原有的 68px 头部高度与目录的 84px 偏移也无需调整。
const standaloneHeader = [
	'<!-- 单文件导出版本：由 scripts/export-ai-course.mjs 生成，请勿手改；重新生成请运行 npm run export:course。 -->',
	'<header data-pagefind-ignore data-astro-cid-nen7h5rs>',
	'<nav aria-label="课程页头" data-astro-cid-nen7h5rs>',
	'<span class="brand" data-astro-cid-nen7h5rs>AI 编程课程 · 讲师手册</span>',
	'<div class="links" data-astro-cid-nen7h5rs>',
	'<button id="theme-toggle" type="button" aria-label="切换深色模式" title="切换深色模式" data-astro-cid-nen7h5rs>◐</button>',
	'</div></nav></header>',
].join('');
// 站内导航头带 data-pagefind-ignore 标记；课程文章自身还有一个 <header class="ac-head"> 区块，不能用泛匹配。
const headers = html.match(/<header data-pagefind-ignore[\s\S]*?<\/header>/g) || [];
assert(headers.length === 1, `预期 1 个站内导航头，实际 ${headers.length} 个`);
html = html.replace(/<header data-pagefind-ignore[\s\S]*?<\/header>/, standaloneHeader);

const footers = html.match(/<footer data-pagefind-ignore[\s\S]*?<\/footer>/g) || [];
assert(footers.length === 1, `预期 1 个站内页脚，实际 ${footers.length} 个`);
html = html.replace(/<footer data-pagefind-ignore[\s\S]*?<\/footer>/, '');

// 终检：不允许残留任何站内绝对链接或未内联的站点资源引用，防止文件在离线电脑上悄悄坏掉。
assert(!/href="\/[^"]*"/.test(html), '仍残留站内绝对链接');
assert(!/(href|src)="\/_astro\//.test(html), '仍残留未内联的站点资源');
assert(html.includes('id="theme-toggle"'), '缺少深浅色切换按钮');
assert(html.includes('data-quiz-panel') && html.includes('beforeprint'), '缺少课程页互动脚本');

html = `<!-- 由 scripts/export-ai-course.mjs 生成；请勿手改，重新生成请运行 npm run export:course。 -->\n${html}`;
writeFileSync(outPath, html);
console.log(`已生成单文件：${outPath}（${Math.round(Buffer.byteLength(html) / 1024)} KB）`);
