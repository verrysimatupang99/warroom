// Stub netral $app/navigation untuk vitest.
//
// MarketShell (shell semua halaman pasar) memakai goto() dari $app/navigation.
// Plugin SvelteKit tidak dipasang di vitest, jadi alias ini mengarah ke stub
// tanpa efek supaya komponen shell bisa dirender mandiri di uji. Pola sama
// dengan stub $env/dynamic/public yang sudah ada.

export async function goto() {}
export async function invalidate() {}
export async function invalidateAll() {}
export async function preloadData() {}
export async function preloadCode() {}
export function beforeNavigate() {}
export function afterNavigate() {}
export function onNavigate() {}
