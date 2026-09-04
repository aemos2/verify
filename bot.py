# bot.py
import discord
from discord.ext import commands
import asyncio
import logging
import os
from config import load_config

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load config
config = load_config()

# Get token from config or environment
TOKEN = config.get("TOKEN") or os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("No token found in config or environment variables!")

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=config.get("PREFIX", "!"),
    intents=intents
)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

async def load_extensions():
    """Load all cogs"""
    try:
        # Load the executor checker cog - CHANGE THIS LINE
        await bot.load_extension('cogs.executor_checker')
        print("✅ Loaded executor_checker cog")
    except Exception as e:
        print(f"❌ Failed to load executor_checker: {e}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
