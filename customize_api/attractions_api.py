# uvicorn attractions_api:app --reload --host 0.0.0.0 --port 8004
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import time
import random
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from translate import chinese_to_english
from fastapi_mcp import FastApiMCP

app = FastAPI(
    title="KKday Attraction API",
    description="API for checking KKday attraction ticket information",
    version="1.0.0"
)

class AttractionInfo(BaseModel):
    name: str
    price: str

class AttractionResponse(BaseModel):
    attractions: List[AttractionInfo]
    total_count: int

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

def get_random_delay():
    """Generate random delay time"""
    return random.uniform(2, 4)

def get_attractions(city_name: str) -> List[AttractionInfo]:
    # Convert city name to English and lowercase
    city_english = chinese_to_english(city_name).lower()
    
    # Build base URL
    base_url = f"https://www.kkday.com/zh-tw/category/{city_english}/attraction-tickets/list/"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Add all request headers
    for key, value in headers.items():
        chrome_options.add_argument(f'--header={key}: {value}')

    attractions = []
    max_pages = 3  # Maximum number of pages to scrape
    
    try:
        browser = webdriver.Chrome(options=chrome_options)
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        # Load initial page
        url = f"{base_url}?currency=HKD&sort=omdesc&ccy=HKD"
        browser.get(url)
        time.sleep(get_random_delay())
        
        wait = WebDriverWait(browser, 20)
        
        for _ in range(max_pages):
            try:
                # Wait for products to load
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
                time.sleep(2)  # Additional wait for content to stabilize
                
                # Get all products
                products = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
                
                if not products:
                    print("No products found on this page")
                    break
                    
                # Process products on current page
                for product in products:
                    try:
                        # Get attraction name (Chinese only)
                        name_element = product.find_element(By.CSS_SELECTOR, "span.product-listview__name")
                        name = name_element.text.strip()
                        
                        # Get price
                        price_element = product.find_element(By.CSS_SELECTOR, "div.kk-price-local__normal")
                        price = f"HKD{price_element.text.strip()}"
                        
                        attractions.append(AttractionInfo(name=name, price=price))
                        
                    except Exception as e:
                        print(f"Error processing product: {e}")
                        continue
                
                print(f"Found {len(products)} products on this page")
                
                # Handle pagination
                try:
                    pagination = browser.find_element(By.CSS_SELECTOR, "ul.pagination")
                    active_page = browser.find_element(By.CSS_SELECTOR, "ul.pagination li.a-page.active")
                    next_page = active_page.find_element(By.XPATH, "following-sibling::li[contains(@class, 'a-page')]")
                    
                    if "disabled" not in next_page.get_attribute("class"):
                        next_page_button = next_page.find_element(By.TAG_NAME, "a")
                        browser.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                        time.sleep(1)
                        next_page_button.click()
                        print("Clicked next page button")
                        time.sleep(get_random_delay())
                        wait.until(EC.staleness_of(active_page))
                    else:
                        print("No more pages available")
                        break
                        
                except Exception as e:
                    print(f"Error handling pagination: {e}")
                    break
                    
            except Exception as e:
                print(f"Error processing page: {e}")
                break
                
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'browser' in locals():
            browser.quit()
    
    return attractions

@app.get("/attractions/{city_name}", response_model=AttractionResponse)
async def get_city_attractions(city_name: str):
    try:
        attractions = get_attractions(city_name)
        return AttractionResponse(
            attractions=attractions,
            total_count=len(attractions)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)