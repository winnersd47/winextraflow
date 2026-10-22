//+------------------------------------------------------------------+
//| Strategy 2 — Mean Reversion.                                     |
//|                                                                  |
//| Fades an extreme: RSI past its threshold AND price outside the   |
//| Bollinger band, with the slow EMA flat. The flat filter is the   |
//| important part — buying an oversold reading inside a downtrend   |
//| is not mean reversion, it is catching a falling knife, and it is |
//| the standard way this rule bankrupts people.                     |
//|                                                                  |
//| Platform record for this label: 6 signals, 4 closed, 2 wins.     |
//| Four trades decide nothing.                                      |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int    RSIPeriod   = 14;
input double RSIOversold = 30.0;
input double RSIOverbought = 70.0;
input int    BandPeriod  = 20;
input double BandDev     = 2.0;
input int    FlatEMA     = 50;
input double FlatSlopeATR = 0.5;   // slope must stay inside this many ATR

int hRSI = INVALID_HANDLE, hBand = INVALID_HANDLE, hEMA = INVALID_HANDLE;

int OnInit()
  {
   hRSI  = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
   hBand = iBands(_Symbol, _Period, BandPeriod, 0, BandDev, PRICE_CLOSE);
   hEMA  = iMA(_Symbol, _Period, FlatEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(hRSI == INVALID_HANDLE || hBand == INVALID_HANDLE || hEMA == INVALID_HANDLE)
      return INIT_FAILED;
   WefBanner("Mean Reversion", 2);
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(2))
      return;

   double rsi[], upper[], lower[], ema[];
   if(CopyBuffer(hRSI, 0, 0, 1, rsi) < 1)
      return;
   if(CopyBuffer(hBand, 1, 0, 1, upper) < 1)
      return;
   if(CopyBuffer(hBand, 2, 0, 1, lower) < 1)
      return;
   if(CopyBuffer(hEMA, 0, 0, 11, ema) < 11)
      return;

   double atr = WefATR();
   if(atr <= 0.0)
      return;
   // Only fade when the market is not trending.
   if(MathAbs(ema[0] - ema[10]) > FlatSlopeATR * atr)
      return;

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(rsi[0] <= RSIOversold && price <= lower[0])
     {
      WefSetup s = WefBuildSetup("buy", StringFormat(
         "RSI %s <= %s, цена ниже нижней полосы, тренд плоский",
         DoubleToString(rsi[0], 1), DoubleToString(RSIOversold, 0)));
      WefAct(s, 2, "Mean Reversion");
     }
   else if(rsi[0] >= RSIOverbought && price >= upper[0])
     {
      WefSetup s = WefBuildSetup("sell", StringFormat(
         "RSI %s >= %s, цена выше верхней полосы, тренд плоский",
         DoubleToString(rsi[0], 1), DoubleToString(RSIOverbought, 0)));
      WefAct(s, 2, "Mean Reversion");
     }
  }
