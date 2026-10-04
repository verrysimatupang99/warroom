<script lang="ts">
	// DecisionFeed: Aliran Keputusan & Eksekusi Real-Time (Inspirasi Fomo Family Feed).
	// Menggantikan tabel statis kaku dengan feed kronologis keputusan:
	// entry, exit, TP/SL, dan veto/penolakan gate dengan alasan bahasa manusia yang eksplisit.
	import { waktuWIB, angka } from '$lib/format';

	export interface DecisionItem {
		id: string;
		ts: string;
		jenis: 'ENTRY' | 'EXIT_TP' | 'EXIT_SL' | 'EXIT_MANUAL' | 'VETO' | 'ALERT';
		pair: string;
		venue: string;
		r?: number | null;
		judul: string;
		alasan: string;
		aturan?: string;
		friksi_pct?: number;
		mode: 'PAPER' | 'LIVE' | 'SIGNAL';
	}

	interface Props {
		items?: DecisionItem[];
	}

	const DEFAULT_DECISIONS: DecisionItem[] = [
		{
			id: 'dec-1',
			ts: '2026-10-04T17:59:40+07:00',
			jenis: 'VETO',
			pair: 'BTCUSDT',
			venue: 'Binance Futures',
			judul: 'Setup Ditolak: Struktur MTF Tidak Kompak',
			alasan: 'Screening SMC mendeteksi 4H=netral vs 1H=bullish. Gate A5 menolak order karena multi-timeframe bias berlawanan.',
			aturan: 'Gate A5 (MTF Alignment)',
			mode: 'PAPER'
		},
		{
			id: 'dec-2',
			ts: '2026-10-04T17:59:40+07:00',
			jenis: 'VETO',
			pair: 'ETHUSDT',
			venue: 'Binance Futures',
			judul: 'Setup Ditolak: Konflik Tren 4H Bearish vs 1H Bullish',
			alasan: 'Tren 4H masih dominan bearish. Menghindari long counter-trend di area resistance.',
			aturan: 'Gate A5 (Trend Alignment)',
			mode: 'PAPER'
		},
		{
			id: 'dec-3',
			ts: '2026-10-04T17:05:00+07:00',
			jenis: 'ALERT',
			pair: 'UBI (LP)',
			venue: 'Solana DEX',
			judul: 'Rekomendasi Keluar: Impermanent Loss Melampaui Batas',
			alasan: 'Impermanent loss mencapai -9.01% setelah 5.3 hari, melampaui toleransi -5.0%. Akumulasi fee $2.12 tidak cukup menutup kerugian harga.',
			aturan: 'Exit Rule: IL Max Cutoff',
			mode: 'PAPER'
		},
		{
			id: 'dec-4',
			ts: '2026-10-04T08:30:00+07:00',
			jenis: 'ALERT',
			pair: 'SAPX / WOOD',
			venue: 'Bursa Efek Indonesia',
			judul: 'Sinyal Akumulasi Screener Arjum Terdeteksi',
			alasan: 'SAPX mencetak skor multi-faktor 3.0 dengan akumulasi broker terkonfirmasi. Disimpan ke watchlist pantauan.',
			aturan: 'Arjum Screener Multi-Factor',
			mode: 'SIGNAL'
		},
		{
			id: 'dec-5',
			ts: '2026-09-26T22:48:43+07:00',
			jenis: 'EXIT_MANUAL',
			pair: 'LINK_USDT',
			venue: 'MEXC Futures',
			r: 0.844,
			judul: 'Posisi Ditutup Manual: Profit +0.844R Diamankan',
			alasan: 'TP1 di 14.242 tersentuh. 1 lot penuh ditutup di 14.25 (partial tak didukung di 1 lot terkecil). Net +$0.0374 setelah friksi fee.',
			aturan: 'Trade Management v2',
			friksi_pct: 0.02,
			mode: 'PAPER'
		},
		{
			id: 'dec-6',
			ts: '2026-09-25T01:05:42+07:00',
			jenis: 'VETO',
			pair: 'SOL_USDT',
			venue: 'MEXC Futures',
			r: 0.0,
			judul: 'Order Expired: Batas Waktu 8 Jam Tanpa Fill',
			alasan: 'Limit order di 115.0 tidak pernah tersentuh selama 8 jam (low 116.03). Order dibatalkan otomatis tanpa risiko rugi.',
			aturan: 'Expiry Limit Guard',
			mode: 'PAPER'
		},
		{
			id: 'dec-7',
			ts: '2026-09-23T13:11:00+07:00',
			jenis: 'EXIT_TP',
			pair: 'FET_USDT',
			venue: 'MEXC Futures',
			r: 0.5,
			judul: 'TP1 Hit + Runner Stop BE: Net +0.50R',
			alasan: 'TP1 di 0.2158 tercapai (+4.76%). 50% profit dilock (+0.5R). Runner SL digeser ke Breakeven (0.2060) dan tersentuh.',
			aturan: 'Breakeven Arm Rule',
			friksi_pct: 0.02,
			mode: 'PAPER'
		}
	];

	let { items = DEFAULT_DECISIONS }: Props = $props();

	let filter = $state<'ALL' | 'EKSEKUSI' | 'VETO' | 'ALERT'>('ALL');

	const filteredItems = $derived.by(() => {
		if (filter === 'ALL') return items;
		if (filter === 'EKSEKUSI') {
			return items.filter((i) => ['ENTRY', 'EXIT_TP', 'EXIT_SL', 'EXIT_MANUAL'].includes(i.jenis));
		}
		if (filter === 'VETO') {
			return items.filter((i) => i.jenis === 'VETO');
		}
		if (filter === 'ALERT') {
			return items.filter((i) => i.jenis === 'ALERT');
		}
		return items;
	});

	function badgeWarna(jenis: DecisionItem['jenis']) {
		switch (jenis) {
			case 'ENTRY':
				return 'bg-accent/15 text-accent border-accent/30';
			case 'EXIT_TP':
				return 'bg-pos/15 text-pos border-pos/30';
			case 'EXIT_SL':
				return 'bg-neg/15 text-neg border-neg/30';
			case 'EXIT_MANUAL':
				return 'bg-pos/15 text-pos border-pos/30';
			case 'VETO':
				return 'bg-warn/15 text-warn border-warn/30';
			case 'ALERT':
				return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
			default:
				return 'bg-surface text-text-3 border-line';
		}
	}
