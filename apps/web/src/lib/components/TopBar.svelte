<script lang="ts">
	// Topbar: MoneyStrip (3 segmen permanen), pencarian, jam WIB, indikator kesegaran global,
	// badge realtime. Semua angka berasal dari API; gagal → tetap `n/a`, bukan angka karangan.
	import { jamWIB } from '$lib/format';
	import { live } from '$lib/api/live.svelte';
	import { getArea, getKesegaran } from '$lib/api/client';
	import type { SegmenUang } from '$lib/uang';
	import MoneyStrip from './MoneyStrip.svelte';
import TemaToggle from './TemaToggle.svelte';

	interface Props {
		jalur: string;
	}
	let { jalur }: Props = $props();

	let jam = $state(jamWIB());
	$effect(() => {
		const t = setInterval(() => (jam = jamWIB()), 1000);
		return () => clearInterval(t);
	});

	// Kesegaran global: jumlah fakta segar/basi (dari /freshness).
	let total = $state<number | null>(null);
	let basi = $state<number | null>(null);
	let cek = $state<string | null>(null);
	async function muatKesegaran() {
		try {
			const f = await getKesegaran();
			total = f.count;
			basi = f.facts.filter((x) => x.status === 'basi').length;
			cek = f.checked_at;
		} catch {
			total = null;
			basi = null;
		}
	}

	// Uang paper dari equity (dalam R). Nyata/Warisan belum punya sumber terverifikasi → `—`.
	let paper = $state<SegmenUang | null>(null);
	async function muatUang() {
		try {
			const p = await getArea('polymarket');
			const f = p.facts.find((x) => x.key === 'equity');
			const stats = (f?.value as { stats?: { total_r?: unknown } } | undefined)?.stats;
			const tr = stats?.total_r;
			paper = {
				nilai: typeof tr === 'number' ? tr : null,
				satuan: 'R',
				sumber: f?.source ?? null,
				age_s: f?.age_s ?? null,
				status: f?.status ?? null,
				keterangan: 'equity paper (R)'
			};
		} catch {
			paper = { nilai: null, keterangan: 'gagal memuat equity paper' };
		}
	}

	$effect(() => {
		void muatKesegaran();
		void muatUang();
		const t = setInterval(() => {
			void muatKesegaran();
			void muatUang();
		}, 15000);
		return () => clearInterval(t);
	});

	let cari = $state('');
	let catatan = $state<string | null>(null);
	const badgeLive = $derived(
		live.status === 'live'
			? { teks: 'live', kelas: 'text-pos border-pos/40' }
			: live.status === 'polling'
				? { teks: 'realtime n/a', kelas: 'text-warn border-warn/40' }
				: live.status === 'menyambung'
					? { teks: 'menyambung', kelas: 'text-text-3 border-line' }
					: { teks: 'realtime n/a', kelas: 'text-text-3 border-line' }
	);
	const segarTeks = $derived(
		total === null ? 'n/a' : `${total - (basi ?? 0)}/${total}${basi ? ` · ${basi} basi` : ''}`
	);
</script>

<header
	class="sticky top-0 z-30 border-b border-line bg-bg-2/95 backdrop-blur"
	data-testid="topbar"
>
	<div class="flex min-h-[56px] flex-wrap items-center gap-2 px-3 py-2">
		<span class="label-mikro text-accent md:hidden">War Room</span>

		<form
			class="order-3 flex w-full items-center gap-2 md:order-none md:w-64"
			onsubmit={(e) => {
				e.preventDefault();
				catatan = cari.trim()
					? `pencarian global untuk “${cari.trim()}” menyusul (P4) — belum ada endpoint`
					: null;
			}}
		>
			<label class="sr-only" for="cari-global">Pencarian global</label>
			<input
				id="cari-global"
				type="search"
				bind:value={cari}
				placeholder="cari pair/token/aturan…"
				class="target-44 min-w-0 flex-1 rounded-control border border-line bg-surface px-2 text-13 text-text placeholder:text-text-3"
			/>
		</form>

		<div class="ml-auto flex items-center gap-2">
			<div class="hidden lg:block"><MoneyStrip {paper} /></div>
			<span
				class="label-mikro rounded-control border px-1.5 py-1 {badgeLive.kelas}"
				title={live.pesan ?? 'status aliran SSE'}
				data-testid="badge-live"
			>
				{badgeLive.teks}
			</span>
			<span
				class="label-mikro hidden items-center gap-1 rounded-control border border-line px-1.5 py-1 text-text-3 sm:inline-flex"
				title={`kesegaran global · dicek ${cek ?? '—'}`}
			>
				segar <span class="angka">{segarTeks}</span>
			</span>
			<span class="angka text-13 text-text-2" aria-label="jam WIB">{jam} WIB</span>
			<TemaToggle />
			<button
				type="button"
				class="target-44 transisi relative inline-flex items-center rounded-control border border-line px-2 text-text-3 hover:border-accent-2 hover:text-text"
				aria-label="Notifikasi"
			>
				<span aria-hidden="true">🔔</span>
				{#if live.kejadian.some((k) => k.type.startsWith('alert.'))}
					<span class="absolute right-1 top-1 h-2 w-2 rounded-full bg-neg" aria-hidden="true"></span>
				{/if}
			</button>
		</div>
	</div>
	{#if catatan}
		<p class="border-t border-line-soft px-3 py-1 text-11 text-warn" role="status">{catatan}</p>
	{/if}
	<div class="px-3 pb-2 lg:hidden"><MoneyStrip {paper} ringkas /></div>
</header>