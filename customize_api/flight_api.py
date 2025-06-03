# uvicorn flight_api:app --reload --host 0.0.0.0 --port 8002
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional
import json
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from fastapi_mcp import FastApiMCP
from enum import Enum
import requests
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Setup DeepSeek API
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-a194d0c4c5364185ac916b8e19c65566")
if not DEEPSEEK_API_KEY:
    raise ValueError("Please setup DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

settings = {
    "model": "deepseek-chat",
    "temperature": 0,
    "response_format": { "type": "json_object" }  # Force JSON response
}

app = FastAPI(
    title="Flight Price API",
    description="API for checking flight prices between cities",
    version="1.0.0",
    docs_url="/docs",
)

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

class CabinClass(str, Enum):
    ECONOMY = "economy"      # Default cabin class
    PREMIUM = "premium"      # Premium economy
    BUSINESS = "business"    # Business class
    FIRST = "first"         # First class

def get_citycode(cityname):
    """Get city code with intelligent matching using DeepSeek API"""
    with open('assets/cities.json', 'r', encoding='utf-8') as json_file:
        city_data = json.load(json_file)

    # First try direct match
    # citycode = city_data.get(cityname)
    # if citycode:
    #     return citycode

    # If no direct match, use DeepSeek API for intelligent matching
    try:
        # Get an example city code for the prompt
        example_city = next(iter(city_data.items()))
        example_response = json.dumps({"citycode": example_city[1]}, ensure_ascii=False)
        not_found_response = json.dumps({"citycode": "NOT_FOUND"}, ensure_ascii=False)

        # Prepare the prompt for DeepSeek
        messages = [
            {"role": "system", "content": f"""You are a helpful assistant that matches city names to their codes.
            You must ALWAYS respond in JSON format with a single field 'citycode'.
            
            Important matching rules:
            1. If the input contains both country and city (e.g., "日本东京"), extract and match only the city part ("东京")
            2. Match should be case-insensitive
            3. Consider both traditional and simplified Chinese characters
            4. Match partial names if they are unique (e.g., "东京" should match "东京")
            5. If multiple matches exist, choose the most common/popular one
            
            Example responses:
            - For a match: {example_response}
            - For no match: {not_found_response}"""},
            {"role": "user", "content": f"""Given the following city name: "{cityname}", find the most likely matching city code from this list:
            {json.dumps(city_data, ensure_ascii=False, indent=2)}
            
            Matching considerations:
            1. If input contains country name (e.g., "日本东京"), match only the city part ("东京")
            2. Traditional/Simplified Chinese variations
            3. Common abbreviations and alternative names
            4. Common typos and misspellings
            5. Partial matches if they are unique
            
            Return ONLY a JSON object with a single field 'citycode' containing the matched code or 'NOT_FOUND'.
            Example format: {example_response}"""}
        ]

        print(f"Attempting to match city: {cityname}")
        response = client.chat.completions.create(
            messages=messages,
            **settings
        )

        try:
            result = json.loads(response.choices[0].message.content)
            matched_code = result.get('citycode')
            print(f"DeepSeek matched code: {matched_code}")
            
            # Verify the matched code exists in our data
            if matched_code in city_data.values():
                return matched_code
            elif matched_code != 'NOT_FOUND':
                # If DeepSeek returned a code but it's not in our data, try to find the closest match
                for code in city_data.values():
                    if code.lower() in matched_code.lower() or matched_code.lower() in code.lower():
                        return code

            print(f"DeepSeek API matching failed for city: {cityname}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}")
            return None

    except Exception as e:
        print(f"Error in intelligent city matching: {str(e)}")
        return None

def build_kayak_url(origin_code, dest_code, departure_date, return_date=None, 
                   adults=1, students=0, youth=0, children=0, seated_infant=0, lap_infant=0,
                   cabin_class=CabinClass.ECONOMY):
    """
    Build Kayak flight search URL
    
    Passenger types and age requirements:
    - adults: 18+ years old
    - students: 18+ years old with student ID
    - youth: 12-17 years old
    - children: 2-11 years old
    - seated_infant: Under 2 years old, requires seat
    - lap_infant: Under 2 years old, sits on lap
    
    Cabin classes:
    - economy: Economy class (default)
    - premium: Premium economy
    - business: Business class
    - first: First class
    """
    # Base URL
    base_url = "https://www.kayak.com.hk/flights"

    # Build route part
    route = f"{origin_code}-{dest_code}"
    departure_date_str = departure_date.strftime("%Y-%m-%d") if hasattr(departure_date, 'strftime') else departure_date
    
    # Handle return date
    if return_date:
        return_date_str = return_date.strftime("%Y-%m-%d") if hasattr(return_date, 'strftime') else return_date
        date_part = f"{departure_date_str}/{return_date_str}"
    else:
        date_part = departure_date_str

    # Build passenger parts
    passenger_parts = []
    
    # Add cabin class if not economy
    if cabin_class != CabinClass.ECONOMY:
        passenger_parts.append(cabin_class.value)
    
    # Add adults (18+)
    if adults > 0:
        passenger_parts.append(f"{adults}adults")
    
    # Add students (18+ with student ID)
    if students > 0:
        passenger_parts.append(f"{students}students")
    
    # Build children part with age codes
    children_parts = []
    if youth > 0:
        children_parts.extend(['17'] * youth)  # Youth (12-17)
    if children > 0:
        children_parts.extend(['11'] * children)  # Children (2-11)
    if seated_infant > 0:
        children_parts.extend(['1S'] * seated_infant)  # Seated infant
    if lap_infant > 0:
        children_parts.extend(['1L'] * lap_infant)  # Lap infant
    
    if children_parts:
        passenger_parts.append(f"children-{'-'.join(children_parts)}")

    # Combine all passenger parts
    passenger_part = "/".join(passenger_parts)

    # Build query parameters
    query_params = "sort=price_a"

    # Combine complete URL
    return f"{base_url}/{route}/{date_part}/{passenger_part}?{query_params}"

def get_flight_price(origin_city, destination_city, departure_date, return_date=None, adults=1, students=0, youth=0, children=0, seated_infant=0, lap_infant=0, cabin_class=CabinClass.ECONOMY):
    origin_code = get_citycode(origin_city)
    dest_code = get_citycode(destination_city)

    # Build dynamic URL
    url = build_kayak_url(
        origin_code=origin_code,
        dest_code=dest_code,
        departure_date=departure_date,
        return_date=return_date,
        adults=adults,
        students=students,
        youth=youth,
        children=children,
        seated_infant=seated_infant,
        lap_infant=lap_infant,
        cabin_class=cabin_class
    )

    print(url)
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")  # Use new headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--window-size=1920,1080")  # Set window size
    chrome_options.add_argument("--start-maximized")  # Maximize window
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disable automation control features
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Exclude automation switches
    chrome_options.add_experimental_option('useAutomationExtension', False)  # Disable automation extension
    chrome_options.add_argument(f'user-agent={headers["User-Agent"]}')  # Set user agent

    try:
        print('start')
        browser = webdriver.Chrome(options=chrome_options)
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })  # Modify webdriver features
        browser.set_page_load_timeout(10000)
        browser.get(url)

        # Increase wait time to ensure page is fully loaded
        time.sleep(5)  # Add fixed wait time

        wait = WebDriverWait(browser, 200)  # Set reasonable wait time
        
        # First try to find the total price for multiple passengers
        try:
            total_price_element = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.f8F1-multiple-ptc-price-label"))
            )
            price = total_price_element.text.replace("總價HK$", "").replace(",", "").strip()
        except:
            # If total price not found, get the single passenger price
            first_price_element = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.e2GB-price-text"))
            )
            price = first_price_element.text.replace("HK$", "").replace(",", "").strip()

        browser.execute_script("window.stop();")
        browser.quit()  # Close browser
        print(price)
        return price

    except Exception as e:
        print("Not found:", e)
        if 'browser' in locals():
            browser.quit()
        return None