</script>

<div class="permukaan-2 rounded-card border border-line p-3" data-testid="decision-feed">
	<div class="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2">
		<div>
			<div class="flex items-center gap-2">
				<h3 class="text-14 font-bold text-text">Aliran Keputusan &amp; Eksekusi</h3>
				<span class="rounded bg-pos/10 px-2 py-0.5 text-10 font-bold uppercase text-pos border border-pos/20">
					Live Feed
				</span>
			</div>
			<p class="text-11 text-text-3 mt-0.5">
				Feed kronologis keputusan trading: eksekusi, exit, dan alasan penolakan gate (Veto)
			</p>
		</div>

		<!-- Filter Buttons (Touch Friendly) -->
		<div class="flex items-center gap-1 rounded bg-surface p-1 border border-line">
			<button
				type="button"
				class="rounded px-2.5 py-1 text-11 font-medium transition-colors {filter === 'ALL' ? 'bg-bg-2 text-text font-bold shadow-sm' : 'text-text-3 hover:text-text'}"
				onclick={() => (filter = 'ALL')}
			>
				Semua
			</button>
			<button
				type="button"
				class="rounded px-2.5 py-1 text-11 font-medium transition-colors {filter === 'EKSEKUSI' ? 'bg-bg-2 text-text font-bold shadow-sm' : 'text-text-3 hover:text-text'}"
				onclick={() => (filter = 'EKSEKUSI')}
			>
				Eksekusi
			</button>
			<button
				type="button"
				class="rounded px-2.5 py-1 text-11 font-medium transition-colors {filter === 'VETO' ? 'bg-bg-2 text-text font-bold shadow-sm' : 'text-text-3 hover:text-text'}"
				onclick={() => (filter = 'VETO')}
			>
				Veto Gate
			</button>
			<button
				type="button"
				class="rounded px-2.5 py-1 text-11 font-medium transition-colors {filter === 'ALERT' ? 'bg-bg-2 text-text font-bold shadow-sm' : 'text-text-3 hover:text-text'}"
				onclick={() => (filter = 'ALERT')}
			>
				Alert
			</button>
		</div>
	</div>

	<!-- Feed Stream -->
	<div class="space-y-2.5">
		{#if filteredItems.length === 0}
			<div class="py-6 text-center text-text-3 text-12">
				Tidak ada aktivitas keputusan pada kategori ini.
			</div>
		{:else}
			{#each filteredItems as item (item.id)}
				<div class="rounded-card border border-line-soft bg-surface p-3 transition-colors hover:border-line">
					<div class="flex flex-wrap items-center justify-between gap-2 mb-1.5">
						<div class="flex items-center gap-2">
							<span class="rounded px-2 py-0.5 text-10 font-bold uppercase border {badgeWarna(item.jenis)}">
								{item.jenis.replace('_', ' ')}
							</span>
							<span class="font-bold text-13 font-mono text-text">{item.pair}</span>
							<span class="text-11 text-text-3 font-mono">({item.venue})</span>
						</div>

						<div class="flex items-center gap-2 text-11">
							{#if item.r != null}
								<span class="angka font-bold {item.r >= 0 ? 'text-pos' : 'text-neg'} text-12">
									{item.r >= 0 ? '+' : ''}{angka(item.r)} R
								</span>
							{/if}
							<span class="text-10 font-mono text-text-3">{waktuWIB(item.ts)}</span>
						</div>
					</div>

					<h4 class="text-12 font-medium text-text-2 mb-1">{item.judul}</h4>
					<p class="text-11 text-text-3 leading-relaxed">{item.alasan}</p>

					<div class="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line-soft pt-1.5 text-10 text-text-3 font-mono">
						{#if item.aturan}
							<span class="rounded bg-canvas px-1.5 py-0.5 border border-line-soft text-text-2">
								{item.aturan}
							</span>
						{/if}
						<div class="flex items-center gap-2">
							{#if item.friksi_pct != null}
								<span>Friksi: ~{item.friksi_pct}%</span>
							{/if}
							<span class="rounded px-1.5 py-0.2 bg-surface border border-line text-accent font-bold">
								{item.mode}
							</span>
						</div>
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
