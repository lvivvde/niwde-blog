import rss from '@astrojs/rss';
import { getPostSlug } from '../categories';
import { getPublishedPosts } from '../lib/posts';
import { siteConfig } from '../site.config';

export async function GET(context) {
	const posts = await getPublishedPosts();
	return rss({
		title: siteConfig.title,
		description: siteConfig.description,
		site: context.site,
		items: posts.map((post) => ({
			...post.data,
			link: `/blog/${getPostSlug(post.id)}/`,
		})),
	});
}
