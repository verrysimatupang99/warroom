<script lang="ts">
	/**
	 * BentoMetrics4Box.svelte
	 * Standard Bento 4-Box per Pasar:
	 * 1. Win Rate & Akurasi
	 * 2. Profit Factor & Return / Net R
	 * 3. Status Gate / Risk Exposure
	 * 4. Active Positions / Open Orders
	 *
	 * Memastikan konsistensi visual di Tab Cockpit/Overview seluruh pasar (Crypto, Forex, Polymarket, IDX, GMGN).
	 */
	import TrackBar from './TrackBar.svelte';
	import HonestyTag from './HonestyTag.svelte';

	interface Props {
		pasar: string;
		winRate?: number | null;
		totalTrades?: number | null;
		winRateLabel?: string;
		profitFactor?: number | null;
		netReturn?: string | number | null;
		returnLabel?: string;
		gateStatus?: 'AMAN' | 'WASPADA' | 'TERKUNCI' | string;
		gateScore?: number | null;
		gateMaxScore?: number;
		gateLabel?: string;
		activePositions?: number;
		maxPositions?: number;
		positionsDetail?: string;
	}

	let {
		pasar = '',
		winRate = null,
		totalTrades = null,
		winRateLabel = 'Win Rate (Teruji)',
		profitFactor = null,
		netReturn = null,
		returnLabel = 'Net Return / Profit',
		gateStatus = 'AMAN',
		gateScore = null,
		gateMaxScore = 6,
		gateLabel = 'Status Gate & Risiko',
		activePositions = 0,
		maxPositions = 3,
		positionsDetail = 'Posisi Terbuka'
	}: Props = $props();

	const wrPersen = $derived(winRate !== null && winRate !== undefined ? Math.round(winRate <= 1 ? winRate * 100 : winRate) : null);
	const pfAngka = $derived(profitFactor !== null && profitFactor !== undefined ? Number(profitFactor).toFixed(2) : null);
</script>

<div class="bento-grid">
	<!-- BOX 1: Win Rate & Akurasi -->
	<div class="bento-box">
		<div class="box-header">
			<span class="box-title">{winRateLabel}</span>
			<HonestyTag terverifikasi={wrPersen !== null} sumber="Kuantitatif" />
		</div>
		<div class="box-metric font-mono">
			{#if wrPersen !== null}
				<span class="text-pos">{wrPersen}%</span>
			{:else}
				<span class="text-text-3">—</span>
			{/if}
		</div>
		<div class="box-sub font-mono">
			{#if totalTrades !== null && totalTrades !== undefined}
				<span>Sampel: <b>{totalTrades}</b> trade selesai</span>
			{:else}
				<span>Sampel historis & forward paper</span>
			{/if}
		</div>
		{#if wrPersen !== null}
			<div class="mt-2">
				<TrackBar label="Akurasi" nilai={wrPersen} maks={100} nada="terkukur" />
			</div>
		{/if}
	</div>

	<!-- BOX 2: Profit Factor & Return -->
	<div class="bento-box">
		<div class="box-header">
			<span class="box-title">{returnLabel}</span>
			<span class="badge-tag">PF Kuantitatif</span>
		</div>
		<div class="box-metric font-mono">
			{#if pfAngka !== null}
				<span class="text-accent">{pfAngka} <span class="text-12 font-normal text-text-3">PF</span></span>
			{:else if netReturn !== null}
				<span class="text-accent">{netReturn}</span>
			{:else}
				<span class="text-text-3">—</span>
			{/if}
		</div>
		<div class="box-sub font-mono">
			{#if netReturn !== null && pfAngka !== null}
				<span>Net: <b>{netReturn}</b></span>
			{:else}
				<span>Target Risk/Reward ≥ 1:2.0</span>
			{/if}
		</div>
	</div>

	<!-- BOX 3: Status Gate / Risk Exposure -->
	<div class="bento-box">
		<div class="box-header">
			<span class="box-title">{gateLabel}</span>
			<span
				class="badge-pill {gateStatus === 'AMAN'
					? 'bg-pos/10 text-pos border-pos/30'
					: gateStatus === 'TERKUNCI'
						? 'bg-neg/10 text-neg border-neg/30'
						: 'bg-warn/10 text-warn border-warn/30'}"
			>
				{gateStatus}
			</span>
		</div>
		<div class="box-metric font-mono">
			{#if gateScore !== null}
				<span class="text-text">{gateScore} <span class="text-12 font-normal text-text-3">/ {gateMaxScore} lolos</span></span>
			{:else}
				<span class="text-pos text-18 font-bold">100% LOLOS</span>
			{/if}
		</div>
		<div class="box-sub">
			<span>Sizing 1.0% · SL Wajib · Rule Keras</span>
		</div>
	</div>

	<!-- BOX 4: Active Positions / Open Orders -->
	<div class="bento-box">
		<div class="box-header">
			<span class="box-title">{positionsDetail}</span>
			<span class="font-mono text-11 text-text-3">{activePositions} / {maxPositions} slot</span>
		</div>
		<div class="box-metric font-mono">
			{#if activePositions > 0}
				<span class="text-accent">{activePositions} AKTIF</span>
			{:else}
				<span class="text-text-2 text-18">0 AKTIF</span>
			{/if}
		</div>
		<div class="box-sub font-mono text-11 text-text-3">
			{#if activePositions === 0}
				<span>Standby menunggu setup terkonfirmasi</span>
			{:else}
				<span>Order paper berjalan terproteksi SL/TP</span>
			{/if}
		</div>
	</div>
</div>

<style>
	.bento-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.65rem;
		margin-bottom: 1rem;
	}
	@media (min-width: 768px) {
		.bento-grid {
			grid-template-columns: repeat(4, minmax(0, 1fr));
			gap: 0.85rem;
		}
	}
	.bento-box {
		background: var(--color-surface);
		border: 1px solid var(--color-line);
		border-radius: var(--radius-card);
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		min-height: 104px;
		font-variant-numeric: tabular-nums;
	}
	.box-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.35rem;
	}
	.box-title {
		font-size: var(--text-11);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-3);
	}
	.box-metric {
		font-size: var(--text-20);
		font-weight: 700;
		line-height: 1.2;
		color: var(--color-text);
		margin-bottom: 0.25rem;
		font-variant-numeric: tabular-nums;
	}
	.box-sub {
		font-size: var(--text-11);
		color: var(--color-text-3);
	}
	.badge-tag {
		font-size: 10px;
		font-weight: 600;
		font-family: monospace;
		padding: 1px 6px;
		border-radius: 4px;
		background: var(--color-surface-2);
		color: var(--color-text-3);
		border: 1px solid var(--color-line-soft);
	}
	.badge-pill {
		font-size: 10px;
		font-weight: 700;
		font-family: monospace;
		padding: 2px 7px;
		border-radius: 4px;
		border-width: 1px;
	}
</style>
