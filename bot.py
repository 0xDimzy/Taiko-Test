import random, json, sys, asyncio, datetime, logging, pytz
import requests
from telegram import Bot
from decimal import Decimal
from colorama import Fore, init
from web3 import Web3
from web3.middleware import geth_poa_middleware
from itertools import cycle
from shutil import get_terminal_size
from threading import Thread
from time import sleep
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.shortcuts import PromptSession
import time

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NumberValidator(Validator):
    def validate(self, document):
        if not document.text.isdigit() or int(document.text) not in [1, 2, 3, 4]:
            raise ValidationError(message='Input must be a number between 1-4', cursor_position=len(document.text))

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
    try:
        response = await bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        if response:
            print("Success: Message sent to Telegram.")
        else:
            print("Failed: No response from Telegram server.")
    except Exception as e:
        print(f"Failed: {str(e)}")

def clear(input, slp=0):
    print(f'{input}')
    sleep(slp)
    sys.stdout.write("\033[F\033[K\033[F\033[K")

def psnE(psn):
    logging.error(f'Message: {psn}')

def psnS(psn):
    tx_link = f"https://taikoscan.io/tx/{psn}"
    return f"{Fore.YELLOW}[SUCCESS] {Fore.RESET}TX hash: {Fore.BLUE}{psn}{Fore.RESET} | Link: {Fore.CYAN}{tx_link}{Fore.RESET}"

def mode(value):
    return ['Send Message.', 'Init.', 'Process Message.', 'Random.'][value-1]

def msg(value):
    return ['Starting to Send Transaction Message...', 'Starting Contract Initialization...', 'Starting to Send Transaction Message...'][value-1]

def msgtypeTX(value, tx):
    return f"{Fore.YELLOW}[INFO] {Fore.RESET}Transaction To{Fore.RED} -> {Fore.YELLOW}{tx}{Fore.RESET} | Mode: {Fore.LIGHTBLUE_EX}{mode(value)}{Fore.RESET}"

def load_config(filename):
    try:
        with open(filename, 'r') as file:
            config = json.load(file)
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading config: {e}")
        sys.exit(1)

def write_config(filename, data):
    try:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logging.error(f"An error occurred while writing to {filename}: {e}")

def signature(value):
    return ['0x1bdb0037', '0xf09a4016', '0x2035065e'][value-1]

async def prosesTX(taiko_url, account_address, private_key, gwei, type, max_retries=3, token=None, chat_id=None):
    retries = 0
    max_retries = int(max_retries)
    while retries < max_retries:
        try:
            w3 = Web3(Web3.HTTPProvider(taiko_url))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            if not w3.is_connected():
                psnE(f'Failed to connect to Taiko network for {account_address}')
                return False
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
            return True
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                if "insufficient funds for gas" in str(e):
                    psnE("Insufficient funds for gas * price + value: balance 0!")
                    if token and chat_id:
                        await send_message(token, chat_id, "Insufficient funds for gas * price + value: balance 0!")
                    print("Not enough gas to continue the transaction. Do you want to continue? (y/n)")
                    try:
                        user_input = await asyncio.wait_for(asyncio.to_thread(input, "Enter your choice within 1 minute: "), timeout=60)
                        if user_input.lower() != 'y':
                            return False
                    except asyncio.TimeoutError:
                        print("Time's up. Transaction not continued.")
                        return False
                elif "transaction underpriced" in str(e):
                    psnE("Gas Gwei too low for this transaction.")
                else:
                    psnE(str(e))
                    psnE("please check again according to the error description above!")
                return False
            else:
                sleep(5)

def get_eth_price_in_usd():
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd')
        response.raise_for_status()
        data = response.json()
        return data['ethereum']['usd']
    except requests.RequestException as e:
        logging.error(f"Error fetching ETH price: {e}")
        return None

