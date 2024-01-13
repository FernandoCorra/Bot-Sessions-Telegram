import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from chavepix import verify_payment , get_payment
from aiogram.dispatcher import FSMContext
import os
from aiogram.types import ParseMode
import random
from aiogram.types import InputFile
from aiogram.utils import executor
import zipfile
import asyncio

IDADM = 2039445723
IDGRUPOCOMPRA = -1001577837817
IDGRUPODEPOSITO = -1001577837817
MINIMODEPOSITO = 1
MENORQUE10 = 4
MAIORQUE10MENORQUE50 = 3.8
MAIORQUE50MENORQUE100 = 3.6
MAIORQUE100 = 3.2

with open('tokenbot.txt', 'r') as f:
    BOT_TOKEN = f.read().strip()
# Substitua 'YOUR_BOT_TOKEN' pelo token do seu bot fornecido pelo BotFather do Telegram
bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot)

# ConfiguraÃ§Ã£o de log para monitorar as interaÃ§Ãµes do bot
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# ConexÃ£o com o banco de dados SQLite para usuÃ¡rios
users_conn = sqlite3.connect('users.db')
users_cursor = users_conn.cursor()
users_cursor.execute('''CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, saldo REAL, selected_country TEXT)''')
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


# DicionÃ¡rio para armazenar o estado do usuÃ¡rio ao depositar saldo
deposit_state = {}
user_state = {}
valoradd = {}
# FunÃ§Ã£o para enviar os arquivos em um ZIP
async def send_files_in_zip(chat_id, file_paths):
    with zipfile.ZipFile('sessions.zip', 'w') as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))
    
    with open('sessions.zip', 'rb') as zip_file:
        await bot.send_document(chat_id, zip_file)

    os.remove('sessions.zip')

idstart = {}
voltarid = {}

# FunÃ§Ã£o para inserir informaÃ§Ãµes sobre a compra no banco de dados
def insert_purchase(chat_id, sessions):
    # Converte a lista de sessions em uma Ãºnica string separada por vÃ­rgulas
    sessions_str = ", ".join(sessions)
    
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO compras (chat_id, sessions) VALUES (?, ?)", (chat_id, sessions_str))
    conn.commit()
    conn.close()

# FunÃ§Ã£o para obter as sessions compradas por um chat_id
def get_purchased_sessions(chat_id):
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sessions FROM compras WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return None


@dp.callback_query_handler(lambda c: c.data == "preÃ§os")
async def send_price_table(callback_query: types.CallbackQuery):
    price_table = f"""
    ðŸ“‹ Tabelas de valores :

ðŸ“Š Ao comprar a partir de: 1   
ðŸ’µ O valor por unidade Ã©: R$ {MENORQUE10}

ðŸ“Š Ao comprar a partir de: 10   
ðŸ’µ O valor por unidade Ã©: R$ {MAIORQUE10MENORQUE50}

ðŸ“Š Ao comprar a partir de: 50   
ðŸ’µ O valor por unidade Ã©: R$ {MAIORQUE50MENORQUE100}

ðŸ“Š Ao comprar a partir de: 100   
ðŸ’µ O valor por unidade Ã©: R$ {MAIORQUE100}

Boas compras ðŸ˜Š
    """

    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    msg = await bot.edit_message_text(chat_id=callback_query.from_user.id,text=price_table,message_id=b,reply_markup=buttons1)
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}




@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    # Verifica se o usuÃ¡rio jÃ¡ estÃ¡ no banco de dados de usuÃ¡rios
    chat_id = message.from_user.id
    users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = users_cursor.fetchone()

    if user is None:
        # Adiciona o usuÃ¡rio ao banco de dados de usuÃ¡rios com saldo inicial de 0.0
        users_cursor.execute("INSERT INTO users (chat_id, saldo) VALUES (?, ?)", (chat_id, 0.0))
        users_conn.commit()

    # ObtÃ©m o saldo do usuÃ¡rio
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    user_saldo = users_cursor.fetchone()[0]
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    # Criando a mensagem com o texto
    message_text = f"""
    Bom Dia, {message.from_user.first_name} Como posso te ajudar?
Temos atualmente {available_sessions} sessÃµes disponÃ­veis

    """

    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("ðŸ“² Exibir perfil", callback_data="view_balance"),
        types.InlineKeyboardButton("ðŸ“Š Tabela de valores", callback_data="preÃ§os"),
        types.InlineKeyboardButton("ðŸ“¦ Comprar session", callback_data="comprar_sessions"),
        types.InlineKeyboardButton("ðŸ¦ Adicionar saldo", callback_data="recarregar"),
        types.InlineKeyboardButton("ðŸ¤– Bot Leads", callback_data="leads"),
        types.InlineKeyboardButton("ðŸ§‘ Preciso de ajuda", callback_data="suporte"),
    )
    
    # Enviando a mensagem com o texto e os botÃµes
    with open("bot.png", "rb") as img:
        startid = await bot.send_message(chat_id, message_text, reply_markup=buttons1)
    
    modificar = startid.message_id
    idstart[chat_id] = {'message_id1': modificar}

    

