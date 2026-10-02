// Dashboard internal berbasis cookie sesi: render di klien supaya `fetch` membawa cookie
// dan SSE tidak dijalankan di server. Tidak ada `meta refresh`.
export const ssr = false;
export const prerender = false;