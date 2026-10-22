//+------------------------------------------------------------------+
//| Strategy 7 — ML / AI.                                            |
//|                                                                  |
//| The entry decision is not made here. The advisor sends candles   |
//| to the bridge, the platform computes indicators, asks the model, |
//| applies the WEF Score and the seven quality checks, and answers. |
//| The terminal executes what comes back.                           |
//|                                                                  |
//| That division is deliberate. Putting the model in MQL5 would     |
//| mean a second, more permissive route for our own signals, and a  |
//| platform that trusts its own output more than its sources' is    |
//| how a track record stops meaning anything.                       |
//|                                                                  |
//| Note on the label: 65% of all stored signals carry Strategy ID 7 |
//| today, but not because a model produced them — the classifier    |
//| assigns it whenever the WEF Score is >= 0.8. That rule is wrong  |
//| and is noted for repair; it does not reflect this advisor.       |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#include "WEF_Common.mqh"

input int CandleCount = 60;      // bars sent for analysis

int OnInit()
  {
   WefBanner("ML / AI", 7);
   Print("Решение принимает платформа; советник отправляет свечи и исполняет ответ.");
   return INIT_SUCCEEDED;
  }

string CandlesJson(const int count)
  {
   MqlRates r[];
   int got = CopyRates(_Symbol, _Period, 0, count, r);
   if(got <= 0)
      return "";
   int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   string out = "[";
   for(int i = 0; i < got; i++)
     {
      if(i > 0)
         out += ",";
      out += "{\"time\":\"" + TimeToString(r[i].time, TIME_DATE | TIME_MINUTES) + "\","
             + "\"open\":"  + DoubleToString(r[i].open,  d) + ","
             + "\"high\":"  + DoubleToString(r[i].high,  d) + ","
             + "\"low\":"   + DoubleToString(r[i].low,   d) + ","
             + "\"close\":" + DoubleToString(r[i].close, d) + ","
             + "\"volume\":" + IntegerToString((long)r[i].tick_volume) + "}";
     }
   return out + "]";
  }

// Minimal extractor: the answers are flat objects, so a full parser would be
// more code than the protocol deserves.
string Field(const string json, const string key)
  {
   string pat = "\"" + key + "\":";
   int p = StringFind(json, pat);
   if(p < 0)
      return "";
   p += StringLen(pat);
   while(p < StringLen(json) && StringGetCharacter(json, p) == ' ')
      p++;
   bool quoted = (StringGetCharacter(json, p) == '"');
   if(quoted)
      p++;
   string out = "";
   for(int i = p; i < StringLen(json); i++)
     {
      ushort c = StringGetCharacter(json, i);
      if(quoted && c == '"')
         break;
      if(!quoted && (c == ',' || c == '}'))
         break;
      out += ShortToString(c);
     }
   return out;
  }

void OnTick()
  {
   if(!WefDue() || WefHasPosition(7))
      return;

   string candles = CandlesJson(CandleCount);
   if(StringLen(candles) == 0)
      return;

   string body = "{" + WefJsonStr("cmd", PublishToPlatform ? "signal" : "analyze") + ","
                 + WefJsonStr("auth", BridgeToken) + ","
                 + WefJsonStr("ticker", _Symbol) + ","
                 + WefJsonStr("timeframe", EnumToString(_Period)) + ","
                 + "\"candles\":" + candles + "}";

   string resp = WefSend(body);
   if(StringLen(resp) == 0)
     {
      Print("ML/AI: мост не ответил");
      return;
     }
   Print("Платформа: ", StringSubstr(resp, 0, 400));

   string action = Field(resp, "action");
   if(action != "buy" && action != "sell")
      return;                       // hold, or the gate refused it

   // Levels come from the platform so an AI signal is held to the same
   // geometry as every other source.
   double tp = StringToDouble(Field(resp, "tp"));
   double sl = StringToDouble(Field(resp, "sl"));

   WefSetup s = WefBuildSetup(action, "Решение платформы: " + Field(resp, "reason"));
   if(s.valid && tp > 0.0 && sl > 0.0)
     {
      s.tp = tp;
      s.sl = sl;
     }
   // The decision was already stored by cmd=signal above. WefAct would report
   // it a second time and create a duplicate row, so execution is done here
   // directly — the fill is still reported, which is the part that matters.
   double lots = WefLots(s.entry, s.sl);
   string head = StringFormat("ML / AI [7] %s %s @ %s  TP %s  SL %s  (%s lots)",
                              _Symbol, s.action,
                              DoubleToString(s.entry, _Digits),
                              DoubleToString(s.tp, _Digits),
                              DoubleToString(s.sl, _Digits),
                              DoubleToString(lots, 2));
   Print(head, " | ", s.why);

   if(!AutoTrade)
     {
      Alert(head, " — AutoTrade=false, сделка не выставлена");
      return;
     }
   if(lots <= 0.0)
     {
      Print("ML/AI: риск не покрывает минимальный лот — пропуск");
      return;
     }

   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = lots;
   req.type         = (s.action == "buy") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price        = s.entry;
   req.sl           = s.sl;
   req.tp           = s.tp;
   req.deviation    = 20;
   req.magic        = MagicBase + 7;
   req.comment      = "ML / AI";
   req.type_filling = ORDER_FILLING_FOK;

   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
     {
      Print("ML/AI: ордер отклонён, retcode=", res.retcode, " ", res.comment);
      return;
     }
   WefReportFill(res.order, s.action, s.entry, res.price, res.volume);
  }
