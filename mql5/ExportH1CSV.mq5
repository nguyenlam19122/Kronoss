//+------------------------------------------------------------------+
//|                                                 ExportH1CSV.mq5   |
//|   Script xuat lich su nen H1 ra file CSV                          |
//|   -> dung lam dau vao cho backtest Python (forex_trend_bot/)      |
//|                                                                  |
//|   Cach dung:                                                     |
//|     1. Mo chart cap tien can xuat, doi khung thoi gian = H1.     |
//|     2. Keo script nay tha vao chart (tu muc Scripts trong         |
//|        Navigator). Dat so nen muon xuat o o InpBars.             |
//|     3. File luu o:  MQL5\Files\<SYMBOL>_H1.csv                    |
//|        (MT5: File -> Open Data Folder -> MQL5 -> Files)          |
//+------------------------------------------------------------------+
#property copyright "forex_trend_bot"
#property version   "1.00"
#property strict
#property script_show_inputs

input int InpBars = 50000;   // So nen H1 gan nhat muon xuat (tang neu muon dai hon)

void OnStart()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);                 // [0] = cu nhat -> [n-1] moi nhat

   int copied = CopyRates(_Symbol, PERIOD_H1, 0, InpBars, rates);
   if(copied <= 0)
   {
      Print("Khong copy duoc rates (", copied, "). ",
            "Hay cuon chart H1 ve qua khu (phim Home / PageUp) de MT5 tai them ",
            "lich su tu server Exness, roi chay lai script.");
      return;
   }

   string fname = _Symbol + "_H1.csv";
   int fh = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(fh == INVALID_HANDLE)
   {
      Print("Khong mo duoc file de ghi: ", fname, "  loi=", GetLastError());
      return;
   }

   // Header khop voi loader cua forex_trend_bot/data.py
   FileWrite(fh, "time", "open", "high", "low", "close", "volume");

   for(int i = 0; i < copied; i++)
   {
      string t = TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES);  // "YYYY.MM.DD HH:MM"
      FileWrite(fh, t,
                DoubleToString(rates[i].open,  _Digits),
                DoubleToString(rates[i].high,  _Digits),
                DoubleToString(rates[i].low,   _Digits),
                DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume);
   }

   FileClose(fh);
   PrintFormat("Da xuat %d nen H1 -> MQL5\\Files\\%s", copied, fname);
   PrintFormat("Tu ngay %s den %s",
               TimeToString(rates[0].time, TIME_DATE | TIME_MINUTES),
               TimeToString(rates[copied - 1].time, TIME_DATE | TIME_MINUTES));
}
//+------------------------------------------------------------------+