class FlightRequest(BaseModel):
    origin_city: str
    destination_city: str
    departure_date: date
    return_date: Optional[date] = None
    adults: Optional[int] = 1
    students: Optional[int] = 0
    youth: Optional[int] = 0
    children: Optional[int] = 0
    seated_infant: Optional[int] = 0
    lap_infant: Optional[int] = 0
    cabin_class: Optional[CabinClass] = CabinClass.ECONOMY

'''
EXAMPLE:
{
    "origin_city": "香港",
    "destination_city": "东京",
    "departure_date": "2025-07-05",
    "return_date": "2025-07-19",  # Optional
    "adults": 1,                  # 18+ years old
    "students": 1,                # 18+ years old with student ID
    "youth": 1,                   # 12-17 years old (code: 17)
    "children": 1,                # 2-11 years old (code: 11)
    "seated_infant": 1,           # Under 2 years old, requires seat (code: 1S)
    "lap_infant": 1,              # Under 2 years old, sits on lap (code: 1L)
    "cabin_class": "business"     # Optional: economy, premium, business, first
}
'''

@app.post("/flight-price")
async def check_flight_price(request: FlightRequest):
    try:
        price = get_flight_price(
            origin_city=request.origin_city,
            destination_city=request.destination_city,
            departure_date=request.departure_date,
            return_date=request.return_date,
            adults=request.adults,
            students=request.students,
            youth=request.youth,
            children=request.children,
            seated_infant=request.seated_infant,
            lap_infant=request.lap_infant,
            cabin_class=request.cabin_class
        )
        
        if price is None:
            raise HTTPException(status_code=404, detail="Flight price not found")
            
        return {
            "origin": request.origin_city,
            "destination": request.destination_city,
            "departure_date": request.departure_date,
            "return_date": request.return_date,
            "cabin_class": request.cabin_class,
            "price": price
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    # uvicorn flight_api:app --reload --port 8002
    uvicorn.run(app, host="0.0.0.0", port=8002) 