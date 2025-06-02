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

class CityInfo(BaseModel):
    name: str
    id: str
    country: str

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
    # Convert to lowercase
    city = city_name.lower()
    # Remove extra spaces
    city = ' '.join(city.split())
    # Remove special characters except spaces and hyphens
    city = re.sub(r'[^a-z0-9\s-]', '', city)
    return city

def get_country_code(city_name: str, city_mapping: dict) -> str:
    """Get country code for a city with improved matching"""
    normalized_city = normalize_city_name(city_name)
    
    # First try exact match
    for country, cities in city_mapping.items():
        for city, code in cities.items():
            if normalize_city_name(city) == normalized_city:
                return code
    
    # If no exact match, try partial match
    for country, cities in city_mapping.items():
        for city, code in cities.items():
            normalized_mapping_city = normalize_city_name(city)
            # Check if the normalized city name is contained in any mapping city
            if normalized_city in normalized_mapping_city or normalized_mapping_city in normalized_city:
                return code
    
    return None

def get_hotels(city_name: str, check_in: date, check_out: date, rooms: int = 1, adults: int = 2, children: int = 0) -> List[HotelInfo]:
    # Load city mapping
    city_mapping = load_city_mapping()
    
    # Convert city name to English and lowercase
    city_english = chinese_to_english(city_name).lower()
    
    # Get country code
    country_code = get_country_code(city_english, city_mapping)
    if not country_code:
        raise HTTPException(status_code=400, detail=f"Unsupported city: {city_name}")
    
    # Format dates
    check_in_str = check_in.strftime("%Y%m%d")
    check_out_str = check_out.strftime("%Y%m%d")
    
    # Build base URL with required parameters
    base_url = f"https://www.kkday.com/zh-tw/category/{country_code}-{city_english}/accommodation/list/"
    
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")
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
            # Required parameters:
            # - currency: 货币类型
            # - sort: 排序方式
            # - check_in: 入住日期
            # - check_out: 退房日期
            # - rooms: 房间数
            # - adults: 成人数量
            url = f"{base_url}?currency=HKD&sort=hotel&check_in={check_in_str}&check_out={check_out_str}&rooms={rooms}&adults={adults}&page={page}&ccy=HKD"
            print(url)
            print(f"Scraping page {page}...")
            
            browser.get(url)
            time.sleep(get_random_delay())
            
            # Wait for hotel list to load
            wait = WebDriverWait(browser, 20)
            try:
                # Wait for the product list container
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
                
                # Wait for dynamic content to load
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.product-listview__name")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.description")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.kk-price-local__normal")))
                
                # Additional wait to ensure content is loaded
                time.sleep(3)
                
                
            except Exception as e:
                print(f"Error waiting for hotel list: {e}")
                break
            
            # Get all hotels
            hotel_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
            print(f"\nFound {len(hotel_elements)} hotel elements")
            
            if not hotel_elements:
                print(f"No hotels found on page {page}")
                break
                
            # Check if reached last page
            is_last_page = False
            try:
                # Get all page numbers using the correct selector
                page_numbers = browser.find_elements(By.CSS_SELECTOR, "ul.pagination li.a-page a")
                if not page_numbers:
                    print("No pagination found, this is the only page")
                    is_last_page = True
                else:
                    last_page = int(page_numbers[-1].text)
                    print(f"Current page: {page}, Last page: {last_page}")
                    
                    if page >= last_page:
                        print("Reached last page")
                        is_last_page = True
                    else:
                        # Find and click the next page button
                        try:
                            # Find the current active page
                            active_page = browser.find_element(By.CSS_SELECTOR, "ul.pagination li.a-page.active")
                            # Get the next page element
                            next_page = active_page.find_element(By.XPATH, "following-sibling::li[contains(@class, 'a-page')]")
                            next_page_button = next_page.find_element(By.TAG_NAME, "a")
                            
                            # Scroll to the button
                            browser.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                            time.sleep(1)
                            
                            # Click the button
                            next_page_button.click()
                            time.sleep(get_random_delay())
                            print(f"Clicked next page button to page {page + 1}")
                            
                            # Wait for the new page to load and elements to be refreshed
                            wait.until(EC.staleness_of(active_page))
                            time.sleep(2)  # Additional wait for content to load
                            
                            # Wait for the new page's hotel list to be visible
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.product-listview__name")))
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.description")))
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.kk-price-local__normal")))
                            
                            # Re-fetch hotel elements after page load
                            hotel_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
                            print(f"\nFound {len(hotel_elements)} hotel elements on new page")
                            
                            # Clear existing hotels list to avoid duplicates
                            hotels = []
                            
                        except Exception as e:
                            print(f"Error clicking next page button: {e}")
                            is_last_page = True
                    
            except Exception as e:
                print(f"Error checking pagination: {e}")
                is_last_page = True
                
            # Process hotels only if we have elements
            if hotel_elements:
                for index, hotel in enumerate(hotel_elements, 1):
                    try:
                        print(f"\nProcessing hotel {index}...")
                        
                        # Re-fetch the hotel element to avoid stale reference
                        hotel = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")[index-1]
                        
                        # Wait for elements to be visible
                        wait.until(EC.visibility_of(hotel))
                        
                        # Get hotel name
                        try:
                            # Try different selectors for name
                            name_selectors = [
                                "span.product-listview__name",
                                "h3 span.product-listview__name",
                                "div.product-detail h3 span"
                            ]
                            name = None
                            for selector in name_selectors:
                                try:
                                    name_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                    name = name_element.text.strip()
                                    if name:
                                        print(f"Found name using selector {selector}: {name}")
                                        break
                                except:
                                    continue
                            
                            if not name:
                                raise Exception("Could not find hotel name with any selector")
                                
                        except Exception as e:
                            print(f"Error getting name: {e}")
                            print("Available elements in hotel:")
                            for element in hotel.find_elements(By.CSS_SELECTOR, "*"):
                                print(f"Tag: {element.tag_name}, Class: {element.get_attribute('class')}")
                            continue
                        
                        # Get description
                        try:
                            # Try different selectors for description
                            desc_selectors = [
                                "p.description",
                                "div.product-detail p.description",
                                "div.product-listview__description"
                            ]
                            description = None
                            for selector in desc_selectors:
                                try:
                                    desc_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                    description = desc_element.text.strip()
                                    if description:
                                        print(f"Found description using selector {selector}: {description}")
                                        break
                                except:
                                    continue
                            
                            if not description:
                                raise Exception("Could not find hotel description with any selector")
                                
                        except Exception as e:
                            print(f"Error getting description: {e}")
                            continue
                        
                        # Get price
                        try:
                            # Try different selectors for price
                            price_selectors = [
                                "div.kk-price-local__normal",
                                "div.product-pricing div.kk-price-local__normal",
                                "div.product-footer div.kk-price-local__normal"
                            ]
                            price = None
                            for selector in price_selectors:
                                try:
                                    price_element = hotel.find_element(By.CSS_SELECTOR, selector)
                                    price_text = price_element.text.strip()
                                    if price_text:
                                        price = f"HKD{price_text}"
                                        print(f"Found price using selector {selector}: {price}")
                                        break
                                except:
                                    continue
                            
                            if not price:
                                raise Exception("Could not find hotel price with any selector")
                                
                        except Exception as e:
                            print(f"Error getting price: {e}")
                            continue
                        
                        print("Successfully processed hotel")
                        hotels.append(HotelInfo(
                            name=name,
                            description=description,
                            price=price
                        ))
                        
                    except Exception as e:
                        print(f"Error processing hotel: {e}")
                        continue
            
            print(f"\nTotal hotels found so far: {len(hotels)}")
            
            # Break after processing all elements on the last page
            if is_last_page:
                print("Finished processing last page")
                break
                
            page += 1
            time.sleep(get_random_delay())
            
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'browser' in locals():
            browser.quit()
    
    print(hotels)
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

