<script lang="ts">
	// Tab Sinyal: bukan daftar sinyal, tapi penjelasan keputusan. Yang paling berguna
	// bagi trader adalah alasan TIDAK masuk, karena itu yang bisa diperiksa.
	import { onMount } from 'svelte';
	import { urlApi } from '$lib/api/client';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	interface Level {
		symbol?: string; play?: string; status?: string; price?: number; trend?: string;
		strategy?: string; reason?: string; blocked_reason?: string; indicator_source?: string;
	}
	interface Mt5 {
		connected?: boolean; account?: string; balance?: number; equity?: number;
		bid?: number; ask?: number; spread_pts?: number; digits?: number; atr_m5?: number;
	}
	interface Bias {
		bias?: string; score?: number | null; dinilai?: boolean; n?: number;
		blackout?: boolean; catatan?: string; age_sec?: number;
	}

	let level = $state<Level | null>(null);
	let mt5 = $state<Mt5 | null>(null);
	let bias = $state<Bias | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(true);

	async function j<T>(jalur: string): Promise<T | null> {
		try {
			const r = await fetch(urlApi(jalur), { credentials: 'include' });
			const isi = await r.json().catch(() => null);
			if (!r.ok) {
				galat ??= isi?.error?.message ?? isi?.detail?.message ?? `HTTP ${r.status}`;
				return null;
			}
			return isi as T;
		} catch (e) {
			galat ??= e instanceof Error ? e.message : 'gagal menghubungi API';
			return null;
		}
	}

	// "Laya SKIP p=0.156 (ambang 0.60, umur 50s/180s) side=LONG sesi=NEW_YORK"
	function urai(alasan?: string) {
		if (!alasan) return null;
		const p = alasan.match(/p=([\d.]+)/);
		const amb = alasan.match(/ambang\s*([\d.]+)/);
		const sisi = alasan.match(/side=([A-Z]+)/);
		const sesi = alasan.match(/sesi=([A-Z_]+)/);
		const prob = p ? Number(p[1]) : null;
		const ambang = amb ? Number(amb[1]) : null;
		return {
			probabilitas: prob,
			ambang,
			selisih: prob != null && ambang != null ? ambang - prob : null,
			sisi: sisi?.[1] ?? null,
			sesi: sesi?.[1]?.replace('_', ' ') ?? null
		};
	}

	const uraiBias = $derived(urai(level?.blocked_reason));
	const arah = $derived((level?.trend ?? '').toUpperCase().includes('BULL'));

	onMount(async () => {
		[level, mt5, bias] = await Promise.all([
			j<Level>('/api/v1/tencent/forex/levels?symbol=XAUUSD'),
			j<Mt5>('/api/v1/tencent/mt5/status'),
			j<Bias>('/api/v1/tencent/forex/bias')
		]);
		memuat = false;
	});

	function angka(v: number | undefined | null, digit = 3) {
		return v == null
			? '—'
			: v.toLocaleString('id-ID', { minimumFractionDigits: digit, maximumFractionDigits: digit });
	}
</script>

