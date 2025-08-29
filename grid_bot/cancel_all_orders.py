#!/usr/bin/env python3
"""
Скрипт для отмены всех активных ордеров на Bybit
Освобождает заблокированные средства для новой сетки
"""

import os
import ccxt
from dotenv import load_dotenv
import time

def cancel_all_orders():
    """Отменить все активные ордера на Bybit"""
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Получаем API ключи
    api_key = os.environ.get("BYBIT_API_KEY")
    api_secret = os.environ.get("BYBIT_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ API ключи не найдены в .env файле")
        return
    
    try:
        # Инициализируем подключение к Bybit
        exchange = ccxt.bybit({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "unified"}
        })
        
        print("🔗 Подключение к Bybit...")
        exchange.load_markets()
        
        # Получаем все активные ордера
        print("📋 Получение активных ордеров...")
        open_orders = exchange.fetch_open_orders()
        
        if not open_orders:
            print("✅ Активных ордеров не найдено")
            return
        
        print(f"📊 Найдено {len(open_orders)} активных ордеров:")
        
        # Показываем информацию об ордерах
        total_value = 0
        for order in open_orders:
            symbol = order['symbol']
            side = order['side']
            amount = order['amount']
            price = order['price']
            order_id = order['id']
            
            # Рассчитываем стоимость ордера
            if side == 'buy':
                value = amount * price
            else:
                value = amount * price
            
            total_value += value
            
            print(f"   {symbol} {side} {amount:.2f} @ {price:.6f} = {value:.2f} USDT (ID: {order_id})")
        
        print(f"💰 Общая заблокированная сумма: {total_value:.2f} USDT")
        
        # Спрашиваем подтверждение
        confirm = input("\n❓ Отменить все ордера? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Отмена операции")
            return
        
        # Отменяем все ордера
        print("🔄 Отмена ордеров...")
        cancelled_count = 0
        
        for order in open_orders:
            try:
                result = exchange.cancel_order(order['id'], order['symbol'])
                if result:
                    cancelled_count += 1
                    print(f"✅ Отменён ордер {order['symbol']} {order['side']} {order['amount']:.2f}")
                time.sleep(0.1)  # Задержка между запросами
            except Exception as e:
                print(f"❌ Ошибка отмены ордера {order['id']}: {e}")
        
        print(f"✅ Отменено {cancelled_count} из {len(open_orders)} ордеров")
        print(f"💰 Освобождено средств: {total_value:.2f} USDT")
        
        # Проверяем новый баланс
        print("\n💰 Проверка нового баланса...")
        balance = exchange.fetch_balance()
        if 'USDT' in balance:
            free_usdt = balance['USDT']['free']
            print(f"✅ Свободный USDT: {free_usdt:.2f}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    cancel_all_orders()
