import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from chavepix import verify_payment , get_payment
from aiogram.dispatcher import FSMContext
import os
import random
from aiogram.types import InputFile
from aiogram.utils import executor
import zipfile
import asyncio

with open('tokenbot.txt', 'r') as f:
    BOT_TOKEN = f.read().strip()
# Substitua 'YOUR_BOT_TOKEN' pelo token do seu bot fornecido pelo BotFather do Telegram
bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot)

# Configuração de log para monitorar as interações do bot
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# Conexão com o banco de dados SQLite para usuários
users_conn = sqlite3.connect('users.db')
users_cursor = users_conn.cursor()
users_cursor.execute('''CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, saldo REAL, selected_country TEXT)''')
users_conn.commit()


# Dicionário para armazenar o estado do usuário ao depositar saldo
deposit_state = {}
user_state = {}

# Função para enviar os arquivos em um ZIP
async def send_files_in_zip(chat_id, file_paths):
    with zipfile.ZipFile('sessions.zip', 'w') as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))
    
    with open('sessions.zip', 'rb') as zip_file:
        await bot.send_document(chat_id, zip_file)

    os.remove('sessions.zip')

@dp.callback_query_handler(lambda c: c.data == "preços")
async def send_price_table(callback_query: types.CallbackQuery):
    price_table = (
        "Tabela de Preços:\n"
        "1 session - $3,10\n"
        "10 sessions (cada) - $3,00\n"
    )
    await bot.send_message(callback_query.from_user.id, price_table)




@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    # Verifica se o usuário já está no banco de dados de usuários
    chat_id = message.from_user.id
    users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = users_cursor.fetchone()

    if user is None:
        # Adiciona o usuário ao banco de dados de usuários com saldo inicial de 0.0
        users_cursor.execute("INSERT INTO users (chat_id, saldo) VALUES (?, ?)", (chat_id, 0.0))
        users_conn.commit()

    # Obtém o saldo do usuário
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    user_saldo = users_cursor.fetchone()[0]
    
    # Criando a mensagem com o texto
    message_text = (
        f"Olá, {message.from_user.first_name}!\n"
        "Seja bem-vindo ao bot de envio de sessions.\n"
        "Eu sou um bot que facilita a compra de sessions.\n\n"
        f"Saldo do usuário: R${user_saldo:.2f}\n"
    )

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("RECARREGAR SALDO 💸", callback_data="recarregar"),
        types.InlineKeyboardButton("TABELA DE PREÇOS", callback_data="preços"),
        types.InlineKeyboardButton("COMPRAR SESSIONS 📲", callback_data="comprar_sessions"),
        types.InlineKeyboardButton("VER SALDO 💰", callback_data="view_balance"),
        types.InlineKeyboardButton("SUPORTE 🤖", callback_data="suporte")
    )
    
    # Enviando a mensagem com o texto e os botões
    with open("bot.png", "rb") as img:
        await message.reply_photo(photo=InputFile(img), caption=message_text, reply_markup=buttons1)
    
@dp.message_handler(commands=['saldo'])
async def activate_balance_button(message: types.Message):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (message.from_user.id,))
    saldo = users_cursor.fetchone()
    options_text = f"👤 Dados do usuário\n🆔 | ID: {message.from_user.id}\n📛 | Nome: {message.from_user.first_name}\n📧 | Username: {message.from_user.username}\n💰 | Saldo: R${saldo[0]}"

    await bot.send_message(message.from_user.id, options_text)
    
@dp.message_handler(commands=['recarregar'])
async def ask_for_deposit_amount(message: types.Message):
    await message.reply("Quanto você deseja depositar?")
    
    # Define o estado do usuário para aguardar o valor do depósito
    deposit_state[message.from_user.id] = "awaiting_deposit_value"
    

@dp.callback_query_handler(lambda c: c.data == "suporte")
async def suporte(callback_query: types.CallbackQuery):
    optiontexto = "Suporte: Para solicitar suporte , por favor entre em contato com @suporteSMSBARATO 📲"
    await bot.send_message(callback_query.from_user.id, optiontexto)

@dp.callback_query_handler(lambda c: c.data == "suporte")
async def suporte(callback_query: types.CallbackQuery):
    optiontexto = "Suporte: Para solicitar suporte , por favor entre em contato com @suporteSMSBARATO 📲"
    await bot.send_message(callback_query.from_user.id, optiontexto)



@dp.callback_query_handler(lambda c: c.data == "view_balance")
async def view_balance(callback_query: types.CallbackQuery):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (callback_query.from_user.id,))
    saldo = users_cursor.fetchone()
    options_text = f"👤 Dados do usuário\n🆔 | ID: {callback_query.from_user.id}\n📛 | Nome: {callback_query.from_user.first_name}\n📧 | Username: {callback_query.from_user.username}\n💰 | Saldo: R${saldo[0]}"

    await bot.send_message(callback_query.from_user.id, options_text)


