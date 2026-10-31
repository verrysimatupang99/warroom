<script lang="ts">
	// Kalkulator ukuran posisi. Semua angka masukan berasal dari akun dan pasar yang
	// sedang berjalan, bukan contoh. Perhitungannya sederhana dan sengaja ditampilkan
	// apa adanya supaya bisa diperiksa: risiko dolar / (jarak stop x nilai per poin).
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Mt5 {
		connected?: boolean; account?: string; equity?: number; balance?: number;
		bid?: number; ask?: number; spread_pts?: number; digits?: number; atr_m5?: number;
	}

	let mt5 = $state<Mt5 | null>(null);
	let risikoPct = $state(1);
	let atrKali = $state(1.5);
	let galat = $state<string | null>(null);

	// XAUUSD: 1 lot = 100 oz, jadi 1 dolar pergerakan harga = 100 dolar per lot.
	const NILAI_PER_HARGA = 100;

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/tencent/mt5/status'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) galat = isi?.error?.message ?? `HTTP ${r.status}`;
			else mt5 = isi;
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
	});

	const ekuitas = $derived(mt5?.equity ?? mt5?.balance ?? 0);
	const atr = $derived(mt5?.atr_m5 ?? 0);
	const hargaStop = $derived(atr * atrKali);
	const risikoUsd = $derived((ekuitas * risikoPct) / 100);
	const lotMentah = $derived(hargaStop > 0 ? risikoUsd / (hargaStop * NILAI_PER_HARGA) : 0);
	// MT5 hanya menerima kelipatan 0,01 lot. Dibulatkan ke bawah supaya risiko tidak
	// melebihi batas yang dipilih.
	const lot = $derived(Math.max(0, Math.floor(lotMentah * 100) / 100));
	// Kalau hasil hitung di bawah 0,01, lot terkecil yang bisa dipasang tetap 0,01.
	// Itu artinya risiko sebenarnya lebih besar dari yang diminta, dan itu harus disebut.
	const lotDipakai = $derived(Math.max(lot, 0.01));
	const risikoMinimum = $derived(hargaStop * NILAI_PER_HARGA * 0.01);
	const lewatBatas = $derived(lot < 0.01 && risikoUsd > 0);
	const porsiMinimum = $derived(ekuitas > 0 ? (risikoMinimum / ekuitas) * 100 : 0);
	const hargaSpread = $derived((mt5?.spread_pts ?? 0) / Math.pow(10, mt5?.digits ?? 3));
	const biayaSpread = $derived(hargaSpread * NILAI_PER_HARGA * lotDipakai);
	const porsiSpread = $derived(risikoUsd > 0 ? (biayaSpread / risikoUsd) * 100 : 0);
	const layak = $derived(biayaSpread > 0 && risikoUsd > 0 && biayaSpread / risikoUsd < 0.25);

	function rp(v: number, digit = 2) {
		return v.toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit });
	}
</script>

