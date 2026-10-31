// WarRoom_TelemetryBridge.mq5
// EA telemetri-saja: tempel di chart akun MT5 mana pun (mis. HSFX cent) untuk
// mengirim saldo, posisi, dan deal tertutup ke War Room. Tidak membuka order.
//
// Syarat:
//   1. Izinkan URL di Terminal > Options > Expert Advisors > Allow WebRequest:
//      https://0xgunsl1ng3r.xyz
//   2. Isi InpToken dengan token EA (env WARROOM_EA_SYNC_TOKEN di server).
//   3. Akun cent (currency USC/EUC): InpNormalizeCent=true membagi nilai uang
//      dengan 100 supaya dashboard menampilkan USD, bukan sen.
//
// Endpoint: /api/v1/tencent/mt5/telemetry dan /api/v1/tencent/mt5/deal.
#property copyright "War Room"
#property version   "1.00"
#property strict

input string InpApiBase          = "https://0xgunsl1ng3r.xyz";
input string InpToken            = "";
input int    InpIntervalSec      = 5;      // kirim telemetri tiap N detik
input int    InpDealPollSec      = 5;      // poll deal tertutup tiap N detik
input string InpStrategyVersion  = "hsfx-onepiece";
input bool   InpNormalizeCent    = true;

datetime g_lastDealPoll = 0;
datetime g_lastDealSend = 0;
ulong    g_sentDeals[];

bool SudahKirim(const ulong t)
{
   for(int i = 0; i < ArraySize(g_sentDeals); i++)
      if(g_sentDeals[i] == t)
         return true;
   return false;
}

void TandaiKirim(const ulong t)
{
   int n = ArraySize(g_sentDeals);
   if(n >= 1000)
   {
      ArrayRemove(g_sentDeals, 0, 1);
      n--;
   }
   ArrayResize(g_sentDeals, n + 1);
   g_sentDeals[n] = t;
}

string JsonEscape(const string teks)
{
   string o = teks;
   StringReplace(o, "\\", "\\\\");
   StringReplace(o, "\"", "\\\"");
   StringReplace(o, "\r", "\\r");
   StringReplace(o, "\n", "\\n");
   StringReplace(o, "\t", "\\t");
   return o;
}

double FaktorAkun()
{
   if(!InpNormalizeCent)
      return 1.0;
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   if(cur == "USC" || cur == "EUC" || cur == "USC." || cur == "EUC.")
      return 0.01;
   return 1.0;
}

bool KirimJson(const string path, const string json)
{
   char data[], hasil[];
   string hdr = "Content-Type: application/json\r\nX-Warroom-Token: " + InpToken + "\r\n";
   int len = StringLen(json);
   ArrayResize(data, len);
   StringToCharArray(json, data, 0, len, CP_UTF8);
   string hasilHdr;
   ResetLastError();
   int code = WebRequest("POST", InpApiBase + path, hdr, 10000, data, hasil, hasilHdr);
   if(code != 200)
   {
      PrintFormat("WarRoom telemetry gagal %s: HTTP %d err=%d", path, code, GetLastError());
      return false;
   }
   return true;
}

string PosisiJson()
{
   string out = "";
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      long tipe = PositionGetInteger(POSITION_TYPE);
      double vol = PositionGetDouble(POSITION_VOLUME);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double current = (tipe == POSITION_TYPE_BUY)
                       ? SymbolInfoDouble(sym, SYMBOL_BID)
                       : SymbolInfoDouble(sym, SYMBOL_ASK);
      double pnl = PositionGetDouble(POSITION_PROFIT)
                 + PositionGetDouble(POSITION_SWAP);
      if(StringLen(out) > 0)
         out += ",";
      out += StringFormat(
         "{\"ticket\":%s,\"symbol\":\"%s\",\"side\":\"%s\",\"volume\":%.2f,"
         "\"open_price\":%.5f,\"current_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,"
         "\"pnl_usd\":%.2f,\"open_time\":\"%s\"}",
         IntegerToString((long)ticket), JsonEscape(sym),
         (tipe == POSITION_TYPE_BUY ? "BUY" : "SELL"), vol,
         open, current, sl, tp, pnl,
         TimeToString((datetime)PositionGetInteger(POSITION_TIME), TIME_DATE | TIME_SECONDS));
   }
   return "[" + out + "]";
}

string PendingJson()
{
   string out = "";
   int total = OrdersTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      long tipe = OrderGetInteger(ORDER_TYPE);
      if(tipe != ORDER_TYPE_BUY_LIMIT && tipe != ORDER_TYPE_SELL_LIMIT
         && tipe != ORDER_TYPE_BUY_STOP && tipe != ORDER_TYPE_SELL_STOP)
         continue;
      if(StringLen(out) > 0)
         out += ",";
      out += StringFormat(
         "{\"ticket\":%s,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,"
         "\"price\":%.5f,\"sl\":%.5f,\"tp\":%.5f}",
         IntegerToString((long)ticket), JsonEscape(OrderGetString(ORDER_SYMBOL)),
         (int)tipe, OrderGetDouble(ORDER_VOLUME_CURRENT),
         OrderGetDouble(ORDER_PRICE_OPEN), OrderGetDouble(ORDER_SL),
         OrderGetDouble(ORDER_TP));
   }
   return "[" + out + "]";
}

