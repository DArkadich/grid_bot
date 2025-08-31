"""
Grid Trading Bot - Автоматическая торговля по логарифмической сетке цен

ВСЕ ПАРАМЕТРЫ НАСТРАИВАЮТСЯ ЧЕРЕЗ .env ФАЙЛ:

ОБЯЗАТЕЛЬНЫЕ:
- BYBIT_API_KEY - API ключ Bybit
- BYBIT_API_SECRET - API секрет Bybit
- SYMBOLS - торговые пары через запятую (например: DOGE/USDT,WIF/USDT,JUP/USDT)

ПАРАМЕТРЫ ЛОГАРИФМИЧЕСКОЙ СЕТКИ:
- GRID_LEVELS - количество уровней сетки (рекомендуется: 5-10)
- GRID_SPREAD - базовый спред между уровнями в % (рекомендуется: 0.001 = 0.1%)
- LEVEL_AMOUNT - USDT на уровень (рекомендуется: 1-5)
- LOG_MULTIPLIER - множитель для логарифмического распределения (рекомендуется: 1.5)

ЛОГАРИФМИЧЕСКАЯ СЕТКА:
- Близко к цене: плотная сетка для быстрых сделок
- Далеко от цены: редкая сетка для защиты от экстремальных движений
- Эффективное использование капитала без замораживания на маловероятных событиях

ЦЕЛЬ: 5-15% доходности в день с умной логарифмической сеткой
"""

import ccxt
import sqlite3
import time
import os
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from telegram import Bot

# ========== КОНФИГУРАЦИЯ ==========
@dataclass
class GridConfig:
    # API
    api_key: str = os.environ.get("BYBIT_API_KEY")
    api_secret: str = os.environ.get("BYBIT_API_SECRET")
    
    # Параметры сетки
    grid_levels: int = int(os.environ.get("GRID_LEVELS"))  # количество уровней
    grid_spread: float = float(os.environ.get("GRID_SPREAD"))  # % между уровнями
    level_amount: float = float(os.environ.get("LEVEL_AMOUNT"))  # USDT на уровень
    
    # Логарифмическая сетка
    log_multiplier: float = float(os.environ.get("LOG_MULTIPLIER", "1.5"))  # множитель для логарифмического распределения
    
    # Пары для торговли
    symbols: List[str] = None
    
    def __post_init__(self):
        # Проверяем все обязательные переменные окружения
        if not self.api_key:
            raise ValueError("BYBIT_API_KEY не указан в переменных окружения")
        if not self.api_secret:
            raise ValueError("BYBIT_API_SECRET не указан в переменных окружения")
        
        # Проверяем параметры сетки
        if not os.environ.get("GRID_LEVELS"):
            raise ValueError("GRID_LEVELS не указан в переменных окружения")
        if not os.environ.get("GRID_SPREAD"):
            raise ValueError("GRID_SPREAD не указан в переменных окружения")
        if not os.environ.get("LEVEL_AMOUNT"):
            raise ValueError("LEVEL_AMOUNT не указан в переменных окружения")
        
        if not self.symbols:
            # Читаем символы из переменной окружения
            env_symbols = os.environ.get("SYMBOLS")
            if not env_symbols:
                raise ValueError("SYMBOLS не указан в переменных окружения")
            self.symbols = [s.strip() for s in env_symbols.split(",")]

