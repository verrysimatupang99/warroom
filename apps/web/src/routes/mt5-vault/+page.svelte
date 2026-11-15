<script lang="ts">
  import { onMount } from "svelte";
  import { urlApi } from "$lib/api/client";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import Skeleton from "$lib/components/Skeleton.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";

  type Akun = {
    id: number;
    label: string;
    login: string;
    server: string;
    password_kind: string;
    note: string;
    active: boolean;
  };

  let akun = $state<Akun[]>([]);
  let kunciVaultAda = $state(false);
  let loading = $state(true);
  let pesan = $state("");
  let error = $state("");

  // form
  let label = $state("");
  let login = $state("");
  let server = $state("");
  let password = $state("");
  let passwordKind = $state<"investor" | "master">("investor");
  let note = $state("");
  let menampilkan = $state(false); // reveal sandi satu akun, sekali, di client
  let sandiTerlihat = $state("");
  let liveAccounts = $state<any[]>([]);
  async function muatLive() {
    try {
      const r = await fetch(urlApi("/api/v1/tencent/mt5/accounts"), { credentials: "include" });
      if (r.ok) {
        const d = await r.json();
        liveAccounts = d.accounts ?? [];
      }
    } catch {}
  }

  async function muat() {
    loading = true;
    error = "";
    try {
      const r = await fetch(urlApi("/api/v1/mt5-vault"), { credentials: "include" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      akun = d.akun ?? [];
      kunciVaultAda = Boolean(d.kunci_vault_ada);
    } catch (e) {
      error = `Gagal memuat: ${String(e)}`;
    } finally {
      loading = false;
    }
  }

  async function simpan() {
    pesan = "";
    error = "";
    try {
      const r = await fetch(urlApi("/api/v1/mt5-vault"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, login, server, password, password_kind: passwordKind, note }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`);
      pesan = "Akun tersimpan ✔";
      label = login = server = password = note = "";
      passwordKind = "investor";
      await muat();
    } catch (e) {
      error = String(e);
    }
  }

  async function hapus(id: number) {
    if (!confirm("Hapus akun ini dari vault?")) return;
    const r = await fetch(urlApi(`/api/v1/mt5-vault/${id}`), {
      method: "DELETE",
      credentials: "include",
    });
    if (r.ok || r.status === 204) await muat();
    else error = `Gagal hapus (HTTP ${r.status})`;
  }

  // Satu-satunya jalan sandi bisa terlihat: minta server dekripsi satu akun,
  // hanya via endpoint khusus owner, ditampilkan sesaat di layar untuk disalin.
  async function tampilkanSandi(a: Akun) {
    sandiTerlihat = "";
    menampilkan = true;
    try {
      const r = await fetch(urlApi(`/api/v1/mt5-vault/${a.id}/sandi`), { credentials: "include" });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`);
      sandiTerlihat = d.password;
    } catch (e) {
      error = String(e);
      menampilkan = false;
    }
  }

  onMount(() => { void muat(); void muatLive(); });
</script>

<svelte:head>
  <title>MT5 Vault | War Room</title>
</svelte:head>

<div class="space-y-4">
  <PageHeader
    eyebrow="War Room · Kontrol Sistem"
    title="MT5 Login Vault"
    tag="TERENKRIPSI"
    description="Gudang detail akun MT5 agar mudah salin-tempel saat login manual di MT5 Webtop. Sandi tersimpan terenkripsi di server dan tidak pernah tampil otomatis. Sarankan pakai Investor Password (read-only), bukan master."
    terverifikasi={true}
    sumber="/api/v1/mt5-vault"
  />

  {#if error}
    <div class="rounded-control border border-neg/40 bg-neg/10 px-3 py-2 text-12 font-mono text-neg" role="alert">
      ! {error}
    </div>
  {/if}
  {#if pesan}
    <div class="rounded-control border border-pos/40 bg-pos/10 px-3 py-2 text-12 font-mono text-pos" role="status">
      {pesan}
    </div>
  {/if}
  {#if !kunciVaultAda && !loading}
    <div class="rounded-control border border-neg/40 bg-neg/10 px-3 py-2 text-12 font-mono text-neg" role="status">
      ! Kunci vault belum terpasang di server, simpan akun dinonaktifkan sementara.
    </div>
  {/if}

  {#if liveAccounts.length > 0}
    <section class="kartu p-4 space-y-3" aria-label="Status Telemetri Multi-Akun MT5">
      <div class="flex items-center justify-between border-b border-line-soft pb-2">
        <h2 class="label-mikro text-text-2">Telemetri Aktif Multi-Akun (Instabox Cloud)</h2>
        <span class="angka text-11 text-pos">{liveAccounts.filter(a => a.connected).length}/{liveAccounts.length} ONLINE</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-12">
        {#each liveAccounts as acc (acc.account)}
          <div class="rounded-control border border-line bg-surface-2 p-3 space-y-1.5">
            <div class="flex items-center justify-between">
              <span class="font-bold text-text">#{acc.account}</span>
              <span class="px-2 py-0.5 rounded text-10 font-bold {acc.connected ? 'bg-pos/15 text-pos border border-pos/30' : 'bg-neg/15 text-neg border border-neg/30'}">
                {acc.connected ? `ONLINE (${acc.seconds_ago}s)` : 'OFFLINE'}
              </span>
            </div>
            <div class="text-11 text-text-3">{acc.account === '452009427' ? 'box-2aacb3 · LIVE CENT (v3.0)' : acc.account === '434446792' ? 'mt5-paper-1 · PAPER-1 (v3.0 NoMon=OFF)' : 'mt5-paper-2 · PAPER-2 (Gold+BTC 24/7)'}</div>
            <div class="flex items-center justify-between pt-1 border-t border-line-soft">
              <span class="text-text-3">Equity:</span>
              <span class="font-bold text-pos">{acc.currency === 'USC' ? `${acc.equity?.toFixed(2)} USC` : `$${acc.equity?.toFixed(2)}`}</span>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <div class="grid gap-4 lg:grid-cols-12">
    <form
      onsubmit={(e) => { e.preventDefault(); void simpan(); }}
      aria-label="Simpan detail akun MT5"
      class="kartu p-4 space-y-3 lg:col-span-5"
    >
      <h2 class="label-mikro text-text-2 border-b border-line-soft pb-2">Tambah akun MT5</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label class="block space-y-1">
          <span class="label-mikro">Label</span>
          <input
            bind:value={label}
            placeholder="mis. Exness cent"
            maxlength={120}
            class="w-full h-9 px-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text placeholder:text-text-3"
          />
        </label>
        <label class="block space-y-1">
          <span class="label-mikro">Login (Angka)</span>
          <input
            bind:value={login}
            placeholder="Login (angka)"
            required
            inputmode="numeric"
            maxlength={32}
            class="w-full h-9 px-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text placeholder:text-text-3"
          />
        </label>
        <label class="block space-y-1">
          <span class="label-mikro">Server Broker</span>
          <input
            bind:value={server}
            placeholder="mis. Exness-MT5Real25"
            required
            maxlength={160}
            class="w-full h-9 px-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text placeholder:text-text-3"
          />
        </label>
        <label class="block space-y-1">
          <span class="label-mikro">Password</span>
          <input
            bind:value={password}
            type="password"
            placeholder="Password"
            required
            maxlength={128}
            autocomplete="off"
            class="w-full h-9 px-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text placeholder:text-text-3"
          />
        </label>
      </div>
      <label class="block space-y-1">
        <span class="label-mikro">Jenis Sandi</span>
        <select
          bind:value={passwordKind}
          aria-label="Jenis sandi"
          class="w-full h-9 px-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text"
        >
          <option value="investor">Investor (read-only, disarankan)</option>
          <option value="master">Master (risiko penuh)</option>
        </select>
      </label>
      <label class="block space-y-1">
        <span class="label-mikro">Catatan</span>
        <textarea
          bind:value={note}
          placeholder="Catatan (opsional)"
          rows={2}
          maxlength={2000}
          class="w-full p-2.5 text-12 font-mono rounded-control bg-surface-2 border border-line text-text placeholder:text-text-3"
        ></textarea>
      </label>
      <button
        type="submit"
        disabled={!kunciVaultAda}
        class="w-full h-9 px-3 text-12 font-mono font-bold rounded-control bg-accent text-on-accent border border-line hover:opacity-90 disabled:opacity-40 cursor-pointer"
      >
        Simpan
      </button>
    </form>

    <section class="kartu p-4 space-y-3 lg:col-span-7" aria-label="Daftar akun MT5">
      <div class="flex items-center justify-between border-b border-line-soft pb-2">
        <h2 class="label-mikro text-text-2">Akun tersimpan</h2>
        <span class="angka text-11 text-text-3">{akun.length} akun</span>
      </div>

      {#if loading}
        <Skeleton baris={4} tinggi={36} />
      {:else if akun.length === 0}
        <EmptyState judul="Belum ada akun tersimpan" pesan="Simpan kredensial investor MT5 lewat formulir di samping." ringkas />
      {:else}
        <div class="overflow-x-auto w-full rounded-control border border-line bg-surface">
          <table class="w-full border-collapse text-12 font-mono text-left">
            <thead class="bg-surface-2 border-b border-line">
              <tr>
                <th class="px-2.5 py-2 label-mikro">Label</th>
                <th class="px-2.5 py-2 label-mikro">Login</th>
                <th class="px-2.5 py-2 label-mikro">Server</th>
                <th class="px-2.5 py-2 label-mikro">Jenis</th>
                <th class="px-2.5 py-2 label-mikro text-right">Aksi</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-line-soft">
              {#each akun as a (a.id)}
                <tr class="hover:bg-surface-2/60 {a.active ? '' : 'opacity-50'}">
                  <td class="px-2.5 py-2 text-text font-sans">{a.label || "—"}</td>
                  <td class="px-2.5 py-2"><code class="text-accent font-semibold">{a.login}</code></td>
                  <td class="px-2.5 py-2 text-text-2">{a.server}</td>
                  <td class="px-2.5 py-2 {a.password_kind === 'master' ? 'text-warn font-bold' : 'text-text-3'}">
                    {a.password_kind === "master" ? "⚠ master" : "investor"}
                  </td>
                  <td class="px-2.5 py-2 text-right space-x-1.5 whitespace-nowrap">
                    <button
                      type="button"
                      class="h-7 px-2.5 rounded-control bg-surface-2 hover:border-accent border border-line text-11 text-text-2 hover:text-text cursor-pointer"
                      onclick={() => tampilkanSandi(a)}
                    >
                      Lihat sandi
                    </button>
                    <button
                      type="button"
                      class="h-7 px-2.5 rounded-control bg-neg/10 hover:bg-neg/20 border border-neg/40 text-11 text-neg cursor-pointer"
                      onclick={() => hapus(a.id)}
                    >
                      Hapus
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  </div>

  {#if menampilkan}
    <div
      class="reveal fixed inset-x-0 bottom-20 mx-auto w-[min(30rem,90vw)] bg-surface border border-line rounded-card p-4 text-center z-50"
      role="dialog"
      aria-label="Sandi akun"
    >
      <p class="label-mikro text-text-3">Salin sekarang, lalu tutup:</p>
      <code class="block my-2.5 rounded-control border border-line bg-surface-2 py-2 text-15 font-bold font-mono text-accent select-all">
        {sandiTerlihat}
      </code>
      <button
        type="button"
        class="h-8 px-4 rounded-control bg-accent text-on-accent font-mono text-12 font-bold cursor-pointer"
        onclick={() => (menampilkan = false)}
      >
        Tutup
      </button>
    </div>
  {/if}
</div>
