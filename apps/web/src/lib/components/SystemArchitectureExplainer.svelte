<script lang="ts">
	/**
	 * SystemArchitectureExplainer.svelte
	 * Komponen transparansi cara kerja War Room di halaman Home.
	 * Memperlihatkan alur data ingestion, 4-gate anti-FOMO verifier, execution guard, dan notifier.
	 */
</script>

<section class="system-explainer" aria-label="Cara Kerja Sistem War Room">
	<div class="explainer-head">
		<div>
			<span class="eyebrow font-mono">ENGINE TRANSPARENCY &amp; ARCHITECTURE</span>
			<h2 class="title font-sans">Bagaimana War Room Menghasilkan Keputusan</h2>
		</div>
		<span class="badge font-mono">ANTI-FOMO 4-GATE PIPELINE</span>
	</div>

	<p class="desc font-sans">
		War Room bukan sekadar penampil grafik. Sistem ini menjalankan pipeline kuantitatif yang menyaring ribuan tick pasar menjadi sinyal berkepastian tinggi (*high conviction*), terverifikasi oleh bukti ledger nyata tanpa halusinasi AI.
	</p>

	<!-- 4-Stage Flow Diagram -->
	<div class="flow-grid font-mono">
		<div class="flow-card">
			<div class="step-num">01</div>
			<div class="step-title font-sans">Data Ingestion</div>
			<div class="step-desc font-sans">
				Mengumpulkan feed harga real-time tanpa jeda: TradingView TVC (Gold spot), OKX/Binance WS (Perp), Polymarket CLOB Gamma API, dan Broker Summary IDX.
			</div>
			<div class="step-badge">LIVE RAW TICKS</div>
		</div>

		<div class="flow-card">
			<div class="step-num">02</div>
			<div class="step-title font-sans">Quant &amp; SMC Filter</div>
			<div class="step-desc font-sans">
				Algoritma mendeteksi formasi Break &amp; Retest 15m, Likuiditas Sweeps, Pool Volatilitas, dan Akumulasi Bandarmologi. Menolak setup di tengah derau (*noise*).
			</div>
			<div class="step-badge">PATTERN RECOGNITION</div>
		</div>

		<div class="flow-card active">
			<div class="step-num">03</div>
			<div class="step-title font-sans">Statistical Gate Verification</div>
			<div class="step-desc font-sans">
				Uji 4-Gate: Hanya meloloskan kandidat dengan Win Rate historis &ge; 55% dan Expected R &gt; +0.20R. Setup yang gagal ditolak ke bayangan (*shadow log*).
			</div>
			<div class="step-badge active">PROMOTABLE EDGE</div>
		</div>

		<div class="flow-card">
			<div class="step-num">04</div>
			<div class="step-title font-sans">Execution &amp; Risk Guard</div>
			<div class="step-desc font-sans">
				Kalkulasi sizing otomatis (0.01 - 0.10 lot), penguncian batas rugi harian $200 (4% Global4Ex), audit Stand-Down news makro, dan push alert ke Telegram.
			</div>
			<div class="step-badge">PROP-FIRM COMPLIANT</div>
		</div>
	</div>

	<!-- 1001Startup Data Provenance Strip -->
	<div class="provenance-strip font-mono text-11">
		<div class="flex items-center gap-2">
			<span class="dot-prov"></span>
			<span class="text-text font-bold">PRINSIP INTEGRITAS 1001STARTUP:</span>
			<span class="text-text-3">Setiap angka di layar ditautkan ke sumber faktual dan ledger tuntas (ADR-003).</span>
		</div>
	</div>
</section>

<style>
	.system-explainer {
		background: #121314;
		border: 1px solid #232629;
		border-radius: 8px;
		padding: 1.25rem;
		margin-block: 1rem 1.5rem;
	}
	.explainer-head {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		border-bottom: 1px solid #232629;
		padding-bottom: 0.75rem;
		margin-bottom: 0.75rem;
	}
	@media (min-width: 768px) {
		.explainer-head {
			flex-direction: row;
			align-items: center;
			justify-content: space-between;
		}
	}
	.eyebrow {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: #f5b83d;
	}
	.title {
		font-size: 17px;
		font-weight: 700;
		color: #ededec;
		margin: 0;
	}
	.badge {
		font-size: 10.5px;
		font-weight: 700;
		color: #3cc76b;
		background: rgba(60, 199, 107, 0.1);
		border: 1px solid rgba(60, 199, 107, 0.25);
		border-radius: 4px;
		padding: 2px 8px;
		align-self: flex-start;
	}
	.desc {
		font-size: 13px;
		color: #a6aab0;
		line-height: 1.5;
		margin-bottom: 1.15rem;
	}
	.flow-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	@media (min-width: 640px) {
		.flow-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (min-width: 1024px) {
		.flow-grid {
			grid-template-columns: repeat(4, 1fr);
		}
	}
	.flow-card {
		background: #16181a;
		border: 1px solid #232629;
		border-radius: 6px;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		position: relative;
	}
	.flow-card.active {
		border-color: rgba(245, 184, 61, 0.4);
		background: #1b1e21;
	}
	.step-num {
		font-size: 22px;
		font-weight: 700;
		color: #787d84;
		line-height: 1;
	}
	.flow-card.active .step-num {
		color: #f5b83d;
	}
	.step-title {
		font-size: 13.5px;
		font-weight: 700;
		color: #ededec;
	}
	.step-desc {
		font-size: 11.5px;
		color: #a6aab0;
		line-height: 1.45;
		flex: 1;
	}
	.step-badge {
		font-size: 9px;
		font-weight: 700;
		color: #787d84;
		border: 1px solid #232629;
		border-radius: 3px;
		padding: 1px 5px;
		width: max-content;
		margin-top: 0.25rem;
	}
	.step-badge.active {
		color: #f5b83d;
		border-color: rgba(245, 184, 61, 0.35);
		background: rgba(245, 184, 61, 0.08);
	}
	.provenance-strip {
		margin-top: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid #232629;
	}
	.dot-prov {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #3cc76b;
	}
</style>
