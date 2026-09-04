import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import PREFIX
from cogs.verification import Verification

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

intents = discord.Intents.default()
intents.members = True


class VerificationBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        await self.add_cog(Verification(self))

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")


bot = VerificationBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Guilds: {len(bot.guilds)}")


@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        message = "You do not have permission to use this command."
    else:
        message = "Something went wrong."
        print(f"[ERROR] {repr(error)}")

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


bot.run(TOKEN)
