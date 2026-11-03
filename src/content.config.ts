import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    linkedinSummary: z.string().optional(),
    affiliateDisclosure: z.boolean().default(true),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts };
