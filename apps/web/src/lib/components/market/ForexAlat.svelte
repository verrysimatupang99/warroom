<script lang="ts">
	// Kalkulator ukuran posisi. Dihitung di browser, tanpa API: rumusnya sederhana
	// dan hasilnya harus bisa diperiksa ulang oleh pengguna.
	import EmptyState from '$lib/components/EmptyState.svelte';

	let saldo = $state(500);
	let risikoPct = $state(1);
	let slPts = $state(300);
	let nilaiPerPts = $state(0.01); // USD per point per 0.01 lot (XAUUSD standar)
	let hasil = $derived.by(() => {
		if (!saldo || !risikoPct || !slPts) return null;
		const risikoUsd = (saldo * risikoPct) / 100;
		const usdPerLotPerPts = nilaiPerPts * 100; // 0.01 lot -> 1.00 lot
		const lot = risikoUsd / (slPts * usdPerLotPerPts);
		return {
			risikoUsd: risikoUsd.toFixed(2),
			lot: lot.toFixed(3),
			lotBulat: Math.max(0.01, Math.floor(lot * 100) / 100).toFixed(2)
		};
	});
</script>

<div class="space-y-4">
	<section class="rounded-card border border-line bg-surface p-4">
		<h2 class="text-13 font-bold text-text">Ukuran posisi</h2>
		<p class="mt-1 text-11 text-text-3">
			Masukkan angka akun dan jarak stop. Kalkulator ini memakai rumus risiko tetap:
			rugi maksimal per trade = saldo × risiko%.
		</p>
		<div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<label class="block">
				<span class="label-mikro font-mono text-text-3">SALDO (USD)</span>
				<input
					type="number"
					class="mt-1 min-h-[44px] w-full rounded-control border border-line bg-surface px-2 font-mono text-12 text-text"
					bind:value={saldo}
				/>
			</label>
			<label class="block">
				<span class="label-mikro font-mono text-text-3">RISIKO (%)</span>
				<input
					type="number"
					step="0.1"
					class="mt-1 min-h-[44px] w-full rounded-control border border-line bg-surface px-2 font-mono text-12 text-text"
					bind:value={risikoPct}
				/>
			</label>
			<label class="block">
				<span class="label-mikro font-mono text-text-3">JARAK SL (POINT)</span>
				<input
					type="number"
					class="mt-1 min-h-[44px] w-full rounded-control border border-line bg-surface px-2 font-mono text-12 text-text"
					bind:value={slPts}
				/>
			</label>
			<label class="block">
				<span class="label-mikro font-mono text-text-3">NILAI / POINT / 0.01 LOT</span>
				<input
					type="number"
					step="0.001"
					class="mt-1 min-h-[44px] w-full rounded-control border border-line bg-surface px-2 font-mono text-12 text-text"
					bind:value={nilaiPerPts}
				/>
			</label>
		</div>
	</section>

	{#if hasil}
		<section class="grid gap-3 sm:grid-cols-3">
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">RISIKO RUPIAH</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">${hasil.risikoUsd}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">LOT (HITUNGAN)</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">{hasil.lot}</div>
			</div>
			<div class="rounded-card border border-line bg-surface p-4">
				<div class="label-mikro font-mono text-text-3">LOT (DIBULATKAN TURUN)</div>
				<div class="mt-1 font-mono text-17 font-bold text-accent">{hasil.lotBulat}</div>
			</div>
		</section>
		<p class="text-11 text-text-3">
			Pembulatan ke bawah disengaja: lebih baik risiko sedikit di bawah batas daripada
			melewatinya. Verifikasi nilai per point dengan spesifikasi kontrak broker sebelum
			memakai angka ini di akun nyata.
		</p>
	{:else}
		<EmptyState judul="Angka belum lengkap" pesan="Isi saldo, risiko, dan jarak SL." ringkas={true} />
	{/if}
</div>
