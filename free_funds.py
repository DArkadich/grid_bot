#!/usr/bin/env python3
"""
Скрипт для освобождения средств от L1 Bot позиций
Проверяет спот и перпетуал позиции, закрывает их для освобождения USDT
"""

import os
import ccxt
import time
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

# ========== КЛИЕНТ БИРЖИ ==========
def create_exchange():
    """Создать клиент Bybit"""
    exchange = ccxt.bybit({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "unified"}
    })
    exchange.load_markets()
    return exchange

# ========== ПРОВЕРКА БАЛАНСА ==========
def check_balance(exchange) -> Dict:
    """Проверить баланс аккаунта"""
    try:
        balance = exchange.fetch_balance(params={"type": "unified"})
        
        print("💰 Баланс аккаунта:")
        print(f"  USDT Total: {balance.get('total', {}).get('USDT', 0):.2f}")
        print(f"  USDT Free: {balance.get('free', {}).get('USDT', 0):.2f}")
        print(f"  USDT Used: {balance.get('used', {}).get('USDT', 0):.2f}")
        
        return balance
    except Exception as e:
        print(f"❌ Ошибка получения баланса: {e}")
        return {}

# ========== ПРОВЕРКА ПОЗИЦИЙ ==========
def check_positions(exchange) -> List[Dict]:
    """Проверить все открытые позиции"""
    try:
        positions = exchange.private_get_v5_position_list({
            "category": "linear"
        })
        
        pos_list = positions.get("result", {}).get("list", [])
        active_positions = [p for p in pos_list if float(p.get("size", 0)) > 0]
        
        print(f"\n📊 Активные позиции: {len(active_positions)}")
        for pos in active_positions:
            symbol = pos.get("symbol", "Unknown")
            side = pos.get("side", "Unknown")
            size = float(pos.get("size", 0))
            avg_price = float(pos.get("avgPrice", 0))
            pnl = float(pos.get("unrealisedPnl", 0))
            
            print(f"  {symbol} {side} {size:.6f} @ {avg_price:.4f} PnL: {pnl:.4f}")
        
        return active_positions
    except Exception as e:
        print(f"❌ Ошибка получения позиций: {e}")
        return []

# ========== ПРОВЕРКА СПОТ БАЛАНСА ==========
def check_spot_balances(exchange) -> List[Dict]:
    """Проверить спот балансы (не USDT)"""
    try:
        balance = exchange.fetch_balance(params={"type": "unified"})
        spot_balances = []
        
        for currency, amount in balance.get("total", {}).items():
            if currency != "USDT" and float(amount) > 0.001:  # Исключаем пыль
                free_amount = float(balance.get("free", {}).get(currency, 0))
                spot_balances.append({
                    "currency": currency,
                    "total": float(amount),
                    "free": free_amount
                })
        
        print(f"\n🪙 Спот балансы (не USDT): {len(spot_balances)}")
        for bal in spot_balances:
            print(f"  {bal['currency']}: {bal['total']:.6f} (free: {bal['free']:.6f})")
        
        return spot_balances
    except Exception as e:
        print(f"❌ Ошибка получения спот балансов: {e}")
        return []

# ========== ЗАКРЫТИЕ ПОЗИЦИЙ ==========
def close_position(exchange, position: Dict) -> bool:
    """Закрыть конкретную позицию"""
    try:
        symbol = position.get("symbol", "")
        side = position.get("side", "")
        size = float(position.get("size", 0))
        
        if size <= 0:
            return False
        
        # Инвертируем сторону для закрытия
        close_side = "sell" if side == "buy" else "buy"
        
        print(f"🔄 Закрываю позицию {symbol} {side} {size:.6f} -> {close_side}")
        
        order = exchange.create_order(
            symbol=symbol,
            type="market",
            side=close_side,
            amount=size,
            params={"reduceOnly": True}
        )
        
        print(f"✅ Позиция закрыта: {order.get('id', 'Unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка закрытия позиции {position.get('symbol', 'Unknown')}: {e}")
        return False

# ========== ПРОДАЖА СПОТ АКТИВОВ ==========
def sell_spot_assets(exchange, spot_balances: List[Dict]) -> bool:
    """Продать спот активы за USDT"""
    try:
        for bal in spot_balances:
            if bal["free"] <= 0.001:
                continue
                
            currency = bal["currency"]
            amount = bal["free"]
            
            # Пытаемся продать за USDT
            try:
                symbol = f"{currency}/USDT"
                if symbol in exchange.markets:
                    print(f"🔄 Продаю {amount:.6f} {currency} за USDT")
                    
                    order = exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side="sell",
                        amount=amount
                    )
                    
                    print(f"✅ Продано: {order.get('id', 'Unknown')}")
                    time.sleep(1)  # Задержка между ордерами
                    
            except Exception as e:
                print(f"⚠️ Не удалось продать {currency}: {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ Ошибка продажи спот активов: {e}")
        return False

# ========== ОСНОВНАЯ ЛОГИКА ==========
def main():
    print("🚀 Скрипт освобождения средств от L1 Bot")
    print("=" * 50)
    
    # Создаём клиент
    exchange = create_exchange()
    
    # Проверяем текущее состояние
    balance = check_balance(exchange)
    positions = check_positions(exchange)
    spot_balances = check_spot_balances(exchange)
    
    print("\n" + "=" * 50)
    
    # Если есть активные позиции - закрываем их
    if positions:
        print("🔄 Закрываю все активные позиции...")
        for pos in positions:
            close_position(exchange, pos)
            time.sleep(1)  # Задержка между операциями
    
    # Если есть спот активы - продаём их
    if spot_balances:
        print("🔄 Продаю спот активы за USDT...")
        sell_spot_assets(exchange, spot_balances)
    
    # Финальная проверка баланса
    print("\n" + "=" * 50)
    print("📊 Финальная проверка баланса:")
    final_balance = check_balance(exchange)
    
    free_usdt = final_balance.get("free", {}).get("USDT", 0)
    if free_usdt > 10:
        print(f"✅ Успешно освобождено {free_usdt:.2f} USDT!")
        print("Теперь можно запускать Grid Trading Bot")
    else:
        print("⚠️ USDT всё ещё недостаточно для Grid Bot")
        print("Возможно, нужно пополнить аккаунт")

if __name__ == "__main__":
    main()
