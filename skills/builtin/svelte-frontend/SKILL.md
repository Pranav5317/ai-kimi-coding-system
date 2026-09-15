---
name: svelte-frontend
description: Svelte 5 / SvelteKit reactive runes, Single File Components, server loaders, and stores.
target_agent: agent1
---

# Svelte / SvelteKit Frontend Framework Skill

When generating Svelte or SvelteKit components and applications:

## Key Guidelines
1. **Reactive State & Runes**:
   - Use Svelte 5 runes (`$state()`, `$derived()`, `$props()`) for clean reactivity.
   - Keep component code concise inside `.svelte` files.

2. **SvelteKit Architecture**:
   - Use `src/routes/` for file-based routing (`+page.svelte`, `+page.server.ts`, `+layout.svelte`).
   - Use `load` functions in `+page.server.ts` for server-side data fetching.

