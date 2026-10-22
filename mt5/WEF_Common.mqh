//+------------------------------------------------------------------+
//| WEF_Common.mqh — shared machinery for the strategy advisors.     |
//|                                                                  |
//| Seven advisors differ only in when they decide to enter. Levels, |
//| position size, the bridge protocol and the execution report are  |
//| identical, so they live here: a fix to the stop rule should not  |
//| have to be made seven times.                                     |
//|                                                                  |
//| READ THIS BEFORE SETTING AutoTrade=true                          |
//|                                                                  |
//| None of these strategies has been validated. The platform's own  |
//| measured record is -0.93% per trade over 22 closed signals, and  |
//| five of the seven strategy labels have fewer than five closed    |
//| trades each. An advisor that trades an unvalidated rule is a     |
//| loss generator with a schedule.                                  |
//|                                                                  |
//| AutoTrade defaults to false for that reason. In that mode the    |
//| advisor still reports every entry it WOULD have taken, which is  |
//| what builds the record that decides whether it should trade.     |
//+------------------------------------------------------------------+
#property strict

input string   ServerHost     = "127.0.0.1";   // Bridge host
input int      ServerPort     = 8765;          // Bridge port
input string   BridgeToken    = "";            // Shared secret (MT5_BRIDGE_TOKEN)
input int      CheckInterval  = 300;           // Seconds between checks
input double   RiskPercent    = 1.0;           // Risk per trade, % of balance
input bool     AutoTrade      = false;         // Execute, or only report
input bool     PublishToPlatform = true;       // Store decisions on the platform
input double   StopATRMult    = 2.0;           // Stop distance, in ATR
input double   TargetATRMult  = 4.0;           // Target distance, in ATR
input int      ATRPeriod      = 14;
input int      MagicBase      = 777000;        // Magic number base

datetime g_lastCheck = 0;
int      g_atrHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Levels. Stop at 2xATR, target at 4xATR — the same rule the       |
//| platform applies to every other source, so an advisor's signal   |
//| is judged by the same geometry as a Telegram one.                |
//+------------------------------------------------------------------+
struct WefSetup
  {
   bool     valid;
   string   action;      // "buy" | "sell"
   double   entry;
   double   tp;
   double   sl;
   double   atr;
   string   why;
  };

double WefATR()
  {
   if(g_atrHandle == INVALID_HANDLE)
      g_atrHandle = iATR(_Symbol, _Period, ATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
      return 0.0;
   double buf[];
   if(CopyBuffer(g_atrHandle, 0, 0, 1, buf) < 1)
      return 0.0;
   return buf[0];
  }

WefSetup WefBuildSetup(const string action, const string why)
  {
   WefSetup s;
   s.valid  = false;
   s.action = action;
   s.why    = why;
   s.atr    = WefATR();
   if(s.atr <= 0.0)
     {
      s.why = why + " | ATR unavailable";
      return s;
     }

   // Entry at the side the order would actually fill on, not at the mid:
   // a buy pays the ask. Using the mid would understate every spread.
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
      return s;

   if(action == "buy")
     {
      s.entry = ask;
      s.sl    = ask - StopATRMult   * s.atr;
      s.tp    = ask + TargetATRMult * s.atr;
     }
   else
     {
      s.entry = bid;
      s.sl    = bid + StopATRMult   * s.atr;
      s.tp    = bid - TargetATRMult * s.atr;
     }
   s.valid = true;
   return s;
  }

//+------------------------------------------------------------------+
//| Position size from risk, never a fixed lot. A fixed lot makes    |
//| the loss depend on the stop distance, which is backwards.        |
//+------------------------------------------------------------------+
double WefLots(const double entry, const double sl)
  {
   double dist = MathAbs(entry - sl);
   if(dist <= 0.0)
      return 0.0;

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0)
      return 0.0;

   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * RiskPercent / 100.0;
   double lossPerLot = dist / tickSize * tickVal;
   if(lossPerLot <= 0.0)
      return 0.0;

   double lots = riskMoney / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0.0)
      lots = MathFloor(lots / step) * step;
   if(lots < minL)
      return 0.0;            // the risk budget does not cover one lot
   if(lots > maxL)
      lots = maxL;
   return lots;
  }

//+------------------------------------------------------------------+
//| Bridge                                                           |
//+------------------------------------------------------------------+
string WefSend(const string payload)
  {
   int sock = SocketCreate();
   if(sock == INVALID_HANDLE)
     {
      Print("WEF: SocketCreate failed — enable the host in Tools > Options > Expert Advisors");
      return "";
     }
   string answer = "";
   if(SocketConnect(sock, ServerHost, ServerPort, 5000))
     {
      char req[];
      StringToCharArray(payload + "\n", req, 0, StringLen(payload) + 1, CP_UTF8);
      if(SocketSend(sock, req, ArraySize(req) - 1) > 0)
        {
         char buf[];
         uint deadline = GetTickCount() + 20000;
         while(GetTickCount() < deadline)
           {
            uint avail = SocketIsReadable(sock);
            if(avail > 0)
              {
               ArrayResize(buf, (int)avail);
               int got = SocketRead(sock, buf, (int)avail, 2000);
               if(got > 0)
                 {
                  answer += CharArrayToString(buf, 0, got, CP_UTF8);
                  if(StringFind(answer, "\n") >= 0)
                     break;
                 }
              }
            Sleep(50);
           }
        }
     }
   else
      Print("WEF: cannot reach bridge at ", ServerHost, ":", ServerPort);
   SocketClose(sock);
   return answer;
  }

