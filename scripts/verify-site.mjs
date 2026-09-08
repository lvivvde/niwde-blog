import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { siteConfig } from '../site.config.mjs';

function filesIn(directory) {
	return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const path = join(directory, entry.name);
		return entry.isDirectory() ? filesIn(path) : [path];
	});
}

const directory = resolve('dist');
assert(existsSync(join(directory, 'index.html')), 'Missing single-site entry point');
assert(!existsSync(join(directory, 'portfolio')), 'Unexpected second site output');
const htmlFiles = filesIn(directory).filter((file) => file.endsWith('.html'));
assert(htmlFiles.length > 0, 'Missing pages');
for (const path of filesIn(directory)) {
	const bytes = readFileSync(path);
	const content = (bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes) : bytes).toString('utf8');
	assert(!/-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----|"TunnelSecret"/.test(content), `Credential marker in ${path}`);
	if (!path.endsWith('.html')) continue;
	const canonical = content.match(/<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/);
	assert(canonical, `Missing canonical: ${path}`);
	assert.equal(new URL(canonical[1]).origin, siteConfig.origin, `Wrong canonical: ${path}`);
	for (const [, url] of content.matchAll(/<meta\b[^>]*property="og:(?:url|image)"[^>]*content="([^"]+)"/g)) {
		assert.equal(new URL(url).origin, siteConfig.origin, `Wrong social metadata origin: ${path}`);
	}
	assert(/<meta\b[^>]*name="robots"[^>]*content="[^"]*noindex/.test(content), `Missing noindex: ${path}`);
	for (const [, href] of content.matchAll(/\b(?:href|src)="(\/(?!\/)[^"?#]*)[^\"]*"/g)) {
		const target = resolve(directory, `.${decodeURIComponent(href)}`);
		assert(target === directory || target.startsWith(`${directory}/`), `Path escapes site: ${href}`);
		assert(existsSync(target) || existsSync(`${target}.html`) || existsSync(join(target, 'index.html')), `Broken local link: ${href}`);
	}
}
const rss = readFileSync(join(directory, 'rss.xml'), 'utf8');
for (const [, url] of rss.matchAll(/<link>([^<]+)<\/link>/g)) assert.equal(new URL(url).origin, siteConfig.origin);
assert(existsSync(join(directory, 'pagefind', 'pagefind.js')), 'Missing search index');
assert(!/^Disallow:\s*\/\s*$/m.test(readFileSync(join(directory, 'robots.txt'), 'utf8')), 'Crawlers cannot see noindex');
assert(!existsSync(join(directory, 'sitemap-index.xml')), 'Unexpected sitemap for noindex site');
console.log(`${htmlFiles.length} pages checked: single-site output, links, metadata, noindex, RSS, and search.`);
