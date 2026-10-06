<script lang="ts">
	// GateMeter: progres `n` vs `n` dibutuhkan + pita CI vs garis BE. Angka apa adanya dari
	// `/api/v1/gate/evaluate`; `required_n` null berarti menambah sampel tidak akan meloloskan.
	import type { HasilGate } from '$lib/api/types';
	import { bulat, persen } from '$lib/format';
	import EmptyState from './EmptyState.svelte';
	import ErrorState from './ErrorState.svelte';
	import Skeleton from './Skeleton.svelte';

	interface Props {
		hasil: HasilGate | null;
		memuat?: boolean;
		galat?: string | null;
		onulang?: (() => void) | null;
	}
	let { hasil, memuat = false, galat = null, onulang = null }: Props = $props();

	const butuh = $derived(hasil?.required_n ?? null);
	const progres = $derived.by(() => {
		if (!hasil) return 0;
		if (butuh && butuh > 0) return Math.min(1, hasil.n / butuh);
		return hasil.verdict === 'lolos' ? 1 : 0;
	});
	// n efektif = n terkoreksi klaster (n ÷ deff). Diambil dari hasil gate bila ada,
	// kalau tidak dari catatan gate ("n efektif 3080 (dari 4133)"). Ini yang membuat
	// angka "n" jujur: 4.133 mentah, tapi yang dihitung gate lebih kecil.
	const nEfektif = $derived.by(() => {
		if (!hasil) return null;
		if (hasil.nEff != null && Number.isFinite(hasil.nEff)) return hasil.nEff;
		for (const n of hasil.notes ?? []) {
			const m = /n efektif\s+([\d.]+)/i.exec(n);
			if (m) {
				const v = Number(String(m[1]).replace(/\./g, ''));
				if (Number.isFinite(v)) return v;
			}
		}
		return null;
	});
	// Kemajuan sampel hanya "selesai" bila gate benar-benar lolos. Bila n tercapai tapi
	// verdict belum lolos (mis. split belum dibekukan), bar TIDAK hijau — supaya tak
	// terbaca "beres" padahal gate masih tertahan.
	const tercapai = $derived(progres >= 1);
	const warnaProgres = $derived(
		hasil?.verdict === 'lolos' ? 'bg-pos' : tercapai ? 'bg-warn' : 'bg-accent'
	);
	const skala = $derived(Math.max(1e-9, Math.max(hasil?.ci_high ?? 0, hasil?.be ?? 0) * 1.05));
	const bandKiri = $derived(((hasil?.ci_low ?? 0) / skala) * 100);
	const bandLebar = $derived((((hasil?.ci_high ?? 0) - (hasil?.ci_low ?? 0)) / skala) * 100);
	const garisBe = $derived(((hasil?.be ?? 0) / skala) * 100);
	const sisa = $derived(butuh != null && hasil ? Math.max(0, butuh - hasil.n) : null);
	const nada = $derived(
		hasil?.verdict === 'lolos'
			? 'text-pos border-pos/40 bg-pos/10'
			: hasil?.verdict === 'gagal'
				? 'text-neg border-neg/40 bg-neg/10'
				: 'text-warn border-warn/40 bg-warn/10'
	);
	// Label kebijakan eksplisit: hasil 90% vs 95%+koreksi klaster bisa berbeda (lihat
	// docs/blueprint/07-perintah-kerja-hermes.md §B). Jangan pernah tampilkan angka tanpa label.
	const kebijakan = $derived.by(() => {
		if (!hasil) return '';
		const ci = hasil.ci != null ? `CI ${Math.round(hasil.ci * 100)}%` : 'CI n/a';
		const deff =
			hasil.deff != null && hasil.deff > 1
				? ` + deff ${hasil.deff.toFixed(3)}`
				: ' · tanpa koreksi klaster';
		return `${ci}${deff}`;
	});
</script>

<div data-testid="gate-meter">
	{#if galat}
		<ErrorState pesan={galat} {onulang} />
	{:else if memuat && !hasil}
		<Skeleton baris={3} />
	{:else if !hasil}
		<EmptyState
			judul="Belum ada hasil gate"
			pesan="Butuh fakta verdict (n, win, BE) untuk dievaluasi; gate tidak menghitung dari nol."
		/>
	{:else}
		<div class="flex flex-wrap items-center gap-2">
			<span class="label-mikro rounded-control border px-2 py-0.5 {nada}">
				{hasil.verdict}
			</span>
			{#if hasil.pakem}
				<span
					class="angka rounded-control border border-line bg-surface px-2 py-0.5 text-11 text-text-2"
					title="pakem bukti: INSUFFICIENT <10 · DIRECTIONAL 10–29 · PRELIMINARY ≥30 · TUNING ≥100 (pada n efektif)"
				>
					{hasil.pakem}
				</span>
			{/if}
			<span class="angka text-12 text-text-2">
				n {bulat(hasil.n)}{#if butuh} / {bulat(butuh)}{:else} / n/a{/if}
			</span>
			{#if nEfektif != null && nEfektif !== hasil.n}
				<span class="angka text-12 text-warn" title="n terkoreksi klaster (deff {hasil.deff?.toFixed(3) ?? '—'})">
					efektif {bulat(nEfektif)}
				</span>
			{/if}
			{#if sisa != null && sisa > 0}
				<span class="angka text-12 text-text-3">butuh {bulat(sisa)} lagi</span>
			{/if}
			<span class="angka ml-auto text-11 text-text-3">
				kebijakan {kebijakan} · {hasil.policy_version}
			</span>
		</div>

		<div class="mt-3">
			<div class="label-mikro mb-1 flex justify-between">
				<span>kemajuan sampel</span><span class="angka">{persen(progres, 0)}</span>
			</div>
			<div class="h-2 w-full overflow-hidden rounded-control bg-surface-3" role="progressbar"
				aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progres * 100)}
				aria-label="kemajuan sampel menuju n dibutuhkan">
				<div class="h-full {warnaProgres} transisi" style={`width:${(progres * 100).toFixed(1)}%`}></div>
			</div>
			{#if tercapai && hasil.verdict !== 'lolos'}
				<p class="mt-1 text-11 text-warn">
					n tercapai, tapi gate belum lolos — lihat alasan di bawah (bukan kurang sampel).
				</p>
			{/if}
		</div>

		<div class="mt-3">
			<div class="label-mikro mb-1">pita CI {hasil.ci_low > hasil.be ? '(batas bawah > BE)' : '(batas bawah ≤ BE)'}</div>
			<div class="relative h-4 w-full rounded-control bg-surface-3" aria-hidden="true">
				<div
					class="absolute inset-y-0 rounded-control bg-accent-2/40 border border-accent-2/60"
					style={`left:${bandKiri.toFixed(1)}%;width:${Math.max(0.5, bandLebar).toFixed(1)}%`}
				></div>
				<div
					class="absolute inset-y-[-2px] w-0.5 bg-accent"
					style={`left:${garisBe.toFixed(1)}%`}
					title="BE {persen(hasil.be, 2)}"
				></div>
			</div>
			<div class="angka mt-1 flex flex-wrap gap-3 text-11 text-text-3">
				<span>CI {persen(hasil.ci_low, 2)}–{persen(hasil.ci_high, 2)}</span>
				<span>BE {persen(hasil.be, 2)}</span>
				<span>winrate {persen(hasil.win_rate, 2)}</span>
			</div>
		</div>

		<p class="mt-2 text-12 text-text-2">{hasil.reason}</p>
	{/if}
</div>