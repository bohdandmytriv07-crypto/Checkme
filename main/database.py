# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

DB_NAME = "cache.db"

def init_db():
    """Створює таблицю з лічильником перевірок"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS url_cache (
                url TEXT PRIMARY KEY,
                status TEXT,
                title TEXT,
                message TEXT,
                last_updated TIMESTAMP,
                check_count INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

def get_cached_info(url):
    """Повертає всю інформацію про посилання, включаючи кількість перевірок"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, title, message, check_count FROM url_cache WHERE url=?", (url,))
        row = cursor.fetchone()
        if row:
            return {
                "status": row[0],
                "title": row[1],
                "message": row[2],
                "check_count": row[3]
            }
        return None

def save_or_update_cache(url, result):
    """
    Якщо посилання нове — створює запис (count=1).
    Якщо старе — оновлює дані та збільшує лічильник на +1.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Спочатку перевіримо, чи є вже такий запис
        cursor.execute("SELECT check_count FROM url_cache WHERE url=?", (url,))
        row = cursor.fetchone()
        
        if row is None:
            # Нове посилання
            cursor.execute('''
                INSERT INTO url_cache (url, status, title, message, last_updated, check_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (url, result["status"], result["title"], result["message"], 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1))
        else:
           
            new_count = row[0] + 1
            cursor.execute('''
                UPDATE url_cache 
                SET status=?, title=?, message=?, last_updated=?, check_count=?
                WHERE url=?
            ''', (result["status"], result["title"], result["message"], 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), new_count, url))
        conn.commit()