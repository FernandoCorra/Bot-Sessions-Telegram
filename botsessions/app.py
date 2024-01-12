import logging
import sqlite3
import os
import asyncio
import zipfile

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from datetime import datetime
from chavepix import verify_payment , get_payment
from verificar import get_sessions, get_sessions_send, verificar_sessions, get_credenciais
from sql import*

credenciais = get_credenciais()

IDADM = credenciais['IDADM']
IDGRUPOCOMPRA = credenciais['IDGRUPOCOMPRA']
IDGRUPODEPOSITO = credenciais['IDGRUPODEPOSITO']
MINIMODEPOSITO = credenciais['MINIMODEPOSITO']
MENORQUE10 = credenciais['MENORQUE10']
MAIORQUE10MENORQUE50 = credenciais['MAIORQUE10MENORQUE50']
MAIORQUE50MENORQUE100 = credenciais['MAIORQUE50MENORQUE100']
MAIORQUE100 = credenciais['MAIORQUE100']
MUDAR_NOME = credenciais['MUDAR_NOME']
SUPORTECONTATO = credenciais['SUPORTECONTATO']
BOT_TOKEN = credenciais['BOT_TOKEN']
TIMEOUT = credenciais['timeout']    

# Substitua 'YOUR_BOT_TOKEN' pelo token do seu bot fornecido pelo BotFather do Telegram
bot = Bot(BOT_TOKEN)
dp = Dispatcher(bot)

# Configuração de log para monitorar as interações do bot
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# Mutex para evitar concorrência no envio das sessions
mutex = asyncio.Lock()

# Dicionário para armazenar o estado do usuário ao depositar saldo
deposit_state = {}
user_state = {}
valoradd = {}

# Função para enviar os arquivos em um ZIP
async def send_files_in_zip(chat_id, file_paths):
    hora = datetime.now().strftime("%d-%m-%y_%H-%M")
    path = os.path.join('vendidas', os.path.join(str(chat_id), hora))
    os.makedirs(path, exist_ok=True)
    file = os.path.join(path, 'sessions.zip')

    with zipfile.ZipFile(file, 'w') as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))

    with open(file, 'rb') as zip_file:
        await bot.send_document(chat_id, zip_file)
    return file

idstart = {}
voltarid = {}

def get_sesssions_compradas(chat_id):
    path = os.path.join(f'vendidas', str(chat_id))
    if os.path.exists(path):
        file = os.path.join(path, 'sessions.zip')
        with zipfile.ZipFile(file, 'w') as zipf:
            for pasta_raiz, _, arquivos in os.walk(path):
                for arquivo in arquivos:
                    caminho_completo = os.path.join(pasta_raiz, arquivo)
                    relativo = os.path.relpath(caminho_completo, path)
                    zipf.write(caminho_completo, relativo)
        return file
    else:
        return None

@dp.callback_query_handler(lambda c: c.data == "preços")
async def send_price_table(callback_query: types.CallbackQuery):
    price_table = (
        "📋 Tabelas de valores :\n\n"
        "📊 Ao comprar a partir de: 1\n💵 O valor por unidade é: R$ {MENORQUE10}\n\n"
        "📊 Ao comprar a partir de: 10\n💵 O valor por unidade é: R$ {MAIORQUE10MENORQUE50}\n\n"
        "📊 Ao comprar a partir de: 50\n💵 O valor por unidade é: R$ {MAIORQUE50MENORQUE100}\n\n"
        "📊 Ao comprar a partir de: 100\n💵 O valor por unidade é: R$ {MAIORQUE100}\n\n"
        "Boas compras 😊"
    )

    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    msg = await bot.edit_message_text(
        chat_id=callback_query.from_user.id, text=price_table,
       message_id=b, reply_markup=buttons1
    )
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}


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
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    # Criando a mensagem com o texto
    message_text = (
        f"Bom Dia, {message.from_user.first_name} Como posso te ajudar?"
        f"Temos atualmente {available_sessions} sessões disponíveis"
    )
    
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("📲 Exibir perfil", callback_data="view_balance"),
        types.InlineKeyboardButton("📊 Tabela de valores", callback_data="preços"),
        types.InlineKeyboardButton("📦 Comprar session", callback_data="comprar_sessions"),
        types.InlineKeyboardButton("🏦 Adicionar saldo", callback_data="recarregar"),
        types.InlineKeyboardButton("🤖 Bot Leads", callback_data="leads"),
        types.InlineKeyboardButton("🧑 Preciso de ajuda", callback_data="suporte"),
        types.InlineKeyboardButton("📂 Minhas sessions", callback_data="sessions_compradas")
    )
    
    # Enviando a mensagem com o texto e os botões
    with open("bot.png", "rb") as img:
        startid = await bot.send_message(chat_id, message_text, reply_markup=buttons1)
    
    modificar = startid.message_id
    idstart[chat_id] = {'message_id1': modificar}

    

