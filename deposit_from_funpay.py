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
    await page.goto(f"{FUNPAY_URL}/account/balance", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    
    content = await page.content()
    return "Вход" not in content and "/account/login" not in page.url

async def withdraw_funds(
    payment_method: str,
    card_number: Optional[str] = None,
    spb_bank: Optional[str] = None,
    phone: Optional[str] = None,
    amount: float = 0,
    headless: bool = False
) -> dict:
    browser = None
    playwright = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        await load_cookies(context)
        
        await page.goto(f"{FUNPAY_URL}/account/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        if not await is_logged_in(page):
            await browser.close()
            await playwright.stop()
            return {"success": False, "error": "Не авторизован. Проверь cookies."}
        
        await page.goto(f"{FUNPAY_URL}/account/balance", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        print(f"Страница загружена")
        
        await page.click('.withdraw')
        await page.wait_for_timeout(1000)
        
        modal = page.locator('.modal-content:has(.withdraw-box)')
        if await modal.is_visible():
            print(f"Модальное окно открыто")
        else:
            print(f"Модальное окно НЕ открыто")
        
        await page.select_option('.modal .withdraw-box select[name="currency_id"]', 'rub', force=True)
        await page.wait_for_timeout(500)
        
        if payment_method == "card":
            await page.select_option('.modal .withdraw-box select[name="ext_currency_id"]', 'card_rub', force=True)
            await page.wait_for_timeout(1000)
            print(f"Выбран способ: Карта")
        else:
            await page.select_option('.modal .withdraw-box select[name="ext_currency_id"]', 'fps', force=True)
            
            await page.evaluate("""
                const select = document.querySelector('.modal .withdraw-box select[name="ext_currency_id"]');
                if (select) {
                    select.value = 'fps';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """)
            await page.wait_for_timeout(2000)
            print(f"Выбран способ: СБП")
            
            await page.evaluate(f"""
                const bankSelect = document.querySelector('.modal .withdraw-box select[name="wallet_extra"]');
                if (bankSelect) {{
                    bankSelect.value = '{spb_bank}';
                    bankSelect.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            """)
            await page.wait_for_timeout(1500)
            print(f"Выбран банк: {spb_bank}")
            
            await page.evaluate(f"""
                const walletInput = document.querySelector('.modal .withdraw-box input[name="wallet"]');
                if (walletInput) {{
                    walletInput.value = '{phone}';
                    walletInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    walletInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            """)
            await page.wait_for_timeout(500)
            print(f"Введён телефон: {phone}")
        
        wallet_input = page.locator('.modal .withdraw-box input[name="wallet"]')
        if payment_method == "card":
            await wallet_input.fill(card_number or "")
            await page.wait_for_timeout(500)
            print(f"Введён номер карты: {card_number}")
        
        await page.wait_for_timeout(500)
        amount_input = page.locator('.modal .withdraw-box input[name="amount_ext"]')
        await amount_input.wait_for(state="visible", timeout=5000)
        await amount_input.fill(str(amount))
        await page.wait_for_timeout(500)
        print(f"Введена сумма к получению: {amount}")
        
        submit_btn = page.locator('.modal .withdraw-box .btn.btn-primary')
        if await submit_btn.is_visible():
            await submit_btn.click()
            print(f"Форма отправлена, ожидание кода 2FA...")
            await page.wait_for_timeout(2000)
            
            twofa_input = page.locator('.modal input[name="twofactor_code"]')
            if await twofa_input.is_visible(timeout=5000):
                code = input("Введите 6-значный код 2FA: ")
                await twofa_input.fill(code)
                await page.wait_for_timeout(1000)
                await submit_btn.click()
                print(f"Код 2FA введён")
            
            await page.wait_for_timeout(3000)
        
        await browser.close()
        await playwright.stop()
        
        return {"success": True}
        
    except Exception as e:
        browser_local = None
        playwright_local = None
        try:
            browser_local = browser
            if browser_local and browser_local.is_connected():
                await browser_local.close()
        except:
            pass
        try:
            playwright_local = playwright
            if playwright_local:
                await playwright_local.stop()
        except:
            pass
        return {"success": False, "error": str(e)}

def deposit_from_funpay(
    order_id: str,
    payment_method: str,
    card_number: Optional[str] = None,
    spb_bank: Optional[str] = None,
    phone: Optional[str] = None,
    amount: float = 0,
    headless: bool = False
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
        amount=amount,
        headless=headless
    ))
    
    return result
