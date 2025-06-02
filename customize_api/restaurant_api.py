# uvicorn restaurant_api:app --reload --host 0.0.0.0 --port 8006
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
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
    title="KKday Restaurant API",
    description="API for checking KKday restaurant information",
    version="1.0.0"
)

class RestaurantInfo(BaseModel):
    name: str
    description: str
    price: str

class RestaurantResponse(BaseModel):
    restaurants: List[RestaurantInfo]
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

def get_restaurants(city_name: str) -> List[RestaurantInfo]:
    # Convert city name to English and lowercase
    city_english = chinese_to_english(city_name).lower()
    
    # Build base URL
    base_url = f"https://www.kkday.com/zh-tw/category/{city_english}/restaurants/list/"
    
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

    restaurants = []
    page = 1
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
        
        while page <= max_pages:
            url = f"{base_url}?currency=HKD&sort=omdesc&page={page}"
            print(f"Scraping page {page}...")
            
            browser.get(url)
            time.sleep(get_random_delay())
            
            # Wait for restaurant list to load
            wait = WebDriverWait(browser, 20)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
            except:
                print(f"No more restaurants found on page {page}")
                break
            
            # Get all restaurants
            restaurant_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
            
            if not restaurant_elements:
                print(f"No restaurants found on page {page}")
                break
                
            # Check if reached last page
            try:
                # Get current page number
                current_page = page
                # Get all page numbers
                page_numbers = browser.find_elements(By.CSS_SELECTOR, "li.a-page a")
                last_page = page_numbers[-1].text
                
                print(f"Current page: {current_page}, Last page: {last_page}")
                
                if current_page == last_page:
                    print("Reached last page")
                    break
                    
            except Exception as e:
                print(f"Error checking pagination: {e}")
                break
                
            for restaurant in restaurant_elements:
                try:
                    # Get restaurant name
                    name_element = restaurant.find_element(By.CSS_SELECTOR, "span.product-listview__name")
                    name = name_element.text.strip()
                    
                    # Get description
                    description_element = restaurant.find_element(By.CSS_SELECTOR, "p.description")
                    description = description_element.text.strip()
                    
                    # Get price
                    price_element = restaurant.find_element(By.CSS_SELECTOR, "div.kk-price-local__normal")
                    price = f"HKD{price_element.text.strip()}"
                    
                    restaurants.append(RestaurantInfo(
                        name=name,
                        description=description,
                        price=price
                    ))
                    
                except Exception as e:
                    print(f"Error processing restaurant: {e}")
                    continue
            
            page += 1
            time.sleep(get_random_delay())
            
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'browser' in locals():
            browser.quit()
    
    return restaurants

class RestaurantRequest(BaseModel):
    city_name: str

@app.post("/restaurants", response_model=RestaurantResponse)
async def get_city_restaurants(request: RestaurantRequest):
    try:
        restaurants = get_restaurants(
            city_name=request.city_name
        )
        return RestaurantResponse(
            restaurants=restaurants,
            total_count=len(restaurants)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006) 