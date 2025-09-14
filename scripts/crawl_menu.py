import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 세팅값 로드
SETTINGS_PATH = 'settings.json'
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    RESTAURANTS = json.load(f)['restaurants']


# headless옵션 설정
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


# 카톡채널에 접속해서 프로필 이미지 가져옴
def get_menu():
    
    menu = ''
    driver = webdriver.Chrome(options=options)

    for res in RESTAURANTS:
        name = res['name']
        url = res['url']

        try:
            driver.get(url)

            # img_thumb 나타날 때까지 4초 대기
            imgs = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "img_thumb"))
            )
            menu += name + ': ' + imgs[-1].get_attribute("src") + '\n'

        except:
            menu += f"{name} URL주소에 접속할 수 없습니다. "

    driver.quit()

    return menu