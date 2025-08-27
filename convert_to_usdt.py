#!/usr/bin/env python3
"""
Скрипт для конвертации всех активов в USDT
Автоматически продаёт все валюты (кроме USDT) за USDT
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
    
    def get_ticker(self, symbol: str) -> Dict:
        """Получить текущие цены"""
        endpoint = "/v5/market/tickers"
        params = {"category": "spot", "symbol": symbol}
        return self._make_request(endpoint, params)
    
    def create_spot_order(self, symbol: str, side: str, qty: str, order_type: str = "Market") -> Dict:
        """Создать спот ордер"""
        endpoint = "/v5/order/create"
        params = {
            "category": "spot",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty
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

def get_spot_symbol(base_currency: str) -> str:
    """Получить символ для спот торговли"""
    if base_currency == "USDT":
        return None
    return f"{base_currency}USDT"

# ========== ОСНОВНАЯ ЛОГИКА ==========
def main():
    print("🚀 Скрипт конвертации всех активов в USDT")
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
    
    # 2. Анализируем активы для конвертации
    print(f"\n📊 Анализирую активы для конвертации...")
    
    assets_to_convert = []
    total_equity_usd = 0
    
    for coin in account.get("coin", []):
        currency = coin.get("coin", "Unknown")
        total = safe_float(coin.get("walletBalance", 0))
        free = safe_float(coin.get("availableToWithdraw", 0))
        equity = safe_float(coin.get("equity", 0))
        usd_value = safe_float(coin.get("usdValue", 0))
        
        print(f"  {currency}:")
        print(f"    Total: {total:.8f}")
        print(f"    Free: {free:.8f}")
        print(f"    Equity: {equity:.8f}")
        print(f"    USD Value: {usd_value:.4f}")
        
        # Добавляем в список для конвертации (кроме USDT и пыли)
        if currency != "USDT" and free > 0.001 and usd_value > 0.1:
            assets_to_convert.append({
                "currency": currency,
                "amount": free,
                "usd_value": usd_value,
                "symbol": get_spot_symbol(currency)
            })
            print(f"    ✅ Добавлен для конвертации")
        elif currency == "USDT":
            print(f"    💰 USDT - оставляем")
        else:
            print(f"    ⚠️ Пыль или слишком мало - пропускаем")
        
        total_equity_usd += usd_value
    
    print(f"\n💵 Общий equity в USD: {total_equity_usd:.4f}")
    
    if not assets_to_convert:
        print("✅ Нет активов для конвертации!")
        return
    
    # 3. Конвертируем активы в USDT
    print(f"\n🔄 Конвертирую {len(assets_to_convert)} активов в USDT...")
    
    converted_total = 0
    
    for asset in assets_to_convert:
        currency = asset["currency"]
        amount = asset["amount"]
        symbol = asset["symbol"]
        
        if not symbol:
            print(f"  ⚠️ Пропускаю {currency} - нет символа для торговли")
            continue
        
        print(f"\n  🔄 Конвертирую {amount:.8f} {currency} в USDT...")
        
        try:
            # Получаем текущую цену
            ticker = client.get_ticker(symbol)
            if "result" in ticker and "list" in ticker["result"]:
                ticker_data = ticker["result"]["list"][0]
                last_price = safe_float(ticker_data.get("lastPrice", 0))
                
                if last_price > 0:
                    estimated_usdt = amount * last_price
                    print(f"    Цена: {last_price:.6f} USDT")
                    print(f"    Ожидаемо: {estimated_usdt:.4f} USDT")
                    
                    # Создаём ордер на продажу
                    result = client.create_spot_order(symbol, "Sell", str(amount))
                    
                    if result.get("retCode") == 0:
                        order_id = result.get("result", {}).get("orderId", "Unknown")
                        print(f"    ✅ Ордер создан: {order_id}")
                        converted_total += estimated_usdt
                    else:
                        print(f"    ❌ Ошибка создания ордера: {result.get('retMsg', 'Unknown')}")
                else:
                    print(f"    ❌ Не удалось получить цену для {symbol}")
            else:
                print(f"    ❌ Не удалось получить тикер для {symbol}")
                
        except Exception as e:
            print(f"    ❌ Ошибка конвертации {currency}: {e}")
        
        # Задержка между ордерами
        time.sleep(2)
    
    # 4. Финальная проверка
    print(f"\n" + "=" * 60)
    print("📊 Финальная проверка баланса...")
    
    final_balance = client.get_wallet_balance()
    if "result" in final_balance and "list" in final_balance["result"]:
        account = final_balance["result"]["list"][0]
        
        usdt_final = 0
        total_equity_final = 0
        
        for coin in account.get("coin", []):
            currency = coin.get("coin", "")
            if currency == "USDT":
                usdt_final = safe_float(coin.get("availableToWithdraw", 0))
                print(f"  USDT Final: {usdt_final:.4f}")
            else:
                usd_value = safe_float(coin.get("usdValue", 0))
                total_equity_final += usd_value
        
        print(f"  Общий equity Final: {total_equity_final:.4f}")
        
        if usdt_final > 10:
            print(f"✅ Успешно получено {usdt_final:.2f} USDT!")
            print("Теперь можно запускать Grid Trading Bot!")
        else:
            print(f"⚠️ USDT всё ещё мало: {usdt_final:.2f}")
            print("Возможно, нужно подождать исполнения ордеров")
    else:
        print("❌ Не удалось получить финальный баланс")

if __name__ == "__main__":
    main()