@dp.callback_query_handler(lambda c: c.data == "suporte")
async def suporte(callback_query: types.CallbackQuery):
    optiontexto = f"Suporte: Para solicitar suporte , por favor entre em contato com @{SUPORTECONTATO} 📲"
    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    msg = await bot.edit_message_text(
        chat_id=callback_query.from_user.id,text=optiontexto,
        message_id=b,reply_markup=buttons1
    )
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}
    
@dp.callback_query_handler(lambda c: c.data == "sessions_compradas")
async def sessions_compradas(callback_query: types.CallbackQuery):
    
    chat_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id, text="Buscando suas sessions", show_alert=False)
    sessions_file =  get_sesssions_compradas(chat_id)
    optiontexto = 'Sessions enviadas com sucesso'
    
    if sessions_file:
        with open(sessions_file, 'rb') as zip_file:
            await bot.send_document(chat_id, zip_file)
        os.remove(sessions_file)
    else:
        optiontexto = 'Você ainda não comprou nenhuma session'
        
    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    msg = await bot.edit_message_text(
        chat_id=callback_query.from_user.id,text=optiontexto,
        message_id=b,reply_markup=buttons1
    )
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}
        

@dp.message_handler(commands=['perfil'])
async def perfil(message: types.Message):

    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (message.from_user.id,))
    saldo = users_cursor.fetchone()
    saldo1 = round(saldo[0],2)
    a = idstart.get(message.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("Exibir Contrato 📝", callback_data="contris"),
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar")
    )
    options_text = (
        f"👤 Dados do usuário\n🆔 | ID: {message.from_user.id}\n📛 |"
        f'Nome: {message.from_user.first_name}\n📧 |'
        f"Username: {message.from_user.username}\n💰 |' Saldo: R${saldo1}"
    )
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
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    if available_sessions == 0:
        await bot.send_message(
            chat_id=message.from_user.id, 
            text="Estamos sem estoque no momento. Quando abastecermos, avisaremos.",
            reply_markup=buttons1
        )
        
    else:
        buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
        buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
        buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
        await bot.send_message(
            chat_id=message.from_user.id, 
            text=f"📟Total escolhido : {valor} (Disponíveis: {available_sessions})",
            reply_markup=buttons1
        )


