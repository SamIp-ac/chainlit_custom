# uvicorn flight_api:app --reload --host 0.0.0.0 --port 8002
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional, List
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
            6. If no match is found in the provided data, use your knowledge to provide the most likely IATA city code
            
            Example responses:
            - For a match: {example_response}
            - For no match but you know the code: {{"citycode": "LHR"}}  # Example for London Heathrow
            - For no match and unknown: {not_found_response}"""},
            {"role": "user", "content": f"""Given the following city name: "{cityname}", find the most likely matching city code from this list:
            {json.dumps(city_data, ensure_ascii=False, indent=2)}
            
            Matching considerations:
            1. If input contains country name (e.g., "日本东京"), match only the city part ("东京")
            2. Traditional/Simplified Chinese variations
            3. Common abbreviations and alternative names
            4. Common typos and misspellings
            5. Partial matches if they are unique
            6. If no match is found in the data, use your knowledge to provide the most likely IATA city code
            
            Return ONLY a JSON object with a single field 'citycode' containing the matched code or your best guess.
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
                # If no close match found but DeepSeek provided a code, use it
                return matched_code

            print(f"DeepSeek API matching failed for city: {cityname}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}")
            return None

    except Exception as e:
        print(f"Error in intelligent city matching: {str(e)}")
        return None

def get_airlinecode(airline_name):
    """Get airline code with intelligent matching using DeepSeek API"""
    with open('assets/airline.json', 'r', encoding='utf-8') as json_file:
        airline_data = json.load(json_file)

    try:
        # Get an example airline code for the prompt
        example_airline = next(iter(airline_data.items()))
        example_response = json.dumps({"airlinecode": example_airline[1]}, ensure_ascii=False)
        not_found_response = json.dumps({"airlinecode": "NOT_FOUND"}, ensure_ascii=False)

        # Prepare the prompt for DeepSeek
        messages = [
            {"role": "system", "content": f"""You are a helpful assistant that matches airline names to their codes.
            You must ALWAYS respond in JSON format with a single field 'airlinecode'.
            
            Important matching rules:
            1. Match should be case-insensitive
            2. Consider both traditional and simplified Chinese characters
            3. Match partial names if they are unique
            4. If multiple matches exist, choose the most common/popular one
            5. For multiple airlines, return a comma-separated list of codes
            6. If no match is found in the provided data, use your knowledge to provide the most likely IATA airline code
            
            Example responses:
            - For a match: {example_response}
            - For no match but you know the code: {{"airlinecode": "BA"}}  # Example for British Airways
            - For no match and unknown: {not_found_response}"""},
            {"role": "user", "content": f"""Given the following airline name(s): "{airline_name}", find the most likely matching airline code(s) from this list:
            {json.dumps(airline_data, ensure_ascii=False, indent=2)}
            
            Matching considerations:
            1. Traditional/Simplified Chinese variations
            2. Common abbreviations and alternative names
            3. Common typos and misspellings
            4. Partial matches if they are unique
            5. For multiple airlines, return comma-separated codes
            6. If no match is found in the data, use your knowledge to provide the most likely IATA airline code
            
            Return ONLY a JSON object with a single field 'airlinecode' containing the matched code(s) or your best guess.
            Example format: {example_response}"""}
        ]

        print(f"Attempting to match airline: {airline_name}")
        response = client.chat.completions.create(
            messages=messages,
            **settings
        )

        try:
            result = json.loads(response.choices[0].message.content)
            matched_codes = result.get('airlinecode')
            print(f"DeepSeek matched code(s): {matched_codes}")
            
            if matched_codes == 'NOT_FOUND':
                return None
                
            # Split multiple codes if present
            codes = [code.strip() for code in matched_codes.split(',')]
            
            # Verify all codes exist in our data
            valid_codes = []
            for code in codes:
                if code in airline_data.values():
                    valid_codes.append(code)
                else:
                    # Try to find closest match
                    for valid_code in airline_data.values():
                        if valid_code.lower() in code.lower() or code.lower() in valid_code.lower():
                            valid_codes.append(valid_code)
                            break
                    # If no close match found but DeepSeek provided a code, use it
                    if not any(valid_code.lower() in code.lower() or code.lower() in valid_code.lower() for valid_code in airline_data.values()):
                        valid_codes.append(code)
            
            return ','.join(valid_codes) if valid_codes else None
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {str(e)}")
            return None

    except Exception as e:
        print(f"Error in intelligent airline matching: {str(e)}")
        return None

def build_kayak_url(origin_code, dest_code, departure_date, return_date=None, 
                   adults=1, students=0, youth=0, children=0, seated_infant=0, lap_infant=0,
                   cabin_class=CabinClass.ECONOMY, airlines=None):
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
    
    Airlines:
    - Comma-separated list of airline codes (e.g., "MU,CX,CZ")
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
    query_params = ["sort=price_a"]
    
    # Add airline filter if specified
    if airlines:
        query_params.append(f"fs=airlines={airlines}")

    # Combine complete URL
    return f"{base_url}/{route}/{date_part}/{passenger_part}?{'&'.join(query_params)}"

