# uvicorn hotel_api:app --reload --host 0.0.0.0 --port 8005
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
import json
import re

app = FastAPI(
    title="KKday Hotel API",
    description="API for checking KKday hotel information",
    version="1.0.0"
)

class HotelInfo(BaseModel):
    name: str
    description: str
    price: str

class HotelResponse(BaseModel):
    hotels: List[HotelInfo]
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

def load_city_mapping():
    """Load city to country code mapping from JSON file"""
    try:
        with open('assets/city_country_mapping.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading city mapping: {e}")
        return {}

def normalize_city_name(city_name: str) -> str:
    """Normalize city name for matching"""
    city = city_name.lower()
    city = ' '.join(city.split())
    city = re.sub(r'[^a-z0-9\s-]', '', city)
    return city

def get_country_code(city_name: str, city_mapping: dict) -> str:
    """Get country code for a city with improved matching"""
    normalized_city = normalize_city_name(city_name)
    
    for country, cities in city_mapping.items():
        for city, code in cities.items():
            if normalize_city_name(city) == normalized_city:
                return code
    
    for country, cities in city_mapping.items():
        for city, code in cities.items():
            normalized_mapping_city = normalize_city_name(city)
            if normalized_city in normalized_mapping_city or normalized_mapping_city in normalized_city:
                return code
    
    return None

def get_hotels(city_name: str, check_in: date, check_out: date, rooms: int = 1, adults: int = 2, children: int = 0) -> List[HotelInfo]:
    city_mapping = load_city_mapping()
    city_english = chinese_to_english(city_name).lower()
    country_code = get_country_code(city_english, city_mapping)
    
    if not country_code:
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city_name}")
    
    check_in_str = check_in.strftime("%Y%m%d")
    check_out_str = check_out.strftime("%Y%m%d")
    base_url = f"https://www.kkday.com/zh-tw/category/{country_code}-{city_english}/accommodation/list/"
    
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
    
    for key, value in headers.items():
        chrome_options.add_argument(f'--header={key}: {value}')

    hotels = []
    max_pages = 3
    
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
        url = f"{base_url}?currency=HKD&sort=hotel&check_in={check_in_str}&check_out={check_out_str}&rooms={rooms}&adults={adults}&ccy=HKD"
        print(f"Initial URL: {url}")
        browser.get(url)
        time.sleep(get_random_delay())
        
        wait = WebDriverWait(browser, 20)
        
        for _ in range(max_pages):
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.product-listview__name")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.description")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.kk-price-local__normal")))
                time.sleep(3)
                
                hotel_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
                print(f"\nFound {len(hotel_elements)} hotel elements")
                
                if not hotel_elements:
                    print("No hotels found on this page")
                    break
                    
                # Process hotels on current page
                for index, hotel in enumerate(hotel_elements, 1):
                    try:
                        print(f"\nProcessing hotel {index}...")
                        hotel = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")[index-1]
                        wait.until(EC.visibility_of(hotel))
                        
                        # Get hotel name
                        name = None
                        for selector in ["span.product-listview__name", "h3 span.product-listview__name", "div.product-detail h3 span"]:
                            try:
                                name_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                name = name_element.text.strip()
                                if name:
                                    print(f"Found name: {name}")
                                    break
                            except:
                                continue
                        if not name:
                            continue
                            
                        # Get description
                        description = None
                        for selector in ["p.description", "div.product-detail p.description", "div.product-listview__description"]:
                            try:
                                desc_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                description = desc_element.text.strip()
                                if description:
                                    break
                            except:
                                continue
                        if not description:
                            continue
                            
                        # Get price
                        price = None
                        for selector in ["div.kk-price-local__normal", "div.product-pricing div.kk-price-local__normal", "div.product-footer div.kk-price-local__normal"]:
                            try:
                                price_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                price_text = price_element.text.strip()
                                if price_text:
                                    price = f"HKD{price_text}"
                                    break
                            except:
                                continue
                        if not price:
                            continue
                            
                        hotels.append(HotelInfo(
                            name=name,
                            description=description,
                            price=price
                        ))
                        
                    except Exception as e:
                        print(f"Error processing hotel: {e}")
                        continue
                
                print(f"\nTotal hotels found so far: {len(hotels)}")
                
                # Check pagination and click next page if available
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
    
    return hotels

class HotelRequest(BaseModel):
    city_name: str
    check_in: date
    check_out: date
    rooms: Optional[int] = 1
    adults: Optional[int] = 2
    children: Optional[int] = 0

@app.post("/hotels", response_model=HotelResponse)
async def get_city_hotels(request: HotelRequest):
    try:
        hotels = get_hotels(
            city_name=request.city_name,
            check_in=request.check_in,
            check_out=request.check_out,
            rooms=request.rooms,
            adults=request.adults,
            children=request.children
        )
        return HotelResponse(
            hotels=hotels,
            total_count=len(hotels)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)