@dp.callback_query_handler(lambda c: c.data == "suporte")
async def suporte(callback_query: types.CallbackQuery):
    optiontexto = "Suporte: Para solicitar suporte , por favor entre em contato com @suporteSMSBARATO ðŸ“²"
    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    msg = await bot.edit_message_text(chat_id=callback_query.from_user.id,text=optiontexto,message_id=b,reply_markup=buttons1)
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}

@dp.message_handler(commands=['perfil'])
async def perfil(message: types.Message):

    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (message.from_user.id,))
    saldo = users_cursor.fetchone()
    saldo1 = round(saldo[0],2)
    a = idstart.get(message.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("Exibir Contrato ðŸ“", callback_data="contris"),
        types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar")
    )
    options_text = f"ðŸ‘¤ Dados do usuÃ¡rio\nðŸ†” | ID: {message.from_user.id}\nðŸ“› | Nome: {message.from_user.first_name}\nðŸ“§ | Username: {message.from_user.username}\nðŸ’° | Saldo: R${saldo1}"
    msg = await bot.send_message(chat_id=message.from_user.id,text=options_text,reply_markup=buttons1)
    modificar = msg.message_id
    voltarid[message.from_user.id] = {'message_id1': modificar}

@dp.message_handler(commands=['comprar'])
async def comprar(message: types.Message):
    aldo = compra.get(message.from_user.id, {})
    valor = aldo.get('saldo')
    valorinicial = 1
    if valor == None:
        compra[message.from_user.id] = {'saldo': valorinicial}
        aldo = compra.get(message.from_user.id, {})
        valor = aldo.get('saldo')
    else:
        aldo = compra.get(message.from_user.id, {})
        valor = aldo.get('saldo')
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    buttons1 = types.InlineKeyboardMarkup(row_width=2)
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    if available_sessions == 0:
        await bot.send_message(chat_id=message.from_user.id, text="Estamos sem estoque no momento. Quando abastecermos, avisaremos.",reply_markup=buttons1)
        
    else:
        buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
        buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
        certo1 = int(valor)
        pix = f"finalizar_{certo1}"
        buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
        buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
        await bot.send_message(chat_id=message.from_user.id, text=f"ðŸ“ŸTotal escolhido : {valor} (DisponÃ­veis: {available_sessions})",reply_markup=buttons1)




@dp.message_handler(commands=['ajuda','termos'])
async def helpp(message: types.Message):
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar")
    )
    text = """
    ðŸ“„ TERMOS DE USO ðŸ“–

1 - Todas as session sÃ£o verificadas antes de serem inseridas no bot, garantindo que estÃ£o ativas.

2 - A session Ã© dependente de terceiros, especificamente do Telegram. Como tal, nÃ£o temos controle ou garantias sobre suas polÃ­ticas e funcionamento.

3 - Garantimos a unicidade de cada session, assim vocÃª nunca receberÃ¡ uma session duplicada.

4 - PossuÃ­mos um sistema de seguranÃ§a anti-fraude que assegura que ninguÃ©m mais receberÃ¡ uma sessÃ£o que vocÃª jÃ¡ adquiriu.

5 - ApÃ³s a compra, a responsabilidade sobre a session nÃ£o Ã© mais nossa. Como indicado no item 2, as sessÃµes dependem inteiramente do Telegram e nÃ£o podemos nos responsabilizar por eventuais problemas.

6 - Caso a sessÃ£o seja banida apÃ³s a compra, nÃ£o oferecemos reembolso ou substituiÃ§Ã£o.

7 - VocÃª serÃ¡ prontamente notificado sobre qualquer atualizaÃ§Ã£o em seu saldo.

8 - InfracÃµes ou violaÃ§Ãµes de nossas regras resultarÃ£o em banimento.

9 -  Clicando em Adicionar Saldo voce declara estar de acordo com nossos termos de uso .

10 - PreÃ§os referentes a tabela de valores podem ser alterados a qualquer momento sem aviso prÃ©vio .

11 - Esses termos podem ser alterado a qualquer momento sem aviso prÃ©vio .
    """
    await bot.send_message(chat_id=message.from_user.id,text=text,reply_markup=buttons1)

