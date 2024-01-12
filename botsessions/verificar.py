# -*- coding: utf-8 -*-

import os
import shutil
import asyncio
import zipfile
import random
import logging
import configparser
import tempfile
from telethon import TelegramClient, utils
from datetime import datetime
from telethon.tl.functions.account import UpdateProfileRequest
from faker import Faker


class CredenciaisError(Exception):
    pass

def get_credenciais():
    config = configparser.ConfigParser()
    config.read('config.ini')

    credenciais = {}

    try:
        # Seção 'contas'
        credenciais['IDADM'] = int(config['contas']['IDADM'])
        credenciais['IDGRUPOCOMPRA'] = int(config['contas']['IDGRUPOCOMPRA'])
        credenciais['IDGRUPODEPOSITO'] = int(config['contas']['IDGRUPODEPOSITO'])
        credenciais['SUPORTECONTATO'] = config['contas']['SUPORTECONTATO']

        # Seção 'valores'
        credenciais['MINIMODEPOSITO'] = float(config['valores']['MINIMODEPOSITO'])
        credenciais['MENORQUE10'] = float(config['valores']['MENORQUE10'])
        credenciais['MAIORQUE10MENORQUE50'] = float(config['valores']['MAIORQUE10MENORQUE50'])
        credenciais['MAIORQUE50MENORQUE100'] = float(config['valores']['MAIORQUE50MENORQUE100'])
        credenciais['MAIORQUE100'] = float(config['valores']['MAIORQUE100'])

        # Seção 'api'
        credenciais['api_id'] = config.get('api', 'api_id', fallback='123')
        credenciais['api_hash'] = config.get('api', 'api_hash', fallback='123')
        credenciais['BOT_TOKEN'] = config['api']['BOT_TOKEN']

        # Seção 'mercadopago'
        credenciais['mercadopago_api'] = config['mercadopago']['api_token']
        credenciais['timeout'] = int(config['mercadopago']['timeout'])
        
        # seção 'telethon'
        credenciais['MUDAR_NOME'] = config.getboolean('telethon', 'MUDAR_NOME')
        credenciais['VERIFICAR'] = config.getboolean('telethon', 'VERIFICAR')

        return credenciais
    
    except Exception as e:
        raise CredenciaisError((
            f"Erro: Problema na chave {str(e)} ou tipo incorreto \n"
            "configure o config.ini com todas as chaves necessárias"
        ))

credenciais = get_credenciais()

def filter_files(file):
    return file.endswith('.session')

def get_sessions(folder):
    
    sessions = []
    
    for root, sub, files in os.walk(folder):
        for file in filter(filter_files, files):
            sessions.append(os.path.join(root, file))

    random.shuffle(sessions)
    return sessions


async def start(session, change_name=False):
        
    phone = os.path.basename(session).replace('.session', '')
    logger = logging.getLogger(f'log_{phone}')
    logger.setLevel(logging.DEBUG)
    handle_novo = logging.FileHandler(f'{os.path.dirname(session)}/{phone}.log')
    logger.addHandler(handle_novo)
    logger.debug(
        f'\nLogando em {phone} Data: {datetime.now().strftime("%d-%m-%y_%H-%M")}\n'
    )
        
    try:
        client = TelegramClient(
            session, credenciais['api_id'], credenciais['api_hash'], base_logger=logger
        )
        await client.start(phone=phone, code_callback=lambda: "123456", max_attempts=1)
        await asyncio.sleep(0.3)
        if change_name:
            fake = Faker('pt_BR') 
            await client(UpdateProfileRequest(
                first_name=fake.first_name(), 
                last_name=fake.last_name())
            )
        me = await client.get_me()
        result = f'\n\nSession {utils.get_display_name(me)} logada com sucesso \n\n'
        return True
        
    except Exception as e:
        result = f'\n\nErro ao processar cliente {phone}: {e} \n\n'
        return False
    finally:
        try:
            await client.disconnect()
        except:
            pass
        finally:
            logger.info(result)
            handle_novo.close()
            await asyncio.sleep(0.2)


async def get_sessions_send(quantidade):
    
    sessions = []
    temp_dir = tempfile.mkdtemp()
    
    for session in get_sessions('arquivos'):
        
        phone = os.path.basename(session).replace('.+', '').replace('.session', '')
        path = shutil.move(
            session,
            os.path.join(temp_dir, f'{phone}.session')
        )
        
        if credenciais['VERIFICAR']:
            if (await start(path)):
                sessions.append(path)
                sessions.append(f'{temp_dir}/{phone}.log')
        else:
            await asyncio.sleep(0.001)
            sessions.append(path)
            
        if len(sessions) >= quantidade:
            break
        
    return sessions


async def verificar_sessions(downloaded_file, path, mudar_nome):
    
    temp_dir = 'sessions'
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, path)
    sessions_boas = []
    count_banidas = 0

    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(downloaded_file.read())

    with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
        
    for session in get_sessions(temp_dir):
        
        if credenciais['VERIFICAR']:
            if (await start(session, mudar_nome)):
                sessions_boas.append(session)
            else:
                count_banidas += 1
        else:
            sessions_boas.append(session)
            await asyncio.sleep(0.001)
    
    for session in sessions_boas:
        shutil.move(
            session,
            os.path.join('arquivos', os.path.basename(session))
        )
        
    shutil.rmtree(temp_dir)
    return len(sessions_boas), count_banidas


    
