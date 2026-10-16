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
	import type { MarketVerdict } from '$lib/api/types';

	interface Props {
		verdict?: MarketVerdict | null;
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
			{ k: 'Boleh dipakai', t: verdict.promotion_state }
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
						class:chip-promosi={s.k === 'Boleh dipakai' && verdict.promotion_state === 'promotable'}>
						<span class="chip-k">{s.k}</span>
						<span class="chip-t">{s.t}</span>
					</span>
				{/each}
			</div>
		</div>
		<!-- STATUS VISUAL UTAMA (audit putaran 3, prioritas 1): PAPER/HISTORIS/BRUTO
		     tidak boleh hanya jadi catatan kaki — ia harus terbaca sebelum angka apa pun. -->
		<div class="mode">
			<span class="badge badge-mode">
				{verdict.execution_state === 'frozen' ? 'HISTORIS' : verdict.execution_state.toUpperCase()}
			</span>
			{#if (verdict.detail as any)?.biaya?.label}
				<span class="badge" class:badge-bruto={(verdict.detail as any).biaya.tercatat === false}>
					{(verdict.detail as any).biaya.label}
				</span>
			{/if}
			{#if verdict.risk_state === 'breach'}
				<span class="badge badge-breach">MODEL BREACH</span>
			{/if}
		</div>
		<p class="keputusan">{verdict.decision}</p>
		{#if verdict.blocked_reason}
			<p class="alasan"><b>Kenapa belum boleh dipercaya:</b> {verdict.blocked_reason}</p>
		{/if}
	</section>
{/if}

<style>
	.kepala-verdict {
		border: 1px solid var(--color-line);
		border-left-width: 3px;
		border-radius: var(--radius-card);
		background: var(--color-surface);
		padding: 0.85rem 1rem;
		margin-bottom: 1rem;
		/* FLAT */
	}
	.nada-kandidat { border-left-color: var(--color-warn); /* FLAT */ }
	.nada-breach { border-left-color: var(--color-neg); /* FLAT */ }
	.nada-beku { border-left-color: var(--color-text-3); }
	.nada-lolos { border-left-color: var(--color-accent); /* FLAT */ }
	.nada-diam { border-left-color: var(--color-line); }

	.baris-utama {
		display: flex; flex-wrap: wrap; align-items: baseline;
		justify-content: space-between; gap: 0.6rem;
	}
	.headline { margin: 0; font-size: var(--text-15); letter-spacing: -0.01em; }
	.keputusan { margin: 0.25rem 0 0; font-size: var(--text-12); color: var(--color-text-2, var(--color-text)); }
	.alasan { margin: 0.35rem 0 0; font-size: var(--text-11); color: var(--color-text-3); }

	.mode { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.4rem; }
	.badge {
		font-size: var(--text-10, 0.65rem); font-weight: 800; letter-spacing: 0.06em;
		border: 1px solid var(--color-line); border-radius: 0.35rem; padding: 0.1rem 0.4rem;
		text-transform: uppercase;
	}
	.badge-mode { color: var(--color-warn); border-color: var(--color-warn); background: color-mix(in srgb, var(--color-warn) 12%, transparent); }
	.badge-bruto { color: var(--color-warn); border-color: var(--color-warn); }
	.badge-breach { color: var(--color-neg); border-color: var(--color-neg); background: color-mix(in srgb, var(--color-neg) 12%, transparent); }

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
