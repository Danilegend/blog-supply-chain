// src/content.config.ts
import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: ({ image }) => z.object({ // Use the image helper
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    linkedinSummary: z.string().optional(),
    affiliateDisclosure: z.boolean().default(true),
    draft: z.boolean().default(false),
    // Add this line to support an array of images
    images: z.array(z.string()).optional(), 
  }),
});

export const collections = { posts };