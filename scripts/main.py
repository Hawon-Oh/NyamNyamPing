import os
from dotenv import load_dotenv
import json

import discord
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
SERVER_ID = int(os.getenv("server_id"))

# 세팅값 로드
SETTINGS_PATH = 'settings.json'
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)
CHANNEL_NAME = settings['channel_name']
RESTAURANTS = settings['restaurants']
holiday_lock = settings['holiday_lock'] # True = 휴일엔 자동메시지 skip함
scheduler_lock = settings['scheduler_lock']  # True = 스케줄러 동작, False면 off
COMMAND_MENU = settings['command_menu']
COMMAND_HELP = settings['command_help']
LUNCH_TIME = list(map(int, settings['lunch_time']))
COMMAND_TEST = settings['command_test']
COMMAND_HOLIDAYSKIP = settings['command_holidayskip']
COMMAND_AUTOMSG = settings['command_automsg']


menus = ""


#----------------------------------------
# 셀레니윰 파트
#-----------------------

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


def send_menus_to_specific_channel():
    global menus

    guild = bot.get_guild(SERVER_ID)
    channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
    
    if not menus:
        get_menus()

    if channel:
        bot.loop.create_task(channel.send(menus))
    else:
        channel = guild.text_channels[0]
        bot.loop.create_task(channel.send(f"세팅된 채널명이 옳바르지 않아 첫번째 채널에 출력합니다. \n{menus}"))


def clear_menus():
    global menus
    menus = ""



#-----------------------------
# 스케줄러 파트
#---------------------------
scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
schedule1 = None
schedule2 = None
schedule3 = None



#-----------------------------
# 디스코드 파트
#---------------------------

# discord 설정
intents = discord.Intents.all()
bot = dis_commands.Bot(command_prefix="!", intents=intents)
guild = bot.get_guild(SERVER_ID)

# 봇체크 및 스케줄러
@bot.event
async def on_ready():
    global schedule1, schedule2, schedule3
    
    # 미리 크롤링하게 점심시간 1분 빼기
    pre_lunch = ((LUNCH_TIME[0] - 1) % 24, (LUNCH_TIME[1] - 2) % 60) if LUNCH_TIME[1] < 2 else (LUNCH_TIME[0], LUNCH_TIME[1] - 1)

    print(f"봇 로그인됨: {bot.user}")
    # 점심시간에 메뉴가져오기
    schedule1 = scheduler.add_job(get_menus, 'cron', day_of_week='mon-fri', hour=pre_lunch[0], minute=pre_lunch[1])
    # 특정 서버에 메뉴보내기
    schedule2 = scheduler.add_job(send_menus_to_specific_channel, 'cron', day_of_week='mon-fri', hour=LUNCH_TIME[0], minute=LUNCH_TIME[1])
    # 2시간 후 메뉴 지우기
    schedule3 = scheduler.add_job(clear_menus, 'cron', day_of_week='mon-fri', hour=min(LUNCH_TIME[0] + 2, 24), minute=LUNCH_TIME[1])
    scheduler.start()


# 메뉴판 전송 커맨드
@bot.command(name=COMMAND_MENU[0], aliases=COMMAND_MENU[1:])
async def menu(ctx):
    global menus
    if not menus:
        get_menus()

    await ctx.channel.send(f"{menus}")



# 휴일스킵모드 변경 커맨드
@bot.command(name=COMMAND_HOLIDAYSKIP[0], aliases=COMMAND_HOLIDAYSKIP[1:])
async def switch_holidayskip(ctx):
    global holiday_lock

    # 값 변경
    holiday_lock = not holiday_lock
    settings["holiday_lock"] = holiday_lock

    # JSON 저장
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    # 결과 메시지
    if holiday_lock:
        await ctx.channel.send("휴일스킵모드 **켜짐**")
    else:
        await ctx.channel.send("휴일스킵모드 **꺼짐**")


# 자동메시지 변경 커맨드
@bot.command(name=COMMAND_AUTOMSG[0], aliases=COMMAND_AUTOMSG[1:])
async def switch_scheduler(ctx):
    global scheduler_lock

    # 값 변경
    scheduler_lock = not scheduler_lock
    settings["scheduler_lock"] = scheduler_lock

    # JSON 저장
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

    # 결과 메시지
    global schedule1, schedule2, schedule3

    # 현재 멈춘 상태면 킴
    if schedule1.next_run_time is None:
        schedule1.resume()
        schedule2.resume()
        schedule3.resume()
        await ctx.channel.send("스케줄러 메시지 전송 **켜짐**")
    else:  # 동작 중이면 끔
        schedule1.pause()
        schedule2.pause()
        schedule3.pause()
        await ctx.channel.send("스케줄러 메시지 전송 **꺼짐**")


# 도움말 커맨드
@bot.command(name=COMMAND_HELP[0], aliases=COMMAND_HELP[1:])
async def help(ctx):
    
    msg = (
    f"<봇 명령어>\n"
    f"- **메뉴 확인** : {COMMAND_MENU}\n"
    f"- **도움말** : {COMMAND_HELP}\n"
    f"- **점심 알림 시간** : {LUNCH_TIME}\n"
    f"- **주말스킵 설정** : {COMMAND_HOLIDAYSKIP}\n"
    f"- **자동문자 설정** : {COMMAND_AUTOMSG}\n\n"
    f"<현재 봇 설정값>\n"
    f"- **채널명 설정** : {CHANNEL_NAME}\n"
    f"- **식당 URL 주소** : {RESTAURANTS}\n"
    f"- **휴일스킵 설정** : {holiday_lock}\n"
    f"- **자동문자 설정** : {scheduler_lock}\n"
    )
    await ctx.channel.send(msg)
    

# 개발용
@bot.command(name=COMMAND_TEST[0], aliases=COMMAND_TEST[1:])
async def test(ctx):
    global menus
    get_menus()
    await ctx.channel.send(menus)


bot.run(DISCORD_BOT)