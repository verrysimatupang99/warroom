<script lang="ts">
	/**
	 * Ringkas per-PAIR forex (7 Okt): XAUUSD (SMC 4-agen), NAS100 & EURUSD (FVG/OB 1H)
	 * punya watak berbeda — menampilkannya sebagai satu blok membuat halaman terasa kosong.
	 * Angka dari fakta `forex_sinyal.per_pair` (mesin pasar.py), bukan hitungan UI.
	 */
	interface Pair {
		pair: string;
		strategi?: string | null;
		n_sinyal?: number;
		n_tuntas?: number;
		menang?: number;
		total_r?: number;
		winrate_pct?: number | null;
		mean_r?: number | null;
		terakhir?: string | null;
		status_terakhir?: string | null;
		arah_terakhir?: string | null;
	}

	interface Props {
		data?: { per_pair?: Record<string, Pair>; tersedia?: boolean } | null;
	}

	let { data }: Props = $props();
	const baris = $derived(Object.values(data?.per_pair ?? {}));

	const kelasStatus = (s: string | null | undefined) => {
		const t = String(s ?? '').toLowerCase();
		if (t.includes('tp') || t.includes('win')) return 'text-pos bg-pos/10 border-pos/20';
		if (t.includes('sl') || t.includes('loss')) return 'text-neg bg-neg/10 border-neg/20';
		if (t.includes('active') || t.includes('jalan')) return 'text-accent bg-accent/10 border-accent/20';
		return 'text-text-3 bg-canvas border-line';
	};

	function waktu(iso: string | null | undefined): string {
		if (!iso) return '—';
		// Jurnal memakai format "2026-10-06T21:00:09+07:00" maupun "2026-10-06 13:32"
		const t = iso.replace(' ', 'T');
		const d = new Date(t);
		if (Number.isNaN(d.getTime())) return iso.slice(0, 16);
		return new Intl.DateTimeFormat('id-ID', {
			timeZone: 'Asia/Jakarta', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false
		}).format(d);
	}
</script>

{#if baris.length}
	<div class="permukaan-2 rounded-card border border-line p-3">
		<div class="mb-3 border-b border-line-soft pb-2">
			<h3 class="text-14 font-medium text-text">Ringkas per Pair</h3>
			<p class="text-11 text-text-3">
				XAUUSD = SMC 4-agen (struktur + berita + risiko) · NAS100/EURUSD = SMC zona FVG/OB 1H
			</p>
		</div>
		<div class="overflow-x-auto">
			<table class="w-full text-left text-12 font-mono">
				<thead class="border-b border-line text-text-3 text-10 uppercase">
					<tr>
						<th class="py-1.5 px-1.5">Pair</th>
						<th class="py-1.5 px-1.5">Strategi</th>
						<th class="py-1.5 px-1.5 text-right">Sinyal</th>
						<th class="py-1.5 px-1.5 text-right">Tuntas</th>
						<th class="py-1.5 px-1.5 text-right">WR</th>
						<th class="py-1.5 px-1.5 text-right">Mean R</th>
						<th class="py-1.5 px-1.5 text-right">Total R</th>
						<th class="py-1.5 px-1.5">Terakhir</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line-soft">
					{#each baris as p (p.pair)}
						<tr class="hover:bg-surface/50 transition-colors">
							<td class="py-1.5 px-1.5 font-bold text-text">{p.pair}</td>
							<td class="py-1.5 px-1.5 text-text-3">{p.strategi ?? '—'}</td>
							<td class="py-1.5 px-1.5 text-right text-text-2">{p.n_sinyal ?? '—'}</td>
							<td class="py-1.5 px-1.5 text-right text-text-2">{p.n_tuntas ?? 0}</td>
							<td class="py-1.5 px-1.5 text-right {p.winrate_pct != null && p.winrate_pct >= 50 ? 'text-pos' : 'text-text-3'}">
								{p.winrate_pct != null ? `${p.winrate_pct}%` : '—'}
							</td>
							<td class="py-1.5 px-1.5 text-right {p.mean_r != null && p.mean_r > 0 ? 'text-pos' : p.mean_r != null && p.mean_r < 0 ? 'text-neg' : 'text-text-3'}">
								{p.mean_r != null ? `${p.mean_r > 0 ? '+' : ''}${p.mean_r}` : '—'}
							</td>
							<td class="py-1.5 px-1.5 text-right {p.total_r != null && p.total_r > 0 ? 'text-pos' : p.total_r != null && p.total_r < 0 ? 'text-neg' : 'text-text-3'}">
								{(p.total_r ?? 0) > 0 ? '+' : ''}{(p.total_r ?? 0).toFixed(2)}R
							</td>
							<td class="py-1.5 px-1.5 whitespace-nowrap text-text-3">
								<span class="text-10">{waktu(p.terakhir)}</span>
								<span class="ml-1 rounded border px-1 py-0.5 text-10 {kelasStatus(p.status_terakhir)}">{p.status_terakhir ?? '—'}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="mt-2 text-10 text-text-3">
			"Tuntas" = trade yang benar-benar terisi & selesai. Order yang dibatalkan/tak terisi dilaporkan di tabel sinyal, tidak dihitung.
		</p>
	</div>
{/if}
