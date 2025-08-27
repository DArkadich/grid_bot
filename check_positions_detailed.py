#!/usr/bin/env python3
"""
Детальная проверка всех позиций, ордеров и заблокированных средств
Помогает понять, где заблокированы активы
"""

import os
import json
import time
import urllib.request
import urllib.parse
import hmac
import hashlib
from typing import Dict, List

# ========== КОНФИГУРАЦИЯ ==========
API_KEY = os.environ.get("BYBIT_API_KEY", "")
API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
ACCOUNT_TYPE = os.environ.get("BYBIT_ACCOUNT_TYPE", "unified")

if not API_KEY or not API_SECRET:
    print("❌ Ошибка: не указаны API ключи Bybit")
    print("Установите переменные окружения:")
    print("export BYBIT_API_KEY=ваш_ключ")
    print("export BYBIT_API_SECRET=ваш_секрет")
    exit(1)

# ========== BYBIT API КЛИЕНТ ==========
class BybitClient:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.bybit.com"
    
    def _sign_request(self, params: str) -> str:
        """Подписать запрос для Bybit"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, endpoint: str, params: Dict = None, method: str = "GET") -> Dict:
        """Выполнить API запрос"""
        try:
            timestamp = str(int(time.time() * 1000))
            
            if params is None:
                params = {}
            
            # Добавляем обязательные параметры
            params.update({
                "api_key": self.api_key,
                "timestamp": timestamp,
                "recv_window": "5000"
            })
            
            # Сортируем параметры для подписи
            sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            signature = self._sign_request(sorted_params)
            params["sign"] = signature
            
            url = f"{self.base_url}{endpoint}"
            
            if method == "GET":
                url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
                request = urllib.request.Request(url)
            else:
                data = urllib.parse.urlencode(params).encode('utf-8')
                request = urllib.request.Request(url, data=data, method=method)
                request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode())
                return result
                
        except Exception as e:
            print(f"❌ Ошибка API запроса: {e}")
            return {}
    
    def get_wallet_balance(self) -> Dict:
        """Получить баланс кошелька"""
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": ACCOUNT_TYPE}
        return self._make_request(endpoint, params)
    
    def get_positions(self) -> Dict:
        """Получить активные позиции"""
        endpoint = "/v5/position/list"
        params = {"category": "linear"}
        return self._make_request(endpoint, params)
    
    def get_open_orders(self) -> Dict:
        """Получить открытые ордера"""
        endpoint = "/v5/order/realtime"
        params = {"category": "linear"}
        return self._make_request(endpoint, params)
    
    def get_spot_orders(self) -> Dict:
        """Получить спот ордера"""
        endpoint = "/v5/order/realtime"
        params = {"category": "spot"}
        return self._make_request(endpoint, params)
    
    def get_account_info(self) -> Dict:
        """Получить информацию об аккаунте"""
        endpoint = "/v5/account/info"
        return self._make_request(endpoint, params={})

# ========== УТИЛИТЫ ==========
def safe_float(value, default=0.0):
    """Безопасное преобразование в float"""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

# ========== ОСНОВНАЯ ЛОГИКА ==========
def main():
    print("🔍 Детальная проверка всех позиций и заблокированных средств")
    print("=" * 70)
    
    # Создаём клиент
    client = BybitClient(API_KEY, API_SECRET)
    
    # 1. Информация об аккаунте
    print("📋 Информация об аккаунте...")
    account_info = client.get_account_info()
    
    if "result" in account_info:
        info = account_info["result"]
        print(f"  Тип аккаунта: {info.get('accountType', 'Unknown')}")
        print(f"  Маржинальный режим: {info.get('marginMode', 'Unknown')}")
        print(f"  Статус: {info.get('accountStatus', 'Unknown')}")
    else:
        print("  ❌ Не удалось получить информацию об аккаунте")
    
    # 2. Проверяем баланс
    print("\n💰 Баланс кошелька...")
    balance = client.get_wallet_balance()
    
    if "result" in balance and "list" in balance["result"]:
        account = balance["result"]["list"][0]
        
        print(f"  Аккаунт: {account['accountType']}")
        
        # Анализируем заблокированные средства
        total_locked = 0
        total_free = 0
        
        for coin in account.get("coin", []):
            currency = coin.get("coin", "Unknown")
            total = safe_float(coin.get("walletBalance", 0))
            free = safe_float(coin.get("availableToWithdraw", 0))
            locked = safe_float(coin.get("locked", 0))
            usd_value = safe_float(coin.get("usdValue", 0))
            
            if total > 0:
                print(f"  {currency}:")
                print(f"    Total: {total:.8f}")
                print(f"    Free: {free:.8f}")
                print(f"    Locked: {locked:.8f}")
                print(f"    USD Value: {usd_value:.4f}")
                
                if free == 0 and total > 0:
                    print(f"    ⚠️ ЗАБЛОКИРОВАН!")
                    total_locked += usd_value
                else:
                    total_free += usd_value
        
        print(f"\n📊 Итого:")
        print(f"  Заблокировано: {total_locked:.2f} USD")
        print(f"  Свободно: {total_free:.2f} USD")
    else:
        print("  ❌ Не удалось получить баланс")
        return
    
    # 3. Проверяем позиции
    print("\n📊 Активные позиции...")
    positions = client.get_positions()
    
    if "result" in positions and "list" in positions["result"]:
        pos_list = positions["result"]["list"]
        active_positions = [p for p in pos_list if safe_float(p.get("size", 0)) > 0]
        
        if active_positions:
            print(f"  Найдено {len(active_positions)} активных позиций:")
            for pos in active_positions:
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                size = safe_float(pos.get("size", 0))
                avg_price = safe_float(pos.get("avgPrice", 0))
                pnl = safe_float(pos.get("unrealisedPnl", 0))
                margin = safe_float(pos.get("positionIM", 0))
                
                print(f"    {symbol} {side} {size:.6f} @ {avg_price:.4f}")
                print(f"      PnL: {pnl:.4f} | Margin: {margin:.4f}")
        else:
            print("  ✅ Активных позиций нет")
    else:
        print("  ❌ Не удалось получить позиции")
    
    # 4. Проверяем открытые ордера
    print("\n📝 Открытые ордера (фьючерсы)...")
    futures_orders = client.get_open_orders()
    
    if "result" in futures_orders and "list" in futures_orders["result"]:
        orders = futures_orders["result"]["list"]
        active_orders = [o for o in orders if o.get("orderStatus") == "New"]
        
        if active_orders:
            print(f"  Найдено {len(active_orders)} открытых ордеров:")
            for order in active_orders:
                symbol = order.get("symbol", "Unknown")
                side = order.get("side", "Unknown")
                qty = safe_float(order.get("qty", 0))
                price = safe_float(order.get("price", 0))
                order_id = order.get("orderId", "Unknown")
                
                print(f"    {symbol} {side} {qty:.6f} @ {price:.4f} (ID: {order_id})")
        else:
            print("  ✅ Открытых ордеров нет")
    else:
        print("  ❌ Не удалось получить ордера фьючерсов")
    
    # 5. Проверяем спот ордера
    print("\n📝 Открытые ордера (спот)...")
    spot_orders = client.get_spot_orders()
    
    if "result" in spot_orders and "list" in spot_orders["result"]:
        orders = spot_orders["result"]["list"]
        active_orders = [o for o in orders if o.get("orderStatus") == "New"]
        
        if active_orders:
            print(f"  Найдено {len(active_orders)} открытых спот ордеров:")
            for order in active_orders:
                symbol = order.get("symbol", "Unknown")
                side = order.get("side", "Unknown")
                qty = safe_float(order.get("qty", 0))
                price = safe_float(order.get("price", 0))
                order_id = order.get("orderId", "Unknown")
                
                print(f"    {symbol} {side} {qty:.6f} @ {price:.4f} (ID: {order_id})")
        else:
            print("  ✅ Открытых спот ордеров нет")
    else:
        print("  ❌ Не удалось получить спот ордера")
    
    # 6. Рекомендации
    print("\n" + "=" * 70)
    print("💡 РЕКОМЕНДАЦИИ:")
    
    if total_locked > 0:
        print(f"  🔒 У вас заблокировано {total_locked:.2f} USD активов")
        print("  📋 Для освобождения нужно:")
        print("    1. Отменить все открытые ордера")
        print("    2. Закрыть все активные позиции")
        print("    3. Дождаться разблокировки маржи")
        print("    4. Затем конвертировать в USDT")
    else:
        print("  ✅ Все средства свободны!")
        print("  🚀 Можно конвертировать в USDT")

if __name__ == "__main__":
    main()