@dp.message_handler(commands=['ajuda','termos'])
async def helpp(message: types.Message):
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  
    buttons1.add(
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar")
    )
    with open ('termos.txt', 'r', encoding='utf-8') as termos:
        text = termos.readlines()

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

    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {valor}
    """
    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    pix = f"gerar_{valor}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))

    await  bot.send_message(chat_id=message.from_user.id,text=text,reply_markup=buttons1)

@dp.callback_query_handler(lambda c: c.data == "contris")
async def view_balance(callback_query: types.CallbackQuery):
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar")
    )
    with open ('termos.txt', 'r', encoding='utf-8') as termos:
        text = termos.readlines()
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,message_id=callback_query.message.message_id,
        reply_markup=buttons1
    )

@dp.callback_query_handler(lambda c: c.data == "view_balance")
async def view_balance(callback_query: types.CallbackQuery):
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (callback_query.from_user.id,))
    saldo = users_cursor.fetchone()
    a = idstart.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    buttons1 = types.InlineKeyboardMarkup(row_width=1)  
    buttons1.add(
        types.InlineKeyboardButton("Exibir Contrato 📝", callback_data="contris"),
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar")
    )
    options_text = (
        f"👤 Dados do usuário\n🆔 "
        f"| ID: {callback_query.from_user.id}\n📛 |"
        f" Nome: {callback_query.from_user.first_name}\n📧 |"
        f"Username: {callback_query.from_user.username}\n💰 | Saldo: R${saldo[0]}"
    )
    msg = await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=options_text,message_id=b,reply_markup=buttons1
    )
    modificar = msg.message_id
    voltarid[callback_query.from_user.id] = {'message_id1': modificar}

@dp.callback_query_handler(lambda c: c.data == "leads")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    url = "https://app.monetizze.com.br/r/AUF23700822"
    text = (
        "🔵 SE VOCÊ ESTÁ PROCURANDO UM ROBÔ DE ENGAJAMENTO PARA TELEGRAM MELHOR QUE O SEU ATUAL.....⤵️\n\n"
        "🤖 Apresento a vocês o Ninja Add !\n\n"
        "❤️ Porque indicamos ele ? \n\n"
        "✅ Capacidade de adicionar em até grupos diferentes ao mesmo tempo !\n"
        "✅ Filtragem fina de membros, podendo filtrar membros ativos por dia, hora,"
        " minuto, foto perfil, usernameme e dentre outros\n"
        "✅ Separação de duplicatas entre grupos diferentes, permitindo que você"
        " nunca adicione membros repetidos mesmo entre diferentes grupos\n"
        "✅ Alta velocidade de adição\n"
        "✅ Suporte a proxy, multithread e diferentes APIs\n"
        "✔️ Para adquirir o Ninja Add, clique no link abaixo 👇"
    )
    buttons1 = types.InlineKeyboardMarkup(row_width=1)
    buttons1.add(
        types.InlineKeyboardButton(" Comprar o Ninja Add 🥷", url=url),
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar")
    )
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id, text=text, 
        message_id=callback_query.message.message_id, reply_markup=buttons1
    )


@dp.callback_query_handler(lambda query: query.data == "voltar")
async def view_balance(callback_query: types.CallbackQuery):
    chat_id = callback_query.from_user.id
    users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = users_cursor.fetchone()

    if user is None:
        # Adiciona o usuário ao banco de dados de usuários com saldo inicial de 0.0
        users_cursor.execute("INSERT INTO users (chat_id, saldo) VALUES (?, ?)", (chat_id, 0.0))
        users_conn.commit()

    # Obtém o saldo do usuário
    users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
    user_saldo = users_cursor.fetchone()[0]
    session_files = os.listdir("arquivos")
    available_sessions = len(session_files)
    # Criando a mensagem com o texto
    message_text = f"""
    Bom Dia, {callback_query.from_user.first_name} Como posso te ajudar?
