import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = await getCollection('posts', ({ data }) => !data.draft);
  
  return rss({
    title: 'Blog Supply Chain',
    description: 'A fully autonomous, AI-driven blog covering automation, DevOps, and AI workflows.',
    site: context.site,
    items: posts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.pubDate,
      description: post.data.description,
      link: `/blog-supply-chain/blog/${post.id}/`,
    })),
    customData: `<language>en-us</language>`,
  });
}
