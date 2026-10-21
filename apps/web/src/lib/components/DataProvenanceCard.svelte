<script lang="ts">
	/**
	 * DataProvenanceCard.svelte
	 * Terinspirasi dari filosofi 1001startup.id ("Every figure linked to its source").
	 * Menampilkan transparansi asal sumber data per pasar secara eksplisit, terverifikasi,
	 * dan bebas klaim palsu (ADR-003).
	 */
	interface Props {
		pasar: string;
		sumber: string;
		keterangan?: string;
		frekuensi?: string;
		metode?: string;
		tautan?: string | null;
	}

	let {
		pasar,
		sumber,
		keterangan = 'Feed resmi terhubung langsung ke mesin audit War Room.',
		frekuensi = 'Real-time / 15m bar',
		metode = 'REST / WebSocket Snapshot',
		tautan = null
	}: Props = $props();
</script>

<div class="provenance-card">
	<div class="prov-header">
		<div class="flex items-center gap-2">
			<span class="prov-dot"></span>
			<span class="prov-label font-mono">SUMBER DATA TERVERIFIKASI · {pasar.toUpperCase()}</span>
		</div>
		<span class="prov-badge font-mono">{sumber}</span>
	</div>

	<p class="prov-desc">
		{keterangan}
	</p>

	<div class="prov-meta font-mono">
		<div class="meta-item">
			<span class="meta-k">Frekuensi:</span>
			<span class="meta-v">{frekuensi}</span>
		</div>
		<div class="meta-item">
			<span class="meta-k">Protokol:</span>
			<span class="meta-v">{metode}</span>
		</div>
		<div class="meta-item">
			<span class="meta-k">Integritas:</span>
			<span class="meta-v text-pos">ADR-003 SSOT</span>
		</div>
	</div>
</div>

<style>
	.provenance-card {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.85rem 1.15rem;
		margin-top: 1rem;
		margin-bottom: 1rem;
	}
	.prov-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.4rem;
	}
	.prov-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background-color: var(--color-pos);
		box-shadow: 0 0 6px var(--color-pos);
	}
	.prov-label {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--color-text-3);
	}
	.prov-badge {
		font-size: 11px;
		font-weight: 600;
		color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--color-accent) 25%, transparent);
		border-radius: 4px;
		padding: 2px 8px;
	}
	.prov-desc {
		font-size: 12px;
		color: var(--color-text-2);
		line-height: 1.45;
		margin-bottom: 0.65rem;
	}
	.prov-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 1.25rem;
		font-size: 11px;
		border-top: 1px solid var(--color-line-soft);
		padding-top: 0.5rem;
	}
	.meta-item {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.meta-k {
		color: var(--color-text-3);
	}
	.meta-v {
		font-weight: 600;
		color: var(--color-text);
	}
</style>
