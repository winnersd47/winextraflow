//+------------------------------------------------------------------+
//| Strategy 3 — Range / Flat.                                       |
//|                                                                  |
//| Buys the floor of a channel and sells its ceiling, but only when |
//| a channel exists: the range of the last N bars must be narrow    |
//| relative to ATR. Without that test the rule "buy the low" fires  |
//| every bar of a downtrend, each time at a lower low.              |
//|                                                                  |
//| Unlike the other six, this one sets its target at the opposite   |
//| edge rather than at 4xATR — a channel trade that aims beyond the |
//| channel is not a channel trade.                                  |
//|                                                                  |
//| Platform record: 7 signals, 4 closed, 3 wins. Four trades.       |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int    ChannelBars    = 30;
input double MaxRangeATR    = 6.0;    // channel height, in ATR, to count as flat
input double EdgeTolerance  = 0.15;   // how close to the edge counts as a touch

int OnInit()
  {
   WefBanner("Range / Flat", 3);
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(3))
      return;

   double atr = WefATR();
   if(atr <= 0.0)
      return;

   int hi = iHighest(_Symbol, _Period, MODE_HIGH, ChannelBars, 1);
   int lo = iLowest(_Symbol, _Period, MODE_LOW, ChannelBars, 1);
   if(hi < 0 || lo < 0)
      return;

   double top = iHigh(_Symbol, _Period, hi);
   double bot = iLow(_Symbol, _Period, lo);
   double height = top - bot;
   if(height <= 0.0)
      return;

   // A channel, or a trend that happens to have a high and a low?
   if(height > MaxRangeATR * atr)
      return;

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double band  = height * EdgeTolerance;

   if(price <= bot + band)
     {
      WefSetup s = WefBuildSetup("buy", StringFormat(
         "Канал %s–%s (%.1fxATR), цена у нижней границы",
         DoubleToString(bot, _Digits), DoubleToString(top, _Digits),
         height / atr));
      // Target the far edge, stop just outside the near one.
      if(s.valid)
        {
         s.tp = top;
         s.sl = bot - StopATRMult * atr * 0.5;
        }
      WefAct(s, 3, "Range / Flat");
     }
   else if(price >= top - band)
     {
      WefSetup s = WefBuildSetup("sell", StringFormat(
         "Канал %s–%s (%.1fxATR), цена у верхней границы",
         DoubleToString(bot, _Digits), DoubleToString(top, _Digits),
         height / atr));
      if(s.valid)
        {
         s.tp = bot;
         s.sl = top + StopATRMult * atr * 0.5;
        }
      WefAct(s, 3, "Range / Flat");
     }
  }
