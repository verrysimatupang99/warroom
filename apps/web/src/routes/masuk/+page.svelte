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
		try {
			await masuk(username, password, totp || undefined);
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
		<label class="block">
			<span class="label-mikro block text-text-3">username</span>
			<input
				bind:value={username}
				autocomplete="username"
				required
				class="target-44 w-full rounded-control border border-line bg-surface px-2 text-13 text-text"
			/>
		</label>
		<label class="block">
			<span class="label-mikro block text-text-3">sandi</span>
			<input
				type="password"
				bind:value={password}
				autocomplete="current-password"
				required
				class="target-44 w-full rounded-control border border-line bg-surface px-2 text-13 text-text"
			/>
		</label>
		<label class="block">
			<span class="label-mikro block text-text-3">kode TOTP (bila aktif)</span>
			<input
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
			class="target-44 transisi rounded-control bg-accent px-3 text-13 font-bold text-[#1a1206] disabled:opacity-60"
		>
			{memuat ? 'memeriksa…' : 'masuk'}
		</button>
	</form>
</div>
