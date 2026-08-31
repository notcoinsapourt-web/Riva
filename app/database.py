import sqlite3

DB_NAME = 'persian_shop.db'

def get_connection():
    return sqlite3.connect(DB_NAME)
