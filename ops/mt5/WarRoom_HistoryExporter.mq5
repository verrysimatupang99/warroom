//+------------------------------------------------------------------+
//| WarRoom_HistoryExporter.mq5                                       |
//| Ekspor data historis OHLCV dari terminal MT5 ke CSV.              |
//|                                                                   |
//| HANYA MEMBACA. Tidak ada OrderSend / trade / close di file ini.   |
//| Akun di terminal ini REAL -- EA ini tidak boleh menyentuh order.  |
//|                                                                   |
//| Hasil ditulis ke MQL5/Files/ agar bisa dibaca dari host (bind     |
//| mount), tidak perlu koneksi jaringan dari dalam Wine.             |
//+------------------------------------------------------------------+
#property copyright "WarRoom"
#property version   "1.00"
#property strict

input string InpSymbols = "XAUUSD";      // Simbol, pisahkan dengan koma
input string  InpFrames = "M1,M5,M15,H1"; // Timeframe
input datetime InpFrom  = D'2015.01.01';  // Mulai
input datetime InpTo    = D'2026.12.31';  // Selesai
input int     InpMaxBar = 3000000;        // Batas bar per ekspor

string namaFile(string simbol, ENUM_TIMEFRAMES tf)
  {
   // Nama timeframe dibersihkan supaya aman dipakai sebagai nama file.
   string ns = simbol;
   StringReplace(ns, ".", "_");
   StringReplace(ns, "#", "_");
   string nt = EnumToString(tf);
   StringReplace(nt, "PERIOD_", "");
   StringToLower(nt);
   return ns + "_" + nt + ".csv";
  }

// Satu berkas per simbol+timeframe. Baris pertama selalu header supaya
// pemroses di host bisa memeriksa format tanpa menebak.
bool ekspor(ENUM_TIMEFRAMES tf)
  {
   string daftar[];
   int n = StringSplit(InpSymbols, ',', daftar);
   bool semuaOk = true;

   for(int i = 0; i < n; i++)
     {
      string simbol = daftar[i];
      StringTrimLeft(simbol);
      StringTrimRight(simbol);
      if(StringLen(simbol) == 0)
         continue;

      if(!SymbolSelect(simbol, true))
        {
         PrintFormat("Simbol %s tidak dikenal terminal", simbol);
         semuaOk = false;
         continue;
        }

      int tersedia = Bars(simbol, tf, InpFrom, InpTo);
      if(tersedia <= 0)
        {
         PrintFormat("%s %s: tidak ada bar", simbol, EnumToString(tf));
         semuaOk = false;
         continue;
        }
      if(tersedia > InpMaxBar)
         tersedia = InpMaxBar;

      MqlRates rates[];
      int disalin = CopyRates(simbol, tf, InpFrom, InpTo, rates);
      int jumlah = MathMin(disalin, tersedia);
      if(jumlah <= 0)
        {
         PrintFormat("%s %s: CopyRates gagal (err %d)", simbol, EnumToString(tf), GetLastError());
         semuaOk = false;
         continue;
        }

      string file = namaFile(simbol, tf);
      int fh = FileOpen(file, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(fh == INVALID_HANDLE)
        {
         PrintFormat("Gagal buka %s (err %d)", file, GetLastError());
         semuaOk = false;
         continue;
        }

      FileWrite(fh, "time_utc_epoch", "open", "high", "low", "close",
                "tick_volume", "real_volume", "spread");
      for(int b = 0; b < jumlah; b++)
         FileWrite(fh, (long)rates[b].time, rates[b].open, rates[b].high,
                   rates[b].low, rates[b].close, (long)rates[b].tick_volume,
                   (long)rates[b].real_volume, (int)rates[b].spread);
      FileClose(fh);

      PrintFormat("%s %s: %d bar -> %s", simbol, EnumToString(tf), jumlah, file);
     }
   return semuaOk;
  }

void OnStart()
  {
   // Tulis penanda supaya host tahu EA benar-benar berjalan.
   int fh = FileOpen("_exporter_status.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh != INVALID_HANDLE)
     {
      FileWrite(fh, "mulai " + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
      FileClose(fh);
     }

   bool ok = ekspor(PERIOD_M1);
   ok = ekspor(PERIOD_M5) && ok;
   ok = ekspor(PERIOD_M15) && ok;
   ok = ekspor(PERIOD_H1) && ok;

   fh = FileOpen("_exporter_status.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh != INVALID_HANDLE)
     {
      FileWrite(fh, (ok ? "selesai" : "selesai-dengan-galat") + " " +
                TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
      FileClose(fh);
     }
   Print("Ekspor selesai: ", ok ? "OK" : "ada yang gagal");
  }
//+------------------------------------------------------------------+
