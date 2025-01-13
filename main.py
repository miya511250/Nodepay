import requests as reqs
import asyncio
import aiohttp
import time
import uuid
from curl_cffi import requests
from loguru import logger
from colorama import Fore, Style, init

# Constants
PING_INTERVAL = 60
RETRIES = 60
TOKEN_FILE = 'token.txt'
PROXY_FILE = 'proxy.txt'
DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": "https://nw.nodepay.org/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}  

def uuidv4():
    return str(uuid.uuid4())

def show_copyright():
    banner = """
    ╔═══════════════════════════════════════╗
    ║           NodePay Client              ║
    ╚═══════════════════════════════════════╝
    """
    print(Fore.MAGENTA + Style.BRIGHT + banner + Style.RESET_ALL)
        
def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp
    
async def render_profile_info(proxy, token):
    global browser_id, account_info

    try:
        np_session_info = load_session_info(proxy)

        if not np_session_info:
            browser_id = uuidv4()
            response = await call_api(DOMAIN_API["SESSION"], {}, proxy, token)
            logger.debug(f"API Response: {response}")
            valid_resp(response)
            
            if response and "data" in response and response["data"]:
                account_info = response["data"]
                logger.debug(f"Account Info: {account_info}")
                if account_info.get("uid"):
                    save_session_info(proxy, account_info)
                    await start_ping(proxy, token)
                else:
                    logger.error(f"No UID found in account info: {account_info}")
                    handle_logout(proxy)
            else:
                logger.error(f"Invalid response structure: {response}")
                handle_logout(proxy)
        else:
            account_info = np_session_info
            await start_ping(proxy, token)
    except Exception as e:
        logger.error(f"代理 {proxy} 配置信息处理错误: {e}")
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            logger.info(f"移除错误代理: {proxy}")
            remove_proxy_from_list(proxy)
            return None
        else:
            logger.error(f"连接错误: {e}")
            return proxy

async def call_api(url, data, proxy, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        response = requests.post(url, json=data, headers=headers, impersonate="safari15_5", proxies={
                                "http": proxy, "https": proxy}, timeout=15)

        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(proxy, token):
    try:
        while True:
            await ping(proxy, token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task for proxy {proxy} was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping for proxy {proxy}: {e}")
        
def get_proxy_ip(proxy_string):
    """Extract only the IP address from proxy string."""
    try:
        # 处理形如 http://user:pass@ip:port 的代理字符串
        if '@' in proxy_string:
            ip = proxy_string.split('@')[1].split(':')[0]
        else:
            # 处理形如 ip:port 的代理字符串
            ip = proxy_string.split(':')[0]
        return ip
    except:
        return proxy_string

async def ping(proxy, token):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()

    if proxy in last_ping_time and (current_time - last_ping_time[proxy]) < PING_INTERVAL:
        return

    last_ping_time[proxy] = current_time

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,  
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, proxy, token)
        if response["code"] == 0:
            ip_score = response.get("data", {}).get("ip_score", 0)
            logger.info(f"Ping成功, token后8位:{token[-8:]}, 代理:{get_proxy_ip(proxy)}, IP分数:{ip_score}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except Exception as e:
        handle_ping_fail(proxy, None)

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)
    logger.info(f"Logged out and cleared session info for proxy {proxy}")

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        raise SystemExit("Exiting due to failure in loading proxies")

def save_status(proxy, status):
    pass  

def save_session_info(proxy, data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id  
    }
    pass

def load_session_info(proxy):
    return {}  

def is_valid_proxy(proxy):
    return True  

def remove_proxy_from_list(proxy):
    pass  
    
def load_tokens_from_file(filename):
    try:
        with open(filename, 'r') as file:
            tokens = file.read().splitlines()
        return tokens
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        raise SystemExit("Exiting due to failure in loading tokens")
        
async def main():
    all_proxies = load_proxies(PROXY_FILE)  
    tokens = load_tokens_from_file(TOKEN_FILE)
    
    if not tokens:
        print("Token cannot be empty. Exiting the program.")
        exit()
    if not all_proxies:
        print("Proxies cannot be empty. Exiting the program.")
        exit()

    # 确保代理和token数量匹配，创建一一对应的配对
    min_length = min(len(all_proxies), len(tokens))
    proxy_token_pairs = list(zip(all_proxies[:min_length], tokens[:min_length]))
    
    while True:
        tasks = []
        # 为每个配对创建一个任务
        for proxy, token in proxy_token_pairs:
            if is_valid_proxy(proxy):
                task = asyncio.create_task(render_profile_info(proxy, token))
                tasks.append(task)
        
        if tasks:
            # 等待所有任务完成或有任务完成
            done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            
            # 处理完成的任务
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(f"Task failed: {e}")
        
        await asyncio.sleep(3)

if __name__ == '__main__':
    show_copyright()
    print("\nwelcome to main script...")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
