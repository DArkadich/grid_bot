#!/usr/bin/env python3
"""
Отмена всех открытых спот ордеров на Bybit
Для освобождения заблокированных средств
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
    
    def get_spot_orders(self) -> Dict:
        """Получить открытые спот ордера"""
        endpoint = "/v5/order/realtime"
        params = {"category": "spot"}
        return self._make_request(endpoint, params)
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Отменить спот ордер"""
        endpoint = "/v5/order/cancel"
        params = {
            "category": "spot",
            "symbol": symbol,
            "orderId": order_id
        }
        return self._make_request(endpoint, params, "POST")
    
    def get_wallet_balance(self) -> Dict:
        """Получить баланс кошелька"""
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": "unified"}
        return self._make_request(endpoint, params)

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
    print("🚨 Отмена всех открытых спот ордеров")
    print("=" * 50)
    
    # Создаём клиент
    client = BybitClient(API_KEY, API_SECRET)
    
    # 1. Проверяем текущий баланс
    print("💰 Проверяю текущий баланс...")
    balance = client.get_wallet_balance()
    
    if "result" in balance and "list" in balance["result"]:
        account = balance["result"]["list"][0]
        usdt_coin = None
        
        for coin in account.get("coin", []):
            if coin.get("coin") == "USDT":
                usdt_coin = coin
                break
        
        if usdt_coin:
            total = safe_float(usdt_coin.get("walletBalance", 0))
            free = safe_float(usdt_coin.get("availableToWithdraw", 0))
            locked = safe_float(usdt_coin.get("locked", 0))
            
            print(f"  USDT: Total: {total:.8f}, Free: {free:.8f}, Locked: {locked:.8f}")
        else:
            print("  ❌ USDT не найден в балансе")
    else:
        print("  ❌ Не удалось получить баланс")
    
    # 2. Получаем открытые спот ордера
    print(f"\n📋 Получаю открытые спот ордера...")
    orders = client.get_spot_orders()
    
    if "result" not in orders or "list" not in orders["result"]:
        print("❌ Не удалось получить ордера")
        return
    
    order_list = orders["result"]["list"]
    open_orders = [o for o in order_list if o.get("orderStatus") == "New"]
    
    if not open_orders:
        print("✅ Открытых спот ордеров нет")
        return
    
    print(f"  Найдено {len(open_orders)} открытых ордеров:")
    
    # 3. Отменяем каждый ордер
    total_cancelled = 0
    
    for order in open_orders:
        symbol = order.get("symbol", "Unknown")
        side = order.get("side", "Unknown")
        qty = safe_float(order.get("qty", 0))
        price = safe_float(order.get("price", 0))
        order_id = order.get("orderId", "Unknown")
        
        print(f"\n  🔄 Отменяю {symbol} {side} {qty} @ {price}")
        print(f"      ID: {order_id}")
        
        # Отменяем ордер
        result = client.cancel_order(symbol, order_id)
        
        if result.get("retCode") == 0:
            print(f"      ✅ Ордер отменён")
            total_cancelled += 1
        else:
            print(f"      ❌ Ошибка отмены: {result.get('retMsg', 'Unknown')}")
        
        # Задержка между операциями
        time.sleep(1)
    
    # 4. Проверяем результат
    print(f"\n" + "=" * 50)
    print(f"📊 Результат отмены ордеров:")
    print(f"  Отменено: {total_cancelled}/{len(open_orders)}")
    
    if total_cancelled == len(open_orders):
        print("  ✅ Все ордера успешно отменены!")
        
        # Ждём и проверяем баланс
        print(f"\n⏳ Жду 10 секунд для разблокировки средств...")
        time.sleep(10)
        
        print(f"💰 Проверяю баланс после отмены...")
        final_balance = client.get_wallet_balance()
        
        if "result" in final_balance and "list" in final_balance["result"]:
            account = final_balance["result"]["list"][0]
            
            for coin in account.get("coin", []):
                if coin.get("coin") == "USDT":
                    total = safe_float(coin.get("walletBalance", 0))
                    free = safe_float(coin.get("availableToWithdraw", 0))
                    locked = safe_float(coin.get("locked", 0))
                    
                    print(f"  USDT: Total: {total:.8f}, Free: {free:.8f}, Locked: {locked:.8f}")
                    
                    if free > 0:
                        print(f"\n🎉 Средства освобождены! Свободно: {free:.2f} USDT")
                    else:
                        print(f"\n⚠️ Средства всё ещё заблокированы")
                    break
        else:
            print("❌ Не удалось получить финальный баланс")
    else:
        print(f"  ⚠️ Не все ордера отменены ({len(open_orders) - total_cancelled} осталось)")
        print("  🔍 Нужна ручная проверка на Bybit")

if __name__ == "__main__":
    main()
