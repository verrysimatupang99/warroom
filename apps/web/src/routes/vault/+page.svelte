<script lang="ts">
  import { onMount } from "svelte";
  import { urlApi } from "$lib/api/client";
  import Skeleton from "$lib/components/Skeleton.svelte";

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
  <title>Vault Kredensial, War Room</title>
</svelte:head>

<section class="wrap">
  <h1>Vault Kredensial</h1>
  <p class="sub">
    Simpan endpoint + API key platform manapun. Vault hanya menyimpan,
    <strong>salin-tempel manual</strong>, tidak ada auto-login. Polymarket tidak didukung.
  </p>

  {#if err}<p class="galat" role="alert">{err}</p>{/if}
  {#if pesan}<p class="ok" role="status">{pesan}</p>{/if}

  <form class="kartu" onsubmit={(e) => { e.preventDefault(); void simpan(); }}>
    <h2>Tambah kredensial</h2>
    <label>
      Platform
      <select bind:value={pilihPlatform}>
        <option value="" disabled>Pilih platform…</option>
        {#each preset as p (p.id)}
          <option value={p.id}>{p.label}</option>
        {/each}
      </select>
    </label>
    <label>
      Label
      <input bind:value={label} placeholder="mis. akun utama" maxlength="128" />
    </label>
    {#if presetAktif?.butuh_endpoint}
      <label>
        Endpoint
        <input bind:value={endpoint} placeholder="https://…" maxlength="2048" />
      </label>
    {/if}
    <label>
      API Key
      <input bind:value={apiKey} type="password" autocomplete="off" />
    </label>
    {#if presetAktif?.butuh_secret}
      <label>
        API Secret
        <input bind:value={apiSecret} type="password" autocomplete="off" />
      </label>
    {/if}
    {#if presetAktif}
      {#each presetAktif.extra as fld (fld)}
        <label>
          {fld}
          <input bind:value={extraFields[fld]} autocomplete="off" />
        </label>
      {/each}
    {/if}
    <button type="submit">Simpan</button>
  </form>

  <h2>Daftar kredensial</h2>
  {#if loading}
    <Skeleton baris={4} tinggi={36} />
  {:else if items.length === 0}
    <p class="kosong">Belum ada kredensial tersimpan.</p>
  {:else}
    <ul class="daftar">
      {#each items as it (it.id)}
        <li class="kartu">
          <div class="baris">
            <span class="badge">{it.platform}</span>
            <strong>{it.label}</strong>
            {#if !it.aktif}<span class="nonaktif">nonaktif</span>{/if}
          </div>
          {#if it.endpoint}<code class="ep">{it.endpoint}</code>{/if}
          <div class="baris aksi">
            <small>{it.punya_key ? "🔑 key" : ""} {it.punya_secret ? "🔐 secret" : ""}
              {#each it.extra_keys as k}· {k}{/each}</small>
            <span>
              <button type="button" onclick={() => tampilkan(it.id)}>Salin rahasia</button>
              <button type="button" class="bahaya" onclick={() => hapus(it.id)}>Hapus</button>
            </span>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .wrap {
    max-width: 40rem;
    margin: 0 auto;
    padding: 1rem;
    display: grid;
    gap: 1rem;
  }
  .sub {
    color: var(--color-text-3);
  }
  .kartu {
    border: 1px solid var(--color-line);
    border-radius: var(--radius-card);
    padding: 1rem;
    display: grid;
    gap: 0.75rem;
    background: var(--color-surface);
  }
  label {
    display: grid;
    gap: 0.25rem;
  }
  input,
  select {
    padding: 0.5rem;
    border: 1px solid var(--color-line);
    border-radius: var(--radius-control);
    background: var(--color-surface-2);
    color: var(--color-text);
  }
  button {
    padding: 0.5rem 1rem;
    border-radius: var(--radius-control);
    border: 1px solid var(--color-line);
    background: var(--color-accent);
    color: var(--color-on-accent);
    font-weight: 600;
    cursor: pointer;
  }
  .bahaya {
    background: var(--color-neg);
    color: #fff;
  }
  .galat {
    color: var(--color-neg);
  }
  .ok {
    color: var(--color-pos);
  }
  .badge {
    border: 1px solid var(--color-line);
    border-radius: var(--radius-control);
    padding: 0 0.5rem;
    font-size: 0.85rem;
  }
  .nonaktif {
    color: var(--color-neg);
  }
  .ep {
    word-break: break-all;
    color: var(--color-text-3);
  }
  .baris {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }
  .aksi {
    flex-wrap: wrap;
  }
  .daftar {
    list-style: none;
    padding: 0;
    display: grid;
    gap: 0.75rem;
  }
  .kosong {
    color: var(--color-text-3);
  }
</style>
