import os
from dotenv import load_dotenv
import json

import discord
from discord.utils import get

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from holidayskr import today_is_holiday


# 키/토큰 로드
load_dotenv()
DISCORD_BOT = os.getenv("discord_bot")

# 변수값 로드
with open('variables.json', "r", encoding="utf-8") as f:
    variables = json.load(f)
restaurants = variables['restaurants']
commands = variables['commands']



#----------------------------------------
# 셀레니윰 파트: 크롤링 (카톡채널 버전)
# last updated 2025-08-26
# coded by Hawon Oh
#-------------------

# headless옵션 설정
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


def get_menus():
    menus = ''
    driver = webdriver.Chrome(options=options)

    for res in restaurants:
        name = res['name']
        url = res['url']

        try:
            driver.get(url)

            # img_thumb 나타날 때까지 최대 5초 대기
            imgs = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "img_thumb"))
            )
            menus += name + ': ' + imgs[-1].get_attribute("src") + '\n'

        except:
            menus += f"{name} URL주소에 접속할 수 없습니다. "

    driver.quit()

    return menus



#-----------------------------
# 디스코드 파트
#---------------------------

# discord intent 설정
intents = discord.Intents.all()
client = discord.Client(intents=intents)

scheduler = AsyncIOScheduler()




# 봇이 속한 모든 서버에 메시지 전송하는 함수
async def send_menus_to_all():

    # 공휴일이면 함수종료
    if today_is_holiday():
        # do nothing
        return

    menus = get_menus()

    # 봇이 속한 서버 목록 확인
    for guild in client.guilds:
        # print(f"봇이 속한 서버: {guild.name}, ID: {guild.id}")

        channel = get(guild.text_channels, name='general')

        if channel is not None:
            await channel.send(menus)
        else:
            print(f"{guild.name} 서버에 적절한 텍스트 채널이 없습니다.")




# 지정문자가 입력된 서버에 메시지 전송
@client.event
async def on_message(message):
    if message.content in commands:
        menus = get_menus()
        await message.channel.send(f"{menus}")
        


# 월~금 지정된 시간에 send_menus_to_all 함수 실행
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    
    scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
    scheduler.add_job(send_menus_to_all, 'cron', day_of_week='mon-fri', hour=12, minute=49)
    scheduler.start()



client.run(DISCORD_BOT)