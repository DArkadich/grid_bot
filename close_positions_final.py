#!/usr/bin/env python3
"""
Финальное закрытие позиций L1 Bot через правильный v5 API
Использует специальный endpoint для закрытия позиций
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
    
    def get_positions_unified(self) -> Dict:
        """Получить позиции в Unified Account"""
        endpoint = "/v5/position/list"
        params = {"category": "linear", "settleCoin": "USDT"}
        return self._make_request(endpoint, params)
    
    def close_position_v5_simple(self, symbol: str, side: str, size: str) -> Dict:
        """Закрыть позицию через простой v5 API"""
        endpoint = "/v5/order/create"
        
        # Инвертируем сторону для закрытия
        close_side = "Buy" if side == "Sell" else "Sell"
        
        # Минимальные параметры для v5 API
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": close_side,
            "orderType": "Market",
            "qty": size
        }
        
        print(f"    🔍 Параметры закрытия: {params}")
        return self._make_request(endpoint, params, "POST")
    
    def close_position_v5_reduce(self, symbol: str, side: str, size: str) -> Dict:
        """Закрыть позицию через reduceOnly"""
        endpoint = "/v5/order/create"
        
        # Инвертируем сторону для закрытия
        close_side = "Buy" if side == "Sell" else "Sell"
        
        # Параметры с reduceOnly
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": close_side,
            "orderType": "Market",
            "qty": size,
            "reduceOnly": "true"
        }
        
        print(f"    🔍 Параметры с reduceOnly: {params}")
        return self._make_request(endpoint, params, "POST")
    
    def close_position_v5_limit(self, symbol: str, side: str, size: str, price: str) -> Dict:
        """Закрыть позицию через лимитный ордер"""
        endpoint = "/v5/order/create"
        
        # Инвертируем сторону для закрытия
        close_side = "Buy" if side == "Sell" else "Sell"
        
        # Лимитный ордер
        params = {
            "category": "linear",
            "symbol": symbol,
            "side": close_side,
            "orderType": "Limit",
            "qty": size,
            "price": price,
            "timeInForce": "GTC"
        }
        
        print(f"    🔍 Параметры лимитного ордера: {params}")
        return self._make_request(endpoint, params, "POST")
    
    def get_wallet_balance(self) -> Dict:
        """Получить баланс кошелька"""
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": ACCOUNT_TYPE}
        return self._make_request(endpoint, params)
    
    def get_account_info(self) -> Dict:
        """Получить информацию об аккаунте"""
        endpoint = "/v5/account/info"
        return self._make_request(endpoint, params={})
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Получить информацию о символе"""
        endpoint = "/v5/market/instruments-info"
        params = {"category": "linear", "symbol": symbol}
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
    print("🔓 Финальное закрытие позиций L1 Bot через v5 API")
    print("=" * 60)
    
    # Создаём клиент
    client = BybitClient(API_KEY, API_SECRET)
    
    # 1. Проверяем информацию об аккаунте
    print("📋 Проверяю информацию об аккаунте...")
    account_info = client.get_account_info()
    
    if "result" in account_info:
        info = account_info["result"]
        print(f"  Тип аккаунта: {info.get('accountType', 'Unknown')}")
        print(f"  Маржинальный режим: {info.get('marginMode', 'Unknown')}")
        print(f"  Статус: {info.get('accountStatus', 'Unknown')}")
    else:
        print("  ❌ Не удалось получить информацию об аккаунте")
    
    # 2. Получаем текущие позиции
    print(f"\n📊 Получаю текущие позиции...")
    positions = client.get_positions_unified()
    
    if "result" not in positions or "list" not in positions["result"]:
        print("❌ Не удалось получить позиции")
        return
    
    pos_list = positions["result"]["list"]
    active_positions = [p for p in pos_list if safe_float(p.get("size", 0)) > 0]
    
    if not active_positions:
        print("✅ Активных позиций нет")
        return
    
    print(f"  Найдено {len(active_positions)} активных позиций:")
    
    # 3. Закрываем каждую позицию разными способами
    total_closed = 0
    
    for pos in active_positions:
        symbol = pos.get("symbol", "Unknown")
        side = pos.get("side", "Unknown")
        size = pos.get("size", "0")
        pnl = safe_float(pos.get("unrealisedPnl", 0))
        mark_price = pos.get("markPrice", "0")
        
        print(f"\n  🔄 Закрываю {symbol} {side} {size} (PnL: {pnl:.4f})")
        
        # Способ 1: Простой рыночный ордер
        print(f"    📈 Способ 1: Простой рыночный ордер...")
        result = client.close_position_v5_simple(symbol, side, size)
        
        if result.get("retCode") == 0:
            order_id = result.get("result", {}).get("orderId", "Unknown")
            print(f"      ✅ Позиция закрыта: {order_id}")
            total_closed += 1
            continue
        
        # Способ 2: С reduceOnly
        print(f"    📉 Способ 2: С reduceOnly...")
        result = client.close_position_v5_reduce(symbol, side, size)
        
        if result.get("retCode") == 0:
            order_id = result.get("result", {}).get("orderId", "Unknown")
            print(f"      ✅ Позиция закрыта: {order_id}")
            total_closed += 1
            continue
        
        # Способ 3: Лимитный ордер
        print(f"    🔒 Способ 3: Лимитный ордер...")
        result = client.close_position_v5_limit(symbol, side, size, mark_price)
        
        if result.get("retCode") == 0:
            order_id = result.get("result", {}).get("orderId", "Unknown")
            print(f"      ✅ Позиция закрыта: {order_id}")
            total_closed += 1
            continue
        
        # Все способы не сработали
        print(f"      ❌ Все способы не сработали")
        print(f"      📡 Последняя ошибка: {result.get('retMsg', 'Unknown')}")
        print(f"      ⚠️ Позиция {symbol} не закрыта!")
        
        # Задержка между операциями
        time.sleep(2)
    
    # 4. Проверяем результат
    print(f"\n" + "=" * 60)
    print(f"📊 Результат закрытия позиций:")
    print(f"  Закрыто: {total_closed}/{len(active_positions)}")
    
    if total_closed == len(active_positions):
        print("  ✅ Все позиции успешно закрыты!")
        
        # Ждём и проверяем баланс
        print(f"\n⏳ Жду 30 секунд для разблокировки средств...")
        time.sleep(30)
        
        print(f"📊 Проверяю баланс после закрытия...")
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
            
            print(f"\n📊 Итоговый результат:")
            if total_free > 10:
                print(f"  ✅ Освобождено: {total_free:.2f} USD")
                print("  🚀 Теперь можно конвертировать в USDT!")
            else:
                print(f"  ⚠️ Освобождено мало: {total_free:.2f} USD")
                print("  🔍 Возможно, нужна дополнительная проверка")
        else:
            print("❌ Не удалось получить финальный баланс")
    else:
        print(f"  ⚠️ Не все позиции закрыты ({len(active_positions) - total_closed} осталось)")
        print("  🔍 Нужна ручная проверка на Bybit")
        print("  💡 Возможно, проблема в правах API ключей")
        print("  🆘 Попробуйте закрыть позиции вручную через Bybit")

if __name__ == "__main__":
    main()
