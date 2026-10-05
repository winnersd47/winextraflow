//+------------------------------------------------------------------+
//| WEF_Bridge.mq5 — WinExtraFlow AI Bridge for MetaTrader 5        |
//|                                                                  |
//| Connects to Python server via TCP (127.0.0.1:8765)               |
//| Sends OHLCV candles → receives AI trade decision                 |
//|                                                                  |
//| No API keys in MQL5 code — all secrets stay in Python .env       |
//+------------------------------------------------------------------+
#property copyright "WinExtraFlow"
#property version   "1.00"
#property indicator_chart_window

#include <Trade\Trade.mqh>

// ═══ INPUT PARAMETERS ═══
input string   ServerHost     = "127.0.0.1";   // Python server IP
input int      ServerPort     = 8765;           // Python server port
// Must match MT5_BRIDGE_TOKEN in the server's .env. Required whenever the server
// listens on anything but 127.0.0.1 — without it the server answers Unauthorized.
input string   BridgeToken    = "";             // Shared secret (MT5_BRIDGE_TOKEN)
input int      CandleCount    = 60;             // Candles to send
input int      CheckInterval  = 300;            // Check every N seconds (300 = 5 min)
input double   RiskPercent    = 1.0;            // Risk % per trade
input bool     AutoTrade      = false;          // Auto-execute signals (false = alerts only)
// true  -> cmd=signal: the decision is stored on the platform, rated, put through
//          the quality gate and published like any other signal.
// false -> cmd=analyze: terminal Alert only, nothing leaves the terminal.
input bool     PublishToPlatform = true;        // Send signals to WinExtraFlow
input ENUM_TIMEFRAMES TF      = PERIOD_H1;      // Timeframe

// ═══ GLOBALS ═══
int g_socket = INVALID_HANDLE;
datetime g_lastCheck = 0;
CTrade g_trade;

//+------------------------------------------------------------------+
int OnInit()
{
   Print("WEF Bridge v1.0 — connecting to ", ServerHost, ":", ServerPort);

   // A remote server always requires the shared secret; failing here is clearer
   // than every request coming back Unauthorized with no explanation.
   bool isLocal = (ServerHost == "127.0.0.1" || ServerHost == "localhost");
   if(!isLocal && BridgeToken == "")
   {
      Print("ERROR: BridgeToken is empty but ServerHost is remote. ",
            "Set it to the same value as MT5_BRIDGE_TOKEN on the server.");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(AutoTrade)
      Print("WARNING: AutoTrade is ON — orders will be placed automatically.");

   EventSetTimer(CheckInterval);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_socket != INVALID_HANDLE)
   {
      SocketClose(g_socket);
      g_socket = INVALID_HANDLE;
   }
   EventKillTimer();
   Print("WEF Bridge disconnected");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   AnalyzeCurrentSymbol();
}

//+------------------------------------------------------------------+
void AnalyzeCurrentSymbol()
{
   string ticker = Symbol();

   // Build candles JSON
   string candles = BuildCandlesJSON(ticker, TF, CandleCount);
   if(candles == "")
   {
      Print("Failed to build candles for ", ticker);
      return;
   }

   // Build request. "signal" stores the decision on the platform and runs it
   // through the quality gate; "analyze" only returns it to the terminal.
   string cmd = PublishToPlatform ? "signal" : "analyze";
   string request = "{\"cmd\":\"" + cmd + "\",\"auth\":\"" + BridgeToken +
                    "\",\"ticker\":\"" + ticker +
                    "\",\"timeframe\":\"" + TimeframeToString(TF) +
                    "\",\"candles\":" + candles + "}";

   // Send to Python server
   string response = SendToServer(request);
   if(response == "")
   {
      Print("No response from server");
      return;
   }

   // Parse response.
   // cmd=analyze returns {action, confidence, tp, sl, reasoning}.
   // cmd=signal returns {stored, action, tp, sl, wef, verdict, published, reason,
   // model_confidence} — its tp/sl are already ATR-adjusted by the platform, and
   // its verdict comes from the seven quality checks.
   string action = JSONGetString(response, "action");
   double tp = JSONGetDouble(response, "tp");
   double sl = JSONGetDouble(response, "sl");
   string reasoning = JSONGetString(response, "reasoning");

   double modelConf = JSONGetDouble(response, "model_confidence");
   if(modelConf <= 0)
      modelConf = JSONGetDouble(response, "confidence");
   double wef = JSONGetDouble(response, "wef");
   string verdict = JSONGetString(response, "verdict");
   string reason = JSONGetString(response, "reason");

   Print("MT5 -> WEF: ", action, " ", ticker,
         " | самооценка модели ", DoubleToString(modelConf * 100, 0), "%",
         " | TP ", DoubleToString(tp, Digits()),
         " | SL ", DoubleToString(sl, Digits()));
   if(reasoning != "")
      Print("Обоснование: ", reasoning);
   if(PublishToPlatform)
      Print("Платформа: WEF ", DoubleToString(wef, 0), "% | вердикт ", verdict,
            (reason == "" ? "" : " | " + reason));

   if(action != "buy" && action != "sell")
      return;                               // hold — nothing to do

   string alertMsg = "WEF " + action + " " + ticker +
                     (PublishToPlatform ? " | WEF " + DoubleToString(wef, 0) + "%"
                                        : " | conf " + DoubleToString(modelConf * 100, 0) + "%") +
                     " | TP " + DoubleToString(tp, Digits()) +
                     " | SL " + DoubleToString(sl, Digits());
   Alert(alertMsg);

   if(!AutoTrade)
      return;

   // The trade trigger is the platform's quality gate, not the model's opinion of
   // itself: `confidence` is a number the model assigns after looking at five
   // indicators, and it has not been shown to mean what it says. When publishing is
   // off there is no gate available, so no automatic trade is placed either.
   if(!PublishToPlatform)
   {
      Print("AutoTrade пропущен: без PublishToPlatform нет вердикта гейта качества.");
      return;
   }
   if(verdict == "SKIP" || verdict == "")
   {
      Print("AutoTrade пропущен: вердикт гейта ", (verdict == "" ? "отсутствует" : verdict));
      return;
   }
   ExecuteTrade(action, tp, sl);
}

