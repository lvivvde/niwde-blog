// @ts-check

import mdx from '@astrojs/mdx';
import { defineConfig, fontProviders } from 'astro/config';
import { siteConfig } from './site.config.mjs';

// https://astro.build/config
export default defineConfig({
	site: siteConfig.origin,
	outDir: './dist',
	integrations: [mdx()],
	markdown: {
		shikiConfig: { themes: { light: 'github-light', dark: 'github-dark' } },
	},
	fonts: [
		{
			provider: fontProviders.local(),
			name: 'Google Sans Code',
			cssVariable: '--font-google-sans-code',
			fallbacks: ['monospace'],
			options: {
				variants: [
					{
						src: ['./src/assets/fonts/google-sans-code.ttf'],
						weight: '300 800',
						style: 'normal',
						display: 'swap',
					},
				],
			},
		},
	],
});
