# Bot sessions Telegram

* You can sell your sessions by placing them within the sales mass;  
* pix and crypto payment method;  

## Requirements:
* Python 3.10 and newer;  
* Linux (should work on Windows, but not tested);   
* Systemd init system (optional).  

## Installation:
1. Clone this repo;
2. `cd` to cloned directory and initialize Python virtual environment (venv);
3. Activate the venv and install all dependencies from `requirements.txt` file;

### Systemd 
1. Put the telegram api key inside the txt tokenbot.txt;
2. Put the Mercado Pago API key in the apimercadopago.txt file;
3. Users.db user database with account balance;
4. folder files with sessions not yet sold, and folder sold for sessions already sold;
5. python botsessions.py to run.
6. commands for users:
/start
/saldo
/recarregar

