---
name: nextjs-frontend
description: Next.js App Router, React Server Components (RSC), Server Actions, and SSR/SSG page layouts.
target_agent: agent1
---

# Next.js Frontend Framework Skill

When generating Next.js frontend applications, pages, or components:

## Key Guidelines
1. **App Router Structure**:
   - Use the `app/` directory layout (`page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`).
   - Distinguish Client Components (`'use client'`) from Server Components (RSC) to minimize client JS bundle size.

2. **Data Fetching & Server Actions**:
   - Use async Server Components for direct database or API fetching.
   - Use Server Actions (`'use server'`) for form mutations and revalidations (`revalidatePath`).

3. **Styling & Image Optimization**:
   - Utilize Next.js `Image` component (`next/image`) and Font optimization (`next/font`).
   - Use Tailwind CSS or CSS Modules for component styling.

