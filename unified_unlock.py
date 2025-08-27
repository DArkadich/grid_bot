#!/usr/bin/env python3
"""
Освобождение средств в Unified Account
Работает с v5 API для Unified Account
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
    
    def get_positions_unified(self) -> Dict:
        """Получить позиции в Unified Account"""
        endpoint = "/v5/position/list"
        params = {"category": "linear", "settleCoin": "USDT"}
        return self._make_request(endpoint, params)
    
    def get_open_orders_unified(self) -> Dict:
        """Получить открытые ордера в Unified Account"""
        endpoint = "/v5/order/realtime"
        params = {"category": "linear", "settleCoin": "USDT"}
        return self._make_request(endpoint, params)
    
    def get_spot_orders_unified(self) -> Dict:
        """Получить спот ордера в Unified Account"""
        endpoint = "/v5/order/realtime"
        params = {"category": "spot"}
        return self._make_request(endpoint, params)
    
    def cancel_order_unified(self, order_id: str, symbol: str) -> Dict:
        """Отменить конкретный ордер"""
        endpoint = "/v5/order/cancel"
        params = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id
        }
        return self._make_request(endpoint, params, "POST")
    
    def cancel_all_orders_unified(self) -> Dict:
        """Отменить все ордера в категории"""
        endpoint = "/v5/order/cancelAll"
        params = {"category": "linear"}
        return self._make_request(endpoint, params, "POST")
    
    def close_position_unified(self, symbol: str, side: str, size: str) -> Dict:
        """Закрыть позицию в Unified Account"""
        endpoint = "/v5/order/create"
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": "Buy" if side == "Sell" else "Sell",
            "orderType": "Market",
            "qty": size,
            "reduceOnly": "true"
        }
        return self._make_request(endpoint, params, "POST")

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
    print("🔓 Освобождение средств в Unified Account")
    print("=" * 60)
    
    # Создаём клиент
    client = BybitClient(API_KEY, API_SECRET)
    
    # 1. Проверяем текущий баланс
    print("💰 Проверяю текущий баланс...")
    balance = client.get_wallet_balance()
    
    if "result" not in balance or "list" not in balance["result"]:
        print("❌ Не удалось получить баланс")
        return
    
    account = balance["result"]["list"][0]
    print(f"  Аккаунт: {account['accountType']}")
    
    # Анализируем заблокированные средства
    total_locked = 0
    locked_assets = []
    
    for coin in account.get("coin", []):
        currency = coin.get("coin", "Unknown")
        total = safe_float(coin.get("walletBalance", 0))
        free = safe_float(coin.get("availableToWithdraw", 0))
        usd_value = safe_float(coin.get("usdValue", 0))
        
        if total > 0 and free == 0:
            total_locked += usd_value
            locked_assets.append({
                "currency": currency,
                "amount": total,
                "usd_value": usd_value
            })
            print(f"  🔒 {currency}: {total:.8f} (${usd_value:.2f})")
    
    print(f"\n📊 Итого заблокировано: {total_locked:.2f} USD")
    
    if total_locked == 0:
        print("✅ Все средства свободны!")
        return
    
    # 2. Пытаемся получить позиции с правильными параметрами
    print(f"\n📊 Пытаюсь получить позиции...")
    positions = client.get_positions_unified()
    
    print(f"📡 Ответ API позиций: {json.dumps(positions, indent=2)}")
    
    if "result" in positions and "list" in positions["result"]:
        pos_list = positions["result"]["list"]
        active_positions = [p for p in pos_list if safe_float(p.get("size", 0)) > 0]
        
        if active_positions:
            print(f"  Найдено {len(active_positions)} активных позиций:")
            for pos in active_positions:
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                size = safe_float(pos.get("size", 0))
                pnl = safe_float(pos.get("unrealisedPnl", 0))
                
                print(f"    {symbol} {side} {size:.6f} PnL: {pnl:.4f}")
                
                # Пытаемся закрыть позицию
                if size > 0:
                    print(f"      🔄 Закрываю позицию...")
                    result = client.close_position_unified(symbol, side, str(size))
                    
                    if result.get("retCode") == 0:
                        print(f"        ✅ Позиция закрыта")
                    else:
                        print(f"        ❌ Ошибка: {result.get('retMsg', 'Unknown')}")
                    
                    time.sleep(1)
        else:
            print("  ✅ Активных позиций не найдено")
    else:
        print("  ❌ Не удалось получить позиции")
    
    # 3. Пытаемся получить ордера
    print(f"\n📝 Пытаюсь получить ордера...")
    futures_orders = client.get_open_orders_unified()
    
    print(f"📡 Ответ API фьючерс ордеров: {json.dumps(futures_orders, indent=2)}")
    
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
                
                # Пытаемся отменить ордер
                print(f"      🔄 Отменяю ордер...")
                result = client.cancel_order_unified(order_id, symbol)
                
                if result.get("retCode") == 0:
                    print(f"        ✅ Ордер отменён")
                else:
                    print(f"        ❌ Ошибка: {result.get('retMsg', 'Unknown')}")
                
                time.sleep(1)
        else:
            print("  ✅ Открытых ордеров не найдено")
    else:
        print("  ❌ Не удалось получить ордера")
    
    # 4. Проверяем спот ордера
    print(f"\n📝 Проверяю спот ордера...")
    spot_orders = client.get_spot_orders_unified()
    
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
    
    # 5. Ждём и проверяем баланс
    print(f"\n⏳ Жду 15 секунд для разблокировки средств...")
    time.sleep(15)
    
    print(f"📊 Проверяю баланс после освобождения...")
    final_balance = client.get_wallet_balance()
    
    if "result" in final_balance and "list" in final_balance["result"]:
        account = final_balance["result"]["list"][0]
        
        total_free = 0
        for coin in account.get("coin", []):
            currency = coin.get("coin", "")
            free = safe_float(coin.get("availableToWithdraw", 0))
            usd_value = safe_float(coin.get("usdValue", 0))
            
            if free > 0:
                print(f"  💰 {currency}: {free:.8f} (${usd_value:.2f})")
                if currency == "USDT":
                    total_free += free
                else:
                    total_free += usd_value
        
        print(f"\n📊 Результат:")
        if total_free > 10:
            print(f"  ✅ Освобождено: {total_free:.2f} USD")
            print("  🚀 Теперь можно конвертировать в USDT!")
        else:
            print(f"  ⚠️ Освобождено мало: {total_free:.2f} USD")
            print("  🔍 Нужна ручная проверка на Bybit")
            print("  💡 Возможно, активы заблокированы в споте")
    else:
        print("❌ Не удалось получить финальный баланс")

if __name__ == "__main__":
    main()
