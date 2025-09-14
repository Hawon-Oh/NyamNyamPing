import os
from dotenv import load_dotenv
import json

import discord
from discord.ext import commands as dis_commands

from crawl_menu import get_menu

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from holidayskr import today_is_holiday


# 키/토큰 로드
load_dotenv()
DISCORD_BOT = os.getenv("discord_bot")

SERVERS_PATH = 'servers.json'
with open(SERVERS_PATH, "r", encoding="utf-8") as f:
    servers = json.load(f)


# 세팅값 로드
SETTINGS_PATH = 'settings.json'
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)

COMMAND_MENU = settings['command_menu']
COMMAND_HELP = settings['command_help']
COMMAND_TEST = settings['command_test']
COMMAND_HOLIDAY_SKIP = settings['command_holiday_skip']
COMMAND_AUTOMSG = settings['command_automsg']
COMMAND_DEFAULT_CHANNEL = settings['command_default_channel']
RESTAURANTS = settings['restaurants']
LUNCH_TIME = list(map(int, settings['lunch_time']))
DINNER_TIME = list(map(int, settings['dinner_time']))



def send_menus_to_all():
    menu = get_menu()
    for guild in bot.guilds:
        msg = ""
        gid = str(guild.id)
        # 해당 서버가 자동메시지 안받으면 패스
        if not servers[gid]['scheduler_on']:
            continue

        # 휴일에 안받기로 했고 오늘이 휴일이면 패스
        if servers[gid]['holiday_skip'] and today_is_holiday():
            continue

        # 디폴트 채널 정보 가져오기
        channel = discord.utils.get(guild.text_channels, name=servers[gid]['channel'])
        
        # 디폴트 채널 정보에 오류가 있거나 메시지 권한이 없다면
        # 대체 가능한 채널 찾기 (text채널 중 보낼 수 있는 첫 채널 선택)
        if not channel or not channel.permissions_for(guild.me).send_messages:
            msg = f"기본채널로 설정된 **{servers[gid]['channel']}**에 메시지를 보낼 수 없습니다. 해당 채널이 존재하지 않거나 메시지 보낼 권한이 없습니다. \n" \
                + menu
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
        else:
            msg = menu

        # create_task는 여러서버에 동시에 메시지를 보낼 수 있음.
        # 다만 서버 수가 많으면 rate limit에 막힐 수 있음.
        if channel:
            try:
                bot.loop.create_task(channel.send(msg))
                print(f"[SUCCESS]{guild.name}({guild.id})에 전송 성공")
            except Exception as e:
                print(f"{guild.name} 전송 실패: {e}")
        else:
            print(f"[ERROR]{guild.name}({guild.id})에 보낼 수 있는 채널 없음")




#-----------------------------
# 스케줄러 파트
#---------------------------
scheduler = AsyncIOScheduler(timezone=timezone('Asia/Seoul'))
schedule1 = None # for lunch
schedule2 = None # for dinner


#-----------------------------
# 디스코드 파트
#---------------------------

# discord 설정
intents = discord.Intents.all()
bot = dis_commands.Bot(command_prefix="!", intents=intents)


# 새 서버 조인 시 settings.json에 추가
@bot.event
async def on_guild_join(guild):
    global servers

    print(f"새로운 서버에 초대됨: {guild.name} (ID: {guild.id})")

    new_server_config = {
        "channel": "general",
        "holiday_skip": True,
        "scheduler_on": False
    }

    # servers 변수와 servers.json 업데이트
    servers[str(guild.id)] = new_server_config
    with open(SERVERS_PATH, "w") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)



# 기존 서버에서 추방 시 settings.json에서 해당서버 config 삭제
@bot.event
async def on_guild_remove(guild):
    global servers

    print(f"서버에서 제거됨: {guild.name} (ID: {guild.id})")

    removed_server_id = str(guild.id)

    # settings에 해당 서버 ID가 있으면
    # servers 변수와 servers.json에서 삭제
    if removed_server_id in servers:
        del servers[removed_server_id]
        with open(SERVERS_PATH, "w") as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)