{#if memuat}
	<Skeleton baris={3} tinggi={44} />
{:else if !level}
	<EmptyState
		judul="Level belum tersedia"
		pesan={galat ?? 'Laya Sentinel tidak mengembalikan level untuk XAUUSD.'}
		langkah="Periksa layanan sentinel di server; tanpa itu tab ini kosong."
	/>
{:else}
	<div class="space-y-4">
		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center gap-2">
				<span class="label-mikro font-mono text-text-3">{level.symbol ?? 'XAUUSD'}</span>
				<span
					class="rounded border px-2 py-0.5 font-mono text-10 uppercase"
					class:border-neg={level.status !== 'ENTRY'}
					class:text-neg={level.status !== 'ENTRY'}
					class:border-pos={level.status === 'ENTRY'}
					class:text-pos={level.status === 'ENTRY'}
				>
					{level.status ?? 'TANPA STATUS'}
				</span>
				<span class="font-mono text-11 text-text-3">{level.strategy ?? ''}</span>
				{#if level.play}
					<span class="rounded border border-line px-2 py-0.5 font-mono text-10 text-text-3">{level.play}</span>
				{/if}
			</div>

			<p class="mt-2 text-13 leading-relaxed text-text">{level.reason ?? '—'}</p>

			{#if level.blocked_reason}
				<div class="mt-3 rounded border border-line bg-surface-2 p-3">
					<div class="label-mikro font-mono text-text-3">ALASAN BLOKIR</div>
					<p class="mt-1 font-mono text-11 leading-relaxed text-text-2">{level.blocked_reason}</p>
				</div>
			{/if}

			{#if uraiBias?.probabilitas != null && uraiBias?.ambang != null}
				<div class="mt-3 grid gap-3 sm:grid-cols-3">
					<div>
						<div class="label-mikro font-mono text-text-3">PROBABILITAS LAYA</div>
						<div class="mt-0.5 font-mono text-14 font-bold text-neg">{uraiBias.probabilitas.toFixed(3)}</div>
					</div>
					<div>
						<div class="label-mikro font-mono text-text-3">AMBANG MASUK</div>
						<div class="mt-0.5 font-mono text-14 font-bold text-text">{uraiBias.ambang.toFixed(2)}</div>
					</div>
					<div>
						<div class="label-mikro font-mono text-text-3">KEKURANGAN</div>
						<div class="mt-0.5 font-mono text-14 font-bold text-neg">−{uraiBias.selisih?.toFixed(3)}</div>
					</div>
				</div>
			{/if}
		</section>

		<section class="rounded-card border border-line bg-surface p-4">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="text-13 font-bold text-text">Pasar saat ini</h2>
				<span class="font-mono text-11 text-text-3">
					{mt5?.connected ? 'MT5 tersambung' : 'MT5 tidak tersambung'}{mt5?.account ? ` · ${mt5.account}` : ''}
				</span>
			</div>
			<dl class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
				<div>
					<dt class="label-mikro font-mono text-text-3">BID</dt>
					<dd class="mt-0.5 font-mono text-12 text-text">{angka(mt5?.bid ?? level.price)}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">ASK</dt>
					<dd class="mt-0.5 font-mono text-12 text-text">{angka(mt5?.ask)}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">SPREAD</dt>
					<dd class="mt-0.5 font-mono text-12 text-text">{mt5?.spread_pts ?? '—'} pts</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">ATR M5</dt>
					<dd class="mt-0.5 font-mono text-12 text-text">{angka(mt5?.atr_m5, 2)}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">TREN</dt>
					<dd class="mt-0.5 font-mono text-12" class:text-pos={arah} class:text-neg={!arah && !!level.trend}>
						{level.trend ?? '—'}{uraiBias?.sisi ? ` · sisi ${uraiBias.sisi}` : ''}
					</dd>
				</div>
			</dl>
			{#if mt5?.spread_pts && mt5.atr_m5}
				{@const hargaSpread = mt5.spread_pts / Math.pow(10, mt5.digits ?? 3)}
				<p class="mt-2 text-11 text-text-3">
					Spread {hargaSpread.toFixed(mt5.digits ?? 3)} harga, menyerap
					{((hargaSpread / mt5.atr_m5) * 100).toFixed(1)}% dari ATR M5.
					{#if uraiBias?.sesi}Sesi aktif: {uraiBias.sesi}.{/if}
				</p>
			{/if}
		</section>

		<section class="rounded-card border border-line bg-surface p-4">
			<h2 class="text-13 font-bold text-text">Penjaga sinyal</h2>
			<dl class="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
				<div>
					<dt class="label-mikro font-mono text-text-3">SUMBER INDIKATOR</dt>
					<dd class="mt-0.5 font-mono text-11 text-text">{level.indicator_source ?? '—'}</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">BIAS BERITA</dt>
					<dd class="mt-0.5 font-mono text-11 text-text-2">
						{bias?.bias ?? '—'}{bias?.dinilai === false ? ' (belum dinilai)' : ''}
					</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">BLACKOUT</dt>
					<dd class="mt-0.5 font-mono text-11" class:text-neg={bias?.blackout} class:text-pos={!bias?.blackout}>
						{bias?.blackout ? 'AKTIF' : 'tidak'}
					</dd>
				</div>
				<div>
					<dt class="label-mikro font-mono text-text-3">SAMPEL DINILAI</dt>
					<dd class="mt-0.5 font-mono text-11 text-text-2">{bias?.n ?? 0} berita</dd>
				</div>
			</dl>
			{#if bias?.dinilai === false}
				<p class="mt-2 text-11 leading-relaxed text-text-3">
					Bias berita belum dinilai karena belum ada berita masuk. Itu bukan berarti pasar netral —
					hanya berarti penilai belum punya bahan.
				</p>
			{/if}
		</section>
	</div>
{/if}