Temos atualmente {available_sessions} sessões disponíveis

    """

    buttons1 = types.InlineKeyboardMarkup(row_width=1)  # Exibe 2 botões por linha
    buttons1.add(
        types.InlineKeyboardButton("📲 Exibir perfil", callback_data="view_balance"),
        types.InlineKeyboardButton("📊 Tabela de valores", callback_data="preços"),
        types.InlineKeyboardButton("📦 Comprar session", callback_data="comprar_sessions"),
        types.InlineKeyboardButton("🏦 Adicionar saldo", callback_data="recarregar"),
        types.InlineKeyboardButton("🤖 Bot Leads", callback_data="leads"),
        types.InlineKeyboardButton("🧑 Preciso de ajuda", callback_data="suporte"),
        types.InlineKeyboardButton("📂 Minhas sessions", callback_data="sessions_compradas")

    )
    a = voltarid.get(callback_query.from_user.id, {})
    b = a.get('message_id1')
    msg = await bot.edit_message_text(
        chat_id=callback_query.from_user.id,text=message_text, 
        message_id=callback_query.message.message_id,reply_markup=buttons1
    )

@dp.callback_query_handler(lambda c: c.data == "baixo100")
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    aldo = valoradd.get(callback_query.from_user.id, {})
    valor = aldo.get('saldo')
    certo = valor - 100
    if certo < MINIMODEPOSITO:
        certo = MINIMODEPOSITO
    valoradd[callback_query.from_user.id] = {'saldo': certo}
    # Atualize o texto com o novo valor
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""     💠 PIX 💠    \n 💵 Valor: R$ {certo}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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

    text = (
        f"     💠 PIX 💠    \n 💵 Valor: R$ {valor}\n"
    )
    buttons1 = types.InlineKeyboardMarkup(row_width=2)
    buttons1.add(
        types.InlineKeyboardButton("+1", callback_data="alto1"),
        types.InlineKeyboardButton("-1", callback_data="baixo1"),
        types.InlineKeyboardButton("+5", callback_data="alto5"),
        types.InlineKeyboardButton("-5", callback_data="baixo5"),
        types.InlineKeyboardButton("+100", callback_data="alto100"),
        types.InlineKeyboardButton("-100", callback_data="baixo100"),
    )
    pix = f"gerar_{valor}"
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))

    await  bot.edit_message_text(
        chat_id=callback_query.from_user.id, text=text, 
        message_id=idstartt, reply_markup=buttons1
    )


@dp.callback_query_handler(lambda c: c.data.startswith("gerar_"))
async def ask_for_deposit_amount(callback_query: types.CallbackQuery):
    deposit_value1 = callback_query.data[6:]
    deposit_value = int(deposit_value1)
    chat_id = callback_query.from_user.id
    chave_pix, id_pagamento = get_payment(deposit_value, "sms")

    text = (
        f"✅ Pagamento gerado\n"
        f"⚠️ Está com problemas no pagamento? Tente pagar meio de outro banco!\n"
        f"💵 Valor: R$ {deposit_value}\n"
        f"⏱ Prazo de expiração: {TIMEOUT} Minutos\n"
        f"💠 Pix Copia e Cola:\n\n"
        f"`{chave_pix}`\n\n"
        f"💡 Dica: Clique no código acima para copiá-lo.\n"
        f"Após o pagamento seu saldo será creditado automaticamente."
    )

    await  bot.edit_message_text(chat_id=callback_query.from_user.id, text=text, message_id=callback_query.message.message_id, parse_mode="Markdown")

    user_name = callback_query.from_user.id
    IDGRUPO = IDGRUPODEPOSITO
    a = 0
    c = 1
    payment_verified = False
    try:
        payment_verified = await asyncio.wait_for(verify_payment(id_pagamento), timeout=TIMEOUT*60)
    except asyncio.TimeoutError:
        new_text = "🔴🔴PIX EXPIRADO🔴🔴 "
        buttons1 = types.InlineKeyboardMarkup(row_width=2)
        buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
        await bot.edit_message_text(
            chat_id=chat_id, message_id=callback_query.message.message_id, 
            text=new_text, reply_markup=buttons1
        )

    if payment_verified == True:
        users_cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (chat_id,))
        current_balance = users_cursor.fetchone()[0]
        new_balance = float(current_balance) + float(deposit_value)

        users_cursor.execute("UPDATE users SET saldo=? WHERE chat_id=?", (new_balance, chat_id))
        users_conn.commit()

        text = (
            f"🟢Seu depósito de {deposit_value} foi adicionado!\n"
            f"🟢Seu saldo atual é R${new_balance:.2f}"
        )
        a = 1
        buttons1 = types.InlineKeyboardMarkup(row_width=2)
        buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
        await  bot.edit_message_text(
            chat_id=callback_query.from_user.id, 
            text=text, message_id=callback_query.message.message_id, reply_markup=buttons1
        )

        abouttext = (
            f"✅Saldo Adicionado por {user_name}🔥 !\n"
            f"📲ID: {chat_id}\n"
            f"📲USERNAME: @{callback_query.from_user.username}\n"
            f"🛒Valor: {deposit_value}"
        )
        await bot.send_message(IDGRUPO, abouttext)

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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo} Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    text = f"""📟Total escolhido : {certo}  Disponíveis: {available_sessions}"""

    buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
    buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    # Atualize a mensagem no Telegram
    await bot.edit_message_text(
        chat_id=callback_query.from_user.id,
        text=text,
        message_id=callback_query.message.message_id,
        reply_markup=buttons1  # Mantenha os botões existentes
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
    buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
    if available_sessions == 0:
        await bot.edit_message_text(
            chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id, 
            text="Estamos sem estoque no momento. Quando abastecermos, avisaremos.",reply_markup=buttons1
        )
        
    else:
        buttons1 = types.InlineKeyboardMarkup(row_width=2)  # Exibe 2 botões por linha
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
        buttons1.add(types.InlineKeyboardButton("FINALIZAR ✅", callback_data=pix))
        buttons1.add(types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"))
        await bot.edit_message_text(
            chat_id=callback_query.from_user.id, message_id=callback_query.message.message_id,
            text=f"📟Total escolhido : {valor} (Disponíveis: {available_sessions})",reply_markup=buttons1
        )

@dp.callback_query_handler(lambda c: c.data.startswith("finalizar_"))
async def ask_quantity(callback_query: types.CallbackQuery):
    session_files = os.listdir("arquivos")
    disponivel = len(session_files)
    buttons1 = types.InlineKeyboardMarkup(row_width=1)
    buttons1.add(
        types.InlineKeyboardButton("🏦 Adicionar saldo", callback_data="recarregar"),
        types.InlineKeyboardButton("VOLTAR 🔙", callback_data="voltar"),
    )
    quant1= callback_query.data[10:]
    quant  = int(quant1)
    if quant > disponivel:
        await bot.edit_message_text(
            chat_id=callback_query.from_user.id, 
            message_id=callback_query.message.message_id, 
            text="Quantidade de sessions desejadas não disponivel, escolha outra quantidade", 
            reply_markup=buttons1
        )
    else:
        if quant < 10:
            session_price = MENORQUE10
        elif 10 <= quant < 50:
            session_price = MAIORQUE10MENORQUE50
        elif 50 <= quant < 100:
            session_price = MAIORQUE50MENORQUE100
        elif quant >= 100:
            session_price = MAIORQUE100
        total_price = session_price * quant

        chat_id = callback_query.from_user.id
        user_balance = get_user_balance(chat_id)

        if user_balance >= total_price:
            await bot.answer_callback_query(callback_query.id, text="Verificando suas sessions...")
            async with mutex:
                session_paths = await get_sessions_send(quant)

            session_files = get_sessions(os.path.dirname(session_paths[0]))
            insert_purchase(callback_query.from_user.id, session_files)
            file_zipado = await send_files_in_zip(chat_id, session_paths)

            new_balance = user_balance - (session_price * len(session_files))
            update_user_balance(chat_id, new_balance)

            texto = (
                f"ID : {callback_query.from_user.id}\n"
                f"USERNAME : @{callback_query.from_user.username}\n"
                f"zip dele abaixo"
            )
            await bot.send_message(chat_id=IDGRUPOCOMPRA, text=texto)
            with open(file_zipado, 'rb') as zip_file:
                await bot.send_document(IDGRUPOCOMPRA, zip_file)

            for session_path in session_paths:
                os.rename(session_path, os.path.join("enviadas", os.path.basename(session_path)))

            await bot.edit_message_text(
                chat_id=callback_query.from_user.id,
                message_id=callback_query.message.message_id,
                text=(
                    f"Foram enviadas {len(session_files)} sessions.\n"
                    f"Seu saldo atualizado: R${new_balance:.2f}"
                ),
                reply_markup=buttons1
            )
        else:
            await bot.edit_message_text(
                chat_id=callback_query.from_user.id,
                message_id=callback_query.message.message_id,
                text="Saldo insuficiente para a compra das sessions.",
                reply_markup=buttons1
            )

deposit_state = {}
remove_saldo_state = {}
historico = {}

# Função para iniciar a adição de saldo
@dp.message_handler(commands=['verificarsaldo'])
async def start_addsaldo(message: types.Message):
    opt = (
        "Digite o id do usuário que deseja verificar!(⚙️)"
    )
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "opt"

# Lidar com a entrada do ID do usuário para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "opt")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id
    db = sqlite3.connect('users.db')
    cursor = db.cursor()
    idd = message.text
    cursor.execute("SELECT saldo FROM users WHERE chat_id=?", (idd,))
    row = cursor.fetchone()
    db.close()

    if row:
        await bot.send_message(chat_id, f"Saldo Do ID {idd} é  R${row[0]}")
    else:
        await bot.send_message(chat_id, "Usuário nao encontrado no banco de dados")

@dp.message_handler(commands=['historico'])
async def start_addsaldo(message: types.Message):
    opt = (
        "Digite o id do usuário que deseja verificar historico!(⚙️)"
    )
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "roco"

# Função para obter as sessions compradas por um chat_id como uma lista
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

# Função para formatar as sessions em uma tabela
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

# Função para iniciar a adição de saldo
@dp.message_handler(commands=['remover'])
async def start_addsaldo(message: types.Message):
    opt = (
        "Digite o id do usuário que deseja retirar saldo!(⚙️)"
    )
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "quicky"

# Lidar com a entrada do ID do usuário para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "quicky")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id

    opt = (
        "Digite o valor que quer retirar do saldo dele!(⚙️)"
    )
    await bot.send_message(chat_id, opt)

    deposit_state[message.from_user.id] = (idd, "quicky_value")

# Lidar com a entrada do valor para adicionar saldo
@dp.message_handler(
        lambda message: isinstance(deposit_state.get(message.from_user.id), tuple) and
        deposit_state.get(message.from_user.id)[1] == "quicky_value"
)
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
        await bot.send_message(message.from_user.id, f"ID de usuário não encontrado!")

    deposit_state[message.from_user.id] = (idd, "quicky_value")

# Função para iniciar a adição de saldo
@dp.message_handler(commands=['addsaldo'])
async def start_addsaldo(message: types.Message):
    opt = (
        "Digite o id do usuário que deseja recarregar!(⚙️)"
    )
    chat_id = message.from_user.id
    if chat_id == IDADM:
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "opqie"

# Lidar com a entrada do ID do usuário para adicionar saldo
@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "opqie")
async def handle_addsaldo_id(message: types.Message):
    idd = message.text
    chat_id = message.from_user.id

    opt = (
        "Digite o valor que quer adicionar ao saldo dele!(⚙️)"
    )
    await bot.send_message(chat_id, opt)

    deposit_state[message.from_user.id] = (idd, "opqie_value")

# Lidar com a entrada do valor para adicionar saldo
@dp.message_handler(
        lambda message: isinstance(deposit_state.get(message.from_user.id), tuple) 
        and deposit_state.get(message.from_user.id)[1] == "opqie_value"
)
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
        await bot.send_message(message.from_user.id, f"ID de usuário não encontrado!")

# Remover o estado após a conclusão

@dp.message_handler(commands=['enviar'])
async def start(message: types.Message):
    opt = (
        "Digite o texto que deseja enviar para os usuarios!(⚙️)"
    )
    chat_id = message.from_user.id
    if chat_id == IDADM:
        users_cursor.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
        user = users_cursor.fetchone()
        await bot.send_message(chat_id, opt)
        deposit_state[message.from_user.id] = "enviando"


@dp.message_handler(lambda message: deposit_state.get(message.from_user.id) == "enviando")
async def handle_deposit_value(message: types.Message):
    users_cursor.execute("SELECT chat_id FROM users")
    await bot.send_message(message.from_user.id, "Começando Envio das Mensagens")
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
     instructions = "Envie o arquivo ZIP contendo as sessões."
     await message.reply(instructions)


# Lida com mensagens de documento (ZIP) recebidas
@dp.message_handler(commands=['sessions'])
async def send_instructions(message: types.Message):
    chat_id = message.from_user.id
    if chat_id == IDADM:
     instructions = "Envie o arquivo ZIP contendo as sessões."
     await message.reply(instructions)

# Lida com mensagens de documento (ZIP) recebidas
@dp.message_handler(content_types=['document'])
async def handle_zip(message: types.Message):
    chat_id = message.from_user.id
    if chat_id == IDADM:
     try:
        # Verifica se o arquivo é um documento (zip)
        if message.document.mime_type == 'application/zip':
            # Baixa o arquivo ZIP
            file_info = await bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            downloaded_file = await bot.download_file(file_path)
            async with mutex:
                sessions_boas, banidas = await verificar_sessions(
                    downloaded_file, message.document.file_name, MUDAR_NOME
                )
            # Exclui o arquivo ZIP
            await message.answer(
                f'Sessions adicionadas com sucesso, {sessions_boas} sessions boas e {banidas} banidas'
            )
            
            if sessions_boas > 1:
                text = f"""{sessions_boas} novas sessions adicionadas corra e adquira a sua"""
                users_cursor.execute("SELECT chat_id FROM users")
                await bot.send_message(message.from_user.id, "Começando Envio das Mensagens")
                chat_ids = [row[0] for row in users_cursor.fetchall()]
                for chat_id in chat_ids:
                    try:
                        await bot.send_message(chat_id=chat_id, text=text)
                    except:
                        continue

                await bot.send_message(message.from_user.id, "Mensagens Enviadas")
        else:
            await message.answer('Por favor, envie um arquivo ZIP válido.')

     except Exception as e:
        await message.answer(f'Ocorreu um erro ao processar o arquivo: {str(e)}')

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)