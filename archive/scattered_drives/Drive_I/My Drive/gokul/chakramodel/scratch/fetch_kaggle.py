import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

print("Initializing Chrome driver...")
driver = webdriver.Chrome(options=options)
try:
    url = "https://www.kaggle.com/code/jayasrikannuchamy/chakramodel-evalharness-kaggle"
    print("Navigating to:", url)
    driver.get(url)
    time.sleep(8)
    print("Page Title:", driver.title)
    body = driver.find_element(By.TAG_NAME, "body").text
    print("=== PAGE TEXT CONTENT ===")
    print(body)
    print("=========================")
finally:
    driver.quit()
