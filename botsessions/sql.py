# -*- coding: utf-8 -*-

import sqlite3, os

if not os.path.exists('vendidas'):
    os.makedirs('vendidas', exist_ok=True)
if not os.path.exists('arquivos'):
    os.makedirs('arquivos', exist_ok=True)

# Conexão com o banco de dados SQLite para usuários
users_conn = sqlite3.connect('users.db')
users_cursor = users_conn.cursor()
users_cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY, 
                saldo REAL, 
                selected_country TEXT
            )
        ''')
users_conn.commit()

conn = sqlite3.connect('vendidas.db')
cursor = conn.cursor()
cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            chat_id INTEGER,
            sessions TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
conn.commit()
conn.close()


# Função para inserir informações sobre a compra no banco de dados
def insert_purchase(chat_id, sessions):
    # Converte a lista de sessions em uma única string separada por vírgulas
    sessions_str = ", ".join(sessions)
    
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO compras (chat_id, sessions) VALUES (?, ?)", (chat_id, sessions_str))
    conn.commit()
    conn.close()

# Função para obter as sessions compradas por um chat_id
def get_purchased_sessions(chat_id):
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sessions FROM compras WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


# Função para obter o saldo do usuário do banco de dados
def get_user_balance(chat_id):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    current_balance = users_cursor.fetchone()[0]
    return current_balance


# Função para atualizar o saldo do usuário no banco de dados
def update_user_balance(chat_id, new_balance):
    users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
    users_conn.commit()
    
