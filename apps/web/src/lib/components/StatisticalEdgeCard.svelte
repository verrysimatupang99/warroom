<script lang="ts">
	// StatisticalEdgeCard: Kartu status bukti statistik (Polymarket / Gate).
	// Menjelaskan secara visual apakah strategi memiliki keunggulan matematis (Edge)
	// yang terbukti secara statistik (Wilson CI95% > Break-Even).
	import { angka } from '$lib/format';
	import type { MarketVerdict } from '$lib/api/types';
	import Istilah from './Istilah.svelte';

	interface VerdictData {
		n?: number;
		win?: number;
		be?: number;
		ci?: number;
		ci95?: [number, number];
		alat?: string;
		/** "frozen:<id>" bila split data sudah dibekukan. null = belum (ADR-003). */
		split?: string | null;
		/** Jumlah sampel yang masih dibutuhkan (dari gate, bukan taksiran UI). */
		nNeeded?: number | null;
		/** min_n dari aturan gate. */
		min_n?: number;
	}

	interface Props {
		verdict?: VerdictData | null;
		/** Verdict kanonik backend; bila ada, ini satu-satunya sumber status promosi. */
		canonical?: MarketVerdict | null;
		judul?: string;
	}

	let { verdict = null, canonical = null, judul = 'Statistical Edge Gate' }: Props = $props();

	const n = $derived(verdict?.n ?? 0);
	const win = $derived(verdict?.win ?? 0);
	const winrate = $derived(n > 0 ? (win / n) * 100 : 0);
	const bePct = $derived((verdict?.be ?? 0.7666) * 100);
	const ciLow = $derived(verdict?.ci95?.[0] ?? winrate * 0.98);
	const ciHigh = $derived(verdict?.ci95?.[1] ?? winrate * 1.02);

	// KONTRADIKSI YANG DIPERBAIKI (audit QA eksternal putaran 2, 7 Okt):
	// kartu ini dulu menulis "EDGE TERBUKTI" hanya dari CI95 bawah > BE, padahal gate
	// resmi proyek (gate.py) MENOLAK promosi selama `split` belum "frozen:<id>"
	// (ADR-003: split harus dibekukan SEBELUM melihat hasil). Akibatnya satu halaman
	// memuat dua kesimpulan yang bertentangan: "EDGE TERBUKTI" di atas, "belum lolos
	// gate — split belum dibekukan" di bawah. Sekarang kartu ini TUNDUK pada gate yang
	// sama: tanpa split beku → status "BELUM BISA DIPROMOSIKAN", bukan "terbukti".
	const splitBeku = $derived(typeof verdict?.split === 'string' && verdict.split.startsWith('frozen:'));
	const ciLolos = $derived(ciLow > bePct);
	const cukupSampel = $derived(verdict?.nNeeded == null || n >= Number(verdict.nNeeded));
	// Status promosi berasal dari verdict canonical backend. Fallback lokal sengaja
	// memblokir bila canonical belum tersedia: angka statistik tanpa verdict policy
	// tidak boleh terlihat sebagai edge yang sudah terbukti.
	const isEdgeProven = $derived(canonical?.promotion_state === 'promotable' && canonical.promotable_edge === true);
	const alasanBelum = $derived(
		canonical?.blocked_reason ||
			(!canonical
				? 'kesimpulan resmi bot belum tersedia — hasil belum boleh dipercaya'
				: !splitBeku
					? 'data uji belum dibekukan — hasil belum boleh dipercaya'
					: !ciLolos
						? 'batas bawah keyakinan masih di bawah titik impas'
						: !cukupSampel
							? `jumlah contoh ${n} < kebutuhan ${verdict?.nNeeded}`
							: n < 100
								? `jumlah contoh ${n} < 100`
								: '')
	);
</script>

