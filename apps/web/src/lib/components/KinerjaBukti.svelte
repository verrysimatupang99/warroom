<script lang="ts">
	/**
	 * Kinerja & Bukti — halaman yang menjawab SATU pertanyaan:
	 * "boleh percaya angka ini atau tidak?"
	 *
	 * Temuan audit QA putaran 3: War Room paling jujur tetapi paling sulit dijual karena
	 * bukti tersebar — pembaca harus membuka tiap pasar untuk tahu apakah angkanya
	 * (a) dari trade tuntas atau kandidat, (b) sudah termasuk biaya atau bruto,
	 * (c) periode berapa, dan (d) berapa denominatornya.
	 *
	 * Halaman ini menaruh tujuh jawaban itu BERDAMPINGAN untuk semua pasar:
	 *   closed trades · win rate · total R · PnL · drawdown · biaya · periode + denominator.
	 *
	 * Aturan yang dipatuhi: angka hanya dari fakta; yang tidak diketahui ditulis "—",
	 * bukan 0. Populasi (denominator) WAJIB disebut di tiap baris — pelajaran dari
	 * temuan "n=12 vs n=16" pada audit sebelumnya.
	 */
	import type { PasarRingkasPayload, ResearchRunDetail, ResearchRunSummary } from '$lib/api/types';
	import { getResearchRun } from '$lib/api/client';
	import { angka, umurDetik } from '$lib/format';

	interface Props {
		/** Payload /api/v1/pasar/ringkas (berisi blok `bukti` per pasar). */
		akurasi?: PasarRingkasPayload | null;
		/** Umur data (detik) untuk keterangan kesegaran; null = tidak diketahui. */
		umurData?: number | null;
		/** Latest immutable research registrations, if available. */
		risetRuns?: ResearchRunSummary[];
	}
	let { akurasi = null, umurData = null, risetRuns = [] }: Props = $props();
	let detail = $state<ResearchRunDetail | null>(null);
	let detailLoading = $state(false);
	let detailError = $state<string | null>(null);

	async function bukaDetail(id: string) {
		detailLoading = true;
		detailError = null;
		try {
			detail = await getResearchRun(id);
		} catch (err) {
			detail = null;
			detailError = err instanceof Error ? err.message : String(err);
		} finally {
			detailLoading = false;
		}
	}

	interface Bukti {
		closed_trades?: number | null;
		win_rate_pct?: number | null;
		mean_r?: number | null;
		total_r?: number | null;
		pnl_usd?: number | null;
		max_drawdown_r?: number | null;
		biaya_tercatat?: boolean | null;
		biaya_keterangan?: string;
		periode?: { dari?: string | null; sampai?: string | null };
		denominator?: string;
		n_hari?: number | null;
		tingkat?: string | null;
		sumber?: string | null;
	}

	const LABEL: Record<string, string> = {
		crypto: 'Crypto (SMC)',
		idx: 'IDX',
		forex: 'Forex',
		gmgn: 'GMGN / LP',
		polymarket: 'Polymarket'
	};

	// Urutan tetap supaya pembaca membandingkan pasar yang sama antar-kunjungan.
	const URUTAN = ['crypto', 'idx', 'forex', 'gmgn', 'polymarket'];

	const baris = $derived.by(() => {
		const pasar = (akurasi?.pasar ?? {}) as Record<string, { bukti?: Bukti; tersedia?: boolean }>;
		return URUTAN.map((k) => ({ kunci: k, label: LABEL[k] ?? k, bukti: pasar[k]?.bukti ?? null }));
	});

	// Ringkasan satu baris: berapa pasar yang punya bukti, berapa yang brutto.
	const ringkas = $derived.by(() => {
		const ada = baris.filter((b) => (b.bukti?.closed_trades ?? 0) > 0);
		const bruto = baris.filter((b) => b.bukti?.biaya_tercatat === false);
		return { jumlah: ada.length, bruto: bruto.map((b) => b.label) };
	});

	const nf = (v: number | null | undefined, dp = 2, tanda = false) =>
		v == null ? '—' : `${tanda && v > 0 ? '+' : ''}${angka(v, { desimal: dp })}`;

