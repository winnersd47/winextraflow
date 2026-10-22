//+------------------------------------------------------------------+
//| Strategy 5 — Multi-Indicator.                                    |
//|                                                                  |
//| Requires agreement from EMA, MACD and RSI before entering, and   |
//| counts how many agree rather than demanding all three: a vote.   |
//| MinVotes is an input so the trade-off is explicit — three of     |
//| three trades rarely and may be right more often; two of three    |
//| trades often. Which is better is exactly what the record is for. |
//|                                                                  |
//| RSI here is a direction filter, not an extreme filter: above 50  |
//| is bullish. Using it as an overbought gate would contradict the  |
//| other two, which is how "confluence" systems end up never firing.|
//|                                                                  |
//| Platform record: 23 signals, 1 closed, 1 win. One trade.         |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int FastEMA  = 12;
input int SlowEMA  = 26;
input int MACDFast = 12;
input int MACDSlow = 26;
input int MACDSig  = 9;
input int RSIPeriod = 14;
input int MinVotes  = 3;    // 2 = more trades, 3 = fewer and stricter

int hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE;
int hMACD = INVALID_HANDLE, hRSI = INVALID_HANDLE;

int OnInit()
  {
   hFast = iMA(_Symbol, _Period, FastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, _Period, SlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   hMACD = iMACD(_Symbol, _Period, MACDFast, MACDSlow, MACDSig, PRICE_CLOSE);
   hRSI  = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE
      || hMACD == INVALID_HANDLE || hRSI == INVALID_HANDLE)
      return INIT_FAILED;
   WefBanner("Multi-Indicator", 5);
   Print("Голосов для входа: ", MinVotes, " из 3");
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(5))
      return;

   double fast[], slow[], macd[], sig[], rsi[];
   if(CopyBuffer(hFast, 0, 0, 1, fast) < 1)
      return;
   if(CopyBuffer(hSlow, 0, 0, 1, slow) < 1)
      return;
   if(CopyBuffer(hMACD, 0, 0, 1, macd) < 1)
      return;
   if(CopyBuffer(hMACD, 1, 0, 1, sig) < 1)
      return;
   if(CopyBuffer(hRSI, 0, 0, 1, rsi) < 1)
      return;

   int bull = 0, bear = 0;
   string why = "";

   if(fast[0] > slow[0]) { bull++; why += "EMA↑ "; }
   else                  { bear++; why += "EMA↓ "; }

   if(macd[0] > sig[0])  { bull++; why += "MACD↑ "; }
   else                  { bear++; why += "MACD↓ "; }

   if(rsi[0] > 50.0)     { bull++; why += StringFormat("RSI %.0f↑", rsi[0]); }
   else                  { bear++; why += StringFormat("RSI %.0f↓", rsi[0]); }

   if(bull >= MinVotes)
     {
      WefSetup s = WefBuildSetup("buy", StringFormat("%d/3 за покупку: %s", bull, why));
      WefAct(s, 5, "Multi-Indicator");
     }
   else if(bear >= MinVotes)
     {
      WefSetup s = WefBuildSetup("sell", StringFormat("%d/3 за продажу: %s", bear, why));
      WefAct(s, 5, "Multi-Indicator");
     }
  }