@dp.message_handler(commands=['recarregar'])
async def refill(message: types.Message):
    iddstart = idstart.get(message.from_user.id, {})
    idstartt = iddstart.get('message_id1')
    aldo = valoradd.get(message.from_user.id, {})
    valor = aldo.get('saldo')
    valorinicial = 1
    if valor == None:
        valoradd[message.from_user.id] = {'saldo': valorinicial}
        aldo = valoradd.get(message.from_user.id, {})
        valor = aldo.get('saldo')
    else:
        aldo = valoradd.get(message.from_user.id, {})
        valor = aldo.get('saldo')

    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {valor}
    """
    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    pix = f"gerar_{valor}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))

    await  bot.send_message(chat_id=message.from_user.id,text=text,reply_markup=buttons1)

@dp.callback_query_handler(lambda c: c.data == "contris")
async def view_balance(callback_query: types.CallbackQuery):
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar")
    )
    text = """
    ðŸ“„ TERMOS DE USO ðŸ“–

1 - Todas as session sÃ£o verificadas antes de serem inseridas no bot, garantindo que estÃ£o ativas.

2 - A session Ã© dependente de terceiros, especificamente do Telegram. Como tal, nÃ£o temos controle ou garantias sobre suas polÃ­ticas e funcionamento.

3 - Garantimos a unicidade de cada session, assim vocÃª nunca receberÃ¡ uma session duplicada.

4 - PossuÃ­mos um sistema de seguranÃ§a anti-fraude que assegura que ninguÃ©m mais receberÃ¡ uma sessÃ£o que vocÃª jÃ¡ adquiriu.

5 - ApÃ³s a compra, a responsabilidade sobre a session nÃ£o Ã© mais nossa. Como indicado no item 2, as sessÃµes dependem inteiramente do Telegram e nÃ£o podemos nos responsabilizar por eventuais problemas.

6 - Caso a sessÃ£o seja banida apÃ³s a compra, nÃ£o oferecemos reembolso ou substituiÃ§Ã£o.

7 - VocÃª serÃ¡ prontamente notificado sobre qualquer atualizaÃ§Ã£o em seu saldo.

8 - InfracÃµes ou violaÃ§Ãµes de nossas regras resultarÃ£o em banimento.

9 -  Clicando em Adicionar Saldo voce declara estar de acordo com nossos termos de uso .

10 - PreÃ§os referentes a tabela de valores podem ser alterados a qualquer momento sem aviso prÃ©vio .

11 - Esses termos podem ser alterado a qualquer momento sem aviso prÃ©vio .
    """
    await bot.edit_message_text(chat_id=callback_query.from_user.id,text=text,message_id=callback_query.message.message_id,reply_markup=buttons1)

@dp.callback_query_handler(lambda c: c.data == "view_balance")
async def view_balance(callback_query: types.CallbackQuery):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (callback_query.from_user.id,))
    saldo = users_cursor.fetchone()
    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("Exibir Contrato ðŸ“", callback_data="contris"),
        types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar")
    )
    options_text = f"ðŸ‘¤ Dados do usuÃ¡rio\nðŸ†” | ID: {callback_query.from_user.id}\nðŸ“› | Nome: {callback_query.from_user.first_name}\nðŸ“§ | Username: {callback_query.from_user.username}\nðŸ’° | Saldo: R${saldo[0]}"
    msg = await bot.edit_message_text(chat_id=callback_query.from_user.id,text=options_text,message_id=b,reply_markup=buttons1)
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}

@dp.callback_query_handler(lambda c: c.data == "leads")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    text = """
    ðŸ”µ SE VOCÃŠ ESTÃ PROCURANDO UM ROBÃ” DE ENGAJAMENTO PARA TELEGRAM MELHOR QUE O SEU ATUAL.....â¤µï¸

