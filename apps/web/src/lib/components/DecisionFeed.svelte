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

	// PENTING (6 Okt 2026): komponen ini dulu punya `DEFAULT_DECISIONS` berisi 7
	// keputusan KARANGAN, dan dirender `<DecisionFeed />` tanpa data — jadi angka
	// dan narasi palsu tampil sebagai "Live Feed". Itu melanggar aturan inti produk
	// ("UI tidak boleh mengarang angka"). Default dihapus; tanpa data, komponen
	// menyatakan kekosongan beserta alasannya.
	let { items = [] }: Props = $props();

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
				return 'bg-accent-2/15 text-accent-2 border-accent-2/30';
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
				{#if items.length > 0}
					<span class="rounded bg-pos/10 px-2 py-0.5 text-10 font-bold uppercase text-pos border border-pos/20">
						{items.length} tercatat
					</span>
				{:else}
					<span class="rounded bg-surface px-2 py-0.5 text-10 font-bold uppercase text-text-3 border border-line">
						kosong
					</span>
				{/if}
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
			<div class="py-6 text-center space-y-1">
				<p class="text-12 font-medium text-text-2">Belum ada keputusan tercatat di kategori ini.</p>
				<p class="text-11 text-text-3">
					Feed ini hanya menampilkan keputusan nyata dari ledger (paper/live). Kosong berarti
					belum ada eksekusi, veto, atau alert yang tercatat — bukan diisi contoh.
				</p>
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
							<span class="rounded px-1.5 py-0.5 bg-surface border border-line text-accent font-bold">
								{item.mode}
							</span>
						</div>
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
