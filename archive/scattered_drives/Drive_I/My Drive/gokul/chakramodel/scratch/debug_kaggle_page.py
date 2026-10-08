import time, json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

options = Options()
options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

driver = webdriver.Chrome(options=options)
try:
    url = "https://www.kaggle.com/code/jayasrikannuchamy/chakramodel-evalharness-kaggle"
    print("Navigating to:", url)
    driver.get(url)
    time.sleep(10)
    
    print("=== BROWSER CONSOLE LOGS ===")
    for entry in driver.get_log('browser'):
        print(entry)
    print("============================")

    # Check page HTML / elements
    elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'SyntaxError') or contains(text(), 'crashed') or contains(text(), 'JSON')]")
    for el in elements:
        print("MATCHED ELEMENT:", el.tag_name, el.text)

finally:
    driver.quit()