ðŸ¤– Apresento a vocÃªs o robÃ´ PRO !

â¤ï¸ Porque indicamos ele ? 

â­ï¸ ApÃ³s varios testes com mais de 20 robÃ´s e bots do telegram de engajamento em massa, chegamos a conclusÃ£o que o software que teve a maior durabilidade com o uso da session Ã© o robÃ´ PRO !

âœ…Ele utiliza uma otima proxy residencial e hash bem antiga, aumentando assim suas resistencias e durabilidades de suas session.

âœ”ï¸ Para saber mais e conhecer o ROBÃ” PRO , clique no link abaixo ðŸ‘‡
    """
    buttons1 = types.InlineKeyboardMarkup(row_width=1)
    buttons1.add(
        types.InlineKeyboardButton("RobÃ´ Leads ðŸ¤–", url="https://app.monetizze.com.br/r/ADM23063593"),
        types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar")
    
    )
    await bot.edit_message_text(chat_id=callback_query.from_user.id,text=text,message_id=callback_query.message.message_id,reply_markup=buttons1)


@dp.callback_query_handler(lambda query: query.data == "voltar")
async def view_balance(callback_query: types.CallbackQuery):
    chat_id = callback_query.from_user.id
    users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = users_cursor.fetchone()

    if user is None:
        # Adiciona o usuÃ¡rio ao banco de dados de usuÃ¡rios com saldo inicial de 0.0
        users_cursor.execute("INSERT INTO users (chat_id, saldo) VALUES (?, ?)", (chat_id, 0.0))
        users_conn.commit()

    # ObtÃ©m o saldo do usuÃ¡rio
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    user_saldo = users_cursor.fetchone()[0]
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    # Criando a mensagem com o texto
    message_text = f"""
    Bom Dia, {callback_query.from_user.first_name} Como posso te ajudar?
Temos atualmente {available_sessions} sessÃµes disponÃ­veis

    """

    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("ðŸ“² Exibir perfil", callback_data="view_balance"),
        types.InlineKeyboardButton("ðŸ“Š Tabela de valores", callback_data="preÃ§os"),
        types.InlineKeyboardButton("ðŸ“¦ Comprar session", callback_data="comprar_sessions"),
        types.InlineKeyboardButton("ðŸ¦ Adicionar saldo", callback_data="recarregar"),
        types.InlineKeyboardButton("ðŸ¤– Bot Leads", callback_data="leads"),
        types.InlineKeyboardButton("ðŸ§‘ Preciso de ajuda", callback_data="suporte")
    )
    a = voltarid.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    msg = await bot.edit_message_text(chat_id=callback_query.from_user.id,text=message_text,message_id=callback_query.message.message_id,reply_markup=buttons1)

@dp.callback_query_handler(lambda c: c.data == "baixo100")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 100
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto100")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 100
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo5")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 5
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto5")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 5
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo1")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 1
    if certo < MINIMODEPOSITO :
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto1")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 1
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    certo1 = int(certo)
    pix = f"gerar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "recarregar")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    iddstart = idstart.get(callback_query.from_user.id, {})
    idstartt = iddstart.get('message_id1')
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    valorinicial = 1
    if valor == None:
        valoradd[callback_query.from_user.id] = {'saldo': valorinicial}
        aldo = valoradd.get(callback_query.from_user.id, {})
        valor = aldo.get('saldo')
    else:
        aldo = valoradd.get(callback_query.from_user.id, {})
        valor = aldo.get('saldo')

    text = f"""     ðŸ’  PIX ðŸ’     \n ðŸ’µ Valor: R$ {valor}
    """
    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    pix = f"gerar_{valor}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))

    await  bot.edit_message_text(chat_id=callback_query.from_user.id,text=text,message_id=idstartt,reply_markup=buttons1)
    # Define o estado do usuÃ¡rio para aguardar o valor do depÃ³sito


@dp.callback_query_handler(lambda c: c.data.startswith("gerar_"))
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
        deposit_value1 = callback_query.data[6:]
        deposit_value = int(deposit_value1) 
        chat_id = callback_query.from_user.id
        # Chama a funÃ§Ã£o get_payment para gerar a chave PIX e ID do pagamento
        chave_pix, id_pagamento = get_payment(deposit_value, "sms")

        text = f"""
