import { getCollection } from 'astro:content';
import { getPostSlug } from '../categories';

export async function getPublishedPosts() {
	const posts = await getCollection('blog', ({ data }) => !data.draft);
	const slugs = posts.map((post) => getPostSlug(post.id));
	if (new Set(slugs).size !== slugs.length) {
		throw new Error('Blog filenames must be unique across category folders.');
	}
	return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf() || a.id.localeCompare(b.id));
}
