//+------------------------------------------------------------------+
//| Strategy 6 — Statistical / Arbitrage.                            |
//|                                                                  |
//| Proper statistical arbitrage trades the SPREAD between two       |
//| correlated instruments and is market-neutral. One chart cannot   |
//| do that, so this is the honest single-symbol version: a z-score  |
//| of price against its own moving average, entering when the       |
//| deviation is statistically large and exiting at the mean.        |
//|                                                                  |
//| Say plainly what that means — it is mean reversion with a        |
//| statistical trigger, not arbitrage. There is no second leg, so   |
//| there is no hedge and no market neutrality. The name comes from  |
//| the platform's strategy table, not from what this file does.     |
//|                                                                  |
//| A real pairs version needs a second symbol and a cointegration   |
//| test; set PairSymbol to enable the spread variant.               |
//|                                                                  |
//| Platform record: 0 signals. This label has never been assigned.  |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int    ZPeriod   = 50;
input double ZEntry    = 2.0;     // standard deviations from the mean
input string PairSymbol = "";     // empty = single-symbol z-score

int OnInit()
  {
   WefBanner("Statistical / Arbitrage", 6);
   if(StringLen(PairSymbol) == 0)
      Print("Режим: z-score по одному инструменту. Это возврат к среднему ",
            "со статистическим триггером, а не арбитраж — второй ноги нет.");
   else
     {
      if(!SymbolSelect(PairSymbol, true))
        {
         Print("Не удалось выбрать ", PairSymbol);
         return INIT_FAILED;
        }
      Print("Режим: спред ", _Symbol, " / ", PairSymbol);
     }
   return INIT_SUCCEEDED;
  }

// Z-score of the latest value of `series` against its own window.
bool ZScore(const double &series[], const int n, double &z, double &mean)
  {
   if(n < 2)
      return false;
   double sum = 0.0;
   for(int i = 0; i < n; i++)
      sum += series[i];
   mean = sum / n;
   double var = 0.0;
   for(int i = 0; i < n; i++)
      var += (series[i] - mean) * (series[i] - mean);
   double sd = MathSqrt(var / n);
   if(sd <= 0.0)
      return false;
   z = (series[0] - mean) / sd;
   return true;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(6))
      return;

   double series[];
   ArrayResize(series, ZPeriod);

   if(StringLen(PairSymbol) == 0)
     {
      for(int i = 0; i < ZPeriod; i++)
         series[i] = iClose(_Symbol, _Period, i);
     }
   else
     {
      // Log ratio: the usual spread definition, scale-free between symbols.
      for(int i = 0; i < ZPeriod; i++)
        {
         double a = iClose(_Symbol, _Period, i);
         double b = iClose(PairSymbol, _Period, i);
         if(a <= 0.0 || b <= 0.0)
            return;
         series[i] = MathLog(a / b);
        }
     }

   double z = 0.0, mean = 0.0;
   if(!ZScore(series, ZPeriod, z, mean))
      return;

   string what = (StringLen(PairSymbol) == 0) ? "цена" : "спред " + _Symbol + "/" + PairSymbol;

   if(z <= -ZEntry)
     {
      WefSetup s = WefBuildSetup("buy", StringFormat(
         "%s на %.2f σ ниже среднего (порог %.1f)", what, -z, ZEntry));
      WefAct(s, 6, "Statistical / Arbitrage");
     }
   else if(z >= ZEntry)
     {
      WefSetup s = WefBuildSetup("sell", StringFormat(
         "%s на %.2f σ выше среднего (порог %.1f)", what, z, ZEntry));
      WefAct(s, 6, "Statistical / Arbitrage");
     }
  }
