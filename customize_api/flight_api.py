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

app = FastAPI(
    title="Flight Price API",
    description="API for checking flight prices between cities",
    version="1.0.0"
)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_citycode(cityname):
    with open('assets/cities.json', 'r', encoding='utf-8') as json_file:
        city_data = json.load(json_file)

    citycode = city_data.get(cityname)

    if citycode:
        return citycode
    else:
        return f"城市 '{cityname}' 未找到。"

def build_kayak_url(origin_code, dest_code, departure_date, return_date, adults, children_count):
    """
    构建Kayak机票搜索URL
    """
    # 基础URL
    base_url = "https://www.kayak.com.hk/flights"

    # 构建路径部分
    route = f"{origin_code}-{dest_code}"
    departure_date_str = departure_date.strftime("%Y-%m-%d") if hasattr(departure_date, 'strftime') else departure_date
    return_date_str = return_date.strftime("%Y-%m-%d") if hasattr(return_date, 'strftime') else return_date
    adults_part = f"{adults}adults"

    # 构建儿童部分
    children_part = ""
    if children_count > 0:
        children_part = "/children-" + "-".join([str(11)] * children_count)

    # 构建查询参数
    query_params = "sort=price_a"

    # 组合完整URL
    return f"{base_url}/{route}/{departure_date_str}/{return_date_str}/{adults_part}{children_part}?{query_params}"

def get_flight_price(origin_city, destination_city, departure_date, return_date, adults=1, children=0):
    origin_code = get_citycode(origin_city)
    dest_code = get_citycode(destination_city)

    # 构建动态URL
    url = build_kayak_url(
        origin_code=origin_code,
        dest_code=dest_code,
        departure_date=departure_date,
        return_date=return_date,
        adults=adults,
        children_count=children
    )

    print(url)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # 使用新版无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
    chrome_options.add_argument("--window-size=1920,1080")  # 设置窗口大小
    chrome_options.add_argument("--start-maximized")  # 最大化窗口
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 禁用自动化控制特征
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # 排除自动化开关
    chrome_options.add_experimental_option('useAutomationExtension', False)  # 禁用自动化扩展
    chrome_options.add_argument(f'user-agent={headers["User-Agent"]}')  # 设置用户代理

    try:
        print('start')
        browser = webdriver.Chrome(options=chrome_options)
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })  # 修改 webdriver 特征
        browser.set_page_load_timeout(10000)
        browser.get(url)

        # 增加等待时间，确保页面完全加载
        time.sleep(5)  # 添加固定等待时间

        wait = WebDriverWait(browser, 200)  # 设置合理的等待时间
        
        first_price_element = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.e2GB-price-text"))
        )

        price = first_price_element.text.replace("HK$", "").strip()

        browser.execute_script("window.stop();")
        browser.quit()  # 关闭浏览器
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
    return_date: date
    adults: Optional[int] = 1
    children: Optional[int] = 0

'''
EXAMPLE:
{
    "origin_city": "香港",
    "destination_city": "北京",
    "departure_date": "2025-06-09",
    "return_date": "2025-06-19",
    "adults": 1,
    "children": 0
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
            children=request.children
        )
        
        if price is None:
            raise HTTPException(status_code=404, detail="Flight price not found")
            
        return {
            "origin": request.origin_city,
            "destination": request.destination_city,
            "departure_date": request.departure_date,
            "return_date": request.return_date,
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
    uvicorn.run(app, host="0.0.0.0", port=8000) 