<div class="space-y-4">
	<section class="rounded-card border border-line bg-surface p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<h2 class="text-13 font-bold text-text">Ukuran posisi XAUUSD</h2>
			<span class="font-mono text-11 text-text-3">
				{mt5?.connected ? `ekuitas $${rp(ekuitas)}` : 'akun tidak terbaca'}
			</span>
		</div>

		{#if galat}
			<p class="mt-2 text-11 text-neg">{galat}</p>
		{:else}
			<div class="mt-3 grid gap-3 sm:grid-cols-2">
				<label class="block">
					<span class="label-mikro font-mono text-text-3">RISIKO PER TRADE (%)</span>
					<input
						type="number" min="0.1" max="5" step="0.1" bind:value={risikoPct}
						class="mt-1 w-full rounded-control border border-line bg-surface-2 px-2 py-2 font-mono text-12 text-text"
					/>
					<span class="mt-1 block text-10 text-text-3">${rp(risikoUsd)} dari ekuitas</span>
				</label>
				<label class="block">
					<span class="label-mikro font-mono text-text-3">JARAK STOP (× ATR M5)</span>
					<input
						type="number" min="0.5" max="5" step="0.1" bind:value={atrKali}
						class="mt-1 w-full rounded-control border border-line bg-surface-2 px-2 py-2 font-mono text-12 text-text"
					/>
					<span class="mt-1 block text-10 text-text-3">
						{atr > 0 ? `${rp(hargaStop, 2)} harga (ATR ${rp(atr, 2)})` : 'ATR belum tersedia'}
					</span>
				</label>
			</div>

			<div class="mt-4 grid gap-3 sm:grid-cols-4">
				<div>
					<div class="label-mikro font-mono text-text-3">LOT</div>
					<div class="mt-0.5 font-mono text-17 font-bold" class:text-neg={lewatBatas} class:text-text={!lewatBatas}>
						{lewatBatas ? '0,01 (minimum)' : rp(lot)}
					</div>
				</div>
				<div>
					<div class="label-mikro font-mono text-text-3">RISIKO</div>
					<div class="mt-0.5 font-mono text-14 text-neg">${rp(risikoUsd)}</div>
				</div>
				<div>
					<div class="label-mikro font-mono text-text-3">BIAYA SPREAD</div>
					<div class="mt-0.5 font-mono text-14 text-text-2">${rp(biayaSpread)}</div>
				</div>
				<div>
					<div class="label-mikro font-mono text-text-3">SPREAD / RISIKO</div>
					<div class="mt-0.5 font-mono text-14" class:text-neg={porsiSpread >= 25} class:text-pos={porsiSpread < 25}>
						{rp(porsiSpread, 1)} %
					</div>
				</div>
			</div>

			<p class="mt-3 text-11 leading-relaxed" class:text-neg={!layak || lewatBatas} class:text-text-3={layak && !lewatBatas}>
				{#if atr <= 0}
					ATR belum tersedia, jadi ukuran posisi belum bisa dihitung.
				{:else if lewatBatas}
					Hasil hitung hanya {rp(lotMentah, 3)} lot, di bawah minimum 0,01. Kalau tetap dipasang
					0,01 lot, risikonya ${rp(risikoMinimum)} atau {rp(porsiMinimum, 1)}% ekuitas — bukan
					{risikoPct}% yang diminta. Dengan akun sebesar ${rp(ekuitas)}, stop selebar {rp(hargaStop, 2)}
					harga terlalu jauh untuk risiko sekecil itu.
				{:else if layak}
					Spread memakan {rp(porsiSpread, 1)}% dari risiko. Masih di bawah batas 25%.
				{:else}
					Spread memakan {rp(porsiSpread, 1)}% dari risiko — di atas batas 25%. Pada jarak stop
					sependek ini, biaya eksekusi ikut menentukan hasil, bukan cuma arah harga.
				{/if}
			</p>
		{/if}
	</section>

	<section class="rounded-card border border-line bg-surface p-4">
		<h2 class="text-13 font-bold text-text">Cara hitungnya</h2>
		<ol class="mt-2 space-y-1 text-11 leading-relaxed text-text-2">
			<li>1. Risiko dolar = ekuitas × persen risiko. Contoh: ${rp(ekuitas)} × {risikoPct}% = ${rp(risikoUsd)}.</li>
			<li>2. Jarak stop dalam harga = ATR M5 × pengali. Sekarang {rp(hargaStop, 2)}.</li>
			<li>3. Lot = risiko dolar ÷ (jarak stop × 100). Hasil mentah {rp(lotMentah, 3)}; yang dipasang {lewatBatas ? '0,01 (minimum broker)' : rp(lot)}.</li>
			<li>4. Biaya spread = spread dalam harga × 100 × lot. Sekarang ${rp(biayaSpread)}, yaitu {rp(porsiSpread, 1)}% dari risiko.</li>
		</ol>
		<p class="mt-2 text-11 text-text-3">
			Pembulatan selalu ke bawah. Lebih baik risiko sedikit di bawah batas daripada lewat.
			Angka ini tidak memperhitungkan komisi, swap, atau slippage — untuk itu lihat uji biaya di tab Uji.
		</p>
	</section>
</div>