âœ… Pagamento gerado 

âš ï¸ EstÃ¡ com problemas no pagamento? Tente pagar meio de outro banco!

ðŸ’µ Valor: R$ {deposit_value}
â± Prazo de expiraÃ§Ã£o: 5 Minutos

ðŸ’  Pix Copia e Cola: 

`{chave_pix}`

ðŸ’¡ Dica: Clique no cÃ³digo acima para copiÃ¡-lo.

ApÃ³s o pagamento aguarde atÃ© o prazo de expiraÃ§Ã£o para que o seu saldo seja creditado automaticamente.
"""
        # Envia a chave PIX para o usuÃ¡rio
        await  bot.edit_message_text(chat_id=callback_query.from_user.id,text=text,message_id=callback_query.message.message_id,parse_mode="Markdown")

        user_name = callback_query.from_user.id 
        IDGRUPO = IDGRUPODEPOSITO
        a = 0
        c = 1
        # Chama a funÃ§Ã£o verify_payment para verificar o pagamento
        payment_verified = await verify_payment(id_pagamento)
        maxtemps = 15
        for i in range(maxtemps):
          c = 0
          await asyncio.sleep(5)
          payment_verified = await verify_payment(id_pagamento)
          if payment_verified == True:
            # Atualiza o saldo do usuÃ¡rio no banco de dados
            users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
            current_balance = users_cursor.fetchone()[0]
            new_balance = float(current_balance) + float(deposit_value)

            users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
            users_conn.commit()

            text = f"""
           ðŸŸ¢Seu deposito de {deposit_value} foi adicionado!
           ðŸŸ¢Seu saldo atual Ã© R${new_balance:.2f}
            """
            a = 1
            buttons1 = types.InlineKeyboardMarkup(row_width=2)
            buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
            await  bot.edit_message_text(chat_id=callback_query.from_user.id,text=text,message_id=callback_query.message.message_id,reply_markup=buttons1)
            abouttext = f"""
            âœ…Saldo Adicionado por {user_name}ðŸ”¥ !
