import os
from dotenv import load_dotenv
import json

import discord
from discord.utils import get
from discord.ext import commands as dis_commands

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

# 세팅값 로드
SETTINGS_PATH = 'settings.json'
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)
RESTAURANTS = settings['restaurants']
holiday_lock = settings['holiday_lock'] # True = 휴일엔 자동메시지 skip함
COMMAND_MENU = settings['command_menu']
COMMAND_HELP = settings['command_help']
LUNCH_TIME = list(map(int, settings['lunch_time']))
COMMAND_TEST = settings['command_test']
COMMAND_HOLIDAYSKIP = settings['command_holidayskip']

# 미리 크롤링하게 점심시간 1분 빼기
LUNCH_TIME = ((LUNCH_TIME[0] - 1) % 24, (LUNCH_TIME[1] - 2) % 60) if LUNCH_TIME[1] < 2 else (LUNCH_TIME[0], LUNCH_TIME[1] - 1)



menus = ""


#----------------------------------------
# 셀레니윰 파트
#-------------------

# headless옵션 설정
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


# 카톡채널 크롤링 버전: last updated 2025-08-26
def get_menus():
    global menus

    # 공휴일이면 함수종료
    if today_is_holiday() and holiday_lock:
        # do nothing
        return
    
    temp_menus = ''
    driver = webdriver.Chrome(options=options)

    for res in RESTAURANTS:
        name = res['name']
        url = res['url']

        try:
            driver.get(url)

            # img_thumb 나타날 때까지 4초 대기
            imgs = WebDriverWait(driver, 4).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "img_thumb"))
            )
            temp_menus += name + ': ' + imgs[-1].get_attribute("src") + '\n'

        except:
            temp_menus += f"{name} URL주소에 접속할 수 없습니다. "

    driver.quit()

    menus = temp_menus


def clear_menus():
    global menus
    menus = ""




#-----------------------------
# 디스코드 파트
#---------------------------

scheduler = AsyncIOScheduler()

# discord 설정
intents = discord.Intents.all()
bot = dis_commands.Bot(command_prefix="!", intents=intents)


# 봇체크 및 스케줄러
@bot.event
async def on_ready():
    print(f"봇 로그인됨: {bot.user}")

    scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
    # 점심시간에 메뉴가져오기
    scheduler.add_job(get_menus, 'cron', day_of_week='mon-fri', hour=LUNCH_TIME[0], minute=LUNCH_TIME[1])
    # 2시간 후 메뉴 지우기
    scheduler.add_job(clear_menus, 'cron', day_of_week='mon-fri', hour=min(LUNCH_TIME[0] + 2, 24), minute=LUNCH_TIME[1])
    scheduler.start()



# 메뉴판 전송 커맨드
@bot.command(name=COMMAND_MENU[0], aliases=COMMAND_MENU[1:])
async def menu(ctx):
    global menus
    if not menus:
        await ctx.channel.send(f"쉬는 날이거나 점심시간이 아닙니다. ")
    else:
        await ctx.channel.send(f"{menus}")


# # 휴일스킵모드 전환 커맨드
# @bot.command(name=COMMAND_HOLIDAYSKIP[0], aliases=COMMAND_HOLIDAYSKIP[1:])
# async def switch_holidayskip(ctx):

#     global holiday_lock
#     holiday_lock = not holiday_lock

#     if holiday_lock:
#         await ctx.channel.send("휴일스킵모드 킴")
#     else:
#         await ctx.channel.send("휴일스킵모드 끔")



# 휴일스킵모드 전환 커맨드
@bot.command(name=COMMAND_HOLIDAYSKIP[0], aliases=COMMAND_HOLIDAYSKIP[1:])
async def switch_holidayskip(ctx):
    global holiday_lock

    # JSON 불러오기
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # 값 토글
    holiday_lock = not settings.get("holiday_lock", False)
    settings["holiday_lock"] = holiday_lock

    # JSON 저장
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    # 결과 메시지
    if holiday_lock:
        await ctx.channel.send("휴일스킵모드 **켜짐**")
    else:
        await ctx.channel.send("휴일스킵모드 **꺼짐**")



# 도움말 커맨드
@bot.command(name=COMMAND_HELP[0], aliases=COMMAND_HELP[1:])
async def help(ctx):
    
    msg = (
    f"봇 명령어\n"
    f"- {COMMAND_MENU} : 메뉴 확인\n"
    f"- {COMMAND_HELP} : 도움말\n"
    f"- {LUNCH_TIME} : 점심 알림 시간\n"
    f"- {COMMAND_HOLIDAYSKIP} : 주말 스킵 설정\n"
    f"- {COMMAND_TEST} : 테스트 실행\n\n"
    f"현재 봇 설정값\n"
    f"- **식당 URL 주소** : {RESTAURANTS}\n"
    f"- **주말 스킵 설정** : {holiday_lock}\n"
    )
    await ctx.channel.send(msg)
    



# 개발용
@bot.command(name=COMMAND_TEST[0], aliases=COMMAND_TEST[1:])
async def test(ctx):
    global menus
    get_menus()
    await ctx.channel.send(menus)



bot.run(DISCORD_BOT)






"""
#bot과 client는 같이 사용 불가 (bot 선택함)


client = discord.Client(intents=intents)


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



#지정문자가 입력된 서버에 메시지 전송
@client.event
async def on_message(message):
    if message.content[0] == '!' and message.content[1:] in COMMAND_MENU:
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
"""