# ========== КЛИЕНТ БИРЖИ ==========
class BybitClient:
    def __init__(self, config: GridConfig):
        self.exchange = ccxt.bybit({
            "apiKey": config.api_key,
            "secret": config.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "unified"}
        })
        self.exchange.load_markets()
    
    def get_ticker(self, symbol: str) -> Dict:
        """Получить текущие цены"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                "bid": float(ticker["bid"]),
                "ask": float(ticker["ask"]),
                "last": float(ticker["last"]),
                "volume": float(ticker["baseVolume"])
            }
        except Exception as e:
            print(f"Ошибка получения тикера {symbol}: {e}")
            return {}
    
    def get_balance(self) -> float:
        """Получить доступный баланс USDT с отладкой"""
        try:
            balance = self.exchange.fetch_balance()
            print(f"🔍 Отладка баланса: получено {len(balance)} ключей")
            print(f"🔍 Основные ключи: {list(balance.keys())[:10]}")
            
            if 'USDT' in balance:
                usdt_balance = balance['USDT']
                print(f"💰 USDT баланс найден: {usdt_balance}")
                print(f"🔍 Ключи USDT: {list(usdt_balance.keys())}")
                
                if 'free' in usdt_balance:
                    free_balance = float(usdt_balance['free'])
                    print(f"✅ Свободный USDT: {free_balance}")
                    return free_balance
                elif 'available' in usdt_balance:
                    available_balance = float(usdt_balance['available'])
                    print(f"✅ Доступный USDT (available): {available_balance}")
                    return available_balance
                elif 'total' in usdt_balance:
                    total_balance = float(usdt_balance['total'])
                    print(f"⚠️ Общий USDT (total): {total_balance}")
                    return total_balance
                else:
                    print(f"❌ Ключи 'free', 'available', 'total' не найдены в USDT балансе")
                    print(f"🔍 Полный USDT баланс: {usdt_balance}")
            else:
                print(f"❌ USDT не найден в балансе")
                print(f"🔍 Доступные валюты: {list(balance.keys())[:15]}")
                
                # Попробуем найти USDT в других форматах
                for key in balance.keys():
                    if 'USDT' in str(key) or 'usdt' in str(key).lower():
                        print(f"🔍 Найден похожий ключ: {key} = {balance[key]}")
            
            return 0.0
        except Exception as e:
            print(f"❌ Ошибка получения баланса: {e}")
            import traceback
            traceback.print_exc()
            return 0.0
    
    def get_base_balance(self, currency: str) -> float:
        """Получить доступный баланс базовой валюты (например DOGE)"""
        try:
            balance = self.exchange.fetch_balance()
            
            if currency in balance:
                currency_balance = balance[currency]
                
                if 'free' in currency_balance:
                    free_balance = float(currency_balance['free'])
                    return free_balance
                elif 'available' in currency_balance:
                    available_balance = float(currency_balance['available'])
                    return available_balance
                elif 'total' in currency_balance:
                    total_balance = float(currency_balance['total'])
                    return total_balance
            
            return 0.0
        except Exception as e:
            print(f"Ошибка получения баланса {currency}: {e}")
            return 0.0
    
    def place_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        """Разместить лимитный ордер"""
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                type="limit",
                side=side,
                amount=amount,
                price=price
            )
            return order
        except Exception as e:
            print(f"Ошибка размещения ордера {symbol}: {e}")
            return {}

# ========== УПРАВЛЕНИЕ СЕТКОЙ ==========
class GridManager:
    def __init__(self, client: BybitClient, config: GridConfig):
        self.client = client
        self.config = config
        self.grids: Dict[str, List[Dict]] = {}
        self.db_path = "/app/shared/grid_trading.db"
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица сеток
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    order_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица сделок
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    profit REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            print("База данных инициализирована")
        except Exception as e:
            print(f"Ошибка инициализации БД: {e}")
    
    def check_available_balance(self, symbol: str, side: str, amount: float, price: float) -> bool:
        """Проверить, достаточно ли средств для создания ордера"""
        try:
            if side == "buy":
                # Для покупки нужен USDT
                required_usdt = amount * price
                available_usdt = self.client.get_balance()
                if available_usdt >= required_usdt:
                    print(f"💰 Доступно USDT: {available_usdt:.2f}, нужно: {required_usdt:.2f}")
                    return True
                else:
                    print(f"❌ Недостаточно USDT: доступно {available_usdt:.2f}, нужно {required_usdt:.2f}")
                    return False
            else:  # sell
                # Для продажи нужна базовая валюта (DOGE)
                base_currency = symbol.split('/')[0]  # DOGE из DOGE/USDT
                available_base = self.client.get_base_balance(base_currency)
                if available_base >= amount:
                    print(f"💰 Доступно {base_currency}: {available_base:.2f}, нужно: {amount:.2f}")
                    return True
                else:
                    print(f"❌ Недостаточно {base_currency}: доступно {available_base:.2f}, нужно {amount:.2f}")
                    return False
        except Exception as e:
            print(f"Ошибка проверки баланса: {e}")
            return False
    
    def load_existing_grids(self):
        """Загрузить существующие сетки из базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем все символы с существующими сетками
            cursor.execute("SELECT DISTINCT symbol FROM grids")
            symbols = [row[0] for row in cursor.fetchall()]
            
            for symbol in symbols:
                # Загружаем все уровни для символа
                cursor.execute("""
                    SELECT level, side, amount, price, order_id, status 
                    FROM grids 
                    WHERE symbol = ? 
                    ORDER BY level, side
                """, (symbol,))
                
                grid = []
                for row in cursor.fetchall():
                    level, side, amount, price, order_id, status = row
                    grid.append({
                        "level": level,
                        "side": side,
                        "amount": amount,
                        "price": price,
                        "order_id": order_id,
                        "status": status
                    })
                
                if grid:
                    self.grids[symbol] = grid
                    print(f"📋 Загружена существующая сетка для {symbol}: {len(grid)} уровней")
            
            conn.close()
            return len(symbols) > 0
            
        except Exception as e:
            print(f"Ошибка загрузки существующих сеток: {e}")
            return False
    
    def create_grid(self, symbol: str, current_price: float):
        """Создать логарифмическую сетку для пары"""
        try:
            grid = []
            base_amount = self.config.level_amount / current_price
            
            # Логарифмический множитель для расстояния между уровнями
            # Можно настроить в .env файле как LOG_MULTIPLIER
            log_multiplier = getattr(self.config, 'log_multiplier', 1.5)
            
            print(f"🔧 Создание логарифмической сетки для {symbol}")
            print(f"   Текущая цена: {current_price}")
            print(f"   Базовый спред: {self.config.grid_spread * 100:.2f}%")
            print(f"   Логарифмический множитель: {log_multiplier}")
            
            # Создаём уровни покупки ниже текущей цены (логарифмически)
            for i in range(self.config.grid_levels):
                # Логарифмическое расстояние: базовый спред * (множитель ^ уровень)
                distance = self.config.grid_spread * (log_multiplier ** i)
                buy_price = current_price * (1 - distance)
                buy_price = round(buy_price, 6)
                
                grid.append({
                    "level": i,
                    "side": "buy",
                    "price": buy_price,
                    "amount": base_amount,
                    "status": "pending"
                })
                
                print(f"   📉 Buy уровень {i}: {buy_price} (-{distance * 100:.2f}%)")
            
            # Создаём уровни продажи выше текущей цены (логарифмически)
            for i in range(self.config.grid_levels):
                # Логарифмическое расстояние: базовый спред * (множитель ^ уровень)
                distance = self.config.grid_spread * (log_multiplier ** i)
                sell_price = current_price * (1 + distance)
                sell_price = round(sell_price, 6)
                
                grid.append({
                    "level": i,
                    "side": "sell", 
                    "price": sell_price,
                    "amount": base_amount,
                    "status": "pending"
                })
                
                print(f"   📈 Sell уровень {i}: {sell_price} (+{distance * 100:.2f}%)")
            
            self.grids[symbol] = grid
            self.save_grid_to_db(symbol, grid)
            print(f"✅ Логарифмическая сетка создана для {symbol}: {len(grid)} уровней")
            
        except Exception as e:
            print(f"Ошибка создания сетки {symbol}: {e}")
    
    def save_grid_to_db(self, symbol: str, grid: List[Dict]):
        """Сохранить сетку в базу данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for level in grid:
                cursor.execute("""
                    INSERT INTO grids (symbol, level, side, amount, price)
                    VALUES (?, ?, ?, ?, ?)
                """, (symbol, level["level"], level["side"], level["amount"], level["price"]))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка сохранения сетки в БД: {e}")
    
    def place_grid_orders(self, symbol: str):
        """Разместить ордера сетки с проверкой баланса, приоритет ближним к цене"""
        try:
            if symbol not in self.grids:
                return
            
            grid = self.grids[symbol]
            placed_orders = 0
            skipped_orders = 0
            
            # Получаем текущую цену для приоритизации
            ticker = self.client.get_ticker(symbol)
            current_price = ticker["last"] if ticker and "last" in ticker else None
            
            # Фильтруем pending ордера и сортируем по близости к текущей цене
            pending_orders = [level for level in grid if level["status"] == "pending"]
            
            if current_price and pending_orders:
                # Сортируем по расстоянию от текущей цены (ближние первыми)
                pending_orders.sort(key=lambda x: abs(x["price"] - current_price))
                print(f"📊 Приоритизация ордеров по близости к цене {current_price:.6f}")
            
            for level in pending_orders:
                # Проверяем, достаточно ли средств для ордера
                if self.check_available_balance(symbol, level["side"], level["amount"], level["price"]):
                    order = self.client.place_order(
                        symbol=symbol,
                        side=level["side"],
                        amount=level["amount"],
                        price=level["price"]
                    )
                    
                    if order and "id" in order:
                        level["order_id"] = order["id"]
                        level["status"] = "active"
                        placed_orders += 1
                        distance = abs(level["price"] - current_price) / current_price * 100 if current_price else 0
                        print(f"✅ Ордер размещён: {symbol} {level['side']} {level['amount']:.2f} @ {level['price']:.6f} (±{distance:.2f}%)")
                    
                    time.sleep(0.1)  # Задержка между ордерами
                else:
                    skipped_orders += 1
                    distance = abs(level["price"] - current_price) / current_price * 100 if current_price else 0
                    print(f"⏭️ Ордер пропущен: {symbol} {level['side']} {level['amount']:.2f} @ {level['price']:.6f} (±{distance:.2f}%) - недостаточно средств")
            
            print(f"📊 {symbol}: размещено {placed_orders} ордеров, пропущено {skipped_orders}")
            if skipped_orders > 0:
                print(f"💡 Пропущенные ордера будут размещены при освобождении средств (приоритет ближним)")
            
            # Сохраняем изменения в базу данных  
            self.save_grid_to_db(symbol)
                    
        except Exception as e:
            print(f"Ошибка размещения ордеров сетки {symbol}: {e}")
    
    def sync_orders_with_exchange(self, symbol: str):
        """Синхронизировать статус ордеров с биржей"""
        try:
            if symbol not in self.grids:
                return
            
            grid = self.grids[symbol]
            for level in grid:
                if level["order_id"] and level["status"] == "active":
                    try:
                        # Получаем статус ордера с биржи
                        order = self.client.exchange.fetch_order(level["order_id"], symbol)
                        if order:
                            # Обновляем статус в БД и памяти
                            new_status = order["status"]
                            if new_status != level["status"]:
                                level["status"] = new_status
                                self.update_order_status_in_db(symbol, level["level"], level["side"], new_status)
                                
                                if new_status == "filled":
                                    print(f"✅ Ордер исполнен: {symbol} {level['side']} {level['amount']} @ {level['price']}")
                                elif new_status == "canceled":
                                    print(f"❌ Ордер отменён: {symbol} {level['side']} {level['amount']} @ {level['price']}")
                    
                    except Exception as e:
                        # Если ордер не найден, возможно он исполнен или отменён
                        print(f"⚠️ Не удалось получить статус ордера {level['order_id']}: {e}")
                        # Можно добавить логику для проверки позиций
                        
        except Exception as e:
            print(f"Ошибка синхронизации ордеров {symbol}: {e}")
    
    def update_order_status_in_db(self, symbol: str, level: int, side: str, status: str):
        """Обновить статус ордера в базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE grids 
                SET status = ? 
                WHERE symbol = ? AND level = ? AND side = ?
            """, (status, symbol, level, side))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Ошибка обновления статуса в БД: {e}")
    
    def check_and_recreate_orders(self, symbol: str):
        """Проверить и пересоздать недостающие ордера с учётом баланса"""
        try:
            if symbol not in self.grids:
                return
            
            # Показываем текущий баланс
            current_balance = self.client.get_balance()
            print(f"💰 Текущий баланс: {current_balance:.2f} USDT")
            
            grid = self.grids[symbol]
            orders_to_recreate = []
            
            for level in grid:
                # Проверяем, нужен ли ордер (только если он не активен)
                if level["status"] in ["filled", "canceled", "pending"] or not level.get("order_id"):
                    orders_to_recreate.append(level)
            
            if orders_to_recreate:
                print(f"🔄 {symbol}: найдено {len(orders_to_recreate)} ордеров для пересоздания")
                
                # Пересчитываем цены только для неактивных ордеров
                ticker = self.client.get_ticker(symbol)
                if ticker and "last" in ticker:
                    current_price = ticker["last"]
                    
                    for level in orders_to_recreate:
                        # Пересчитываем цену для уровня (логарифмически)
                        distance = self.config.grid_spread * (self.config.log_multiplier ** level["level"])
                        
                        if level["side"] == "buy":
                            new_price = current_price * (1 - distance)
                        else:  # sell
                            new_price = current_price * (1 + distance)
                        
                        new_price = round(new_price, 6)
                        level["price"] = new_price
                        level["status"] = "pending"
                        level["order_id"] = None
                        
                        # Обновляем в БД
                        self.update_order_in_db(symbol, level["level"], level["side"], new_price, None, "pending")
                        
                        print(f"   📝 {level['side']} уровень {level['level']}: цена обновлена до {new_price} (±{distance * 100:.2f}%)")
                    
                    # Размещаем новые ордера (с проверкой баланса)
                    self.place_grid_orders(symbol)
                else:
                    print(f"❌ Не удалось получить текущую цену для {symbol}")
            else:
                print(f"✅ {symbol}: все ордера активны, пересоздание не требуется")
            
        except Exception as e:
            print(f"Ошибка проверки и пересоздания ордеров {symbol}: {e}")
    
    def update_order_in_db(self, symbol: str, level: int, side: str, price: float, order_id: str, status: str):
        """Обновить ордер в базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE grids 
                SET price = ?, order_id = ?, status = ? 
                WHERE symbol = ? AND level = ? AND side = ?
            """, (price, order_id, status, symbol, level, side))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Ошибка обновления ордера в БД: {e}")

# ========== ОСНОВНОЙ ЦИКЛ ==========
def main():
    print("🚀 Grid Trading Bot запущен!")
    
    # Инициализация
    config = GridConfig()
    client = BybitClient(config)
    grid_manager = GridManager(client, config)
    
    # Попытка загрузить существующие сетки
    has_existing_grids = grid_manager.load_existing_grids()
    
    if has_existing_grids:
        print("📋 Найдены существующие сетки. Проверяем и пересоздаём недостающие ордера...")
        # Синхронизируем статус с биржей
        for symbol in grid_manager.grids.keys():
            grid_manager.sync_orders_with_exchange(symbol)
            # Проверяем и пересоздаём недостающие ордера
            grid_manager.check_and_recreate_orders(symbol)
    else:
        print("📝 Существующие сетки не найдены. Создаём новые...")
        # Создание сеток для всех пар
        for symbol in config.symbols:
            try:
                ticker = client.get_ticker(symbol)
                if ticker and "last" in ticker:
                    current_price = ticker["last"]
                    grid_manager.create_grid(symbol, current_price)
                    grid_manager.place_grid_orders(symbol)
                    print(f"Сетка активирована для {symbol}")
                else:
                    print(f"Не удалось получить цену для {symbol}")
            except Exception as e:
                print(f"Ошибка инициализации {symbol}: {e}")
    
    print("✅ Все сетки готовы к работе!")
    print("📊 Мониторинг активен...")
    
    # БЕСКОНЕЧНЫЙ ЦИКЛ МОНИТОРИНГА
    while True:
        try:
            # Мониторинг активных сеток (приоритет DOGE/USDT)
            symbols_priority = ['DOGE/USDT'] + [s for s in grid_manager.grids.keys() if s != 'DOGE/USDT']
            for symbol in symbols_priority:
                # Проверяем статус ордеров
                ticker = client.get_ticker(symbol)
                if ticker and "last" in ticker:
                    current_price = ticker["last"]
                    print(f"💰 {symbol}: текущая цена {current_price}")
                    
                    # Синхронизируем статус ордеров с биржей
                    grid_manager.sync_orders_with_exchange(symbol)
                    
                    # Постоянно проверяем и пересоздаём недостающие ордера
                    grid_manager.check_and_recreate_orders(symbol)
            
            # Пауза между проверками (10 секунд)
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки. Завершение работы...")
            break
        except Exception as e:
            print(f"❌ Ошибка в цикле мониторинга: {e}")
            time.sleep(10)  # Пауза при ошибке

if __name__ == "__main__":
    main()

