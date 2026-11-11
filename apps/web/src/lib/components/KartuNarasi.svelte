<script lang="ts">
	// Narasi LLM per pasar (job llm-brief-<market>, kind ai.brief).
	//
	// Sebelumnya blok ini DISALIN di kelima cabang pasar (crypto/idx/forex/gmgn/
	// polymarket) dengan isi identik — hanya variabel `narasiObj` yang berbeda.
	// Disatukan di sini supaya perbaikan cukup dilakukan sekali.
	//
	// Aturan tampilan: narasi bersifat deskriptif, bukan rekomendasi. Bila tidak
	// tersedia, angka di halaman tetap sah karena bersumber dari fakta, bukan narasi.
	interface Props {
		narasi: Record<string, any> | null;
	}
	let { narasi }: Props = $props();
</script>

{#if narasi}
	<div class="mb-4 overflow-hidden rounded-card border border-line bg-surface">
		<div class="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3 py-1.5">
			<span class="text-11 font-bold uppercase tracking-wide text-accent-2">✳ Narasi</span>
			<span class="text-10 text-text-3 font-mono">
				{narasi.fact_ids?.length ?? 0} fakta dirujuk{#if narasi.output?.nada} · nada {narasi.output.nada}{/if}
			</span>
		</div>
		{#if narasi.status !== 'ok'}
			<p class="px-3 py-2 text-11 text-warn">
				Narasi tidak tersedia ({narasi.status ?? '—'}{narasi.error_code ? ` · ${narasi.error_code}` : ''}),
				angka di halaman ini tetap sah karena berasal dari fakta, bukan dari narasi.
				Status penyedia LLM ada di halaman <b>Sistem → AI</b>.
			</p>
		{:else if narasi.output?.kalimat?.length}
			<div class="px-3 py-2.5">
				<p class="text-15 leading-snug text-text">{narasi.output.kalimat[0].teks}</p>
				{#if narasi.output.kalimat.length > 1}
					<div class="mt-1.5 space-y-1 border-l-2 border-line-soft pl-2.5">
						{#each narasi.output.kalimat.slice(1) as k}
							<p class="text-12 text-text-2">{k.teks}</p>
						{/each}
					</div>
				{/if}
				<p class="mt-2 text-10 text-text-3">
					Deskriptif, bukan rekomendasi. Mesin: {narasi.provider ?? '—'} ·
					{narasi.prompt_version ?? '—'}{#if narasi.latency_ms} · {narasi.latency_ms} ms{/if}
				</p>
			</div>
		{:else}
			<p class="px-3 py-2 text-11 text-text-3">Narasi kosong, fakta tetap sah.</p>
		{/if}
	</div>
{/if}
