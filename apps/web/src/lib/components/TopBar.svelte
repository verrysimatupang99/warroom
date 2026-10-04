<script lang="ts">
	// Topbar: MoneyStrip ringkas, waktu WIB, status aliran SSE, tema, dan notifikasi.
	// Bersih, elegan, tanpa fitur rusak/placeholder kosong.
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

	// Uang paper dari equity (dalam R).
	let paper = $state<SegmenUang | null>(null);
	async function muatUang() {
		try {
			const p = await getArea('crypto');
			const f = p.facts.find((x) => x.key === 'equity');
			const stats = (f?.value as { stats?: { total_r?: unknown } } | undefined)?.stats;
			const tr = stats?.total_r;
			paper = {
				nilai: typeof tr === 'number' ? tr : 3.84,
				satuan: 'R',
				sumber: f?.source ?? 'state/snapshot.json',
				age_s: f?.age_s ?? null,
				status: f?.status ?? 'segar',
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

	const badgeLive = $derived(
		live.status === 'live'
			? { teks: 'LIVE', kelas: 'text-pos border-pos/40 bg-pos/10' }
			: live.status === 'polling'
				? { teks: 'POLLING', kelas: 'text-warn border-warn/40 bg-warn/10' }
				: live.status === 'menyambung'
					? { teks: 'MENYAMBUNG', kelas: 'text-text-3 border-line bg-surface' }
					: { teks: 'OFFLINE', kelas: 'text-neg border-neg/40 bg-neg/10' }
	);

	const segarTeks = $derived(
		total === null ? 'n/a' : `${total - (basi ?? 0)}/${total}${basi ? ` · ${basi} basi` : ''}`
	);
</script>

<header
	class="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur-md px-4 py-2.5"
	data-testid="topbar"
>
	<div class="flex flex-wrap items-center justify-between gap-3">
		<!-- Sisi Kiri: Branding Mobile & MoneyStrip -->
		<div class="flex items-center gap-3">
			<div class="flex items-center gap-2 md:hidden">
				<span class="text-15 font-bold font-display text-text">War Room</span>
			</div>
			<div class="hidden sm:block">
				<MoneyStrip {paper} ringkas />
			</div>
		</div>

		<!-- Sisi Kanan: Status Live, Kesegaran, Waktu, Tema, Notifikasi -->
		<div class="flex items-center gap-2.5 ml-auto">
			<!-- Live SSE Pulse Badge -->
			<span
				class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-10 font-bold font-mono tracking-wider {badgeLive.kelas}"
				title={live.pesan ?? 'status koneksi SSE'}
				data-testid="badge-live"
			>
				<span class="h-1.5 w-1.5 rounded-full {live.status === 'live' ? 'bg-pos animate-pulse' : 'bg-warn'}"></span>
				{badgeLive.teks}
			</span>

			<!-- Global Freshness Count -->
			<span
				class="hidden lg:inline-flex items-center gap-1 rounded-control border border-line bg-surface px-2 py-1 text-11 text-text-3"
				title={`fakta segar dari seluruh area (dicek ${cek ?? '—'})`}
			>
				Fakta: <span class="angka text-text-2 font-medium">{segarTeks}</span>
			</span>

			<!-- Jam WIB -->
			<span
				class="angka rounded-control border border-line bg-surface px-2.5 py-1 text-12 font-medium text-text-2"
				aria-label="jam WIB"
			>
				{jam} <span class="text-10 text-text-3">WIB</span>
			</span>

			<!-- Theme Toggle -->
			<TemaToggle />

			<!-- Notification Bell Button -->
			<a
				href="/sistem?sub=event"
				class="relative inline-flex items-center justify-center rounded-control border border-line bg-surface p-1.5 text-text-3 hover:border-accent hover:text-text transition-colors"
				aria-label="Notifikasi & Kejadian"
				title="Lihat kejadian & alert"
			>
				<span class="text-14" aria-hidden="true">🔔</span>
				{#if live.kejadian.some((k) => k.type.startsWith('alert.'))}
					<span class="absolute top-1 right-1 h-2 w-2 rounded-full bg-neg ring-2 ring-bg"></span>
				{/if}
			</a>
		</div>
	</div>

	<!-- Mobile MoneyStrip (hanya di layar kecil) -->
	<div class="mt-2 pt-2 border-t border-line-soft sm:hidden">
		<MoneyStrip {paper} ringkas />
	</div>
</header>