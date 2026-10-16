import type { Page } from "../pages/page";

const TAB = "rounded-md px-3 py-1.5 text-sm transition-colors";
const TAB_ACTIVE = "bg-accent/15 text-accent";
const TAB_IDLE = "text-muted hover:text-ink";

/** The top bar with the page tabs and the theme toggle over the main area, one page mounted at a time. */
export function shellHtml(pages: readonly Page[]): string {
  const tabs = pages.map((page) => `
    <a href="#/${page.id}" class="${TAB}" :class="page === '${page.id}' ? '${TAB_ACTIVE}' : '${TAB_IDLE}'">${page.title}</a>`);
  const views = pages.map((page) => `<template x-if="page === '${page.id}'">${page.html}</template>`);
  return `
    <div x-data="shell" @hashchange.window="go()" class="flex h-full flex-col">
      <header class="flex h-12 shrink-0 items-center gap-6 border-b border-line bg-card px-4">
        <span class="font-semibold tracking-tight">RatReplay</span>
        <nav class="flex gap-1">${tabs.join("")}</nav>
        <button type="button" @click="toggle()" x-text="dark ? 'Light mode' : 'Dark mode'"
          class="ml-auto rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-ink"></button>
      </header>
      <main class="min-h-0 flex-1 p-4">${views.join("")}</main>
    </div>`;
}
