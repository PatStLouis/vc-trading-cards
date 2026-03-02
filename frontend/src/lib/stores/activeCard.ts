import { writable } from 'svelte/store';

export const activeCard = writable<HTMLDivElement | null>(null);