ðŸ“²ID: {chat_id}
ðŸ“²USERNAME: @{callback_query.from_user.username}
ðŸ›’Valor: {deposit_value}
            """
            await bot.send_message(IDGRUPO, abouttext)
            break  # Remove o estado de depÃ³sito do usuÃ¡rio apÃ³s a conclusÃ£o
        
        if a == 0 and c == 0:
            new_text = "ðŸ”´ðŸ”´PIX EXPIRADOðŸ”´ðŸ”´ "
            buttons1 = types.InlineKeyboardMarkup(row_width=2)
            buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
            await bot.edit_message_text(chat_id=chat_id, message_id=callback_query.message.message_id, text=new_text,reply_markup=buttons1)

compra = {}

@dp.callback_query_handler(lambda c: c.data == "alto11")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    valor = aldo.get('saldo')
    certo = valor + 1
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo11")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    certo = valor - 1
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo} DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto51")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 5
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo51")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 5
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto101")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 10
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo101")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 10
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto501")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):

    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 50
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo501")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 50
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "alto1001")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor + 100
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "baixo1001")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 100
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    if certo < 1:
        certo = 1
    compra[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""ðŸ“ŸTotal escolhido : {certo}  DisponÃ­veis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
    certo1 = int(certo)
    pix = f"finalizar_{certo1}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botÃµes existentes
    )

@dp.callback_query_handler(lambda c: c.data == "comprar_sessions")
async def ask_quantity(callback_query: types.CallbackQuery):
    aldo = compra.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    valorinicial = 1
    if valor == None:
        compra[callback_query.from_user.id] = {'saldo': valorinicial}
        aldo = compra.get(callback_query.from_user.id, {})
        valor = aldo.get('saldo')
    else:
        aldo = compra.get(callback_query.from_user.id, {})
        valor = aldo.get('saldo')
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    buttons1 = types.InlineKeyboardMarkup(row_width=2)
    buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
    if available_sessions == 0:
        await bot.edit_message_text(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, text="Estamos sem estoque no momento. Quando abastecermos, avisaremos.",reply_markup=buttons1)
        
    else:
        buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botÃµes por linha
        buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto11"),
        types.InlineKeyboardButton("-1", callback_data="baixo11"),
        types.InlineKeyboardButton("+5", callback_data="alto51"),
        types.InlineKeyboardButton("-5", callback_data="baixo51"),
        types.InlineKeyboardButton("+10", callback_data="alto101"),
        types.InlineKeyboardButton("-10", callback_data="baixo101"),
        types.InlineKeyboardButton("+50", callback_data="alto501"),
        types.InlineKeyboardButton("-50", callback_data="baixo501"),
        types.InlineKeyboardButton("+100", callback_data="alto1001"),
        types.InlineKeyboardButton("-100", callback_data="baixo1001"),
    )
        certo1 = int(valor)
        pix = f"finalizar_{certo1}"
        buttons1.add(types.InlineKeyboardButton("FINALIZAR âœ…", callback_data=pix))
        buttons1.add(types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"))
        await bot.edit_message_text(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, text=f"ðŸ“ŸTotal escolhido : {valor} (DisponÃ­veis: {available_sessions})",reply_markup=buttons1)




@dp.callback_query_handler(lambda c: c.data.startswith("finalizar_"))
async def ask_quantity(callback_query: types.CallbackQuery):
    session_files = os.listdir("arquivos")
    disponivel = len(session_files)
    buttons1 = types.InlineKeyboardMarkup(row_width=1)
    buttons1.add(
                types.InlineKeyboardButton("ðŸ¦ Adicionar saldo", callback_data="recarregar"),
                types.InlineKeyboardButton("VOLTAR ðŸ”™", callback_data="voltar"),
                    )
    quant1= callback_query.data[10:]
    quant  = int(quant1)
    if quant > disponivel:
        await bot.edit_message_text(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, text="Quantidade de sessions desejadas nÃ£o disponivel , escolha outra quantidade",reply_markup=buttons1)
    else:
     if quant < 10 :
        session_price = MENORQUE10
     if 10 <= quant < 50:
        session_price = MAIORQUE10MENORQUE50
     if 50 <= quant < 100:
        session_price = MAIORQUE50MENORQUE100
     if  quant >= 100:
        session_price = MAIORQUE100
     total_price = session_price * quant

     chat_id = callback_query.from_user.id
     user_balance = get_user_balance(chat_id)  # FunÃ§Ã£o para obter o saldo do usuÃ¡rio do banco de dados

     if user_balance >= total_price:
        # Atualiza o saldo do usuÃ¡rio no banco de dados
        new_balance = user_balance - total_price
        update_user_balance(chat_id, new_balance)  # FunÃ§Ã£o para atualizar o saldo do usuÃ¡rio no banco de dados

        session_files = os.listdir("arquivos")
        random.shuffle(session_files)
        session_files = session_files[:quant]
        insert_purchase(callback_query.from_user.id,session_files)

        session_paths = [os.path.join("arquivos", session_file) for session_file in session_files]

        await send_files_in_zip(chat_id, session_paths)
        texto = f"""
