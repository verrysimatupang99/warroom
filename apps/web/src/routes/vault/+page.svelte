<script lang="ts">
  import { onMount } from "svelte";
  import { urlApi } from "$lib/api/client";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  type Preset = {
    id: string;
    label: string;
    butuh_endpoint: boolean;
    butuh_secret: boolean;
    extra: string[];
  };

  type Item = {
    id: number;
    platform: string;
    label: string;
    endpoint: string | null;
    aktif: boolean;
    punya_key: boolean;
    punya_secret: boolean;
    extra_keys: string[];
  };

  let preset = $state<Preset[]>([]);
  let items = $state<Item[]>([]);
  let loading = $state(true);
  let pesan = $state("");
  let err = $state("");

  let pilihPlatform = $state("");
  let label = $state("");
  let endpoint = $state("");
  let apiKey = $state("");
  let apiSecret = $state("");
  let extraFields = $state<Record<string, string>>({});

  let presetAktif = $derived(preset.find((p) => p.id === pilihPlatform));

  async function muat() {
    loading = true;
    err = "";
    try {
      const [rp, ri] = await Promise.all([
        fetch(urlApi("/api/v1/vault/platform"), { credentials: "include" }),
        fetch(urlApi("/api/v1/vault"), { credentials: "include" }),
      ]);
      if (rp.ok) preset = (await rp.json()).platform;
      if (ri.ok) items = (await ri.json()).items;
    } catch (e) {
      err = String(e);
    } finally {
      loading = false;
    }
  }

  async function simpan() {
    err = "";
    pesan = "";
    if (!pilihPlatform || !label) {
      err = "Pilih platform dan isi label.";
      return;
    }
    const res = await fetch(urlApi("/api/v1/vault"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: pilihPlatform,
        label,
        endpoint: endpoint || null,
        api_key: apiKey || null,
        api_secret: apiSecret || null,
        extra: extraFields,
      }),
    });
    if (res.ok) {
      pesan = "Kredensial tersimpan.";
      label = "";
      endpoint = "";
      apiKey = "";
      apiSecret = "";
      extraFields = {};
      await muat();
    } else {
      const j = await res.json().catch(() => ({}));
      err = j.detail ?? `Gagal (${res.status})`;
    }
  }

  async function hapus(id: number) {
    if (!confirm("Hapus kredensial ini?")) return;
    const res = await fetch(urlApi(`/api/v1/vault/${id}`), {
      method: "DELETE",
      credentials: "include"
    });
    if (res.ok || res.status === 204) await muat();
    else err = `Gagal hapus (${res.status})`;
  }

  async function tampilkan(id: number) {
    const res = await fetch(urlApi(`/api/v1/vault/${id}/rahasia`), { credentials: "include" });
    if (!res.ok) {
      err = `Gagal ambil rahasia (${res.status})`;
      return;
    }
    const j = await res.json();
    const teks = [
      `Platform: ${j.platform}`,
      `Label: ${j.label}`,
      j.endpoint ? `Endpoint: ${j.endpoint}` : null,
      j.api_key ? `API Key: ${j.api_key}` : null,
      j.api_secret ? `API Secret: ${j.api_secret}` : null,
      ...Object.entries(j.extra ?? {}).map(([k, v]) => `${k}: ${v}`),
    ]
      .filter(Boolean)
      .join("\n");
    await navigator.clipboard.writeText(teks).catch(() => {});
    pesan = "Rahasia disalin ke clipboard, tempel manual, jangan dibagikan.";
  }

  onMount(muat);
</script>

<svelte:head>
  <title>Vault Kredensial | War Room</title>
</svelte:head>

