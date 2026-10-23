#!/usr/bin/env bash
# Pustaka bersama deploy/rollback service sumber (api/worker).
# Di-source oleh ops/deploy-service.sh dan ops/rollback-service.sh — jangan dijalankan langsung.
# Pemanggil wajib menetapkan: svc, unit, ROOT, BUILD_ID, TIMEOUT_S, INTERVAL_S.

API_BASE="http://127.0.0.1:8800"

# Sidik jari kode yang SEHARUSNYA jalan (dihitung dari isi berkas di disk repo).
# Dibandingkan dengan yang dilaporkan proses: build_id saja tidak cukup karena nilainya
# berasal dari env yang ditulis sesi deploy itu sendiri (temuan audit TINGGI-4).
fingeprint_disk() {
	"$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/packages/core/src")
try:
    from warroom_core.fingerprint import kode_fingerprint

    print(kode_fingerprint())
except Exception:
    print("")
PY
}

# Build_id proses harus sama dengan yang baru diset: tanpa itu "restart" bisa berarti
# proses lama yang masih jalan (pola insiden 2026-10 api/web). Ditambah bukti kedua:
# sidik jari kode yang dilaporkan proses harus sama dengan isi berkas di disk.
gate_identity_api() {
	local id_proses fp_proses fp_disk
	local body
	body="$(curl -sf --max-time 5 "$API_BASE/api/v1/build" 2>/dev/null)" || return 1
	id_proses="$(printf '%s' "$body" | \
		sed -nE 's/.*"build_id"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' | head -n1)"
	fp_proses="$(printf '%s' "$body" | \
		sed -nE 's/.*"kode_fingerprint"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p' | head -n1)"
	[[ -n "$id_proses" && "$id_proses" == "$BUILD_ID" ]] || return 1

	# Bila proses belum melaporkan fingerprint (versi lama), jangan gagalkan deploy:
	# gate kedua ini menambah bukti, tidak boleh memblokir rollback ke build lama.
	[[ -n "$fp_proses" ]] || return 0

	fp_disk="$(fingeprint_disk)"
	[[ -n "$fp_disk" && "$fp_proses" == "$fp_disk" ]]
}

# Tanpa crash-loop: restart manual menyetel NRestarts=0; bacaan >0 berarti unit sempat mati.
gate_no_restarts() {
	local n
	n="$(systemctl show -p NRestarts --value "$unit" 2>/dev/null)" || return 1
	[[ "$n" == "0" ]]
}

gate_api() {
	local elapsed=0
	while (( elapsed < TIMEOUT_S )); do
		systemctl is-active --quiet "$unit" || return 1
		if gate_identity_api && gate_no_restarts; then
			return 0
		fi
		sleep "$INTERVAL_S"
		elapsed=$(( elapsed + INTERVAL_S ))
	done
	systemctl is-active --quiet "$unit" && gate_identity_api && gate_no_restarts
}

# Worker tak punya endpoint HTTP; bukti sehat = selalu aktif selama jendela gate
# dan tidak auto-restart (ExecStartPre gagal / import crash muncul dalam hitungan detik).
gate_worker() {
	local elapsed=0
	while (( elapsed < TIMEOUT_S )); do
		systemctl is-active --quiet "$unit" || return 1
		sleep "$INTERVAL_S"
		elapsed=$(( elapsed + INTERVAL_S ))
	done
	gate_no_restarts
}

gate() {
	if [[ "$svc" == "api" ]]; then gate_api; else gate_worker; fi
}

# Hanya kode; bila deploy sebelumnya menjalankan migrasi, skema bisa lebih baru dari
# kode lama -> unit menolak start. Penurunan skema adalah keputusan owner.
rollback_dan_restart() {
	local rev="$1"
	git -C "$ROOT" reset --hard "$rev"
	BUILD_ID="$(git -C "$ROOT" rev-parse --short HEAD)-$(date -u +%Y%m%dT%H%M%SZ)"
	bash "$OPS_DIR/set-build-id.sh" "$BUILD_ID"
	sudo -n systemctl restart "$unit"
	echo "PERINGATAN: rollback kode ke $rev selesai — bila DB sudah dimigrasi lebih jauh,
dan unit gagal start, jalan ulang hanya setelah keputusan skema (lihat runbook deploy)."
}
