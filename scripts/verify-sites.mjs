import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';

function filesIn(directory) {
	return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const path = join(directory, entry.name);
		return entry.isDirectory() ? filesIn(path) : [path];
	});
}

for (const variant of ['portfolio', 'blog']) {
	const directory = resolve('dist', variant);
	const origin = variant === 'portfolio' ? 'https://yangjiexin.com' : 'https://niwde.com';
	const files = filesIn(directory);
	const htmlFiles = files.filter((file) => file.endsWith('.html'));
	assert(htmlFiles.length > 0, `${variant}: missing HTML`);
	for (const path of files) {
		const bytes = readFileSync(path);
		const content = (bytes[0] === 0x1f && bytes[1] === 0x8b ? gunzipSync(bytes) : bytes).toString('utf8');
		assert(!/-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----|"TunnelSecret"/.test(content), `Credential marker in ${path}`);
		if (variant === 'blog') assert(!/yangjiexin/i.test(content), `Personal domain leaked into ${path}`);
		if (!path.endsWith('.html')) continue;
		const canonical = content.match(/<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"/);
		assert(canonical, `Missing canonical: ${path}`);
		assert.equal(new URL(canonical[1]).origin, origin, `Incorrect canonical: ${path}`);
		const noindex = /<meta\b[^>]*name="robots"[^>]*content="[^"]*noindex/.test(content);
		assert.equal(noindex, variant === 'portfolio', `Incorrect indexing policy: ${path}`);
		for (const [, href] of content.matchAll(/\b(?:href|src)="(\/(?!\/)[^"?#]*)[^\"]*"/g)) {
			const target = resolve(directory, `.${decodeURIComponent(href)}`);
			assert(target === directory || target.startsWith(`${directory}/`), `Path escapes site: ${href}`);
			assert(existsSync(target) || existsSync(`${target}.html`) || existsSync(join(target, 'index.html')), `Broken local link in ${path}: ${href}`);
		}
	}
	const rss = readFileSync(join(directory, 'rss.xml'), 'utf8');
	assert(rss.includes(`${origin}/`), `${variant}: wrong RSS origin`);
	assert(existsSync(join(directory, 'pagefind', 'pagefind.js')), `${variant}: missing search index`);
	const robots = readFileSync(join(directory, 'robots.txt'), 'utf8');
	assert(!/^Disallow:\s*\/\s*$/m.test(robots), `${variant}: crawlers cannot see noindex`);
	assert.equal(existsSync(join(directory, 'sitemap-index.xml')), variant === 'blog');
	assert.equal(robots.includes(`Sitemap: ${origin}/sitemap-index.xml`), variant === 'blog');
	console.log(`${variant}: ${htmlFiles.length} pages, links, canonical, indexing, RSS, and search checked.`);
}

console.log('Public blog output contains no personal domain or credential markers.');