@dp.callback_query_handler(lambda c: c.data == "recarregar")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id, "Quanto você deseja depositar?")
    await bot.send_message(callback_query.from_user.id, "Por favor, digite o valor desejado do depósito:")

    # Define o estado do usuário para aguardar o valor do depósito
    deposit_state[callback_query.from_user.id] = "awaiting_deposit_value"

@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "awaiting_deposit_value")
async def handle_deposit_value(message: types.Message):
    try:
        deposit_value = float(message.text)
        chat_id = message.from_user.id

        # Chama a função get_payment para gerar a chave PIX e ID do pagamento
        chave_pix, id_pagamento = get_payment(deposit_value, "sms")

        # Envia a chave PIX para o usuário
        await bot.send_message(chat_id, f"Chave PIX: {chave_pix}")

        # Adiciona o botão "PIX ENVIADO" após a chave PIX
        buttons = types.InlineKeyboardMarkup(row_width=1)
        buttons.add(types.InlineKeyboardButton("PIX ENVIADO", callback_data=f"verify_{id_pagamento}"))
        await bot.send_message(chat_id, "Por favor, clique em 'PIX ENVIADO' após enviar o PIX.", reply_markup=buttons)

        # Armazena o ID do pagamento na sessão do usuário
        deposit_state[chat_id] = (id_pagamento, deposit_value)
    except ValueError:
        await bot.send_message(chat_id, "Por favor, digite um valor numérico válido.")




@dp.callback_query_handler(lambda c: c.data.startswith("verify_"))
async def verify_deposit(callback_query: types.CallbackQuery):
    chat_id = callback_query.from_user.id
    id_pagamento = callback_query.data[len("verify_"):]

    # Chama a função verify_payment para verificar o pagamento
    payment_verified = verify_payment(id_pagamento)

    if payment_verified:
        deposit_data = deposit_state.get(chat_id)
        if deposit_data:
            id_pagamento, deposit_value = deposit_data

            # Atualiza o saldo do usuário no banco de dados
            users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
            current_balance = users_cursor.fetchone()[0]
            print(current_balance)
            new_balance = float(current_balance) + deposit_value

            users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
            users_conn.commit()

            # Envia a mensagem de saldo atualizado
            await bot.send_message(chat_id, f"Seu saldo foi atualizado. Novo saldo: R${new_balance:.2f}")
            del deposit_state[chat_id]  # Remove o estado de depósito do usuário após a conclusão
        else:
            await bot.send_message(chat_id, "Erro interno ao processar o depósito. Por favor, tente novamente.")
    else:
        await bot.send_message(chat_id, "Pagamento não verificado. Por favor, verifique o PIX e tente novamente.")

# Callback handler para comprar sessions
@dp.callback_query_handler(lambda c: c.data == "comprar_sessions")
async def ask_quantity(callback_query: types.CallbackQuery):
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    
    if available_sessions == 0:
        await bot.send_message(callback_query.from_user.id, "Estamos sem estoque no momento. Quando abastecermos, avisaremos.")
    else:
        await bot.send_message(callback_query.from_user.id, f"Quantas sessions deseja comprar? (Disponíveis: {available_sessions})")

        # Define o estado do usuário para aguardar a quantidade de sessions
        user_state[callback_query.from_user.id] = "awaiting_session_quantity"


# Tratando a quantidade informada pelo usuário
@dp.message_handler(lambda message: user_state.get(message.from_user.id) == "awaiting_session_quantity" and message.text.isdigit())
async def process_quantity(message: types.Message):
    quantity = int(message.text)
    session_price = 3.10  # Preço por session
    total_price = session_price * quantity

    chat_id = message.from_user.id
    user_balance = get_user_balance(chat_id)  # Função para obter o saldo do usuário do banco de dados

    if user_balance >= total_price:
        # Atualiza o saldo do usuário no banco de dados
        new_balance = user_balance - total_price
        update_user_balance(chat_id, new_balance)  # Função para atualizar o saldo do usuário no banco de dados

        session_files = os.listdir("arquivos")
        random.shuffle(session_files)
        session_files = session_files[:quantity]

        session_paths = [os.path.join("arquivos", session_file) for session_file in session_files]

        await send_files_in_zip(chat_id, session_paths)

        # Mover os arquivos para a pasta "enviadas"
        for session_path in session_paths:
            os.rename(session_path, os.path.join("enviadas", os.path.basename(session_path)))

        await bot.send_message(chat_id, f"Foram enviadas {quantity} sessions. Seu saldo atualizado: R${new_balance:.2f}")
    else:
        await bot.send_message(chat_id, "Saldo insuficiente para a compra das sessions.")

    del user_state[chat_id]  # Remove o estado de aguardar quantidade do usuário


# Função para obter o saldo do usuário do banco de dados
def get_user_balance(chat_id):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    current_balance = users_cursor.fetchone()[0]
    return current_balance


# Função para atualizar o saldo do usuário no banco de dados
def update_user_balance(chat_id, new_balance):
    users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
    users_conn.commit()


if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)