void KirimTelemetri()
{
   double f = FaktorAkun();
   double balance = AccountInfoDouble(ACCOUNT_BALANCE) * f;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY) * f;
   double floating = AccountInfoDouble(ACCOUNT_PROFIT) * f;
   double margin = AccountInfoDouble(ACCOUNT_MARGIN) * f;
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE) * f;
   string akun = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string broker = AccountInfoString(ACCOUNT_COMPANY);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   double netHari = 0.0;
   int menang = 0, kalah = 0, totalDeal = 0;
   datetime awalHari = (datetime)((long)TimeCurrent() - ((long)TimeCurrent() % 86400));
   if(HistorySelect(awalHari, TimeCurrent() + 60))
   {
      int n = HistoryDealsTotal();
      for(int i = 0; i < n; i++)
      {
         ulong t = HistoryDealGetTicket(i);
         if(t == 0)
            continue;
         if(HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT)
            continue;
         double laba = HistoryDealGetDouble(t, DEAL_PROFIT)
                     + HistoryDealGetDouble(t, DEAL_SWAP)
                     + HistoryDealGetDouble(t, DEAL_COMMISSION);
         netHari += laba;
         totalDeal++;
         if(laba > 0)
            menang++;
         else if(laba < 0)
            kalah++;
      }
   }
   string json = StringFormat(
      "{\"account\":\"%s\",\"broker\":\"%s\",\"currency\":\"%s\",\"cent_factor\":%.2f,"
      "\"balance\":%.2f,\"equity\":%.2f,\"floating_pnl\":%.2f,\"margin\":%.2f,"
      "\"free_margin\":%.2f,\"positions\":%s,\"pending_orders\":%s,"
      "\"net_pnl_today_usd\":%.2f,\"total_trades_today\":%d,\"wins\":%d,\"losses\":%d,"
      "\"server_time\":%s}",
      akun, JsonEscape(broker), JsonEscape(currency), f,
      balance, equity, floating, margin, freeMargin,
      PosisiJson(), PendingJson(), netHari * f, totalDeal, menang, kalah,
      IntegerToString((long)TimeCurrent()));
   KirimJson("/api/v1/tencent/mt5/telemetry", json);
}

void KirimDeal()
{
   datetime sekarang = TimeCurrent();
   if(sekarang - g_lastDealSend < InpDealPollSec)
      return;
   g_lastDealSend = sekarang;
   datetime dari = (g_lastDealPoll > 0) ? g_lastDealPoll - 120 : sekarang - 86400;
   if(!HistorySelect(dari, sekarang + 60))
      return;
   g_lastDealPoll = sekarang;
   double f = FaktorAkun();
   string akun = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
   {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0 || SudahKirim(t))
         continue;
      if(HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT)
         continue;
      // Deal penutup tidak membawa harga/waktu entry; biarkan kosong daripada
      // mengarang. Jurnal memakai close_price dan net.
      long posId = HistoryDealGetInteger(t, DEAL_POSITION_ID);
      string openTime = "";
      double openPrice = 0.0;
      long tipe = HistoryDealGetInteger(t, DEAL_TYPE);
      string json = StringFormat(
         "{\"ticket\":%s,\"position\":%s,\"symbol\":\"%s\",\"side\":\"%s\","
         "\"volume\":%.2f,\"open_time\":\"%s\",\"open_price\":%.5f,"
         "\"close_time\":\"%s\",\"close_price\":%.5f,\"profit\":%.2f,\"swap\":%.2f,"
         "\"commission\":%.2f,\"magic\":%s,\"comment\":\"%s\",\"account\":\"%s\","
         "\"strategy_version\":\"%s\"}",
         IntegerToString((long)t), IntegerToString(posId),
         JsonEscape(HistoryDealGetString(t, DEAL_SYMBOL)),
         (tipe == DEAL_TYPE_BUY ? "BUY" : "SELL"),
         HistoryDealGetDouble(t, DEAL_VOLUME), openTime, openPrice,
         TimeToString((datetime)HistoryDealGetInteger(t, DEAL_TIME), TIME_DATE | TIME_SECONDS),
         HistoryDealGetDouble(t, DEAL_PRICE),
         HistoryDealGetDouble(t, DEAL_PROFIT) * f,
         HistoryDealGetDouble(t, DEAL_SWAP) * f,
         HistoryDealGetDouble(t, DEAL_COMMISSION) * f,
         IntegerToString(HistoryDealGetInteger(t, DEAL_MAGIC)),
         JsonEscape(HistoryDealGetString(t, DEAL_COMMENT)), akun,
         JsonEscape(InpStrategyVersion));
      if(KirimJson("/api/v1/tencent/mt5/deal", json))
         TandaiKirim(t);
   }
}

int OnInit()
{
   if(StringLen(InpToken) == 0)
      Print("WarRoom bridge: InpToken kosong; telemetri akan ditolak 401.");
   g_lastDealPoll = TimeCurrent() - 86400;
   EventSetTimer((int)MathMax(1, InpIntervalSec));
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   KirimTelemetri();
   KirimDeal();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}
