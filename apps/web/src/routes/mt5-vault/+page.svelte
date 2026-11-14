<script lang="ts">
  import { onMount } from "svelte";
  import { urlApi } from "$lib/api/client";
  import Skeleton from "$lib/components/Skeleton.svelte";

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

  onMount(muat);
</script>

<svelte:head>
  <title>MT5 Vault | War Room</title>
</svelte:head>

<section class="vault max-w-4xl mx-auto p-4 w-full">
  <h2 class="text-xl font-bold font-mono text-text">MT5 Login Vault</h2>
  <p class="hint text-xs text-text-3 mt-1 leading-relaxed">
    Gudang detail akun MT5 biar tinggal salin-tempel saat login manual di MT5 Webtop.
    Sandi tersimpan terenkripsi di server dan tidak pernah tampil otomatis, buka manual satu akun saja.
    <strong>Sarankan pakai Investor Password</strong> (read-only), bukan master.
  </p>

  {#if error}<p class="err text-xs text-neg font-mono mt-2" role="alert">{error}</p>{/if}
  {#if pesan}<p class="ok text-xs text-pos font-mono mt-2" role="status">{pesan}</p>{/if}
  {#if !kunciVaultAda && !loading}
    <p class="err text-xs text-neg font-mono mt-2">Kunci vault belum terpasang di server, simpan akun dinonaktifkan sementara.</p>
  {/if}

  <form
    onsubmit={(e) => { e.preventDefault(); void simpan(); }}
    aria-label="Simpan detail akun MT5"
    class="grid grid-cols-1 sm:grid-cols-2 gap-3 my-4 w-full"
  >
    <input bind:value={label} placeholder="Label (mis. Exness cent)" maxlength={120} class="p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text" />
    <input bind:value={login} placeholder="Login (angka)" required inputmode="numeric" maxlength={32} class="p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text" />
    <input bind:value={server} placeholder="Server (mis. Exness-MT5Real25)" required maxlength={160} class="p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text" />
    <input bind:value={password} type="password" placeholder="Password" required maxlength={128} autocomplete="off" class="p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text" />
    <select bind:value={passwordKind} aria-label="Jenis sandi" class="p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text">
      <option value="investor">Investor (read-only, disarankan)</option>
      <option value="master">Master (risiko penuh)</option>
    </select>
    <textarea bind:value={note} placeholder="Catatan (opsional)" rows={2} maxlength={2000} class="col-span-full p-2 text-xs font-mono rounded bg-surface-2 border border-line text-text"></textarea>
    <button type="submit" disabled={!kunciVaultAda} class="col-span-full p-2.5 text-xs font-mono font-bold rounded bg-accent text-on-accent border border-line hover:opacity-90 disabled:opacity-40 cursor-pointer">Simpan</button>
  </form>

  {#if loading}
    <Skeleton baris={4} tinggi={36} />
  {:else if akun.length === 0}
    <p class="hint text-xs text-text-3 font-mono">Belum ada akun tersimpan.</p>
  {:else}
    <div class="overflow-x-auto w-full rounded border border-line">
      <table class="w-full border-collapse text-xs font-mono text-left">
        <thead class="bg-surface-2 border-b border-line text-text-3">
          <tr>
            <th class="p-2.5">Label</th>
            <th class="p-2.5">Login</th>
            <th class="p-2.5">Server</th>
            <th class="p-2.5">Jenis</th>
            <th class="p-2.5 text-right">Aksi</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-line-soft">
          {#each akun as a (a.id)}
            <tr class="hover:bg-surface-2/50 {a.active ? '' : 'opacity-50'}">
              <td class="p-2.5 text-text">{a.label || "—"}</td>
              <td class="p-2.5"><code class="text-accent">{a.login}</code></td>
              <td class="p-2.5 text-text-3">{a.server}</td>
              <td class="p-2.5 {a.password_kind === 'master' ? 'text-warn font-bold' : 'text-text-3'}">
                {a.password_kind === "master" ? "⚠ master" : "investor"}
              </td>
              <td class="p-2.5 text-right space-x-2">
                <button type="button" class="px-2 py-1 rounded bg-surface-3 hover:bg-surface-2 border border-line text-text cursor-pointer" onclick={() => tampilkanSandi(a)}>Lihat sandi</button>
                <button type="button" class="px-2 py-1 rounded bg-neg/15 hover:bg-neg/25 border border-neg/30 text-neg cursor-pointer" onclick={() => hapus(a.id)}>Hapus</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if menampilkan}
    <div class="reveal fixed inset-x-0 bottom-20 mx-auto w-[min(30rem,90vw)] bg-surface border border-line rounded-lg p-4 text-center shadow-xl z-50" role="dialog" aria-label="Sandi akun">
      <p class="text-xs text-text-3 font-mono">Salin sekarang, lalu tutup:</p>
      <code class="block my-2 text-base font-bold font-mono text-accent select-all">{sandiTerlihat}</code>
      <button type="button" class="px-3 py-1 rounded bg-accent text-on-accent font-mono text-xs font-bold cursor-pointer" onclick={() => (menampilkan = false)}>Tutup</button>
    </div>
  {/if}
</section>
