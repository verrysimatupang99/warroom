# Laya AI di server ini — instalasi & batas aman

Dokumen ini mencatat cara memasang Laya AI untuk middleware forex **tanpa** menabrak
keterbatasan mesin (tanpa GPU, RAM 14,8 GB, swap 2 GB, disk 48 GB yang sudah 78% penuh).

## Masalah yang sudah terjadi (23 Okt 2026)

`uv pip install laya` menarik **torch versi CUDA** (`2.14.1+cu130`) beserta
**`nvidia_*` 15 paket (3,2 GB) + triton (895 MB)**, padahal server ini **tidak punya GPU**
(`nvidia-smi` kosong, `torch.cuda.is_available()` = False).

Akibatnya:
- `.venv` membengkak **5,7 GB**
- inferensi Laya memakai **~1,1 GB RAM**
- saat RAM sudah mepet (swap 2 GB sudah terpakai oleh proses lain: OpenClaw 1,8 GB,
  mariadb, npx node, Hermes), lonjakan itu mendorong sistem ke batas dan
  **`/api/v1/build` berhenti merespons (000)** selama inferensi.

## Perbaikan yang diterapkan

1. **torch CPU-only**, dipasang ulang secara eksplisit:

   ```bash
   uv pip install --python .venv/bin/python --reinstall \
     --index-url https://download.pytorch.org/whl/cpu torch
   ```

   Catatan: tanpa `--reinstall`, uv hanya mencetak *"Checked 1 package in 7ms"* dan
   TIDAK mengganti wheel — torch CUDA tetap terpakai.

2. **Hapus paket CUDA yatim** (tidak dipakai karena tak ada GPU):

   ```bash
   uv pip uninstall --python .venv/bin/python \
     nvidia_cublas nvidia_cuda_cupti nvidia_cuda_nvrtc nvidia_cuda_runtime \
     nvidia_cudnn_cu13 nvidia_cufft nvidia_cufile nvidia_curand nvidia_cusolver \
     nvidia_cusparse nvidia_cusparselt_cu13 nvidia_nccl_cu13 nvidia_nvjitlink \
     nvidia_nvshmem_cu13 nvidia_nvtx
   uv pip uninstall --python .venv/bin/python triton
   ```

3. **Hasil terukur**: `.venv` **5,7 GB -> 1,2 GB** (hemat 4,5 GB).
   `torch 2.14.1+cpu`, `transformers 5.20.2` tetap berfungsi.
   Inferensi Laya tetap memberi verdict nyata:
   `SKIP, keyakinan 0.4588 (ambang 0.60)` dalam ~27 detik.

## Aturan pemakaian (WAJIB)

Inferensi Laya **dimatikan secara default** di API karena modelnya bisa menjatuhkan
layanan. Nyalakan hanya bila disengaja:

```bash
sudo systemctl edit warroom-api      # tambah: Environment=WARROOM_LAYA_ENABLE=1
sudo systemctl restart warroom-api
```

Tanpa itu, `GET /api/v1/tencent/forex/laya` menjawab:

```json
{"tersedia": false, "verdict": "TAK_DIKETAHUI",
 "alasan": "inferensi dimatikan demi kestabilan layanan; ..."}
```

**Jangan menyalakan on-demand di jam trading.** Model 421M + torch memakan ~1 GB RAM
dan CPU; bila dipanggil saat pasar aktif, risiko API tersendat lebih besar daripada
manfaat verdict-nya. Jalur yang disarankan: jalankan `laya_cli.py` lewat timer
terjadwal (mis. tiap 15 menit), simpan hasilnya ke state, lalu endpoint hanya membaca.

## Peringatan lain

- `laya` terdaftar sebagai **extra opsional** (`--extra forex`). Menjalankan
  `uv sync` tanpa extra itu akan **menghapus** laya dari venv.
- Setelah `uv sync` apa pun, **periksa ulang** apakah torch kembali ke versi CUDA:
  `.venv/bin/python -c "import torch; print(torch.__version__)"` harus berakhiran `+cpu`.
- Disk saat ini ~80% (9,7 GB sisa). Menarik ulang paket CUDA butuh ~4,5 GB ruang.
