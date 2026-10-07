<script lang="ts">
	// Halaman masuk (W7). Sesi = cookie HttpOnly dari API; halaman ini TIDAK dijaga guard.
	// Pesan galat diteruskan apa adanya dari API (mis. "kredensial tidak sah").
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { masuk } from '$lib/api/client';

	let username = $state('');
	let password = $state('');
	let totp = $state('');
	let galat = $state<string | null>(null);
	let memuat = $state(false);

	async function kirim(e: SubmitEvent) {
		e.preventDefault();
		memuat = true;
		galat = null;
		// Nilai diambil dari FORM, bukan hanya dari state Svelte. Temuan 7 Okt: auditor
		// eksternal melaporkan "vault mengembalikan sukses tetapi password tidak masuk ke
		// field" — password manager mengisi elemen DOM tanpa selalu memicu binding Svelte
		// (`bind:value`), sehingga form terlihat terisi tetapi state tetap kosong dan login
		// gagal. Membaca FormData membuat jalur autofill/paste/skrip tetap bekerja.
		const fd = new FormData(e.currentTarget as HTMLFormElement);
		const u = String(fd.get('username') ?? username);
		const p = String(fd.get('password') ?? password);
		const k = String(fd.get('totp') ?? totp);
		try {
			await masuk(u, p, k || undefined);
			await goto(page.url.searchParams.get('lanjut') || '/');
		} catch (err) {
			galat = err instanceof Error ? err.message : String(err);
		} finally {
			memuat = false;
		}
	}
</script>

<div class="mx-auto mt-14 w-full max-w-sm" data-testid="masuk">
	<h1 class="text-19 text-text">Masuk War Room</h1>
	<p class="mt-1 text-12 text-text-3">
		Sesi cookie HttpOnly; TLS dan origin tunggal ditangani reverse proxy.
	</p>

	<form class="mt-5 space-y-3" onsubmit={kirim}>
		<label class="block" for="masuk-username">
			<span class="label-mikro block text-text-3">username</span>
			<input
				id="masuk-username"
				name="username"
				bind:value={username}
				autocomplete="username"
				required
				class="target-44 w-full rounded-control border border-line bg-surface px-2 text-13 text-text"
			/>
		</label>
		<label class="block" for="masuk-sandi">
			<span class="label-mikro block text-text-3">sandi</span>
			<input
				id="masuk-sandi"
				name="password"
				type="password"
				bind:value={password}
				autocomplete="current-password"
				required
				class="target-44 w-full rounded-control border border-line bg-surface px-2 text-13 text-text"
			/>
		</label>
		<label class="block" for="masuk-totp">
			<span class="label-mikro block text-text-3">kode TOTP (bila aktif)</span>
			<input
				id="masuk-totp"
				name="totp"
				bind:value={totp}
				inputmode="numeric"
				autocomplete="one-time-code"
				class="target-44 w-full rounded-control border border-line bg-surface px-2 text-13 text-text"
			/>
		</label>

		{#if galat}
			<p class="text-12 text-neg" role="alert">{galat}</p>
		{/if}

		<button
			type="submit"
			disabled={memuat}
			class="target-44 transisi rounded-control bg-accent px-3 text-13 font-bold text-on-accent disabled:opacity-60"
		>
			{memuat ? 'memeriksa…' : 'masuk'}
		</button>
	</form>
</div>
