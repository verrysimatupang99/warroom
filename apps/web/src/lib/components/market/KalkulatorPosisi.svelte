<script lang="ts">
	// Kalkulator ukuran posisi. Semua angka masukan berasal dari akun dan pasar yang
	// sedang berjalan, bukan contoh. Mendukung mode Akun Cent (USC) dan Standar (USD).
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';

	interface Mt5 {
		connected?: boolean; account?: string; currency?: string; equity?: number; balance?: number;
		bid?: number; ask?: number; spread_pts?: number; digits?: number; atr_m5?: number;
	}

	let mt5 = $state<Mt5 | null>(null);
	let modeAkun = $state<'cent' | 'standar'>('cent');
	let risikoPct = $state(1.5);
	let atrKali = $state(1.5);
	let twinOrder = $state(true);
	let galat = $state<string | null>(null);

	// XAUUSD Standar: 1 lot = 100 oz ($100 per $1 gerak harga).
	// XAUUSDc Cent: dalam satuan USC, 1 lot = 100 USC per $1 gerak harga (0.01 lot = 1 USC per $1 gerak harga).
	const NILAI_PER_HARGA = 100;

	onMount(async () => {
		try {
			const r = await fetch(urlApi('/api/v1/tencent/mt5/status?account=452009427'), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) galat = isi?.error?.message ?? `HTTP ${r.status}`;
			else {
				mt5 = isi;
				modeAkun = isi?.currency === 'USC' || isi?.account === '452009427' ? 'cent' : 'standar';
			}
		} catch (e) {
			galat = e instanceof Error ? e.message : 'gagal menghubungi API';
		}
	});

	const satuan = $derived(modeAkun === 'cent' ? 'USC' : 'USD');
	const ekuitas = $derived(mt5?.equity ?? mt5?.balance ?? 0);
	const atr = $derived(mt5?.atr_m5 ?? 0);
	const hargaStop = $derived(atr * atrKali);
	const risikoSatuan = $derived((ekuitas * risikoPct) / 100);
	const jumlahTiket = $derived(twinOrder ? 2 : 1);
	const lotMentahTotal = $derived(hargaStop > 0 ? risikoSatuan / (hargaStop * NILAI_PER_HARGA) : 0);
	const lotMentahPerTiket = $derived(lotMentahTotal / jumlahTiket);
	// MT5 hanya menerima kelipatan 0,01 lot per tiket.
	const lotPerTiket = $derived(Math.max(0, Math.floor(lotMentahPerTiket * 100) / 100));
	const lotDipakaiPerTiket = $derived(Math.max(lotPerTiket, 0.01));
	const lotDipakaiTotal = $derived(lotDipakaiPerTiket * jumlahTiket);
	const risikoMinimum = $derived(hargaStop * NILAI_PER_HARGA * (0.01 * jumlahTiket));
	const lewatBatas = $derived(lotPerTiket < 0.01 && risikoSatuan > 0);
	const porsiMinimum = $derived(ekuitas > 0 ? (risikoMinimum / ekuitas) * 100 : 0);
	const hargaSpread = $derived((mt5?.spread_pts ?? 0) / Math.pow(10, mt5?.digits ?? 3));
	const biayaSpread = $derived(hargaSpread * NILAI_PER_HARGA * lotDipakaiTotal);
	const porsiSpread = $derived(risikoSatuan > 0 ? (biayaSpread / risikoSatuan) * 100 : 0);
	const layak = $derived(biayaSpread > 0 && risikoSatuan > 0 && biayaSpread / risikoSatuan < 0.25);

	function rp(v: number, digit = 2) {
		return v.toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit });
	}
	function fmtUang(v: number) {
		if (modeAkun === 'cent') {
			return `${rp(v)} USC ($${rp(v / 100)})`;
		}
		return `$${rp(v)}`;
	}
</script>

