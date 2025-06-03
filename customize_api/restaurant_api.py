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
    name: str          # Restaurant name
    description: str   # Restaurant description
    price: str         # Price information

class RestaurantResponse(BaseModel):
    restaurants: List[RestaurantInfo]  # List of restaurants
    total_count: int                   # Total count

# Browser request headers
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
    """Generate random delay time (between 2-4 seconds)"""
    return random.uniform(2, 4)

def get_restaurants(city_name: str) -> List[RestaurantInfo]:
    """Get restaurant information for a specified city
    
    Args:
        city_name: City name (in Chinese)
        
    Returns:
        List of restaurant information
    """
    # Convert Chinese city name to English and lowercase
    city_english = chinese_to_english(city_name).lower()
    
    # Build base URL
    base_url = f"https://www.kkday.com/zh-tw/category/{city_english}/restaurants/list/"
    
    # Configure Chrome browser options
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Add request headers
    for key, value in headers.items():
        chrome_options.add_argument(f'--header={key}: {value}')

    restaurants = []
    max_pages = 3  # Maximum number of pages to scrape
    
    try:
        # Initialize browser
        browser = webdriver.Chrome(options=chrome_options)
        # Hide automation testing features
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
                # Wait for restaurant list to load
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-detail")))
                time.sleep(2)  # Additional wait to ensure content stability
                
                # Get all restaurant elements on current page
                restaurant_elements = browser.find_elements(By.CSS_SELECTOR, "div.product-detail")
                
                if not restaurant_elements:
                    print("No restaurants found on current page")
                    break
                    
                # Process restaurants on current page
                for restaurant in restaurant_elements:
                    try:
                        # Get restaurant name
                        name_element = restaurant.find_element(By.CSS_SELECTOR, "span.product-listview__name")
                        name = name_element.text.strip()
                        
                        # Get restaurant description
                        description_element = restaurant.find_element(By.CSS_SELECTOR, "p.description")
                        description = description_element.text.strip()
                        
                        # Get price information
                        price_element = restaurant.find_element(By.CSS_SELECTOR, "div.kk-price-local__normal")
                        price = f"HKD{price_element.text.strip()}"
                        
                        restaurants.append(RestaurantInfo(
                            name=name,
                            description=description,
                            price=price
                        ))
                        
                    except Exception as e:
                        print(f"Error processing restaurant information: {e}")
                        continue
                
                print(f"Found {len(restaurant_elements)} restaurants on current page")
                
                # Handle pagination
                try:
                    # Locate pagination component
                    pagination = browser.find_element(By.CSS_SELECTOR, "ul.pagination")
                    # Get current active page
                    active_page = browser.find_element(By.CSS_SELECTOR, "ul.pagination li.a-page.active")
                    # Get next page button
                    next_page = active_page.find_element(By.XPATH, "following-sibling::li[contains(@class, 'a-page')]")
                    
                    # Check if next page button is available
                    if "disabled" not in next_page.get_attribute("class"):
                        next_page_button = next_page.find_element(By.TAG_NAME, "a")
                        # Scroll to button position
                        browser.execute_script("arguments[0].scrollIntoView(true);", next_page_button)
                        time.sleep(1)
                        # Click next page
                        next_page_button.click()
                        print("Clicked next page button")
                        time.sleep(get_random_delay())
                        # Wait for page refresh
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
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Ensure browser is closed
        if 'browser' in locals():
            browser.quit()
    
    return restaurants

class RestaurantRequest(BaseModel):
    city_name: str  # Request parameter: city name

@app.post("/restaurants", response_model=RestaurantResponse, summary="Get city restaurant list")
async def get_city_restaurants(request: RestaurantRequest):
    """Get KKday restaurant list by city name
    
    Args:
        - city_name: City name in Chinese (e.g., "Taipei")
        
    Returns:
        - Response object containing restaurant list and total count
    """
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

# Mount MCP monitoring
mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)