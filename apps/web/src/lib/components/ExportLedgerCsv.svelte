<script lang="ts">
	/**
	 * ExportLedgerCsv.svelte
	 * Tombol satu klik ekspor rekaman ledger & verdict ke CSV (Standar Awesome-Omni-Skills).
	 * Memungkinkan audit kuantitatif independen di Excel, Pandas, atau R.
	 */
	interface Props {
		pasar: string;
		entries: any[];
	}
	let { pasar, entries = [] }: Props = $props();

	function downloadCsv() {
		if (!entries || !entries.length) {
			alert('Belum ada data transaksi ledger untuk diekspor.');
			return;
		}

		const headers = ['Timestamp', 'Pair', 'Direction', 'Status', 'Entry', 'Exit', 'R_Multiple', 'Note'];
		const rows = entries.map((e) => [
			e.closed_at || e.logged_at || e.ts || '',
			e.pair || '',
			e.direction || '',
			e.status || '',
			e.entry ?? '',
			e.exit ?? '',
			e.r ?? '',
			`"${(e.note || e.alasan || '').replace(/"/g, '""')}"`
		]);

		const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
		const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.setAttribute('href', url);
		link.setAttribute('download', `warroom_${pasar}_ledger_${new Date().toISOString().slice(0, 10)}.csv`);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}
</script>

<button 
	type="button" 
	class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-2 border border-line hover:border-accent text-11 font-mono text-text hover:text-accent transition-colors cursor-pointer"
	onclick={downloadCsv}
	title="Unduh seluruh riwayat trade untuk audit kuantitatif"
>
	<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
		<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
		<polyline points="7 10 12 15 17 10"></polyline>
		<line x1="12" y1="15" x2="12" y2="3"></line>
	</svg>
	<span>Unduh Ledger (.CSV)</span>
</button>
