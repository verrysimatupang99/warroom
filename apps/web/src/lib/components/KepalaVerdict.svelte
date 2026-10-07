<script lang="ts">
	/**
	 * KepalaVerdict — headline keputusan di paling atas halaman pasar.
	 *
	 * Audit QA 7 Okt (prioritas 2): "Tambahkan di setiap halaman: Keputusan: boleh
	 * dipantau / paper-only / jangan dipromosikan / sumber basi / model breach. Satu
	 * kalimat. Di paling atas."
	 *
	 * Komponen ini TIDAK menghitung apa pun — ia merender verdict kanonik dari backend
	 * (`/api/v1/verdict`). Jadi tidak mungkin lagi kartu di halaman ini bilang "terbukti"
	 * sementara bagian gate di bawahnya bilang "belum lolos".
	 */
	import type { VerdictPasar } from '$lib/api/types';

	interface Props {
		verdict?: VerdictPasar | null;
	}
	let { verdict = null }: Props = $props();

	// Nada visual ditentukan backend (promotion/risk/execution state), bukan ditebak UI.
	const nada = $derived.by(() => {
		if (!verdict) return 'netral';
		if (verdict.execution_state === 'frozen') return 'beku';
		if (verdict.risk_state === 'breach') return 'breach';
		if (verdict.promotion_state === 'promotable') return 'lolos';
		if (verdict.signal_state === 'none') return 'diam';
		return 'kandidat';
	});

	const labelState: { k: string; t: string }[] = $derived.by(() => {
		if (!verdict) return [];
		return [
			{ k: 'Sinyal', t: verdict.signal_state },
			{ k: 'Bukti', t: verdict.evidence_state },
			{ k: 'Risiko', t: verdict.risk_state },
			{ k: 'Eksekusi', t: verdict.execution_state },
			{ k: 'Promosi', t: verdict.promotion_state }
		];
	});
</script>

{#if verdict}
	<section class="kepala-verdict nada-{nada}" aria-live="polite">
		<div class="baris-utama">
			<h2 class="headline">{verdict.headline}</h2>
			<div class="state">
				{#each labelState as s (s.k)}
					<span class="chip" class:chip-risiko={s.k === 'Risiko' && verdict.risk_state === 'breach'}
						class:chip-promosi={s.k === 'Promosi' && verdict.promotion_state === 'promotable'}>
						<span class="chip-k">{s.k}</span>
						<span class="chip-t">{s.t}</span>
					</span>
				{/each}
			</div>
		</div>
		<p class="keputusan">{verdict.decision}</p>
		{#if verdict.blocked_reason}
			<p class="alasan"><b>Kenapa belum bisa dipromosikan:</b> {verdict.blocked_reason}</p>
		{/if}
	</section>
{/if}

<style>
	.kepala-verdict {
		border: 1px solid var(--color-line);
		border-left-width: 3px;
		border-radius: var(--radius-card);
		background: var(--color-surface);
		padding: 0.7rem 0.85rem;
		margin-bottom: 0.85rem;
	}
	.nada-kandidat { border-left-color: var(--color-warn); }
	.nada-breach { border-left-color: var(--color-neg); }
	.nada-beku { border-left-color: var(--color-text-3); }
	.nada-lolos { border-left-color: var(--color-accent); }
	.nada-diam { border-left-color: var(--color-line); }

	.baris-utama {
		display: flex; flex-wrap: wrap; align-items: baseline;
		justify-content: space-between; gap: 0.6rem;
	}
	.headline { margin: 0; font-size: var(--text-15); letter-spacing: -0.01em; }
	.keputusan { margin: 0.25rem 0 0; font-size: var(--text-12); color: var(--color-text-2, var(--color-text)); }
	.alasan { margin: 0.35rem 0 0; font-size: var(--text-11); color: var(--color-text-3); }

	.state { display: flex; flex-wrap: wrap; gap: 0.3rem; }
	.chip {
		display: inline-flex; align-items: baseline; gap: 0.25rem;
		border: 1px solid var(--color-line); border-radius: 999px;
		padding: 0.05rem 0.45rem; font-size: var(--text-10, 0.65rem);
	}
	.chip-k { color: var(--color-text-3); }
	.chip-t { font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
	.chip-risiko { border-color: var(--color-neg); }
	.chip-risiko .chip-t { color: var(--color-neg); }
	.chip-promosi { border-color: var(--color-accent); }
	.chip-promosi .chip-t { color: var(--color-accent); }
</style>
