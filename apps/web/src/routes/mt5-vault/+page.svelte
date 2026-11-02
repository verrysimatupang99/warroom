<script lang="ts">
  import { onMount } from "svelte";

  type Akun = {
    id: number;
    label: string;
    login: string;
    server: string;
    password_kind: string;
    note: string;
    active: boolean;
  };

  let akun: Akun[] = [];
  let kunciVaultAda = false;
  let loading = true;
  let pesan = "";
  let error = "";

  // form
  let label = "";
  let login = "";
  let server = "";
  let password = "";
  let passwordKind: "investor" | "master" = "investor";
  let note = "";
  let menampilkan = false; // reveal sandi satu akun, sekali, di client
  let sandiTerlihat = "";

  async function muat() {
    loading = true;
    error = "";
    try {
      const r = await fetch("/api/v1/mt5-vault", { credentials: "include" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      akun = d.akun;
      kunciVaultAda = d.kunci_vault_ada;
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
      const r = await fetch("/api/v1/mt5-vault", {
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
    const r = await fetch(`/api/v1/mt5-vault/${id}`, {
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
      const r = await fetch(`/api/v1/mt5-vault/${a.id}/sandi`, { credentials: "include" });
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

<section class="vault">
  <h2>MT5 Login Vault</h2>
  <p class="hint">
    Gudang detail akun MT5 biar tinggal salin-tempel saat login manual di MT5 Webtop.
    Sandi tersimpan terenkripsi di server dan tidak pernah tampil otomatis — buka manual satu akun saja.
    <strong>Sarankan pakai Investor Password</strong> (read-only), bukan master.
  </p>

  {#if error}<p class="err">{error}</p>{/if}
  {#if pesan}<p class="ok">{pesan}</p>{/if}
  {#if !kunciVaultAda && !loading}
    <p class="err">Kunci vault belum terpasang di server — simpan akun dinonaktifkan sementara.</p>
  {/if}

  <form
    on:submit|preventDefault={simpan}
    aria-label="Simpan detail akun MT5"
  >
    <input bind:value={label} placeholder="Label (mis. Exness cent)" maxlength={120} />
    <input bind:value={login} placeholder="Login (angka)" required inputmode="numeric" maxlength={32} />
    <input bind:value={server} placeholder="Server (mis. Exness-MT5Real25)" required maxlength={160} />
    <input bind:value={password} type="password" placeholder="Password" required maxlength={128} autocomplete="off" />
    <select bind:value={passwordKind} aria-label="Jenis sandi">
      <option value="investor">Investor (read-only, disarankan)</option>
      <option value="master">Master (risiko penuh)</option>
    </select>
    <textarea bind:value={note} placeholder="Catatan (opsional)" rows={2} maxlength={2000}></textarea>
    <button type="submit" disabled={!kunciVaultAda}>Simpan</button>
  </form>

  {#if loading}
    <p>Memuat…</p>
  {:else if akun.length === 0}
    <p class="hint">Belum ada akun tersimpan.</p>
  {:else}
    <table>
      <thead>
        <tr><th>Label</th><th>Login</th><th>Server</th><th>Jenis</th><th></th></tr>
      </thead>
      <tbody>
        {#each akun as a (a.id)}
          <tr class:nonaktif={!a.active}>
            <td>{a.label || "—"}</td>
            <td><code>{a.login}</code></td>
            <td>{a.server}</td>
            <td>{a.password_kind === "master" ? "⚠ master" : "investor"}</td>
            <td class="aksi">
              <button on:click={() => tampilkanSandi(a)}>Lihat sandi</button>
              <button class="bahaya" on:click={() => hapus(a.id)}>Hapus</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if menampilkan}
    <div class="reveal" role="dialog" aria-label="Sandi akun">
      <p>Salin sekarang, lalu tutup:</p>
      <code>{sandiTerlihat}</code>
      <button on:click={() => (menampilkan = false)}>Tutup</button>
    </div>
  {/if}
</section>

<style>
  .vault { max-width: 60rem; margin: 0 auto; padding: var(--space-3, 1rem); }
  .hint { color: var(--color-text-muted, var(--color-text)); }
  .err { color: var(--color-neg); }
  .ok { color: var(--color-pos); }
  form { display: grid; gap: var(--space-2, 0.5rem); grid-template-columns: 1fr 1fr; margin: var(--space-3, 1rem) 0; }
  textarea, form button { grid-column: 1 / -1; }
  input, select, textarea, button { border: 1px solid var(--color-line); border-radius: var(--radius-sm, 0.375rem); font: inherit; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; border-bottom: 1px solid var(--color-line-soft); }
  .nonaktif { opacity: 0.5; }
  .aksi { display: flex; gap: var(--space-2, 0.5rem); }
  .bahaya { color: var(--color-neg); }
  .reveal { position: fixed; inset: auto 0 20% 0; margin: 0 auto; width: min(30rem, 90vw);
    background: var(--color-paper); border: 1px solid var(--color-line); border-radius: var(--radius-md, 0.625rem); padding: var(--space-3, 1rem); text-align: center; }
  .reveal code { display: block; margin: var(--space-2, 0.5rem) 0; font-size: 1.1rem; user-select: all; }
</style>
