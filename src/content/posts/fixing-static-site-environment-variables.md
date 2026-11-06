---
title: "Fixing Static Site Environment Variables"
description: "Learn why static site environment variables are broken, how secrets leak into client bundles, and how to securely manage configs in modern SSGs."
pubDate: 2026-11-06
linkedinSummary: "Static site generators like Astro, Hugo, and Gatsby handle environment variables differently than traditional servers—and getting it wrong can leak API keys directly into client bundles. This article breaks down the build-time vs. runtime boundary, how to use Zod for strict validation, and best practices for securing your CI/CD pipeline. Stop exposing production secrets to the browser. Click through to read the full guide and secure your static deployments today."
affiliateDisclosure: true
draft: false
---

## Why Static Site Environment Variables Are Broken (And How to Fix Them)

Static site generators (SSGs) like Hugo, Gatsby, and Astro have revolutionized web performance by shifting server computation to build time. However, this architectural paradigm introduces a fundamental mismatch between build-time execution and runtime delivery. When developers coming from dynamic server environments (Node.js, Ruby, Python) transition to SSGs, they often treat environment variables the same way, leading to severe security vulnerabilities.

The core danger lies in how static assets are distributed. Unlike a Node.js server where `process.env` remains safely hidden on the host machine, any environment variable referenced during an SSG build process can be permanently compiled into the resulting JavaScript bundles or static HTML files. If a developer references a database URL, a private API key, or a secret token in a component that gets bundled for the client, that secret is exposed to every single user who visits the site.

Consider a real-world scenario from an open-source static site repository. The project used a poorly configured default setup in a modern frontend framework. The developer wanted to fetch data from a third-party analytics API on the client side, so they added `API_SECRET_KEY=xyz123` to their `.env` file and referenced it directly in a React component using standard environment injection. Because the framework's bundler saw the variable inside client-side code, it replaced the reference with the literal string `xyz123` during the build.

When the site was deployed to a public CDN, anyone inspecting the minified JavaScript bundle via browser developer tools could read the secret key in plain text. Within hours, automated scraping bots flagged the leaked credential, resulting in unauthorized access to the third-party service. This catastrophic failure was not caused by a sophisticated cyberattack, but by a misunderstanding of how static bundlers handle environment scope.

## Build-Time vs. Runtime: The Architecture of Static Deployments

To prevent these leaks, you must understand the exact boundary between the CI/CD runner and the user's browser. During the build phase, your CI/CD pipeline (e.g., GitHub Actions, Netlify, Vercel) executes the SSG code, compiles Markdown to HTML, and bundles JavaScript. At this exact moment, environment variables are accessible and can be injected into the output.

Once the build finishes, the resulting static files are pushed to a CDN. The build environment vanishes. The code running in the user's browser has zero access to the server's environment variables. Any configuration required by the client must be explicitly baked into the static assets during the build.

To manage this safely, modern frameworks rely on strict prefix conventions:

- `VITE_` or `PUBLIC_` prefixes explicitly tell the bundler: "It is safe to expose this variable to the browser."
- Variables without these prefixes are treated as private and must only be used during server-side data fetching or build-time API calls.

When configuring your CI/CD runner, ensure that private secrets (like Stripe secret keys or database connection strings) are strictly withheld from any build step that generates client-side assets.

## Designing a Scalable Configuration Schema

Scattering raw `process.env` or `import.meta.env` calls across your component tree makes your codebase fragile and hard to audit. Instead, implement a centralized `config` module that acts as the single source of truth for all environment variables.

By leveraging validation libraries like Zod, you can enforce strict type-checking and validation for environment variables the moment the build starts. If a required variable is missing or malformed, the build fails immediately rather than deploying a broken or insecure site.

```typescript
import { z } from 'zod';

const envSchema = z.object({
  PUBLIC_API_URL: z.string().url(),
  STRIPE_PUBLIC_KEY: z.string().startsWith('pk_'),
  // Private build-time only secret
  INTERNAL_BUILD_TOKEN: z.string().min(32),
});

const parsed = envSchema.safeParse({
  PUBLIC_API_URL: import.meta.env.PUBLIC_API_URL,
  STRIPE_PUBLIC_KEY: import.meta.env.STRIPE_PUBLIC_KEY,
  INTERNAL_BUILD_TOKEN: process.env.INTERNAL_BUILD_TOKEN,
});

if (!parsed.success) {
  console.error('Invalid environment configuration:', parsed.error.format());
  process.exit(1);
}

export const config = parsed.data;
```

This pattern also simplifies multi-environment setups (Preview, Staging, Production). Instead of duplicating configuration files, your centralized module normalizes environment differences based on the execution context, ensuring consistent behavior across deployments.

## Automating Secrets Management and CI/CD Pipelines

Storing production secrets as plain-text repository secrets in GitHub or GitLab is a scaling bottleneck and a security risk. As teams grow, managing access manually becomes unsustainable. Moving to a secure secret injection model within automated pipelines is essential.

Best practices for pipeline security include:

- Using encrypted environment files and role-based access control (RBAC) to restrict production credential visibility.
- Setting up automated PR previews with ephemeral test environments that use isolated, low-privilege API keys.
- Managing secure environment handoff seamlessly when scaling your team using [Akeyless](https://akeyless.io) for robust, developer-friendly secrets orchestration across distributed CI/CD runners.

## Auditing and Monitoring Your Static Deployments

Even with robust CI/CD configurations, human error happens. Implementing automated pre-build lint scripts to scan final HTML and JS outputs for unmasked secrets provides an essential safety net. You can write custom Node.js scripts that search the `./dist` folder for regex patterns matching known secret formats (such as JWTs, AWS keys, or private tokens) before deployment proceeds.

Additionally, integrate bundle analyzers into your CI pipeline to verify that sensitive keys are completely absent from client-facing assets. Finally, set up alerts for unexpected configuration changes or failed build injections in your deployment logs to catch drift before it impacts users.