def get_city_id(city_name: str) -> Optional[str]:
    """Get city ID from KKday website"""
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
    
    try:
        browser = webdriver.Chrome(options=chrome_options)
        browser.get("https://www.kkday.com/zh-tw/category/1/accommodation/list/")
        time.sleep(2)
        
        # Wait for city selection to load
        wait = WebDriverWait(browser, 20)
        city_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.location-item")))
        
        for element in city_elements:
            try:
                name = element.find_element(By.CSS_SELECTOR, "span.location-name").text
                if city_name.lower() in name.lower():
                    city_id = element.get_attribute("data-id")
                    return city_id
            except:
                continue
                
    except Exception as e:
        print(f"Error getting city ID: {e}")
    finally:
        if 'browser' in locals():
            browser.quit()
    
    return None

@app.get("/cities", response_model=List[CityInfo])
async def list_cities():
    """List all available cities with their IDs"""
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
    
    cities = []
    try:
        browser = webdriver.Chrome(options=chrome_options)
        browser.get("https://www.kkday.com/zh-tw/category/1/accommodation/list/")
        time.sleep(2)
        
        # Wait for city selection to load
        wait = WebDriverWait(browser, 20)
        city_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.location-item")))
        
        for element in city_elements:
            try:
                name = element.find_element(By.CSS_SELECTOR, "span.location-name").text
                city_id = element.get_attribute("data-id")
                country = element.find_element(By.CSS_SELECTOR, "span.location-country").text
                
                cities.append(CityInfo(
                    name=name,
                    id=city_id,
                    country=country
                ))
            except:
                continue
                
    except Exception as e:
        print(f"Error listing cities: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'browser' in locals():
            browser.quit()
    
    return cities

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005) 