<div class="space-y-4">
  <PageHeader
    eyebrow="War Room · Kontrol Sistem"
    title="Vault Kredensial"
    tag="TERENKRIPSI"
    description="Simpan endpoint + API key platform manapun. Vault hanya menyimpan, salin-tempel manual, tidak ada auto-login. Polymarket tidak didukung."
    terverifikasi={true}
    sumber="/api/v1/vault"
  />

  {#if err}
    <div class="rounded-control border border-neg/40 bg-neg/10 px-3 py-2 text-12 font-mono text-neg" role="alert">
      ! {err}
    </div>
  {/if}
  {#if pesan}
    <div class="rounded-control border border-pos/40 bg-pos/10 px-3 py-2 text-12 font-mono text-pos" role="status">
      ✓ {pesan}
    </div>
  {/if}

  <div class="grid gap-4 lg:grid-cols-12">
    <form
      class="kartu p-4 space-y-3 lg:col-span-5"
      onsubmit={(e) => { e.preventDefault(); void simpan(); }}
      aria-label="Tambah kredensial"
    >
      <h2 class="label-mikro text-text-2 border-b border-line-soft pb-2">Tambah kredensial</h2>
      <label class="block space-y-1 text-12 text-text-2">
        <span class="label-mikro">Platform</span>
        <select
          bind:value={pilihPlatform}
          class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text"
        >
          <option value="" disabled>Pilih platform…</option>
          {#each preset as p (p.id)}
            <option value={p.id}>{p.label}</option>
          {/each}
        </select>
      </label>
      <label class="block space-y-1 text-12 text-text-2">
        <span class="label-mikro">Label</span>
        <input
          bind:value={label}
          placeholder="mis. akun utama"
          maxlength={128}
          class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text placeholder:text-text-3"
        />
      </label>
      {#if presetAktif?.butuh_endpoint}
        <label class="block space-y-1 text-12 text-text-2">
          <span class="label-mikro">Endpoint</span>
          <input
            bind:value={endpoint}
            placeholder="https://…"
            maxlength={2048}
            class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text placeholder:text-text-3"
          />
        </label>
      {/if}
      <label class="block space-y-1 text-12 text-text-2">
        <span class="label-mikro">API Key</span>
        <input
          bind:value={apiKey}
          type="password"
          autocomplete="off"
          placeholder="••••••••••••"
          class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text placeholder:text-text-3"
        />
      </label>
      {#if presetAktif?.butuh_secret}
        <label class="block space-y-1 text-12 text-text-2">
          <span class="label-mikro">API Secret</span>
          <input
            bind:value={apiSecret}
            type="password"
            autocomplete="off"
            placeholder="••••••••••••"
            class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text placeholder:text-text-3"
          />
        </label>
      {/if}
      {#if presetAktif}
        {#each presetAktif.extra as fld (fld)}
          <label class="block space-y-1 text-12 text-text-2">
            <span class="label-mikro">{fld}</span>
            <input
              bind:value={extraFields[fld]}
              autocomplete="off"
              class="w-full h-9 rounded-control border border-line bg-surface-2 px-2.5 text-12 font-mono text-text"
            />
          </label>
        {/each}
      {/if}
      <button
        type="submit"
        class="w-full h-9 rounded-control bg-accent px-3 text-12 font-mono font-bold text-on-accent hover:opacity-90"
      >
        Simpan Kredensial
      </button>
    </form>

    <section class="kartu p-4 space-y-3 lg:col-span-7" aria-label="Daftar kredensial">
      <div class="flex items-center justify-between border-b border-line-soft pb-2">
        <h2 class="label-mikro text-text-2">Daftar kredensial</h2>
        <span class="angka text-11 text-text-3">{items.length} tersimpan</span>
      </div>

      {#if loading}
        <Skeleton baris={4} tinggi={36} />
      {:else if items.length === 0}
        <EmptyState judul="Belum ada kredensial tersimpan" pesan="Tambahkan endpoint atau API key lewat formulir di samping." ringkas />
      {:else}
        <ul class="space-y-2">
          {#each items as it (it.id)}
            <li class="rounded-control border border-line bg-surface-2 p-3 space-y-2">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="rounded border border-line bg-surface px-2 py-0.5 font-mono text-11 text-accent uppercase">
                    {it.platform}
                  </span>
                  <strong class="text-13 text-text">{it.label}</strong>
                </div>
                {#if !it.aktif}
                  <span class="font-mono text-11 text-neg">! nonaktif</span>
                {/if}
              </div>
              {#if it.endpoint}
                <code class="block font-mono text-11 text-text-3 break-all">{it.endpoint}</code>
              {/if}
              <div class="flex flex-wrap items-center justify-between gap-2 border-t border-line-soft pt-2">
                <span class="font-mono text-11 text-text-3">
                  {it.punya_key ? "key tersedia" : ""}
                  {it.punya_secret ? " · secret tersedia" : ""}
                  {#each it.extra_keys as k} · {k}{/each}
                </span>
                <div class="flex items-center gap-1.5">
                  <button
                    type="button"
                    class="h-7 rounded-control border border-line bg-surface px-2.5 font-mono text-11 text-text-2 hover:border-accent hover:text-text"
                    onclick={() => tampilkan(it.id)}
                  >
                    Salin rahasia
                  </button>
                  <button
                    type="button"
                    class="h-7 rounded-control border border-neg/40 bg-neg/10 px-2.5 font-mono text-11 text-neg hover:bg-neg/20"
                    onclick={() => hapus(it.id)}
                  >
                    Hapus
                  </button>
                </div>
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
</div>
