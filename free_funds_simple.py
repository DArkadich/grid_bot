#!/usr/bin/env python3
"""
Упрощённый скрипт для освобождения средств от L1 Bot
Работает с минимальными зависимостями
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
    
    def _sign_request(self, params: str, timestamp: str) -> str:
        """Подписать запрос"""
        sign_str = timestamp + self.api_key + "5000" + params
        return hmac.new(
            self.api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
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
            signature = self._sign_request(sorted_params, timestamp)
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
    
    def close_position(self, symbol: str, side: str, size: str) -> Dict:
        """Закрыть позицию"""
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
    
    def sell_spot(self, symbol: str, qty: str) -> Dict:
        """Продать спот актив"""
        endpoint = "/v5/order/create"
        params = {
            "category": "spot",
            "symbol": symbol,
            "side": "Sell",
            "orderType": "Market",
            "qty": qty
        }
        return self._make_request(endpoint, params, "POST")

# ========== ОСНОВНАЯ ЛОГИКА ==========
def main():
    print("🚀 Упрощённый скрипт освобождения средств от L1 Bot")
    print("=" * 60)
    
    # Создаём клиент
    client = BybitClient(API_KEY, API_SECRET)
    
    # 1. Проверяем баланс
    print("💰 Проверяю баланс...")
    balance = client.get_wallet_balance()
    
    if "result" in balance:
        account = balance["result"]["list"][0]
        print(f"  Аккаунт: {account['accountType']}")
        
        for coin in account.get("coin", []):
            if coin["coin"] == "USDT":
                total = float(coin.get("walletBalance", 0))
                free = float(coin.get("availableToWithdraw", 0))
                print(f"  USDT Total: {total:.2f}")
                print(f"  USDT Free: {free:.2f}")
                break
    else:
        print("❌ Не удалось получить баланс")
        return
    
    # 2. Проверяем позиции
    print("\n📊 Проверяю позиции...")
    positions = client.get_positions()
    
    active_positions = []
    if "result" in positions:
        pos_list = positions["result"]["list"]
        for pos in pos_list:
            size = float(pos.get("size", 0))
            if size > 0:
                active_positions.append(pos)
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                avg_price = float(pos.get("avgPrice", 0))
                pnl = float(pos.get("unrealisedPnl", 0))
                print(f"  {symbol} {side} {size:.6f} @ {avg_price:.4f} PnL: {pnl:.4f}")
    
    if not active_positions:
        print("  ✅ Активных позиций нет")
    
    # 3. Закрываем позиции
    if active_positions:
        print(f"\n🔄 Закрываю {len(active_positions)} позиций...")
        for pos in active_positions:
            symbol = pos.get("symbol", "")
            side = pos.get("side", "")
            size = pos.get("size", "0")
            
            print(f"  Закрываю {symbol} {side} {size}...")
            result = client.close_position(symbol, side, size)
            
            if result.get("retCode") == 0:
                print(f"    ✅ Позиция закрыта")
            else:
                print(f"    ❌ Ошибка: {result.get('retMsg', 'Unknown')}")
            
            time.sleep(1)  # Задержка между операциями
    
    # 4. Финальная проверка
    print("\n" + "=" * 60)
    print("📊 Финальная проверка баланса...")
    
    final_balance = client.get_wallet_balance()
    if "result" in final_balance:
        account = final_balance["result"]["list"][0]
        for coin in account.get("coin", []):
            if coin["coin"] == "USDT":
                free_usdt = float(coin.get("availableToWithdraw", 0))
                print(f"  USDT Free: {free_usdt:.2f}")
                
                if free_usdt > 10:
                    print(f"✅ Успешно освобождено {free_usdt:.2f} USDT!")
                    print("Теперь можно запускать Grid Trading Bot")
                else:
                    print("⚠️ USDT всё ещё недостаточно для Grid Bot")
                    print("Возможно, нужно пополнить аккаунт")
                break
    else:
        print("❌ Не удалось получить финальный баланс")

if __name__ == "__main__":
    main()
