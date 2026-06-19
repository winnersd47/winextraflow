# WinExtraFlow — Подключение реальных сигналов

## Способ 1: TradingView Webhook (рекомендуемый)

### Шаг 1 — Endpoint
```
POST https://your-domain.com/api/v1/signals/webhook/tradingview
```
Для локальной разработки: `http://localhost:8000/api/v1/signals/webhook/tradingview`

### Шаг 2 — Формат JSON
```json
{
  "ticker": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": {{close}},
  "timeframe": "{{interval}}",
  "take_profit": null,
  "stop_loss": null,
  "secret": "your_webhook_secret"
}
```

### Шаг 3 — Настройка в TradingView

1. Откройте **TradingView** → ваша стратегия/индикатор
2. Нажмите **Создать оповещение** (Alert)
3. В поле **Webhook URL** вставьте endpoint
4. В поле **Сообщение** вставьте JSON шаблон:

#### Шаблон для стратегии (с авто-действием):
```json
{
  "ticker": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": {{strategy.order.price}},
  "timeframe": "{{interval}}",
  "take_profit": {{strategy.order.price * 1.03}},
  "stop_loss": {{strategy.order.price * 0.98}}
}
```

#### Шаблон для ручного BUY:
```json
{
  "ticker": "SBER",
  "action": "buy",
  "price": {{close}},
  "timeframe": "1h",
  "take_profit": {{close * 1.05}},
  "stop_loss": {{close * 0.97}}
}
```

#### Шаблон для ручного SELL:
```json
{
  "ticker": "BTCUSDT",
  "action": "sell",
  "price": {{close}},
  "timeframe": "4h",
  "take_profit": {{close * 0.95}},
  "stop_loss": {{close * 1.03}}
}
```

### Поддерживаемые тикеры
- **MOEX**: SBER, GAZP, LKOH, YNDX, ROSN, GMKN, NVTK и ещё 17
- **Crypto**: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT и любые *USDT
- **Forex**: EURUSD, GBPUSD, USDJPY и любые валютные пары
- **US Stocks**: AAPL, NVDA, TSLA, AMZN и ещё 43

### Безопасность (опционально)
Добавьте secret в `.env`:
```
TRADINGVIEW_WEBHOOK_SECRET=your_random_secret_here
```
И в JSON шаблон:
```json
"secret": "your_random_secret_here"
```

---

## Способ 2: CLI скрипт

```bash
cd backend
python scripts/send_signal.py SBER buy 315.50 340 298
python scripts/send_signal.py BTCUSDT sell 67200 63000 69000
python scripts/send_signal.py EURUSD buy 1.0892 1.0950 1.0830
```

---

## Способ 3: cURL / API напрямую

```bash
curl -X POST http://localhost:8000/api/v1/signals/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"ticker":"SBER","action":"buy","price":315.50,"take_profit":340,"stop_loss":298}'
```

---

## Способ 4: Telegram каналы (автопарсинг)

1. Авторизуйте Telethon (один раз, из дома):
```bash
cd backend
python scripts/telegram_auth.py
```

2. Добавьте каналы в `.env`:
```
TELEGRAM_PARSE_CHANNELS=beststocksru,cryptosignals,moex_signals
```

3. Перезапустите backend — парсер автоматически мониторит каналы

---

## Способ 5: Ручное создание (через UI)

1. Войдите как **Analyst** или **Admin**
2. В sidebar нажмите **Создать сигнал**
3. Заполните форму: тикер, действие, цена, TP, SL
4. AI автоматически оценит сигнал (WEF Score)

---

## Что происходит при получении сигнала

```
Webhook/Telegram/UI
    ↓
1. Валидация (тикер, цена > 0)
2. Создание Signal в БД
3. AI Rating → WEF Score (9 факторов)
4. WebSocket broadcast → все подключённые клиенты
5. Telegram bot → VIP канал (мгновенно) + Free (с задержкой)
6. Copy Trading → автоисполнение для подписчиков
7. Notification → in-app уведомление
```

## Тестирование

Отправьте тестовый сигнал:
```bash
python scripts/send_signal.py SBER buy 315.50 340 298
```

Проверьте:
- http://localhost:3000/dashboard — сигнал в ленте
- WEF Score присвоен автоматически
- WebSocket: звук + badge на вкладке
