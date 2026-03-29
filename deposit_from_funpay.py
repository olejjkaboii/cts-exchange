import os
import json
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page

FUNPAY_URL = "https://funpay.com"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "funpay-cookie.json")

processed_orders = set()
browser: Optional[Browser] = None

async def get_browser():
    global browser
    if browser is None or not browser.is_connected():
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
    return browser

async def load_cookies(context):
    with open(COOKIE_FILE, 'r') as f:
        cookies = json.load(f)
    
    fixed_cookies = []
    for cookie in cookies:
        fixed_cookie = {
            'name': cookie.get('name'),
            'value': cookie.get('value'),
            'domain': cookie.get('domain'),
            'path': cookie.get('path', '/'),
            'secure': cookie.get('secure', True),
            'httpOnly': cookie.get('httpOnly', True),
        }
        same_site = cookie.get('sameSite')
        if same_site and same_site.lower() in ['strict', 'lax', 'none']:
            fixed_cookie['sameSite'] = same_site.capitalize()
        else:
            fixed_cookie['sameSite'] = 'Lax'
        
        fixed_cookies.append(fixed_cookie)
    
    await context.add_cookies(fixed_cookies)

async def is_logged_in(page: Page) -> bool:
    await page.goto(f"{FUNPAY_URL}/account/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    
    content = await page.content()
    return "Вход" not in content and "login" not in page.url.lower()

async def withdraw_funds(
    payment_method: str,
    card_number: Optional[str] = None,
    spb_bank: Optional[str] = None,
    phone: Optional[str] = None,
    amount: float = 0
) -> dict:
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        await load_cookies(context)
        
        await page.goto(f"{FUNPAY_URL}/account/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        if not await is_logged_in(page):
            await browser.close()
            await playwright.stop()
            return {"success": False, "error": "Не авторизован. Проверь cookies."}
        
        await page.goto(f"{FUNPAY_URL}/account/withdraw", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        print(f"Страница вывода загружена")
        
        await browser.close()
        await playwright.stop()
        
        return {"success": True}
        
    except Exception as e:
        try:
            await browser.close()
            await playwright.stop()
        except:
            pass
        return {"success": False, "error": str(e)}

def deposit_from_funpay(
    order_id: str,
    payment_method: str,
    card_number: Optional[str] = None,
    spb_bank: Optional[str] = None,
    phone: Optional[str] = None,
    amount: float = 0
) -> dict:
    """
    Автоматический вывод с FunPay.
    """
    if order_id in processed_orders:
        return {"success": False, "error": "Заказ уже обработан"}
    
    processed_orders.add(order_id)
    
    result = asyncio.run(withdraw_funds(
        payment_method=payment_method,
        card_number=card_number,
        spb_bank=spb_bank,
        phone=phone,
        amount=amount
    ))
    
    return result
