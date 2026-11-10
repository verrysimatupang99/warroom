<script lang="ts">
	import Ikon from '$lib/components/Ikon.svelte';

	interface Props {
		marketTitle: string;
		category?: string;
		eta?: string;
		detail?: string;
	}

	let {
		marketTitle = 'Pasar Ini',
		category = 'PENGEMBANGAN SISTEM',
		eta = 'Pasca Stabilitas Forex',
		detail = 'Sistem sedang difokuskan 100% pada eksekusi dan validasi Pasar Gold & Forex (XAUUSD) Exness Demo. Integrasi modul ini sementara ditangguhkan agar alokasi modal dan pemantauan terpusat penuh (mode formula, Laya nonaktif).'
	}: Props = $props();
</script>

<div class="under-construction-wrap font-sans">
	<div class="banner-border">
		<!-- Header status strip -->
		<div class="status-strip font-mono">
			<div class="flex items-center gap-2">
				<span class="w-2 h-2 rounded-full bg-warn animate-pulse"></span>
				<span class="text-11 font-bold text-warn tracking-wider">UNDER CONSTRUCTION // {category}</span>
			</div>
			<span class="text-11 text-text-3 font-mono">FASE: FOREX CONVERGENCE</span>
		</div>

		<!-- Main Card Content -->
		<div class="content-body">
			<div class="icon-bubble">
				<Ikon nama="mesin" ukuran={32} />
			</div>

			<div class="text-center max-w-xl mx-auto space-y-3">
				<div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-warn/30 bg-warn/10 text-warn font-mono text-11">
					<span>🚧</span>
					<span>Fokus Saat Ini: Live Forex &amp; Gold Execution</span>
				</div>

				<h2 class="text-22 sm:text-26 font-bold text-text tracking-tight font-display">
					{marketTitle} Sedang Dalam Pengerjaan
				</h2>

				<p class="text-14 leading-relaxed text-text-2">
					{detail}
				</p>
			</div>

			<!-- Forex Quick Switch Box -->
			<div class="forex-switch-box">
				<div class="flex flex-col sm:flex-row items-center justify-between gap-4">
					<div class="flex items-center gap-3">
						<div class="w-10 h-10 rounded-control border border-accent/40 bg-accent/10 flex items-center justify-center text-accent">
							<Ikon nama="forex" ukuran={20} />
						</div>
						<div>
							<div class="text-13 font-bold text-text font-display">Pasar Aktif: Gold &amp; Forex (XAUUSD)</div>
							<div class="text-11 text-text-3 font-mono">Exness Demo #416510164 • Modal: $456.98 USD • Mode formula (Laya nonaktif)</div>
						</div>
					</div>

					<a 
						href="/forex" 
						class="target-44 inline-flex items-center gap-2 px-5 py-2.5 rounded-control font-mono font-bold text-12 bg-accent text-surface hover:brightness-110 shadow-lg shadow-accent/20 transition-all"
					>
						<span>Buka Terminal Forex</span>
						<span>→</span>
					</a>
				</div>
			</div>

			<!-- Technical Milestones -->
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-line/60">
				<div class="milestone-card">
					<div class="text-10 font-mono text-text-3 uppercase tracking-wider">Status Modul</div>
					<div class="text-13 font-bold text-warn mt-1 font-mono">Standby / Paused</div>
				</div>
				<div class="milestone-card">
					<div class="text-10 font-mono text-text-3 uppercase tracking-wider">Prioritas Eksekusi</div>
					<div class="text-13 font-bold text-text mt-1 font-mono">Forex &amp; XAUUSD (Tier 1)</div>
				</div>
				<div class="milestone-card">
					<div class="text-10 font-mono text-text-3 uppercase tracking-wider">Rencana Rilis</div>
					<div class="text-13 font-bold text-text-2 mt-1 font-mono">{eta}</div>
				</div>
			</div>
		</div>
	</div>
</div>

<style>
	.under-construction-wrap {
		padding: 1.5rem 1rem;
		max-width: 900px;
		margin: 2rem auto;
	}

	.banner-border {
		border: 1px solid var(--line);
		border-radius: var(--radius-card, 8px);
		background: var(--surface);
		overflow: hidden;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
	}

	.status-strip {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.625rem 1rem;
		background: var(--surface-2);
		border-bottom: 1px solid var(--line);
	}

	.content-body {
		padding: 2.5rem 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2rem;
	}

	.icon-bubble {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--surface-2);
		border: 1px dashed var(--line);
		color: var(--text-2);
	}

	.forex-switch-box {
		width: 100%;
		max-width: 650px;
		padding: 1rem 1.25rem;
		border-radius: var(--radius-control, 6px);
		border: 1px solid var(--line);
		background: var(--surface-2);
	}

	.milestone-card {
		padding: 0.75rem 1rem;
		background: var(--surface-2);
		border-radius: var(--radius-control, 6px);
		border: 1px solid var(--line);
	}
</style>