ID : {callback_query.from_user.id}
        USERNAME : @{callback_query.from_user.username}
        zip dele abaixo
        """
        await bot.send_message(chat_id=IDGRUPOCOMPRA,text=texto)
        await send_files_in_zip(chat_id=IDGRUPOCOMPRA, file_paths=session_paths)
        # Mover os arquivos para a pasta "enviadas"
        for session_path in session_paths:
            os.rename(session_path, os.path.join("enviadas", os.path.basename(session_path)))

        await bot.edit_message_text(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, text=f"Foram enviadas {quant} sessions. Seu saldo atualizado: R${new_balance:.2f}",reply_markup=buttons1)
     else:
        await bot.edit_message_text(chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, text="Saldo insuficiente para a compra das sessions.",reply_markup=buttons1)
 
 # Remove o estado de aguardar quantidade do usuÃ¡rio

# FunÃ§Ã£o para obter o saldo do usuÃ¡rio do banco de dados
def get_user_balance(chat_id):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    current_balance = users_cursor.fetchone()[0]
    return current_balance


# FunÃ§Ã£o para atualizar o saldo do usuÃ¡rio no banco de dados
def update_user_balance(chat_id, new_balance):
    users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
    users_conn.commit()

deposit_state = {}
remove_saldo_state = {}
historico = {}
# FunÃ§Ã£o para iniciar a adiÃ§Ã£o de saldo
@dp.message_handler(commands=['verificarsaldo'])
async def start_addsaldo(message: types.Message):
    opt = """
    Digite o id do usuÃ¡rio que deseja verificar!(âš™ï¸)
    """
    chat_id = message.from_user.id
    if chat_id == IDADM :
        await bot.send_message(chat_id, opt)
            # Conectar ao banco de dados

        deposit_state[message.from_user.id] = "opt"

# Lidar com a entrada do ID do usuÃ¡rio para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "opt")
async def handle_addsaldo_id(message: types.Message):
        idd = message.text
        chat_id = message.from_user.id
        db = sqlite3.connect('users.db')
        cursor = db.cursor()
        idd = message.text
    # Consultar o saldo com base no chat_id
        cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (idd,))
        row = cursor.fetchone()
    # Fechar a conexÃ£o com o banco de dados
        db.close()

        if row:
            await bot.send_message(chat_id, f"Saldo Do ID {idd} Ã©  R${row[0]}")  # Retorna o saldo se encontrado
        else:
            await bot.send_message(chat_id, "UsuÃ¡rio nao encontrado no banco de dados") 

@dp.message_handler(commands=['historico'])
async def start_addsaldo(message: types.Message):
    opt = """
    Digite o id do usuÃ¡rio que deseja verificar historico!(âš™ï¸)
    """
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "roco"

# FunÃ§Ã£o para obter as sessions compradas por um chat_id como uma lista
# FunÃ§Ã£o para obter as sessions compradas por um chat_id como uma lista
def get_purchased_sessions(chat_id):
    conn = sqlite3.connect('vendidas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, sessions FROM compras WHERE chat_id = ?", (chat_id,))
    results = cursor.fetchall()
    conn.close()
    
    purchases = []
    for result in results:
        chat_id, sessions_str = result
        sessions = sessions_str.split(", ")
        purchases.append((chat_id, sessions))
    
    return purchases

# FunÃ§Ã£o para formatar as sessions em uma tabela
def format_sessions_table(purchases):
    formatted_table = "Chat ID   Sessions\n"
    for purchase in purchases:
        chat_id, sessions = purchase
        formatted_table += f"{chat_id}   {', '.join(sessions)}\n"
    return formatted_table

@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "roco")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id
    purchases = get_purchased_sessions(chat_id)
    formatted_table = format_sessions_table(purchases)
    await bot.send_message(chat_id, formatted_table)

    deposit_state.pop(message.from_user.id)

# FunÃ§Ã£o para iniciar a adiÃ§Ã£o de saldo
@dp.message_handler(commands=['remover'])
async def start_addsaldo(message: types.Message):
    opt = """
    Digite o id do usuÃ¡rio que deseja retirar saldo!(âš™ï¸)
    """
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "quicky"

# Lidar com a entrada do ID do usuÃ¡rio para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "quicky")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id

    opt = """
    Digite o valor que quer retirar do saldo dele!(âš™ï¸)
    """
    await bot.send_message(chat_id, opt)

    deposit_state[message.from_user.id] = (idd, "quicky_value")

# Lidar com a entrada do valor para adicionar saldo
@dp.message_handler(lambda message: isinstance(deposit_state.get(message.from_user.id), tuple) and deposit_state.get(message.from_user.id)[1] == "quicky_value")
async def handle_addsaldo_amount(message: types.Message):
    idd, _ = deposit_state[message.from_user.id]
    valor = message.text

    users_cursor.execute("SELECT saldo, selected_country FROM users WHERE chat_id=?", (idd,))
    row = users_cursor.fetchone()

    if row:
        current_balance, selected_country = row

        new_balance = current_balance - float(valor)
        users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, idd))
        users_conn.commit()

        await bot.send_message(message.from_user.id, f"Saldo retirado ao id: {idd}")
        deposit_state.pop(message.from_user.id) 
    else:
        await bot.send_message(message.from_user.id, f"ID de usuÃ¡rio nÃ£o encontrado!")

    deposit_state[message.from_user.id] = (idd, "quicky_value")

# FunÃ§Ã£o para iniciar a adiÃ§Ã£o de saldo
@dp.message_handler(commands=['addsaldo'])
async def start_addsaldo(message: types.Message):
    opt = """
    Digite o id do usuÃ¡rio que deseja recarregar!(âš™ï¸)
    """
    chat_id = message.from_user.id
    if chat_id == IDADM :
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "opqie"

# Lidar com a entrada do ID do usuÃ¡rio para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "opqie")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id

    opt = """
    Digite o valor que quer adicionar ao saldo dele!(âš™ï¸)
    """
    await bot.send_message(chat_id, opt)

    deposit_state[message.from_user.id] = (idd, "opqie_value")

# Lidar com a entrada do valor para adicionar saldo
@dp.message_handler(lambda message: isinstance(deposit_state.get(message.from_user.id), tuple) and deposit_state.get(message.from_user.id)[1] == "opqie_value")
async def handle_addsaldo_amount(message: types.Message):
    idd, _ = deposit_state[message.from_user.id]
    valor = message.text

    users_cursor.execute("SELECT saldo, selected_country FROM users WHERE chat_id=?", (idd,))
    row = users_cursor.fetchone()

    if row:
        current_balance, selected_country = row

        new_balance = current_balance + float(valor)
        users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, idd))
        users_conn.commit()

        await bot.send_message(message.from_user.id, f"Saldo adicionado ao id: {idd}")
        deposit_state.pop(message.from_user.id) 
    else:
        await bot.send_message(message.from_user.id, f"ID de usuÃ¡rio nÃ£o encontrado!")
  # Remover o estado apÃ³s a conclusÃ£o

@dp.message_handler(commands=['enviar'])
async def start(message: types.Message):
    opt = """
    Digite o texto que deseja enviar para os usuarios!(âš™ï¸)
    """
    chat_id = message.from_user.id
    if chat_id == IDADM:
        users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
        user = users_cursor.fetchone()
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "enviando"

@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "enviando")
async def handle_deposit_value(message: types.Message):
    users_cursor.execute("SELECT chat_id FROM users")
    await bot.send_message(message.from_user.id, "ComeÃ§ando Envio das Mensagens")
    chat_ids = [row[0] for row in users_cursor.fetchall()]
    for chat_id in chat_ids:
        
        try:
            await bot.send_message(chat_id, message.text)
        
        except:
            continue

    await bot.send_message(message.from_user.id, "Mensagens Enviadas")
    deposit_state.pop(message.from_user.id, None)

@dp.message_handler(commands=['sessions'])
async def send_instructions(message: types.Message):
    chat_id = message.from_user.id
    if chat_id == IDADM:
     instructions = "Envie o arquivo ZIP contendo as sessÃµes."
     await message.reply(instructions)

# Lida com mensagens de documento (ZIP) recebidas
@dp.message_handler(content_types=['document'])
async def handle_zip(message: types.Message):
    save_dir = 'arquivos/'
    chat_id = message.from_user.id
    if chat_id == IDADM:
     try:
        # Verifica se o arquivo Ã© um documento (zip)
        if message.document.mime_type == 'application/zip':
            # Baixa o arquivo ZIP
            file_info = await bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            downloaded_file = await bot.download_file(file_path)

            # Salva o arquivo ZIP na pasta de destino
            save_path = os.path.join(save_dir, message.document.file_name)
            with open(save_path, 'wb') as new_file:
                new_file.write(downloaded_file.read())

            # Extrai o conteÃºdo do arquivo ZIP
            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                zip_ref.extractall(save_dir)
            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
            num_files = len(file_list)
            # Exclui o arquivo ZIP
            os.remove(save_path)
            text = f"""{num_files} novas sessions adicionadas corra e adquira a sua"""
            await message.answer(f'Arquivo ZIP "{message.document.file_name}" extraÃ­do com sucesso e arquivo ZIP removido.')
            users_cursor.execute("SELECT chat_id FROM users")
            await bot.send_message(message.from_user.id, "ComeÃ§ando Envio das Mensagens")
            chat_ids = [row[0] for row in users_cursor.fetchall()]
            for chat_id in chat_ids:
             try:
              await bot.send_message(chat_id=chat_id, text=text)
             except:
              continue

            await bot.send_message(message.from_user.id, "Mensagens Enviadas")
        else:
            await message.answer('Por favor, envie um arquivo ZIP vÃ¡lido.')

     except Exception as e:
        await message.answer(f'Ocorreu um erro ao processar o arquivo: {str(e)}')


if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
