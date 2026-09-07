// Separate builds keep the resume site out of the public blog's metadata.
const variant = process.env.SITE_VARIANT || 'portfolio';
if (!['portfolio', 'blog'].includes(variant)) {
	throw new Error('SITE_VARIANT must be portfolio or blog.');
}
export const siteConfig = {
	variant,
	origin: variant === 'portfolio' ? 'https://yangjiexin.com' : 'https://niwde.com',
	indexable: variant === 'blog',
};
