import { IS_PORTFOLIO, SITE_URL } from '../consts';

export function GET() {
	// Crawlers must be allowed to read the portfolio's noindex directives.
	const sitemap = IS_PORTFOLIO ? '' : `\nSitemap: ${SITE_URL}/sitemap-index.xml\n`;
	return new Response(`User-agent: *\nAllow: /\n${sitemap}`, {
		headers: { 'Content-Type': 'text/plain; charset=utf-8' },
	});
}
