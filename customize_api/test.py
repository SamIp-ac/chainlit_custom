import random
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# --- 配置 ---
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TARGET_URL = "https://www.hotels.com/?locale=en_US&siteid=300000001"
DESTINATION_BUTTON_SELECTOR = '[data-stid="destination_form_field-dialog-trigger"]'
DATE_BUTTON_SELECTOR = '[data-stid="uitk-date-selector-input1-default"]'
WAIT_TIMEOUT = 25 # 稍微增加等待超時

def setup_driver():
    """配置並返回 WebDriver 實例"""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("start-maximized")
    options.add_argument(f"user-agent={USER_AGENT}")
    driver = webdriver.Chrome(options=options)
    return driver

def handle_cookie_popup(driver, wait_obj, timeout=7):
    """嘗試處理常見的 Cookie 彈窗"""
    try:
        # Hotels.com 常用的 OneTrust Cookie 同意按鈕
        cookie_button = wait_obj.until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        if cookie_button:
            cookie_button.click()
            print("✅ 已點擊 OneTrust Cookie 同意按鈕。")
            sleep(random.uniform(1.5, 2.5)) # 等待彈窗消失
            return True
    except TimeoutException:
        print("[ℹ️] 未找到 OneTrust Cookie 同意按鈕 (可能已被處理或不存在)。")
    except Exception as e:
        print(f"[⚠️] 點擊 OneTrust Cookie 按鈕時發生錯誤: {e}")
    return False

def click_element_with_mouse_simulation(driver, wait_obj, selector, description):
    """
    等待元素可點擊，然後模擬鼠標移動到元素並點擊。
    """
    print(f"\n--- 嘗試點擊 '{description}' (選擇器: {selector}) ---")
    try:
        # 1. 等待元素在 DOM 中出現並且可見
        print(f"等待 '{description}' 出現並可見...")
        element = wait_obj.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
        )
        print(f"✅ '{description}' 已可見。")

        # 2. 滾動到元素使其完全可見 (確保中心點可交互)
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'center'});", 
            element
        )
        sleep(random.uniform(0.5, 1.0)) # 等待滾動完成和頁面穩定
        print(f"滾動到 '{description}' 後，元素是否仍在顯示: {element.is_displayed()}")

        # 3. 再次確認元素是否可點擊 (滾動後狀態可能改變)
        element_clickable = wait_obj.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        print(f"✅ '{description}' 現在可點擊。")
        
        # 4. 模擬鼠標移動並點擊
        actions = ActionChains(driver)
        # 稍微隨機化移動前的停頓
        actions.pause(random.uniform(0.2, 0.7))
        # 移動到元素 (Selenium 的 move_to_element 會移動到元素中心)
        actions.move_to_element(element_clickable)
        # 點擊前的短暫停頓
        actions.pause(random.uniform(0.1, 0.4))
        actions.click()
        actions.perform()
        
        print(f"✅ 成功模擬鼠標點擊 '{description}'！")
        return True

    except TimeoutException:
        print(f"[❌] 等待或操作 '{description}' 超時。元素可能未出現、不可見或不可點擊。")
        driver.save_screenshot(f"error_timeout_{description.replace(' ', '_')}.png")
    except ElementClickInterceptedException:
        print(f"[❌] 點擊 '{description}' 被攔截。可能有其他元素覆蓋。")
        driver.save_screenshot(f"error_intercepted_{description.replace(' ', '_')}.png")
    except Exception as e:
        print(f"[❌] 操作 '{description}' 時發生其他錯誤: {e}")
        driver.save_screenshot(f"error_other_{description.replace(' ', '_')}.png")
    return False

def main():
    driver = setup_driver()
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    try:
        print(f"正在打開網站: {TARGET_URL}")
        driver.get(TARGET_URL)
        print("網站已初步加載，等待幾秒讓動態內容穩定...")
        sleep(random.uniform(2.5, 4.0)) # 初始加載等待

        # 首先處理 Cookie 彈窗
        handle_cookie_popup(driver, wait)

        # 嘗試點擊目的地按鈕
        if click_element_with_mouse_simulation(driver, wait, DESTINATION_BUTTON_SELECTOR, "目的地按鈕"):
            print("目的地按鈕點擊流程完成。")
            sleep(random.uniform(1.5, 2.5)) # 點擊成功後等待可能的彈窗/動畫
            # 在此處添加後續操作，如輸入目的地等
        else:
            print("[⚠️] 未能成功點擊目的地按鈕，後續依賴此操作的步驟可能失敗。")

        # 即使目的地失敗，也嘗試點擊日期按鈕作為演示
        if click_element_with_mouse_simulation(driver, wait, DATE_BUTTON_SELECTOR, "日期按鈕"):
            print("日期按鈕點擊流程完成。")
            sleep(random.uniform(1.5, 2.5))
        else:
            print("[⚠️] 未能成功點擊日期按鈕。")
            
        print("\n[🏁] 腳本主要操作執行完畢。")
        sleep(5) # 保持瀏覽器以便查看

    except Exception as e_global:
        print(f"[🚨] 腳本發生嚴重錯誤: {e_global}")
        driver.save_screenshot("critical_error_main.png")
    finally:
        if 'driver' in locals() and driver is not None:
            print("\n正在關閉瀏覽器...")
            driver.quit()

if __name__ == "__main__":
    main()