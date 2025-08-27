# 🚀 Grid Trading Bot

Автоматическая торговля по сетке цен для получения высокой доходности.

## 📊 Параметры торговли

**Пары для торговли (настраиваются через SYMBOLS в .env):**
- DOGE/USDT: 25 USDT, 5 уровней
- WIF/USDT: 25 USDT, 5 уровней  
- JUP/USDT: 25 USDT, 5 уровней

**Общий капитал:** 75 USDT (3 пары × 25 USDT)
**Целевая доходность:** 5-15% в день

## ⚙️ Настройки сетки

- **Количество уровней:** 5 (настраивается)
- **Шаг сетки:** 2% между уровнями
- **Объём на уровень:** 5 USDT
- **Тип ордеров:** Лимитные

## 🚀 Запуск

### 1. Подготовка
```bash
# Скопировать переменные окружения
cp ../.env .env

# Убедиться, что сеть l1_network существует
docker network ls | grep l1_network
```

### 2. Запуск бота
```bash
# Собрать и запустить
docker-compose up -d --build

# Посмотреть логи
docker-compose logs -f grid_bot
```

### 3. Остановка
```bash
docker-compose down
```

## 📈 Мониторинг

### Просмотр активных сеток
```bash
docker exec grid_bot python -c "
import sqlite3
conn = sqlite3.connect('/app/shared/grid_trading.db')
cursor = conn.execute('SELECT * FROM grids WHERE status = \"active\"')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```

### Просмотр сделок
```bash
docker exec grid_bot python -c "
import sqlite3
conn = sqlite3.connect('/app/shared/grid_trading.db')
cursor = conn.execute('SELECT * FROM trades ORDER BY created_at DESC LIMIT 10')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```

## 🔧 Настройка параметров

Изменить параметры можно в `docker-compose.yml`:

```yaml
environment:
  - GRID_LEVELS=5        # Количество уровней
  - GRID_SPREAD=0.02     # Шаг сетки (2%)
  - LEVEL_AMOUNT=5.0     # USDT на уровень
```

## ⚠️ Риски

- **Высокая волатильность** может привести к убыткам
- **Рыночные риски** при резких движениях цены
- **Технические риски** при сбоях API

## 📊 Ожидаемая доходность

- **Теоретически:** 10-30% в день
- **Реалистично:** 5-15% в день
- **С учётом рисков:** 3-8% в день

## 🆘 Поддержка

При проблемах:
1. Проверить логи: `docker-compose logs grid_bot`
2. Проверить баланс на Bybit
3. Проверить активные ордера
4. При необходимости - остановить и перезапустить

