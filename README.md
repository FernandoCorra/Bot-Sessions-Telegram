# Bot sessions Telegram

* You can sell your sessions by placing them within the sales mass;  
* pix and crypto payment method;
* verification of the sessions 

## Requirements:
* Python 3.11 and newer;  
* Systemd init system (optional).  

## Installation:
1. Clone this repo;
2. `cd` to cloned directory and initialize Python virtual environment (venv);
3. Activate the venv and install all dependencies from `requirements.txt` file;

## Config
1. Open the config.ini file
2. set the telegram token bot (from @botfather) in BOT_TOKEN;
3. set the Mercado Pago API key in api_token
4. if your wish verify sessions before send to yours customers, set VERIFICAR = True and set api_id and api_hash of telegram API
5. set another configs according your application

### Systemd 
1. Users.db user database with account balance;
2. folder files with sessions not yet sold, and folder sold for sessions already sold;
3. python app.py to run.
4. commands for users:
/start
/saldo
/recarregar
