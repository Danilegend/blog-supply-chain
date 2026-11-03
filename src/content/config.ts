import { defineCollection, z } from 'astro:content';

const posts = defineCollection({
  type: 'content',
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
