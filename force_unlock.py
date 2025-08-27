#!/usr/bin/env python3
"""
Принудительное освобождение заблокированных средств
Пытается закрыть все возможные позиции и отменить ордера
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
    
    def get_positions_v2(self) -> Dict:
        """Получить позиции через v2 API"""
        endpoint = "/v2/private/position/list"
        return self._make_request(endpoint, params={})
    
    def get_open_orders_v2(self) -> Dict:
        """Получить открытые ордера через v2 API"""
        endpoint = "/v2/private/order"
        params = {"limit": 50}
        return self._make_request(endpoint, params)
    
    def cancel_all_orders(self) -> Dict:
        """Отменить все ордера"""
        endpoint = "/v2/private/order/cancelAll"
        return self._make_request(endpoint, params={}, method="POST")
    
    def close_position(self, symbol: str, side: str, size: str) -> Dict:
        """Закрыть позицию"""
        endpoint = "/v2/private/position/trading-stop"
        params = {
            "symbol": symbol,
            "stop_loss": "0",
            "take_profit": "0"
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
    print("🔓 Принудительное освобождение заблокированных средств")
    print("=" * 70)
    
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
    
    # 2. Пытаемся получить позиции через v2 API
    print(f"\n📊 Пытаюсь получить позиции через v2 API...")
    positions = client.get_positions_v2()
    
    if "result" in positions:
        pos_list = positions["result"]
        if pos_list:
            print(f"  Найдено {len(pos_list)} позиций:")
            for pos in pos_list:
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                size = safe_float(pos.get("size", 0))
                pnl = safe_float(pos.get("unrealised_pnl", 0))
                
                print(f"    {symbol} {side} {size:.6f} PnL: {pnl:.4f}")
                
                # Пытаемся закрыть позицию
                if size > 0:
                    print(f"      🔄 Закрываю позицию...")
                    result = client.close_position(symbol, side, str(size))
                    
                    if result.get("ret_code") == 0:
                        print(f"        ✅ Позиция закрыта")
                    else:
                        print(f"        ❌ Ошибка: {result.get('ret_msg', 'Unknown')}")
                    
                    time.sleep(1)
        else:
            print("  ✅ Позиций не найдено")
    else:
        print("  ❌ Не удалось получить позиции через v2 API")
    
    # 3. Пытаемся получить ордера через v2 API
    print(f"\n📝 Пытаюсь получить ордера через v2 API...")
    orders = client.get_open_orders_v2()
    
    if "result" in orders:
        order_list = orders["result"]
        if order_list:
            print(f"  Найдено {len(order_list)} ордеров:")
            for order in order_list:
                symbol = order.get("symbol", "Unknown")
                side = order.get("side", "Unknown")
                qty = safe_float(order.get("qty", 0))
                price = safe_float(order.get("price", 0))
                order_id = order.get("order_id", "Unknown")
                
                print(f"    {symbol} {side} {qty:.6f} @ {price:.4f} (ID: {order_id})")
        else:
            print("  ✅ Открытых ордеров не найдено")
    else:
        print("  ❌ Не удалось получить ордера через v2 API")
    
    # 4. Принудительно отменяем все ордера
    print(f"\n🔄 Принудительно отменяю все ордера...")
    cancel_result = client.cancel_all_orders()
    
    if cancel_result.get("ret_code") == 0:
        print("  ✅ Все ордера отменены")
    else:
        print(f"  ❌ Ошибка отмены: {cancel_result.get('ret_msg', 'Unknown')}")
    
    # 5. Ждём и проверяем баланс
    print(f"\n⏳ Жду 10 секунд для разблокировки средств...")
    time.sleep(10)
    
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
            print("  🔍 Возможно, нужна ручная проверка на Bybit")
    else:
        print("❌ Не удалось получить финальный баланс")

if __name__ == "__main__":
    main()
