<script lang="ts">
	// Badge kesegaran: `segar Xm` / `basi Xm` / `cache Xm` / `n/a`. Selalu membawa sumber + TTL
	// di title supaya tiap angka bisa diaudit (aturan 1).
	import { umurDetik } from '$lib/format';

	interface Props {
		status?: string | null;
		age_s?: number | null;
		ttl_s?: number | null;
		source?: string | null;
		/** data dari cache lokal, bukan langsung dari sumber */
		cache?: boolean;
		ringkas?: boolean;
	}
	let {
		status = null,
		age_s = null,
		ttl_s = null,
		source = null,
		cache = false,
		ringkas = false
	}: Props = $props();

	type Nada = 'segar' | 'basi' | 'cache' | 'n/a';
	const nada = $derived<Nada>(
		cache ? 'cache' : status === 'segar' ? 'segar' : status === 'basi' ? 'basi' : 'n/a'
	);
	const umur = $derived(umurDetik(age_s));
	const label = $derived(nada === 'n/a' ? 'n/a' : `${nada} ${umur}`);
	const judul = $derived.by(() => {
		const bagian: string[] = [nada === 'n/a' ? 'kesegaran tidak diketahui' : `${nada}, umur ${umur}`];
		if (source) bagian.push(`sumber: ${source}`);
		if (ttl_s != null) bagian.push(`TTL ${umurDetik(ttl_s)}`);
		if (age_s != null && status && status !== nada) bagian.push(`status API: ${status}`);
		if (cache) bagian.push('dari cache');
		return bagian.join(' · ');
	});
	const kelas = $derived(
		{
			segar: 'text-pos border-pos/40 bg-pos/10',
			basi: 'text-neg border-neg/40 bg-neg/10',
			cache: 'text-paper border-paper/40 bg-paper/10',
			'n/a': 'text-text-3 border-line bg-surface-2'
		}[nada]
	);
</script>

<span
	class="label-mikro transisi inline-flex items-center gap-1 rounded-control border px-1.5 py-0.5 {kelas}"
	title={judul}
	aria-label={judul}
	data-nada={nada}
	data-testid="freshness"
>
	<span aria-hidden="true" class="inline-block h-1.5 w-1.5 rounded-full bg-current"></span>
	{#if ringkas}{nada}{:else}{label}{/if}
</span>