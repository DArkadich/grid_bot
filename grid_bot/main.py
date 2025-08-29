"""
Grid Trading Bot - Автоматическая торговля по сетке цен

ВСЕ ПАРАМЕТРЫ НАСТРАИВАЮТСЯ ЧЕРЕЗ .env ФАЙЛ:

ОБЯЗАТЕЛЬНЫЕ:
- BYBIT_API_KEY - API ключ Bybit
- BYBIT_API_SECRET - API секрет Bybit
- SYMBOLS - торговые пары через запятую (например: DOGE/USDT,WIF/USDT,JUP/USDT)

ПАРАМЕТРЫ СЕТКИ:
- GRID_LEVELS - количество уровней сетки (рекомендуется: 5)
- GRID_SPREAD - спред между уровнями в % (рекомендуется: 0.005 = 0.5%)
- LEVEL_AMOUNT - USDT на уровень (рекомендуется: 25)

ЦЕЛЬ: 5-15% доходности в день с узкой и эффективной сеткой
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
        """Получить доступный баланс USDT"""
        try:
            balance = self.exchange.fetch_balance()
            if 'USDT' in balance and 'free' in balance['USDT']:
                return float(balance['USDT']['free'])
            return 0.0
        except Exception as e:
            print(f"Ошибка получения баланса: {e}")
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
    
    def check_available_balance(self, required_amount: float) -> bool:
        """Проверить, достаточно ли средств для создания ордера"""
        try:
            available_balance = self.client.get_balance()
            if available_balance >= required_amount:
                print(f"💰 Доступно USDT: {available_balance:.2f}, нужно: {required_amount:.2f}")
                return True
            else:
                print(f"❌ Недостаточно средств: доступно {available_balance:.2f} USDT, нужно {required_amount:.2f} USDT")
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
        """Создать сетку для пары"""
        try:
            grid = []
            base_amount = self.config.level_amount / current_price
            
            # Создаём уровни покупки ниже текущей цены
            for i in range(self.config.grid_levels):
                buy_price = current_price * (1 - self.config.grid_spread * (i + 1))
                buy_price = round(buy_price, 6)
                
                grid.append({
                    "level": i,
                    "side": "buy",
                    "price": buy_price,
                    "amount": base_amount,
                    "status": "pending"
                })
            
            # Создаём уровни продажи выше текущей цены
            for i in range(self.config.grid_levels):
                sell_price = current_price * (1 + self.config.grid_spread * (i + 1))
                sell_price = round(sell_price, 6)
                
                grid.append({
                    "level": i,
                    "side": "sell", 
                    "price": sell_price,
                    "amount": base_amount,
                    "status": "pending"
                })
            
            self.grids[symbol] = grid
            self.save_grid_to_db(symbol, grid)
            print(f"Сетка создана для {symbol}: {len(grid)} уровней")
            
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
        """Разместить ордера сетки с проверкой баланса"""
        try:
            if symbol not in self.grids:
                return
            
            grid = self.grids[symbol]
            placed_orders = 0
            skipped_orders = 0
            
            for level in grid:
                if level["status"] == "pending":
                    # Рассчитываем требуемую сумму для ордера
                    required_amount = level["amount"] * level["price"]
                    
                    # Проверяем, достаточно ли средств
                    if self.check_available_balance(required_amount):
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
                            print(f"✅ Ордер размещён: {symbol} {level['side']} {level['amount']:.2f} @ {level['price']}")
                        
                        time.sleep(0.1)  # Задержка между ордерами
                    else:
                        skipped_orders += 1
                        print(f"⏭️ Ордер пропущен: {symbol} {level['side']} {level['amount']:.2f} @ {level['price']} (недостаточно средств)")
            
            print(f"📊 {symbol}: размещено {placed_orders} ордеров, пропущено {skipped_orders}")
                    
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
                        # Пересчитываем цену для уровня
                        if level["side"] == "buy":
                            new_price = current_price * (1 - self.config.grid_spread * (level["level"] + 1))
                        else:  # sell
                            new_price = current_price * (1 + self.config.grid_spread * (level["level"] + 1))
                        
                        new_price = round(new_price, 6)
                        level["price"] = new_price
                        level["status"] = "pending"
                        level["order_id"] = None
                        
                        # Обновляем в БД
                        self.update_order_in_db(symbol, level["level"], level["side"], new_price, None, "pending")
                    
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
            # Мониторинг активных сеток
            for symbol in grid_manager.grids.keys():
                # Проверяем статус ордеров
                ticker = client.get_ticker(symbol)
                if ticker and "last" in ticker:
                    current_price = ticker["last"]
                    print(f"💰 {symbol}: текущая цена {current_price}")
                    
                    # Синхронизируем статус ордеров с биржей
                    grid_manager.sync_orders_with_exchange(symbol)
                    
                    # Каждые 5 минут проверяем и пересоздаём недостающие ордера
                    if int(time.time()) % 300 < 60:  # Каждые 5 минут
                        grid_manager.check_and_recreate_orders(symbol)
            
            # Пауза между проверками (1 минута)
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки. Завершение работы...")
            break
        except Exception as e:
            print(f"❌ Ошибка в цикле мониторинга: {e}")
            time.sleep(10)  # Пауза при ошибке

if __name__ == "__main__":
    main()

