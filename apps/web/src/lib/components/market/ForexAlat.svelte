<script lang="ts">
	// Simulator ukuran posisi manual. Dihitung di browser, tanpa API: rumusnya sederhana
	// dan hasilnya harus bisa diperiksa ulang oleh pengguna.
	import EmptyState from '$lib/components/EmptyState.svelte';

	let saldo = $state(1095);
	let satuan = $state<'USC' | 'USD'>('USC');
	let risikoPct = $state(1.5);
	let slPts = $state(350);
	let nilaiPerPts = $state(0.01); // Satuan (USC atau USD) per point per 0.01 lot
	let hasil = $derived.by(() => {
		if (!saldo || !risikoPct || !slPts) return null;
		const risikoUang = (saldo * risikoPct) / 100;
		const uangPerLotPerPts = nilaiPerPts * 100; // 0.01 lot -> 1.00 lot
		const lot = risikoUang / (slPts * uangPerLotPerPts);
		const lotBulat = Math.max(0.01, Math.floor(lot * 100) / 100);
		return {
			risikoUang: risikoUang.toFixed(2),
			risikoUsdSetara: satuan === 'USC' ? (risikoUang / 100).toFixed(2) : risikoUang.toFixed(2),
			lot: lot.toFixed(3),
			lotBulat: lotBulat.toFixed(2)
		};
	});
</script>

<div class="space-y-4">
	<section class="rounded-card border border-line bg-surface p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<h2 class="text-13 font-bold text-text">Simulator ukuran posisi (manual)</h2>
			<div class="inline-flex rounded-control border border-line bg-surface-2 p-0.5 font-mono text-10">
				<button
					type="button"
					class="rounded px-2 py-0.5 {satuan === 'USC' ? 'bg-accent/20 text-accent font-bold' : 'text-text-3'}"
					onclick={() => (satuan = 'USC')}
				>
					USC (Cent)
				</button>
				<button
					type="button"
					class="rounded px-2 py-0.5 {satuan === 'USD' ? 'bg-accent/20 text-accent font-bold' : 'text-text-3'}"
					onclick={() => (satuan = 'USD')}
				>
					USD (Standar)
				</button>
			</div>
		</div>
		<p class="mt-1 text-11 text-text-3">
			Masukkan angka saldo dan jarak stop dalam point secara bebas. Rumus risiko tetap:
			rugi maksimal per trade = saldo × risiko%.
		</p>
		<div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			<label class="block">
				<span class="label-mikro font-mono text-text-3">SALDO ({satuan})</span>
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
				<span class="label-mikro font-mono text-text-3">NILAI ({satuan}) / POINT / 0.01 LOT</span>
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
				<div class="label-mikro font-mono text-text-3">RISIKO ({satuan})</div>
				<div class="mt-1 font-mono text-17 font-bold text-text">
					{satuan === 'USC' ? `${hasil.risikoUang} USC ($${hasil.risikoUsdSetara})` : `$${hasil.risikoUang}`}
				</div>
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
