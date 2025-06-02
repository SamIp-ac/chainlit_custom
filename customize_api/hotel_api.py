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

def get_hotels(city_name: str, check_in: date, check_out: date, rooms: int = 1, adults: int = 2, children: int = 0) -> List[HotelInfo]:
    # Convert city name to English and lowercase
    city_english = chinese_to_english(city_name).lower()
    
    # Format dates
    check_in_str = check_in.strftime("%Y%m%d")
    check_out_str = check_out.strftime("%Y%m%d")
    
    # Build base URL
    base_url = f"https://www.kkday.com/zh-tw/category/{city_english}/accommodation/list/"
    
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

    hotels = []
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
            url = f"{base_url}?currency=HKD&sort=hotel&check_in={check_in_str}&check_out={check_out_str}&rooms={rooms}&adults={adults}&children={children}&page={page}"
            print(f"Scraping page {page}...")
            
            browser.get(url)
            time.sleep(get_random_delay())
            
            # Wait for hotel list to load
            wait = WebDriverWait(browser, 20)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
            except:
                print(f"No more hotels found on page {page}")
                break
            
            # Get all hotels
            hotel_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
            
            if not hotel_elements:
                print(f"No hotels found on page {page}")
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
                
            for hotel in hotel_elements:
                try:
                    # Get hotel name
                    name_element = hotel.find_element(By.CSS_SELECTOR, "span.product-listview__name")
                    name = name_element.text.strip()
                    
                    # Get description
                    description_element = hotel.find_element(By.CSS_SELECTOR, "p.description")
                    description = description_element.text.strip()
                    
                    # Get price
                    price_element = hotel.find_element(By.CSS_SELECTOR, "div.kk-price-local__normal")
                    price = f"HKD{price_element.text.strip()}"
                    
                    hotels.append(HotelInfo(
                        name=name,
                        description=description,
                        price=price
                    ))
                    
                except Exception as e:
                    print(f"Error processing hotel: {e}")
                    continue
            
            page += 1
            time.sleep(get_random_delay())
            
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

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005) 