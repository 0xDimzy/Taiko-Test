import random, time, json, sys, asyncio, datetime
from telegram import Bot
from colorama import Fore, init
from web3 import Web3
from web3.middleware import geth_poa_middleware
from itertools import cycle
from shutil import get_terminal_size
from threading import Thread
from time import sleep
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator, ValidationError
import logging

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NumberValidator(Validator):
    def validate(self, document):
        if not document.text.isdigit():
            raise ValidationError(message='Input harus berupa angka', cursor_position=len(document.text))
        value = int(document.text)
        if value not in [1, 2, 3, 4]:
            raise ValidationError(message='Input anda tidak sesuai', cursor_position=len(document.text))

class Loader:
    def __init__(self, desc="Loading....", end="", timeout=0.1):
        self.desc = desc
        self.end = end
        self.timeout = timeout
        self._thread = Thread(target=self._animate, daemon=True)
        self.steps = ['⣾', '⣷', '⣯', '⣟', '⡿', '⢿', '⣻', '⣽']
        self.done = False

    def start(self):
        self._thread.start()
        return self

    def _animate(self):
        for c in cycle(self.steps):
            if self.done:
                break
            print(f"{Fore.YELLOW}\r{self.desc} {c}{Fore.RESET}", end="\r")
            sleep(self.timeout)

    def __enter__(self):
        self.start()
        return self

    def stop(self):
        self.done = True
        cols = get_terminal_size((80, 20)).columns
        print("\r" + " " * cols, end="", flush=True)
        print(f"\r{self.end}", flush=True)

    def __exit__(self, exc_type, exc_value, tb):
        self.stop()

async def send_message(token, chat_id, message):
    bot = Bot(token=token)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

def clear(input, slp=0):
    print(f'{input}')
    sleep(slp)
    sys.stdout.write("\033[F\033[K\033[F\033[K")

def psnE(psn):
    logging.error(f'Message: {psn}')

def psnS(psn):
    return f"{Fore.YELLOW}[SUCCESS] {Fore.RESET}TX hash: {Fore.BLUE}{psn}{Fore.RESET}"

def mode(value):
    return ['Send Message.', 'Init.', 'Process Message.', 'Random.'][value-1]

def msg(value):
    return ['Memulai mengirim pesan...', 'Memulai inisialisasi Contract...', 'Memulai memproses pesan...'][value-1]

def msgtypeTX(value, tx):
    return f"{Fore.YELLOW}[INFO] {Fore.RESET}TX ke{Fore.RED} -> {Fore.YELLOW}{tx}{Fore.RESET} | Mode: {Fore.LIGHTBLUE_EX}{mode(value)}{Fore.RESET}"

def load_config(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"Configuration file {filename} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {filename}.")
        sys.exit(1)

def write_config(filename, data):
    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logging.error(f"An error occurred while writing to {filename}: {e}")

def signature(value):
    return ['0x1bdb0037', '0xf09a4016', '0x2035065e'][value-1]

