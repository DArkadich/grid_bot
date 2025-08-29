#!/usr/bin/env python3
"""
Скрипт для очистки базы данных Grid Bot
Удаляет лишние уровни, оставляя только актуальные сетки
"""

import sqlite3
import os

def clean_database():
    """Очистить базу данных от лишних уровней"""
    db_path = "grid_data.db"
    
    if not os.path.exists(db_path):
        print("База данных не найдена")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем статистику
        cursor.execute("SELECT COUNT(*) FROM grids")
        total_levels = cursor.fetchone()[0]
        
        cursor.execute("SELECT DISTINCT symbol FROM grids")
        symbols = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Текущая статистика:")
        print(f"   Всего уровней: {total_levels}")
        print(f"   Символы: {', '.join(symbols)}")
        
        # Показываем количество уровней по символам
        for symbol in symbols:
            cursor.execute("SELECT COUNT(*) FROM grids WHERE symbol = ?", (symbol,))
            count = cursor.fetchone()[0]
            print(f"   {symbol}: {count} уровней")
        
        print(f"\n🧹 Очистка базы данных...")
        
        # Удаляем все уровни
        cursor.execute("DELETE FROM grids")
        deleted_count = cursor.rowcount
        
        # Удаляем все сделки
        cursor.execute("DELETE FROM trades")
        deleted_trades = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ Очистка завершена:")
        print(f"   Удалено уровней: {deleted_count}")
        print(f"   Удалено сделок: {deleted_trades}")
        print(f"   База данных готова для новых сеток")
        
    except Exception as e:
        print(f"❌ Ошибка очистки: {e}")

if __name__ == "__main__":
    clean_database()
