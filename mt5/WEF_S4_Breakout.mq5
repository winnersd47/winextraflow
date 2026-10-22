//+------------------------------------------------------------------+
//| Strategy 4 — Breakout.                                           |
//|                                                                  |
//| Enters when price leaves a consolidation. Two filters decide     |
//| whether it is a breakout or noise: the range before the break    |
//| must have been tight (a break out of nothing is not a break),    |
//| and the breaking bar must carry above-average volume.            |
//|                                                                  |
//| The project measured where this family goes wrong: targets set   |
//| far beyond the break lose money. The replay of 80 signals showed |
//| the widest-target band at -7.04% per trade. Hence the standard   |
//| 4xATR target rather than "run it".                               |
//|                                                                  |
//| Platform record: 23 signals, 6 closed, 1 win.                    |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int    SqueezeBars   = 20;
input double MaxSqueezeATR = 4.0;    // consolidation height, in ATR
input double VolumeMult    = 1.5;    // breaking bar vs average volume

int OnInit()
  {
   WefBanner("Breakout", 4);
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(4))
      return;

   double atr = WefATR();
   if(atr <= 0.0)
      return;

   int hi = iHighest(_Symbol, _Period, MODE_HIGH, SqueezeBars, 1);
   int lo = iLowest(_Symbol, _Period, MODE_LOW, SqueezeBars, 1);
   if(hi < 0 || lo < 0)
      return;
   double top = iHigh(_Symbol, _Period, hi);
   double bot = iLow(_Symbol, _Period, lo);
   double height = top - bot;
   if(height <= 0.0 || height > MaxSqueezeATR * atr)
      return;          // no consolidation to break out of

   // Volume confirmation on the most recent closed bar.
   long vols[];
   if(CopyTickVolume(_Symbol, _Period, 1, SqueezeBars, vols) < SqueezeBars)
      return;
   double avg = 0.0;
   for(int i = 1; i < SqueezeBars; i++)
      avg += (double)vols[i];
   avg /= (double)(SqueezeBars - 1);
   if(avg <= 0.0 || (double)vols[0] < VolumeMult * avg)
      return;

   double close = iClose(_Symbol, _Period, 1);

   if(close > top)
     {
      WefSetup s = WefBuildSetup("buy", StringFormat(
         "Пробой вверх из диапазона %.1fxATR, объём %.1fx среднего",
         height / atr, (double)vols[0] / avg));
      WefAct(s, 4, "Breakout");
     }
   else if(close < bot)
     {
      WefSetup s = WefBuildSetup("sell", StringFormat(
         "Пробой вниз из диапазона %.1fxATR, объём %.1fx среднего",
         height / atr, (double)vols[0] / avg));
      WefAct(s, 4, "Breakout");
     }
  }
