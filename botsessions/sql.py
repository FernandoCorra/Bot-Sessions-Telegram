# -*- coding: latin1 -*-

import sqlite3


# Conex�o com o banco de dados SQLite para usu�rios
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


# Fun��o para inserir informa��es sobre a compra no banco de dados
def insert_purchase(chat_id, sessions):
    # Converte a lista de sessions em uma �nica string separada por v�rgulas
    sessions_str = ", ".join(sessions)
    
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO compras (chat_id, sessions) VALUES (?, ?)", (chat_id, sessions_str))
    conn.commit()
    conn.close()

# Fun��o para obter as sessions compradas por um chat_id
def get_purchased_sessions(chat_id):
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sessions FROM compras WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


# Fun��o para obter o saldo do usu�rio do banco de dados
def get_user_balance(chat_id):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    current_balance = users_cursor.fetchone()[0]
    return current_balance


# Fun��o para atualizar o saldo do usu�rio no banco de dados
def update_user_balance(chat_id, new_balance):
    users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
    users_conn.commit()
    
