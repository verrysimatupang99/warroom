<script lang="ts">
  import { onMount } from "svelte";

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

  let preset: Preset[] = [];
  let items: Item[] = [];
  let loading = true;
  let pesan = "";
  let err = "";

  let pilihPlatform = "";
  let label = "";
  let endpoint = "";
  let apiKey = "";
  let apiSecret = "";
  let extraFields: Record<string, string> = {};

  $: presetAktif = preset.find((p) => p.id === pilihPlatform);

  async function muat() {
    loading = true;
    err = "";
    try {
      const [rp, ri] = await Promise.all([
        fetch("/api/v1/vault/platform"),
        fetch("/api/v1/vault"),
      ]);
      if (rp.ok) preset = (await rp.json()).platform;
      if (ri.ok) items = (await ri.json()).items;
    } catch (e) {
      err = String(e);
    }
    loading = false;
  }

  async function simpan() {
    err = "";
    pesan = "";
    if (!pilihPlatform || !label) {
      err = "Pilih platform dan isi label.";
      return;
    }
    const res = await fetch("/api/v1/vault", {
      method: "POST",
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
    const res = await fetch(`/api/v1/vault/${id}`, { method: "DELETE" });
    if (res.ok || res.status === 204) await muat();
    else err = `Gagal hapus (${res.status})`;
  }

  async function tampilkan(id: number) {
    const res = await fetch(`/api/v1/vault/${id}/rahasia`);
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
    pesan = "Rahasia disalin ke clipboard — tempel manual, jangan dibagikan.";
  }

  onMount(muat);
</script>

<svelte:head>
  <title>Vault Kredensial — War Room</title>
</svelte:head>

<section class="wrap">
  <h1>Vault Kredensial</h1>
  <p class="sub">
    Simpan endpoint + API key platform manapun. Vault hanya menyimpan —
    <strong>salin-tempel manual</strong>, tidak ada auto-login. Polymarket tidak didukung.
  </p>

  {#if err}<p class="galat" role="alert">{err}</p>{/if}
  {#if pesan}<p class="ok" role="status">{pesan}</p>{/if}

  <form class="kartu" on:submit|preventDefault={simpan}>
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
    <p>Memuat…</p>
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
              <button type="button" on:click={() => tampilkan(it.id)}>Salin rahasia</button>
              <button type="button" class="bahaya" on:click={() => hapus(it.id)}>Hapus</button>
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
    padding: var(--space-4);
    display: grid;
    gap: var(--space-4);
  }
  .sub {
    color: var(--color-text-muted);
  }
  .kartu {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    display: grid;
    gap: var(--space-3);
    background: var(--color-surface);
  }
  label {
    display: grid;
    gap: var(--space-1);
  }
  input,
  select {
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised, var(--color-surface));
    color: var(--color-text);
  }
  button {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-accent);
    color: var(--color-text-inverted);
    cursor: pointer;
  }
  .bahaya {
    background: var(--color-danger);
  }
  .galat {
    color: var(--color-danger);
  }
  .ok {
    color: var(--color-success);
  }
  .badge {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: 0 var(--space-2);
    font-size: var(--font-size-sm, 0.85rem);
  }
  .nonaktif {
    color: var(--color-danger);
  }
  .ep {
    word-break: break-all;
    color: var(--color-text-muted);
  }
  .baris {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
  }
  .aksi {
    flex-wrap: wrap;
  }
  .daftar {
    list-style: none;
    padding: 0;
    display: grid;
    gap: var(--space-3);
  }
  .kosong {
    color: var(--color-text-muted);
  }
</style>
