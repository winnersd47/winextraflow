//+------------------------------------------------------------------+
//| Strategy 1 — Trend Following.                                    |
//|                                                                  |
//| Enters in the direction of an established trend: fast EMA above  |
//| slow EMA, price above both, and the slow EMA itself rising. The  |
//| third condition is what separates a trend from a cross that just |
//| happened inside a range — a cross alone fires constantly in a    |
//| flat market, which is how this family of rules usually loses.    |
//|                                                                  |
//| Platform record for this label: 3 signals, 0 closed. Nothing is  |
//| known about whether it works. AutoTrade=false until it is.       |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int FastEMA = 12;
input int SlowEMA = 26;
input int SlopeBars = 5;      // bars over which the slow EMA must rise

int hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE;

int OnInit()
  {
   hFast = iMA(_Symbol, _Period, FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, _Period, SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE)
      return INIT_FAILED;
   WefBanner("Trend Following", 1);
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(1))
      return;

   double fast[], slow[];
   if(CopyBuffer(hFast, 0, 0, 2, fast) < 2)
      return;
   if(CopyBuffer(hSlow, 0, 0, SlopeBars + 1, slow) < SlopeBars + 1)
      return;

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slope = slow[0] - slow[SlopeBars];

   if(fast[0] > slow[0] && price > fast[0] && slope > 0.0)
     {
      WefSetup s = WefBuildSetup("buy", StringFormat(
         "EMA%d>%d, цена выше обеих, наклон +%s за %d баров",
         FastEMA, SlowEMA, DoubleToString(slope, _Digits), SlopeBars));
      WefAct(s, 1, "Trend Following");
     }
   else if(fast[0] < slow[0] && price < fast[0] && slope < 0.0)
     {
      WefSetup s = WefBuildSetup("sell", StringFormat(
         "EMA%d<%d, цена ниже обеих, наклон %s за %d баров",
         FastEMA, SlowEMA, DoubleToString(slope, _Digits), SlopeBars));
      WefAct(s, 1, "Trend Following");
     }
  }
