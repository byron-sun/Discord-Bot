"""This file contains the main framework for the Discord Bot to function."""

import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from datastore import data_store

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

intents = discord.Intents().all()
bot = commands.Bot(command_prefix='!', intents=intents)

print('Loading Cogs...\n')
for filename in os.listdir('./cogs'):
  if filename.endswith('.py'):
    bot.load_extension(f'cogs.{filename[:-3]}')

print('--------------------- EVENT LOGS ---------------------\n')

@bot.event
async def on_ready():
    """This function prints information out to standard output when
    the bot has established a connection to Discord.
    """

    for guild in bot.guilds:
        if guild.name == GUILD:
            break
    print(f'{bot.user} is connected to the following guild:\n'
          f'{guild.name} (id: {guild.id})\n')

    members = '\n - '.join([member.name for member in guild.members])
    print(f'Guild Members:\n - {members}\n')

    # If a profile for the guild does not already exist, append a new one onto
    # the list of guilds.
    data = data_store.get()
    guilds = data['guilds']
    if not f'{guild.id}' in guilds:
        guilds[f'{guild.id}'] = ({
            'filter': False,
        })
        data_store.set(data)
        print('A new guild profile has been created for '
             f'{guild.name} (id: {guild.id})')

@bot.event
async def GuildLeaveEvent(guild):
    """This function removes the guild profile corresponding to the guild_id
    from the list of guild profiles when the bot is removed or kicked.
    """
    data = data_store.get()
    guilds = data['guilds']
    guilds.pop(guild.id, None)
    data_store.set(data)
    print(f'The profile for {guild.name} (id: {guild.id} has been removed.')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the permissions required to use this c'
        'ommand.')

bot.run(TOKEN)