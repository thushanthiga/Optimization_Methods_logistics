from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

try:
    driver = webdriver.Chrome(options=options)
    driver.get("http://localhost:8081/dashboard.html")
    
    time.sleep(2)
    
    select_from = Select(driver.find_element(By.ID, "master_from"))
    select_from.select_by_value("Depot: Colombo")
    
    select_to = Select(driver.find_element(By.ID, "master_to"))
    select_to.select_by_value("Depot: Galle")
    
    driver.find_element(By.XPATH, "//button[contains(text(), 'Analyze Connection')]").click()
    
    time.sleep(3)
    
    for entry in driver.get_log('browser'):
        print(entry)
        
    driver.quit()
    print("Selenium test completed.")
except Exception as e:
    print(f"Error: {e}")
