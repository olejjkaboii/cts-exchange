from tronapi import Tron
import os

FULLNODE = 'https://api.trongrid.io'
SOLIDITYNODE = 'https://api.trongrid.io'
EVENTSERVER = 'https://api.trongrid.io'

TRON_OWNER_PRIVATE_KEY = os.getenv('TRON_PRIVATE_KEY', 'ТВОЙ_ПРИВАТНЫЙ_КЛЮЧ')
TRON_OWNER_ADDRESS = os.getenv('TRON_ADDRESS', 'ТВОЙ_АДРЕС_КОШЕЛЬКА')

tron = Tron(
    full_node=FULLNODE,
    solidity_node=SOLIDITYNODE,
    event_server=EVENTSERVER,
    private_key=TRON_OWNER_PRIVATE_KEY
)

def create_trc20_address():
    try:
        new_account = tron.create_account.address
        new_address = new_account['base58checkAddress']
        return new_address
    except Exception as e:
        print(f"Error creating address: {e}")
        return None

def check_balance(address):
    try:
        balance = tron.trx.get_balance(address)
        return balance / 1000000
    except Exception as e:
        print(f"Error checking balance: {e}")
        return 0