string WefJsonStr(const string key, const string val)
  {
   return "\"" + key + "\":\"" + val + "\"";
  }

string WefJsonNum(const string key, const double val, const int digits)
  {
   return "\"" + key + "\":" + DoubleToString(val, digits);
  }

//+------------------------------------------------------------------+
//| Report a decision. The platform rates it, runs the quality gate  |
//| and decides on publication — the advisor does not get a more     |
//| permissive route just because the signal is ours.                |
//+------------------------------------------------------------------+
string WefReportSignal(const WefSetup &s, const int strategyId, const string name)
  {
   if(!PublishToPlatform || !s.valid)
      return "";
   int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   string body = "{" + WefJsonStr("cmd", "signal") + ","
                 + WefJsonStr("auth", BridgeToken) + ","
                 + WefJsonStr("ticker", _Symbol) + ","
                 + WefJsonStr("action", s.action) + ","
                 + WefJsonNum("price", s.entry, d) + ","
                 + WefJsonNum("tp", s.tp, d) + ","
                 + WefJsonNum("sl", s.sl, d) + ","
                 + WefJsonNum("atr_pct", s.atr / s.entry * 100.0, 4) + ","
                 + WefJsonStr("timeframe", EnumToString(_Period)) + ","
                 + WefJsonNum("strategy_id", strategyId, 0) + ","
                 + WefJsonStr("strategy", name) + ","
                 + WefJsonStr("reasoning", s.why) + "}";
   return WefSend(body);
  }

//+------------------------------------------------------------------+
//| Report an execution. This is the only message carrying a price   |
//| the platform did not choose — the gap between requested and      |
//| filled is the one number no competitor publishes.                |
//+------------------------------------------------------------------+
void WefReportFill(const ulong ticket, const string action,
                   const double requested, const double filled,
                   const double volume)
  {
   int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                   - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string body = "{" + WefJsonStr("cmd", "fill") + ","
                 + WefJsonStr("auth", BridgeToken) + ","
                 + WefJsonStr("ticker", _Symbol) + ","
                 + WefJsonStr("action", action) + ","
                 + WefJsonNum("requested_price", requested, d) + ","
                 + WefJsonNum("fill_price", filled, d) + ","
                 + WefJsonNum("spread", spread, d) + ","
                 + WefJsonNum("volume", volume, 2) + ","
                 + "\"ticket\":" + IntegerToString((long)ticket) + "}";
   string resp = WefSend(body);
   Print("WEF fill -> ", resp);
  }

//+------------------------------------------------------------------+
//| Execute, or say what would have been executed.                   |
//+------------------------------------------------------------------+
void WefAct(const WefSetup &s, const int strategyId, const string name)
  {
   if(!s.valid)
      return;

   double lots = WefLots(s.entry, s.sl);
   string head = StringFormat("%s [%d] %s %s @ %s  TP %s  SL %s  (%s lots)",
                              name, strategyId, _Symbol, s.action,
                              DoubleToString(s.entry, _Digits),
                              DoubleToString(s.tp, _Digits),
                              DoubleToString(s.sl, _Digits),
                              DoubleToString(lots, 2));
   Print(head, " | ", s.why);

   string platform = WefReportSignal(s, strategyId, name);
   if(StringLen(platform) > 0)
      Print("Платформа: ", platform);

   if(!AutoTrade)
     {
      // The record still gets built: the platform stores the decision, the
      // monitor settles it at the level it reaches, and after 30 closed trades
      // there is something to judge. Trading first would only add losses to
      // the same conclusion.
      Alert(head, " — AutoTrade=false, сделка не выставлена");
      return;
     }
   if(lots <= 0.0)
     {
      Print("WEF: risk budget does not cover the minimum lot — skipped");
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
   req.magic        = MagicBase + strategyId;
   req.comment      = name;
   req.type_filling = ORDER_FILLING_FOK;

   if(!OrderSend(req, res) || res.retcode != TRADE_RETCODE_DONE)
     {
      Print("WEF: order rejected, retcode=", res.retcode, " ", res.comment);
      return;
     }
   // Requested vs filled: the whole point of reporting this.
   WefReportFill(res.order, s.action, s.entry, res.price, res.volume);
  }

bool WefDue()
  {
   if(TimeCurrent() - g_lastCheck < CheckInterval)
      return false;
   g_lastCheck = TimeCurrent();
   return true;
  }

bool WefHasPosition(const int strategyId)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == MagicBase + strategyId)
         return true;
     }
   return false;
  }

void WefBanner(const string name, const int strategyId)
  {
   Print("=== ", name, " (Strategy ID ", strategyId, ") on ", _Symbol,
         " ", EnumToString(_Period), " ===");
   Print("AutoTrade=", AutoTrade ? "ON — живые сделки" : "OFF — только отчёт",
         ", риск ", DoubleToString(RiskPercent, 2), "%",
         ", стоп ", DoubleToString(StopATRMult, 1), "xATR",
         ", цель ", DoubleToString(TargetATRMult, 1), "xATR");
   if(AutoTrade)
      Print("ВНИМАНИЕ: стратегия не прошла проверку на данных. ",
            "Измеренный результат платформы -0.93% на сделку.");
  }
//+------------------------------------------------------------------+