<div class="space-y-4">
	<section class="rounded-card border border-line bg-surface p-4">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<div class="flex items-center gap-2">
				<h2 class="text-13 font-bold text-text">Ukuran posisi XAUUSD (Live ATR)</h2>
				<div class="inline-flex rounded-control border border-line bg-surface-2 p-0.5 font-mono text-10">
					<button
						type="button"
						class="rounded px-2 py-0.5 {modeAkun === 'cent' ? 'bg-accent/20 text-accent font-bold' : 'text-text-3'}"
						onclick={() => (modeAkun = 'cent')}
					>
						CENT (USC)
					</button>
					<button
						type="button"
						class="rounded px-2 py-0.5 {modeAkun === 'standar' ? 'bg-accent/20 text-accent font-bold' : 'text-text-3'}"
						onclick={() => (modeAkun = 'standar')}
					>
						STANDAR (USD)
					</button>
				</div>
			</div>
			<span class="font-mono text-11 text-text-3">
				{mt5?.connected ? `ekuitas ${fmtUang(ekuitas)}` : 'akun tidak terbaca'}
			</span>
		</div>

		{#if galat}
			<p class="mt-2 text-11 text-neg">{galat}</p>
		{:else}
			<div class="mt-3 grid gap-3 sm:grid-cols-3">
				<label class="block">
					<span class="label-mikro font-mono text-text-3">RISIKO PER SETUP (%)</span>
					<input
						type="number" min="0.1" max="5" step="0.1" bind:value={risikoPct}
						class="mt-1 w-full rounded-control border border-line bg-surface-2 px-2 py-2 font-mono text-12 text-text"
					/>
					<span class="mt-1 block text-10 text-text-3">{fmtUang(risikoSatuan)} dari ekuitas</span>
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
				<div class="block">
					<span class="label-mikro font-mono text-text-3">MODE ORDER REAPER</span>
					<button
						type="button"
						class="mt-1 w-full rounded-control border border-line bg-surface-2 px-3 py-2 text-left font-mono text-12 text-text hover:border-accent"
						onclick={() => (twinOrder = !twinOrder)}
					>
						{twinOrder ? 'Twin-Order (2 tiket: Scalp + Runner)' : 'Single-Order (1 tiket)'}
					</button>
					<span class="mt-1 block text-10 text-text-3">
						{twinOrder ? 'TP1 +0.7R (Scalp) & TP2 +2.0R (Runner)' : '1 tiket penuh'}
					</span>
				</div>
			</div>

			<div class="mt-4 grid gap-3 sm:grid-cols-4">
				<div>
					<div class="label-mikro font-mono text-text-3">LOT ({twinOrder ? 'PER TIKET × 2' : 'TUNGGAL'})</div>
					<div class="mt-0.5 font-mono text-17 font-bold" class:text-neg={lewatBatas} class:text-text={!lewatBatas}>
						{#if lewatBatas}
							{twinOrder ? '2 × 0,01 (min)' : '0,01 (min)'}
						{:else}
							{twinOrder ? `2 × ${rp(lotPerTiket)}` : rp(lotPerTiket)}
						{/if}
					</div>
				</div>
				<div>
					<div class="label-mikro font-mono text-text-3">RISIKO ({satuan})</div>
					<div class="mt-0.5 font-mono text-14 text-neg">{fmtUang(lewatBatas ? risikoMinimum : risikoSatuan)}</div>
				</div>
				<div>
					<div class="label-mikro font-mono text-text-3">BIAYA SPREAD</div>
					<div class="mt-0.5 font-mono text-14 text-text-2">{fmtUang(biayaSpread)}</div>
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
					ATR belum tersedia dari telemetri MT5, jadi ukuran posisi live belum bisa dihitung. Gunakan simulator manual di bawah bila ingin menghitung sendiri.
				{:else if lewatBatas}
					Hasil hitung per tiket hanya {rp(lotMentahPerTiket, 3)} lot, di bawah minimum broker 0,01 lot. Bila dipasang {twinOrder ? '2 × 0,01' : '0,01'} lot, risikonya {fmtUang(risikoMinimum)} ({rp(porsiMinimum, 1)}% ekuitas).
				{:else if layak}
					Spread memakan {rp(porsiSpread, 1)}% dari risiko. Masih sehat di bawah batas 25%.
				{:else}
					Spread memakan {rp(porsiSpread, 1)}% dari risiko, di atas batas 25%. Pada jarak stop sependek ini, biaya eksekusi ikut menentukan hasil.
				{/if}
			</p>
		{/if}
	</section>

	<section class="rounded-card border border-line bg-surface p-4">
		<h2 class="text-13 font-bold text-text">Cara hitungnya ({modeAkun === 'cent' ? 'XAUUSDc Akun Cent' : 'XAUUSD Standar'})</h2>
		<ol class="mt-2 space-y-1 text-11 leading-relaxed text-text-2">
			<li>1. Risiko per setup = ekuitas × persen risiko ({fmtUang(ekuitas)} × {risikoPct}% = {fmtUang(risikoSatuan)}).</li>
			<li>2. Jarak stop dalam harga Emas = ATR M5 × {atrKali} = ${rp(hargaStop, 2)}.</li>
			<li>3. Pada {modeAkun === 'cent' ? 'XAUUSDc (Cent), 0,01 lot bernilai 1 USC ($0,01)' : 'XAUUSD (Standar), 0,01 lot bernilai $1,00'} untuk setiap $1,00 gerak harga Emas.</li>
			<li>4. Biaya spread = spread harga (${rp(hargaSpread, 3)}) × 100 × total lot ({rp(lotDipakaiTotal)}) = {fmtUang(biayaSpread)} ({rp(porsiSpread, 1)}% dari risiko).</li>
		</ol>
	</section>
</div>
