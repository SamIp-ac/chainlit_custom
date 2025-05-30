# uvicorn kkday_api:app --reload --host 0.0.0.0 --port 8004
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
    """生成随机延迟时间"""
    return random.uniform(2, 4)

def get_attractions(city_name: str) -> List[AttractionInfo]:
    # 转换城市名为英文并转为小写
    city_english = chinese_to_english(city_name).lower()
    
    # 构建基础URL
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
    
    # 添加所有请求头
    for key, value in headers.items():
        chrome_options.add_argument(f'--header={key}: {value}')

    attractions = []
    page = 1
    
    try:
        browser = webdriver.Chrome(options=chrome_options)
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        while True:
            url = f"{base_url}?currency=HKD&sort=omdesc&page={page}&ccy=HKD"
            print(f"Scraping page {page}...")
            
            browser.get(url)
            time.sleep(get_random_delay())
            
            # 等待产品列表加载
            wait = WebDriverWait(browser, 20)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
            except:
                print(f"No more products found on page {page}")
                break
            
            # 获取所有产品
            products = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
            
            if not products:
                print(f"No products found on page {page}")
                break
                
            # 检查是否到达最后一页
            try:
                # 获取当前页码
                current_page = page
                # 获取所有页码
                page_numbers = browser.find_elements(By.CSS_SELECTOR, "li.a-page a")
                last_page = page_numbers[-1].text
                
                print(f"Current page: {current_page}, Last page: {last_page}")
                
                #if current_page == last_page:
                if current_page==2:
                    print("Reached last page")
                    break
                    
            except Exception as e:
                print(f"Error checking pagination: {e}")
                break
                
            for product in products:
                try:
                    # 获取景点名称
                    name_element = product.find_element(By.CSS_SELECTOR, "span.product-listview__name")
                    name = name_element.text.split(' ')[0]  # 只取中文名称
                    
                    # 获取价格
                    price_element = product.find_element(By.CSS_SELECTOR, "div.kk-price-local__normal")
                    price = f"HKD{price_element.text.strip()}"
                    
                    attractions.append(AttractionInfo(name=name, price=price))
                    
                except Exception as e:
                    print(f"Error processing product: {e}")
                    continue
            
            page += 1
            time.sleep(get_random_delay())
            
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

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)