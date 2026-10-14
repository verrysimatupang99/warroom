<script lang="ts">
	// Blok gate: hanya dievaluasi bila ada fakta verdict/gate yang benar-benar memuat n/win/be.
	// Tidak ada fakta → EmptyState (gate tidak pernah menebak dari nol).
	import type { AreaPayload, GateResult, GateInput } from '$lib/api/types';
	import { nilaiGate } from '$lib/api/client';
	import GateMeter from './GateMeter.svelte';

	interface Props {
		data: AreaPayload;
	}
	let { data }: Props = $props();

	const masukan = $derived.by<GateInput | null>(() => {
		for (const f of data.facts) {
			if (f.key !== 'verdict' && f.key !== 'gate') continue;
			const v = f.value as Record<string, unknown> | null;
			if (!v || typeof v !== 'object') continue;
			const n = Number(v.n);
			const win = Number(v.win ?? v.wins);
			const be = Number(v.be);
			if (Number.isFinite(n) && Number.isFinite(win) && Number.isFinite(be)) {
				return {
					n,
					win,
					be,
					ci: Number.isFinite(Number(v.ci)) ? Number(v.ci) : undefined,
					min_n: Number.isFinite(Number(v.min_n)) ? Number(v.min_n) : undefined,
					deff: Number.isFinite(Number(v.deff)) ? Number(v.deff) : undefined,
					nEff: Number.isFinite(Number(v.nEff)) ? Number(v.nEff) : undefined,
					split: typeof v.split === 'string' ? v.split : null,
					rule: typeof v.rule === 'string' ? v.rule : ''
				};
			}
		}
		return null;
	});

	let hasil = $state<GateResult | null>(null);
	let galat = $state<string | null>(null);
	let memuat = $state(false);

	async function nilai(m: GateInput) {
		memuat = true;
		try {
			hasil = await nilaiGate(m);
			galat = null;
		} catch (e) {
			galat = e instanceof Error ? e.message : String(e);
		} finally {
			memuat = false;
		}
	}

	$effect(() => {
		const m = masukan;
		if (!m) {
			hasil = null;
			galat = null;
			return;
		}
		void nilai(m);
	});
</script>

<GateMeter {hasil} {memuat} {galat} onulang={masukan ? () => nilai(masukan) : null} />