def prosesTX(taiko_url, account_address, private_key, gwei, type, max_retries=3):
    retries = 0
    while retries < max_retries:
        try:
            w3 = Web3(Web3.HTTPProvider(taiko_url))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            if not w3.is_connected():
                psnE(f'Gagal terhubung ke jaringan Taiko untuk {account_address}')
                return
            nonce = w3.eth.get_transaction_count(account_address)
            transaction = {
                'from': account_address,
                'to': '0x1670000000000000000000000000000000000001',
                'nonce': nonce,
                'gas': 23000,
                'gasPrice': w3.to_wei(gwei, 'gwei'),
                'chainId': 167000,
                'value': w3.to_wei(0, 'ether'),
                'data': signature(type)
            }
            signed_tx = w3.eth.account.sign_transaction(transaction, private_key=private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            with Loader(msg(type), psnS(tx_hash.hex())):
                w3.eth.wait_for_transaction_receipt(tx_hash)
            break
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                if "insufficient funds for gas" in str(e):
                    psnE("Insufficient funds for gas * price + value: balance 0!")
                else:
                    psnE(str(e))
                    psnE("mohon periksa lagi sesuai dengan keterangan error diatas!")
                return
            else:
                sleep(5)  # Wait before retrying

def balance(taiko_url, address):
    try:
        w3 = Web3(Web3.HTTPProvider(taiko_url))
        eth = w3.from_wei(w3.eth.get_balance(address), 'ether')
        return "{:.6f}".format(eth)
    except Exception as e:
        return str(e)

def main():
    config = load_config('config.json')
    try:
        taiko_url = config['taiko_url']
        account_address = config['address']
    except KeyError:
        config['address'] = ''
        account_address = config['address']
    chat_id = config['chat_id']
    token = config['auth_token']
    notif = config['bot_notification']
    print("-" * 60)
    print("-                 Push Point Taiko Blazer                  -")
    print("-" * 60)
    awal = ''
    if account_address:
        print('-           Anda menggunakan Address Wallet                -')
        print(f'-        {account_address}        -')
        print("-       1. Edit Wallet          2. Enter melanjutkan       -")
        print("-" * 60)
        awal = input("Edit or Enter.?: ")
        clear(awal, 0.1)
    if awal == '1' or not account_address:
        print("-" * 60)
        print(" " * 60)
        config['address'] = input("Edit alamat wallet: " if awal == '1' else "Masukkan alamat wallet: ")
        write_config('config.json', config)
        account_address = config['address']
        clear(config['address'], 0.1)
    private_key = input("Masukkan private key: ")
    clear(private_key, 0.1)
    print("-                     Pilih Mode Operasi                   -")
    print("-            1. Send Message          2. Init              -")
    print("-            3. ProcessMessage        4. Random            -")
    print("-" * 60)
    mode_choice = int(prompt("Masukkan Mode (1-4): ", validator=NumberValidator()))
    num_txs = int(input("Masukkan jumlah transaksi: "))
    min_delay, max_delay = map(int, input("Masukkan rentang delay per transaksi (contoh: 20-60): ").split('-'))
    print(f'{Fore.MAGENTA}[INFO]{Fore.RESET} Push Point Taiko Blazer Mode: {Fore.LIGHTBLUE_EX}{mode(mode_choice)}{Fore.RESET} | {Fore.BLUE}{num_txs}{Fore.RESET} tx')
    print(f'{Fore.RESET}-' * 60)
    hari = 0
    while True:
        sekarang = datetime.datetime.now()
        tanggal = sekarang.strftime("%d-%m-%Y")
        jam = sekarang.strftime("%H:%M:%S")
        saldoawal = balance(taiko_url, account_address)
        if notif: asyncio.run(send_message(token, chat_id, f'Info: {hari+1}\nAddress: {account_address}\nSaldo anda: {saldoawal} ETH\nTanggal: {tanggal}\nJam: {jam}'))
        for i in range(num_txs):
            randomDelay = round(random.uniform(min_delay, max_delay))
            mode_c = random.choice([1, 2, 3]) if mode_choice == 4 else mode_choice
            if i == 0: print(f'{msgtypeTX(mode_c, i+1)}')
            prosesTX(taiko_url, account_address, private_key, 0.09, mode_c)
            if i == num_txs - 1:
                l = True
                sleep(0.1)
                print(f'-' * 73)
                print(f"{Fore.YELLOW}[INFO]{Fore.RESET} Proses transaksi sebanyak {num_txs} kali sudah selesai")
            else:
                with Loader(f"Mohon tunggu {randomDelay} detik..", f"{Fore.YELLOW}[INFO] {Fore.RESET}Waktu tunggu {randomDelay} detik sudah tercapai. \n{Fore.RESET}{'-' * 73}\n{msgtypeTX(mode_c, i+2)}"):
                    sleep(randomDelay)
        if l:
            saldoakhir = balance(taiko_url, account_address)
            pemakaian = float(saldoawal)-float(saldoakhir)
            print(f'Proses akan dilakukan besok hari secara otomatis, terima kasih..\n{Fore.YELLOW}[INFO]{Fore.RESET}Sisa Saldo: {saldoakhir} ETH\nUntuk menghentikan proses tekan CTRL+C')
            if notif: asyncio.run(send_message(token, chat_id, f'[INFO] Proses TX sebanyak {num_txs} kali sudah selesai.\nSaldo Awal: {saldoawal} ETH\nSaldo akhir: {saldoakhir} ETH\nSaldo digunakan: {pemakaian} ETH\nAkan dilanjutkan kembali besok hari secara otomatis, terima kasih..'))
            l = False
            print(f'-' * 73)
        sleep(24*60*60)
        hari += 1

if __name__ == "__main__":
    main()