</script>

<div class="kepala">
	<div>
		<h1>Kinerja &amp; Bukti</h1>
		<p class="dim">
			Semua pasar, satu tabel: berapa trade tuntas, seberapa akurat, berapa hasilnya, dan
			<b>apakah biayanya sudah dihitung</b>. Populasi (denominator) disebut di tiap baris —
			angka dari trade tuntas tidak boleh dibandingkan dengan angka dari kandidat.
		</p>
	</div>
	{#if umurData != null}
		<span class="umur">data {umurDetik(umurData)} lalu</span>
	{/if}
</div>

{#if akurasi}
	<div class="ringkas">
		<span>
			<b class="angka">{ringkas.jumlah}</b> dari {baris.length} pasar punya trade tuntas.
			{#if ringkas.bruto.length}
				<span class="bruto">⚠ {ringkas.bruto.join(' & ')} masih <b>BRUTO</b> (biaya belum tercatat)</span>
			{/if}
		</span>
	</div>

	<div class="bungkus">
		<table class="tabel">
			<thead>
				<tr>
					<th>Pasar</th>
					<th class="ka">Trade tuntas</th>
					<th class="ka">Win rate</th>
					<th class="ka">Total R</th>
					<th class="ka">PnL</th>
					<th class="ka">Drawdown</th>
					<th>Biaya</th>
					<th>Periode</th>
				</tr>
			</thead>
			<tbody>
				{#each baris as b (b.kunci)}
					{@const bk = b.bukti}
					<tr class:kosong={!bk?.closed_trades}>
						<td class="nama">
							{b.label}
							{#if bk?.tingkat}
								<span class="pakem pakem-{bk.tingkat}">{bk.tingkat}</span>
							{/if}
						</td>
						<td class="ka angka">{bk?.closed_trades ?? '—'}</td>
						<td class="ka angka">{bk?.win_rate_pct != null ? `${angka(bk.win_rate_pct)}%` : '—'}</td>
						<td class="ka angka {bk?.total_r != null && bk.total_r > 0 ? 'pos' : bk?.total_r != null && bk.total_r < 0 ? 'neg' : ''}">
							{nf(bk?.total_r, 2, true)}
						</td>
						<td class="ka angka {bk?.pnl_usd != null && bk.pnl_usd > 0 ? 'pos' : bk?.pnl_usd != null && bk.pnl_usd < 0 ? 'neg' : ''}">
							{bk?.pnl_usd != null ? `${nf(bk.pnl_usd, 2, true)} USD` : '—'}
						</td>
						<td class="ka angka">{bk?.max_drawdown_r != null ? `${angka(bk.max_drawdown_r)} R` : '—'}</td>
						<td>
							{#if bk?.biaya_tercatat === true}
								<span class="biaya ok" title={bk.biaya_keterangan ?? ''}>net biaya</span>
							{:else if bk?.biaya_tercatat === false}
								<span class="biaya brutto" title={bk.biaya_keterangan ?? ''}>BRUTO</span>
							{:else}
								<span class="biaya tidak" title={bk?.biaya_keterangan ?? ''}>tidak diketahui</span>
							{/if}
						</td>
						<td class="angka dim">
							{#if bk?.periode?.dari && bk?.periode?.sampai}
								{bk.periode.dari} → {bk.periode.sampai}
								{#if bk.n_hari != null}<span class="hari">({bk.n_hari} hari)</span>{/if}
							{:else}
								—
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="riset-contracts">
		<h2>Research registrations</h2>
		<p class="dim">Contract fingerprint, status, dan provenance. Ini registrasi riset—bukan bukti profit atau signal live.</p>
		{#if risetRuns.length}
			{#each risetRuns as run (run.id)}
				<article class="riset-run">
					<div class="run-head"><b>{run.research_key}</b><span class="pakem">{run.status}</span></div>
					<div class="run-meta"><span>hypothesis <code>{run.hypothesis_hash.slice(0, 12)}…</code></span><span>execution <code>{run.execution_hash.slice(0, 12)}…</code></span></div>
					<div class="run-meta dim"><span>{run.created_at ?? '—'}</span><button type="button" class="detail-button" onclick={() => void bukaDetail(run.id)}>lihat evidence detail</button></div>
				</article>
			{/each}
		{:else}
			<p class="dim">Belum ada research registration yang tercatat.</p>
		{/if}

		{#if detailLoading}
			<div class="evidence-detail" aria-live="polite">Memuat evidence detail…</div>
		{:else if detailError}
			<div class="evidence-detail blocked" role="alert">Evidence detail tidak dapat dimuat: {detailError}</div>
		{:else if detail}
			<section class="evidence-detail" aria-label="Evidence detail">
				<div class="run-head"><h3>{detail.research_key}</h3><span class="pakem">{detail.status}</span></div>
				<div class="fingerprints">
					<span>hypothesis <code>{detail.hypothesis_hash}</code></span>
					<span>execution <code>{detail.execution_hash}</code></span>
				</div>
				<p class:blocked={detail.evidence_status === 'blocked'}>
					Evidence: <b>{detail.evidence_status}</b>{#if detail.blocked_reason} — {detail.blocked_reason}{/if}
				</p>
				<p class="dim">Provenance run: <code>{JSON.stringify(detail.provenance)}</code></p>
				{#if detail.artifacts.length}
					<ul class="artifact-list">
						{#each detail.artifacts as artifact (artifact.id)}
							<li><b>{artifact.kind}</b> <code>{artifact.sha256}</code><span class="dim">{artifact.status} · {artifact.uri}</span><small>provenance: {JSON.stringify(artifact.provenance)}</small></li>
						{/each}
					</ul>
				{:else}
					<p class="blocked">No artifact records. This run is not evidence-backed.</p>
				{/if}
			</section>
		{/if}
	</div>

	<div class="catatan">
		<h2>Yang harus dibaca sebelum menyimpulkan</h2>
		<ul>
			<li>
				<b>Denominator:</b> {baris[0]?.bukti?.denominator ?? 'trade TUNTAS di ledger'}.
				Baris <span class="mono">expired</span> (order tak pernah terisi) tidak dihitung,
				dan kandidat aktif bukan trade.
			</li>
			<li>
				<b>R tidak bisa dibandingkan antar-pasar.</b> 1R crypto ≠ 1R IDX. Yang bisa
				dibandingkan adalah saldo dompet dengan risiko yang sama (halaman Riset → Kinerja).
			</li>
			<li>
				<b>PnL absolut bukan return on capital.</b> Ia belum memperhitungkan modal,
				margin, dan leverage. Untuk itu lihat drawdown dan jumlah trade.
			</li>
			<li>
				<b>Pakem sampel:</b> INSUFFICIENT &lt;10 hari · DIRECTIONAL &lt;30 ·
				PRELIMINARY &lt;100 · TUNING ≥100. Selama INSUFFICIENT, angka ditampilkan tetapi
				belum boleh dipakai mengambil keputusan.
			</li>
			<li>
				<b>Semua jalur masih PAPER.</b> Tidak ada order yang dikirim ke bursa; yang
				dinilai adalah perilaku mesin, bukan hasil uang nyata.
			</li>
		</ul>
	</div>
{/if}

<style>
	.kepala {
		display: flex; align-items: flex-start; justify-content: space-between;
		gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem;
	}
	.kepala h1 { margin: 0; font-family: var(--font-display); font-size: var(--text-24); letter-spacing: -0.02em; }
	.kepala p { margin: 0.2rem 0 0; font-size: var(--text-12); max-width: 52rem; }
	.umur { font-size: var(--text-11); color: var(--color-text-3); white-space: nowrap; }

	.ringkas {
		border: 1px solid var(--color-line); border-radius: var(--radius-card);
		background: var(--color-surface); padding: 0.6rem 0.8rem; font-size: var(--text-12);
		margin-bottom: 0.75rem;
	}
	.ringkas .bruto { color: var(--color-warn); margin-left: 0.4rem; }

	.bungkus { overflow-x: auto; border: 1px solid var(--color-line); border-radius: var(--radius-card); background: var(--color-surface); }
	.tabel { width: 100%; border-collapse: collapse; font-size: var(--text-12); }
	.tabel th {
		text-align: left; font-weight: 500; color: var(--color-text-3);
		padding: 0.6rem 0.7rem; border-bottom: 1px solid var(--color-line); white-space: nowrap;
	}
	.tabel td { padding: 0.55rem 0.7rem; border-bottom: 1px solid var(--color-line); vertical-align: middle; }
	.tabel tr:last-child td { border-bottom: none; }
	.tabel tr.kosong { opacity: 0.6; }
	.ka { text-align: right; }
	.nama { font-weight: 600; white-space: nowrap; }
	.pos { color: var(--color-accent); }
	.neg { color: var(--color-neg); }
	.dim { color: var(--color-text-3); }
	.mono { font-family: var(--font-mono); }
	.hari { color: var(--color-text-3); }

	.pakem {
		margin-left: 0.35rem; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.03em;
		border: 1px solid var(--color-line); border-radius: 0.35rem; padding: 0 0.3rem;
		color: var(--color-text-3);
	}
	.pakem-INSUFFICIENT { color: var(--color-neg); border-color: var(--color-neg); }
	.pakem-DIRECTIONAL { color: var(--color-warn); border-color: var(--color-warn); }
	.pakem-PRELIMINARY { color: var(--color-accent); border-color: var(--color-accent); }
	.pakem-TUNING { color: var(--color-text); }

	.biaya { font-size: 0.62rem; font-weight: 700; border: 1px solid var(--color-line); border-radius: 0.35rem; padding: 0 0.3rem; white-space: nowrap; }
	.biaya.ok { color: var(--color-accent); border-color: var(--color-accent); }
	.biaya.brutto { color: var(--color-warn); border-color: var(--color-warn); }
	.biaya.tidak { color: var(--color-text-3); border-style: dashed; }

	.riset-contracts {
		margin-top: 1rem; border: 1px solid var(--color-line); border-radius: var(--radius-card);
		background: var(--color-surface); padding: 0.8rem 0.9rem;
	}
	.riset-contracts h2 { margin: 0; font-size: var(--text-13); }
	.riset-contracts > p { margin: 0.3rem 0 0.7rem; font-size: var(--text-12); }
	.riset-run { border-top: 1px solid var(--color-line); padding: 0.55rem 0; }
	.run-head, .run-meta { display: flex; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
	.run-meta { margin-top: 0.25rem; font-size: var(--text-11); }
	.run-meta code { font-family: var(--font-mono); }

	.riset-run { border-top: 1px solid var(--color-line); padding: 0.65rem 0; }
	.detail-button { border: 1px solid var(--color-line); border-radius: 0.35rem; background: var(--color-surface); color: var(--color-text); padding: 0.25rem 0.45rem; cursor: pointer; }
	.evidence-detail { margin-top: 0.8rem; border: 1px solid var(--color-line); border-radius: var(--radius-card); padding: 0.8rem; background: var(--color-surface); }
	.evidence-detail h3 { margin: 0; }
	.fingerprints { display: grid; gap: 0.35rem; margin: 0.6rem 0; overflow-wrap: anywhere; }
	.artifact-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.6rem; }
	.artifact-list li { display: grid; gap: 0.15rem; border-top: 1px solid var(--color-line); padding-top: 0.5rem; overflow-wrap: anywhere; }
	.blocked { color: var(--color-warn); }

	.catatan {
		margin-top: 1rem; border: 1px solid var(--color-line); border-radius: var(--radius-card);
		background: var(--color-surface); padding: 0.8rem 0.9rem;
	}
	.catatan h2 { margin: 0 0 0.5rem; font-size: var(--text-13); }
	.catatan ul { margin: 0; padding-left: 1.1rem; display: flex; flex-direction: column; gap: 0.35rem; }
	.catatan li { font-size: var(--text-12); color: var(--color-text-2, var(--color-text)); }
</style>