# 봇체크 및 스케줄러
@bot.event
async def on_ready():
    print(f"봇 로그인됨: {bot.user}")

    global schedule1, schedule2
    current_guild_ids = {str(guild.id) for guild in bot.guilds}

    # 봇 서버가 꺼진 동안 봇을 초대하거나 추방한 서버가 있을 수 있음
    # 새로운 서버가 있다면 servers에 추가
    is_edited = False
    for guild in bot.guilds:
        gid = str(guild.id)
        if gid not in servers:
            # 초대한 서버의 기본값
            servers[gid] = {
                "channel": "general",      
                "holiday_skip": True,
                "scheduler_on": False
            }
            print(f"신규 서버 추가됨: {guild.name} ({gid})")
            is_edited = True
        
    # 봇을 추방(kick)한 서버의 config를 severs에서 제거
    for gid in list(servers.keys()):
        if gid not in current_guild_ids:
            print(f"나간 서버 제거됨: {gid}")
            del servers[gid]
            is_edited = True

    # 변경사항이 있으면 JSON 파일에 저장
    if is_edited:
        with open(SERVERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)


    # 테스트 할 때 쓰는거 
    # # 자동메시지 킨 모든서버에 점심 메뉴보내기
    # schedule1 = scheduler.add_job(send_menus_to_all, 'cron', hour=LUNCH_TIME[0], minute=LUNCH_TIME[1])
    # # 자동메시지 킨 모든서버에 저녁 메뉴보내기
    # schedule2 = scheduler.add_job(send_menus_to_all, 'cron', hour=DINNER_TIME[0], minute=DINNER_TIME[1])
    # scheduler.start()
    #
    # 배포용
    # 자동메시지 킨 모든서버에 점심 메뉴보내기
    schedule1 = scheduler.add_job(send_menus_to_all, 'cron', day_of_week='mon-fri', hour=LUNCH_TIME[0], minute=LUNCH_TIME[1])
    # 자동메시지 킨 모든서버에 저녁 메뉴보내기
    schedule2 = scheduler.add_job(send_menus_to_all, 'cron', day_of_week='mon-fri', hour=DINNER_TIME[0], minute=DINNER_TIME[1])
    scheduler.start()


# 메뉴판 전송 커맨드
@bot.command(name=COMMAND_MENU[0], aliases=COMMAND_MENU[1:])
async def menu(ctx):
    menu = get_menu()
    await ctx.channel.send(f"{menu}")



# 휴일스킵 설정변경 커맨드
@bot.command(name=COMMAND_HOLIDAY_SKIP[0], aliases=COMMAND_HOLIDAY_SKIP[1:])
async def switch_holiday_skip(ctx):
    gid = str(ctx.guild.id)

    # 값 변경
    servers[gid]['holiday_skip'] = not servers[gid]['holiday_skip']

    # JSON 저장
    with open(SERVERS_PATH, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

    # 결과 메시지
    if servers[gid]['holiday_skip']:
        await ctx.channel.send("휴일스킵모드 **켜짐**")
    else:
        await ctx.channel.send("휴일스킵모드 **꺼짐**")

# 자동메시지 받을 채널명 저장
@bot.command(name=COMMAND_DEFAULT_CHANNEL[0], aliases=COMMAND_DEFAULT_CHANNEL[1:])
async def change_channel(ctx, channel_name: str):
    gid = str(ctx.guild.id)

    # 채널 값 변경
    servers[gid]["channel"] = channel_name

    # servers.json 업데이트
    with open(SERVERS_PATH, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)
    
    await ctx.send(f"채널이 **{channel_name}**(으)로 변경됨")


# 자동메시지 변경 커맨드
@bot.command(name=COMMAND_AUTOMSG[0], aliases=COMMAND_AUTOMSG[1:])
async def switch_scheduler(ctx):
    global schedule1, schedule2

    gid = str(ctx.guild.id)
    
    # 값 변경
    servers[gid]["scheduler_on"] = not servers[gid]["scheduler_on"]

    # JSON 저장
    with open(SERVERS_PATH, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

    # 바뀐 값에 따라 스케줄러 resume/pause
    # if schedule1.next_run_time is None:
    if servers[gid]["scheduler_on"]:
        schedule1.resume()
        schedule2.resume()
        await ctx.channel.send("메뉴 자동문자 **켜짐**")
    # 동작 중이면 끔
    else:
        schedule1.pause()
        schedule2.pause()
        await ctx.channel.send("메뉴 자동문자 **꺼짐**")


# 도움말 커맨드
@bot.command(name=COMMAND_HELP[0], aliases=COMMAND_HELP[1:])
async def help(ctx):
    gid = str(ctx.guild.id)
    msg = (
    f"<명령어>\n"
    f"- **메뉴 확인** : {COMMAND_MENU}\n"
    f"- **도움말** : {COMMAND_HELP}\n"
    f"- **휴일스킵 온/오프** : {COMMAND_HOLIDAY_SKIP}\n"
    f"- **자동문자 온/오프** : {COMMAND_AUTOMSG}\n"
    f"- **자동문자 받을 채널지정 (미지정 시 첫번째 채널)**: {COMMAND_DEFAULT_CHANNEL}\n\n"
    f"<서버 설정값 (이 서버에만 적용)>\n"
    f"- **자동문자 받을 채널** : {servers[gid]['channel']}\n"
    f"- **휴일스킵** : {servers[gid]['holiday_skip']}\n"
    f"- **자동문자** : {servers[gid]['scheduler_on']}\n\n"
    f"<봇 설정값 (모든 서버에 일괄적용)>\n"
    f"- **점심 알림시간** : {LUNCH_TIME}\n"
    f"- **저녁 알림시간** : {DINNER_TIME}\n"
    f"- **식당 URL주소** : {RESTAURANTS}\n"
    )
    await ctx.channel.send(msg)
    

# 개발용
@bot.command(name=COMMAND_TEST[0], aliases=COMMAND_TEST[1:])
async def test(ctx):
    menu = get_menu()
    await ctx.channel.send(menu)


bot.run(DISCORD_BOT)