class FlightInfo(BaseModel):
    departure_time: str
    arrival_time: str
    departure_airport: str
    arrival_airport: str
    duration: str
    stops: str
    next_day_arrival: bool = False

class FlightResponse(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date] = None
    cabin_class: CabinClass
    price: str
    outbound_flight: FlightInfo
    return_flight: Optional[FlightInfo] = None

def get_flight_info(origin_city, destination_city, departure_date, return_date=None, 
                   adults=1, students=0, youth=0, children=0, seated_infant=0, lap_infant=0, 
                   cabin_class=CabinClass.ECONOMY, airlines=None):
    origin_code = get_citycode(origin_city)
    dest_code = get_citycode(destination_city)
    
    # Get airline codes if specified
    airline_codes = None
    if airlines:
        airline_codes = get_airlinecode(airlines)
        if not airline_codes:
            print(f"Warning: Could not match airline codes for: {airlines}")

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
        cabin_class=cabin_class,
        airlines=airline_codes
    )

    print(url)
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
    chrome_options.add_argument(f'user-agent={headers["User-Agent"]}')

    try:
        print('start')
        browser = webdriver.Chrome(options=chrome_options)
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        browser.set_page_load_timeout(10000)
        browser.get(url)

        time.sleep(5)

        wait = WebDriverWait(browser, 200)
        
        # Get price
        try:
            price_element = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.e2GB-price-text"))
        )
            price = price_element.text.replace("HK$", "").replace(",", "").strip()
            print(f"Found price: {price}")
        except Exception as e:
            print(f"Error getting price: {str(e)}")
            price = None

        # Get flight information
        outbound_flight = None
        return_flight = None
        
        try:
            # Get the first flight list (cheapest option)
            flight_list = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ol.hJSA-list"))
            )
            
            # Get all flight items in the list
            flight_items = flight_list.find_elements(By.CSS_SELECTOR, "li.hJSA-item")
            
            # Process each flight item
            for i, flight in enumerate(flight_items):
                try:
                    # Get times
                    times = flight.find_element(By.CSS_SELECTOR, "div.vmXl-mod-variant-large").text
                    departure_time, arrival_time = times.split(" – ")
                    
                    # Check for next day arrival
                    next_day = False
                    if "+1" in arrival_time:
                        next_day = True
                        arrival_time = arrival_time.replace("+1", "").strip()
                    
                    # Get airports
                    airports = flight.find_elements(By.CSS_SELECTOR, "div.c_cgF-mod-variant-full-airport-wide")
                    departure_airport_info = airports[0].find_element(By.CSS_SELECTOR, "span.jLhY-airport-info").text.split()
                    arrival_airport_info = airports[1].find_element(By.CSS_SELECTOR, "span.jLhY-airport-info").text.split()
                    
                    departure_airport = departure_airport_info[0]
                    arrival_airport = arrival_airport_info[0]
                    
                    # Get duration and stops
                    duration = flight.find_element(By.CSS_SELECTOR, "div.xdW8-mod-full-airport div.vmXl").text
                    stops = flight.find_element(By.CSS_SELECTOR, "span.JWEO-stops-text").text
                    
                    flight_info = FlightInfo(
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        departure_airport=departure_airport,
                        arrival_airport=arrival_airport,
                        duration=duration,
                        stops=stops,
                        next_day_arrival=next_day
                    )
                    
                    # First flight is always outbound, second is return (if exists)
                    if i == 0:
                        outbound_flight = flight_info
                    elif i == 1:
                        return_flight = flight_info
                        
                except Exception as e:
                    print(f"Error parsing flight info: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error getting flight list: {str(e)}")

        browser.execute_script("window.stop();")
        browser.quit()
        
        return {
            "price": price,
            "outbound_flight": outbound_flight,
            "return_flight": return_flight
        }

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
    airlines: Optional[str] = None  # Comma-separated airline names or codes

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
    "cabin_class": "business",    # Optional: economy, premium, business, first
    "airlines": "MU,CX,CZ"        # Optional: Comma-separated airline names or codes
}
'''

@app.post("/flight-info")
async def check_flight_info(request: FlightRequest):
    try:
        result = get_flight_info(
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
            cabin_class=request.cabin_class,
            airlines=request.airlines
        )
        
        if result is None or result["outbound_flight"] is None:
            raise HTTPException(status_code=404, detail="Flight information not found")
            
        return FlightResponse(
            origin=request.origin_city,
            destination=request.destination_city,
            departure_date=request.departure_date,
            return_date=request.return_date,
            cabin_class=request.cabin_class,
            price=result["price"],
            outbound_flight=result["outbound_flight"],
            return_flight=result["return_flight"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    # uvicorn flight_api:app --reload --port 8002
    uvicorn.run(app, host="0.0.0.0", port=8002) 