def balance(taiko_url, address):
    try:
        w3 = Web3(Web3.HTTPProvider(taiko_url))
        eth = w3.from_wei(w3.eth.get_balance(address), 'ether')
        eth_price = get_eth_price_in_usd()

        if eth_price is not None:
            usd_value = Decimal(eth) * Decimal(eth_price)
            return "{:.6f} ETH (${:.2f} USD)".format(eth, usd_value)
        else:
            return "{:.6f} ETH".format(eth)
    except Exception as e:
        return str(e)
    
async def countdown(seconds):
    while seconds:
        mins, secs = divmod(seconds, 60)
        timeformat = f'{mins:02d}:{secs:02d}'
        print(f"{Fore.YELLOW}\rWaiting Time: {timeformat}{Fore.RESET}", end="\r")
        await asyncio.sleep(1)
        seconds -= 1
    print(f"{Fore.YELLOW}\rWaiting Time Finished!{Fore.RESET}", end="\r")

async def main():
    config = load_config('config.json')
    taiko_url = config.get('taiko_url')
    chat_id = config.get('chat_id')
    token = config.get('auth_token')
    notif = config.get('bot_notification')
    
    print("-" * 60)
    print("-                 Push Point Taiko Blazer                  -")
    print("-" * 60)
    
    num_wallets = int(input("Enter the number of wallets: "))
    wallets = []
    
    for i in range(num_wallets):
        while True:
            print(f"- Wallet {i+1} -")
            address_input = input(f"Enter wallet address {i+1}: ")
            private_key = input(f"Enter private key {i+1}: ")
            print(f"Wallet address {i+1}: {address_input}")
            print(f"Private key {i+1}: {private_key}")
            confirm = input("Is this information correct? (y/n): ").strip().lower()
            if confirm == 'y':
                wallets.append((Web3.to_checksum_address(address_input), private_key))
                clear(f"Enter wallet address {i+1}: {address_input}", 0.1)
                clear(f"Enter private key {i+1}: {private_key}", 0.1)
                break
            else:
                print("Please re-enter the wallet information.")
    
    print("-" * 60)
    print("-                     Select Operation Mode                -")
    print("-            1. Send Message          2. Init              -")
    print("-            3. ProcessMessage        4. Random            -")
    print("-" * 60)
    
    session = PromptSession()
    mode_choice = int(await session.prompt_async("Enter Mode (1-4): ", validator=NumberValidator()))
    num_txs = int(input("Enter the number of transactions ( e.g., 100): "))
    
    while True:
        try:
            min_delay, max_delay = map(int, input("Enter the delay range per transaction (e.g., 20-60): ").split('-'))
            if min_delay < 0 or max_delay < 0 or min_delay > max_delay:
                raise ValueError
            break
        except ValueError:
            print("Invalid input. Please enter a valid delay range (e.g., 20-60).")
    
    gwei_input = float(input("Enter the gwei value for the transaction (e.g., 0.1): "))
    
    print(f'{Fore.MAGENTA}[Transaction Info]{Fore.RESET} Push Point Taiko Blazer Mode: {Fore.LIGHTBLUE_EX}{mode(mode_choice)}{Fore.RESET} | {Fore.BLUE}{num_txs}{Fore.RESET} tx')
    print(f'{Fore.RESET}-' * 60)
    
    day = 0
    stop_process = False
    
    while not stop_process:
        now = datetime.datetime.now(pytz.timezone('Asia/Jakarta'))
        date = now.strftime("%d-%m-%Y")
        time = now.strftime("%H:%M:%S")
        
        all_addresses = []
        
        for account_address, private_key in wallets:
            initial_balance = balance(taiko_url, account_address)
            all_addresses.append(f"Address: {account_address}\nYour Balance: {initial_balance}\nDate: {date}\nTime: {time}")
            
            if notif:
                await send_message(token, chat_id, f'[INFO] Transactions will soon be executed for wallet: {account_address}\nDate: {date}\nTime: {time}')
            
            tx_counter = 0  # Reset transaction counter for each wallet
            
            for i in range(num_txs):
                if tx_counter >= 150:
                    print(f"{Fore.YELLOW}[INFO]{Fore.RESET} Daily transaction limit of 150 reached for wallet {account_address}.")
                    break
                
                randomDelay = round(random.uniform(min_delay, max_delay))
                mode_c = random.choice([1, 2, 3]) if mode_choice == 4 else mode_choice
                
                if i == 0:
                    print(f'{msgtypeTX(mode_c, i+1)}')
                
                success = await prosesTX(taiko_url, account_address, private_key, gwei_input, mode_c, 3, token, chat_id)
                if not success:
                    stop_process = True
                    break
                
                tx_counter += 1
                
                if tx_counter % 10 == 0:
                    final_balance = balance(taiko_url, account_address)
                    usage = float(initial_balance.split()[0]) - float(final_balance.split()[0])
                    formatted_usage = "{:.6f}".format(usage)
                    eth_price = get_eth_price_in_usd()
                    if eth_price is not None:
                        usd_value = Decimal(usage) * Decimal(eth_price)
                        formatted_usd_value = "{:.2f}".format(usd_value)
                    else:
                        formatted_usd_value = "N/A"
                    if notif:
                        await send_message(token, chat_id, f'[INFO] {tx_counter} Transactions Have Been Processed for Address: {account_address}.\nInitial Balance: {initial_balance}\nFinal Balance: {final_balance}\nBalance Used: {formatted_usage} ETH (${formatted_usd_value} USD)')
                
                if i == num_txs - 1:
                    l = True
                    sleep(0.1)
                    print(f'-' * 73)
                    print(f"{Fore.YELLOW}[INFO]{Fore.RESET} Transaction Process of {num_txs} Times Completed")
                else:
                    with Loader(f"Please Wait {randomDelay} Seconds..", f"{Fore.YELLOW}[INFO] {Fore.RESET}Wait time of {randomDelay} Seconds Reached. \n{Fore.RESET}{'-' * 73}\n{msgtypeTX(mode_c, i+2)}"):
                        sleep(randomDelay)
                        print(f"{Fore.YELLOW}[INFO]{Fore.RESET} Processing Next Transaction")
                    sleep(3)
            
            if l or tx_counter >= 150:
                final_balance = balance(taiko_url, account_address)
                usage = float(initial_balance.split()[0]) - float(final_balance.split()[0])
                formatted_usage = "{:.6f}".format(usage)
                eth_price = get_eth_price_in_usd()
                if eth_price is not None:
                    usd_value = Decimal(usage) * Decimal(eth_price)
                    formatted_usd_value = "{:.2f}".format(usd_value)
                else:
                    formatted_usd_value = "N/A"
                now = datetime.datetime.now(pytz.timezone('Asia/Jakarta'))
                date = now.strftime("%d-%m-%Y")
                time = now.strftime("%H:%M:%S")
                print(f'The process will be carried out automatically tomorrow, thank you..\n{Fore.YELLOW}[Transaction Info]{Fore.RESET}Remaining Balance: {final_balance}\nTo Stop the Process Press CTRL+C')
                if notif:
                    await send_message(token, chat_id, f'[Transaction Info] The process of {num_txs} transactions has been completed.\nInitial Balance: {initial_balance}\nFinal Balance: {final_balance}\nETH Fee Used: {formatted_usage} ETH (${formatted_usd_value} USD)\nDate: {date}\nTime: {time}\nWill Continue Automatically Tomorrow, Thank You..')
                l = False
                print(f'-' * 73)
                tx_counter = 0
        
        if notif and all_addresses:
            await send_message(token, chat_id, f'Info: {day+1}\n' + '\n\n'.join(all_addresses))
        
        if stop_process:
            break
        
        await asyncio.sleep(24*60*60)
        day += 1

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(main())
    else:
        asyncio.run(main())