//+------------------------------------------------------------------+
string BuildCandlesJSON(string symbol, ENUM_TIMEFRAMES tf, int count)
{
   MqlRates rates[];
   int copied = CopyRates(symbol, tf, 0, count, rates);
   if(copied < 20) return "";

   string json = "[";
   for(int i = 0; i < copied; i++)
   {
      if(i > 0) json += ",";
      json += "{\"open\":" + DoubleToString(rates[i].open, Digits()) +
              ",\"high\":" + DoubleToString(rates[i].high, Digits()) +
              ",\"low\":" + DoubleToString(rates[i].low, Digits()) +
              ",\"close\":" + DoubleToString(rates[i].close, Digits()) +
              ",\"volume\":" + IntegerToString(rates[i].tick_volume) + "}";
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
string SendToServer(string request)
{
   // Connect if not connected
   if(g_socket == INVALID_HANDLE)
   {
      g_socket = SocketCreate();
      if(g_socket == INVALID_HANDLE)
      {
         Print("Socket create failed: ", GetLastError());
         return "";
      }

      if(!SocketConnect(g_socket, ServerHost, ServerPort, 5000))
      {
         Print("Socket connect failed to ", ServerHost, ":", ServerPort);
         SocketClose(g_socket);
         g_socket = INVALID_HANDLE;
         return "";
      }
      Print("Connected to WEF server");
   }

   // Send request + newline
   string toSend = request + "\n";
   uchar sendBuf[];
   StringToCharArray(toSend, sendBuf, 0, WHOLE_ARRAY, CP_UTF8);

   if(SocketSend(g_socket, sendBuf, ArraySize(sendBuf) - 1) < 0)
   {
      Print("Socket send failed, reconnecting...");
      SocketClose(g_socket);
      g_socket = INVALID_HANDLE;
      return "";
   }

   // Read response (wait up to 10 seconds)
   string response = "";
   uchar recvBuf[];
   uint startTime = GetTickCount();

   while(GetTickCount() - startTime < 10000)
   {
      uint available = SocketIsReadable(g_socket);
      if(available > 0)
      {
         int read = SocketRead(g_socket, recvBuf, available, 1000);
         if(read > 0)
         {
            response += CharArrayToString(recvBuf, 0, read, CP_UTF8);
            if(StringFind(response, "\n") >= 0)
               break;
         }
      }
      Sleep(100);
   }

   return StringTrimRight(response);
}

//+------------------------------------------------------------------+
void ExecuteTrade(string action, double tp, double sl)
{
   double lotSize = CalcLotSize(sl);
   if(lotSize <= 0) return;

   if(action == "buy")
   {
      double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      g_trade.Buy(lotSize, Symbol(), ask, sl, tp, "WEF Signal");
      Print("WEF: Opened BUY ", lotSize, " lots at ", ask);
   }
   else if(action == "sell")
   {
      double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      g_trade.Sell(lotSize, Symbol(), bid, sl, tp, "WEF Signal");
      Print("WEF: Opened SELL ", lotSize, " lots at ", bid);
   }
}

//+------------------------------------------------------------------+
double CalcLotSize(double sl)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * RiskPercent / 100.0;
   double price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   double slDistance = MathAbs(price - sl);

   if(slDistance <= 0) return 0.01;

   double tickValue = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0 || tickSize <= 0) return 0.01;

   double lots = riskAmount / (slDistance / tickSize * tickValue);
   double minLot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_STEP);

   lots = MathFloor(lots / stepLot) * stepLot;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   return lots;
}

//+------------------------------------------------------------------+
string TimeframeToString(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      default:         return "H1";
   }
}

//+------------------------------------------------------------------+
// Simple JSON parsing helpers (no external libraries needed)
//+------------------------------------------------------------------+
string JSONGetString(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int pos = StringFind(json, search);
   if(pos < 0) return "";
   pos += StringLen(search);
   int end = StringFind(json, "\"", pos);
   if(end < 0) return "";
   return StringSubstr(json, pos, end - pos);
}

double JSONGetDouble(string json, string key)
{
   string search = "\"" + key + "\":";
   int pos = StringFind(json, search);
   if(pos < 0) return 0;
   pos += StringLen(search);
   string sub = StringSubstr(json, pos, 20);
   // Remove non-numeric chars
   string num = "";
   for(int i = 0; i < StringLen(sub); i++)
   {
      ushort ch = StringGetCharacter(sub, i);
      if((ch >= '0' && ch <= '9') || ch == '.' || ch == '-')
         num += ShortToString(ch);
      else if(ch != ' ')
         break;
   }
   return StringToDouble(num);
}
//+------------------------------------------------------------------+