<div class="permukaan-2 rounded-card border border-line p-3">
	<div class="mb-2.5 flex items-center justify-between border-b border-line-soft pb-2">
		<div>
			<h3 class="text-13 font-medium text-text">{judul}</h3>
			<p class="text-11 text-text-3">Perbandingan tingkat menang bot vs titik impas — sudah lulus pemeriksaan wajib atau belum</p>
		</div>

		{#if n > 0}
			<span
				class="rounded px-2 py-0.5 text-10 font-bold uppercase tracking-wider border {isEdgeProven
					? 'bg-pos/15 text-pos border-pos/40'
					: 'bg-warn/15 text-warn border-warn/40'}"
				title={alasanBelum || 'gate lolos: CI bawah > BE, sampel cukup, split beku'}
			>
				{isEdgeProven ? 'LAYAK DIPERCAYA' : 'BELUM LAYAK DIPERCAYA'}
			</span>
		{/if}
	</div>

	{#if n > 0}
		<div class="space-y-3">
			<div class="grid grid-cols-3 gap-2 text-center">
				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block"><Istilah k="WR">Tingkat menang</Istilah></span>
					<span class="angka text-15 font-bold {winrate > bePct ? 'text-pos' : 'text-neg'}">
						{angka(winrate)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">{win} / {n} sampel</span>
				</div>

				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block"><Istilah k="break-even">Titik impas</Istilah></span>
					<span class="angka text-15 font-bold text-text-2">
						{angka(bePct)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">ambang batas</span>
				</div>

				<div class="rounded bg-surface p-2 border border-line-soft">
					<span class="text-10 uppercase text-text-3 block"><Istilah k="ci_low">Batas bawah keyakinan</Istilah></span>
					<span class="angka text-15 font-bold {ciLow > bePct ? 'text-pos' : 'text-warn'}">
						{angka(ciLow)}%
					</span>
					<span class="text-10 text-text-3 block mt-0.5">hitungan Wilson</span>
				</div>
			</div>

			<!-- Status split ditampilkan EKSPLISIT: inilah satu-satunya alasan yang membuat
			     angka di atas belum boleh disebut "terbukti" (ADR-003). -->
			<div class="flex flex-wrap items-center gap-2 text-11">
				<span class="text-text-3">data uji:</span>
				{#if splitBeku}
					<span class="rounded border border-pos/40 bg-pos/10 px-1.5 py-0.5 font-mono text-10 text-pos">{verdict?.split}</span>
				{:else}
					<span class="rounded border border-warn/40 bg-warn/10 px-1.5 py-0.5 font-mono text-10 text-warn">belum dibekukan</span>
					<span class="text-text-3">→ hasil belum boleh dipercaya sampai dibekukan</span>
				{/if}
				{#if verdict?.nNeeded != null && !cukupSampel}
					<span class="text-text-3">· butuh ≈{verdict.nNeeded} sampel (kini {n})</span>
				{/if}
			</div>

			<!-- Visual Scale Indicator -->
			<div>
				<div class="flex justify-between text-10 text-text-3 mb-1">
					<span>BE ({angka(bePct)}%)</span>
					<span class="text-pos font-medium">Rentang Kepercayaan [{angka(ciLow)}% - {angka(ciHigh)}%]</span>
				</div>
				<div class="relative h-2 w-full rounded-full bg-surface border border-line-soft overflow-hidden">
					<!-- Threshold marker at BE -->
					<div
						class="absolute top-0 bottom-0 w-0.5 bg-warn z-10"
						style={`left: ${Math.min(95, Math.max(5, bePct))}%`}
						title={`Break Even ${bePct}%`}
					></div>
					<!-- Range of confidence interval -->
					<div
						class="absolute top-0 bottom-0 {isEdgeProven ? 'bg-pos' : 'bg-warn'} rounded-full opacity-80"
						style={`left: ${Math.min(95, Math.max(5, ciLow))}%; width: ${Math.max(4, ciHigh - ciLow)}%`}
					></div>
				</div>
				<p class="mt-1.5 text-11 text-text-3">
					{#if isEdgeProven}
						<span class="text-pos font-medium">✓ Lulus pemeriksaan:</span> batas bawah keyakinan 95% ({angka(ciLow)}%) di atas
						titik impas ({angka(bePct)}%), jumlah contoh cukup, dan data uji sudah dibekukan. Baru pada keadaan ini
						angka boleh disebut keunggulan.
					{:else}
						<span class="text-warn font-medium">⚠ Belum boleh dipercaya:</span> {alasanBelum}.
						{#if ciLolos}
							Angkanya memang sudah di atas titik impas, tapi <b>pemeriksaan wajib belum lulus</b> — halaman ini
							menampilkannya sebagai bukti berjalan, bukan kesimpulan.
						{/if}
					{/if}
				</p>
			</div>
		</div>
	{:else}
		<div class="py-4 text-center text-text-3 text-12">
			Menunggu sinkronisasi data verdict statistik...
		</div>
	{/if}
</div>
