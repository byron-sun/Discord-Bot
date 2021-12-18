import asyncio

import discord
import youtube_dl

from discord.ext import commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='join', help='Joins the voice channel you are currently in.')
    async def join(self, ctx):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send('You must be connected to a voice channel to use this command.')
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)
            ctx.voice_client

    @commands.command(name='leave', help='Disconnects bot from vc if connected.')
    async def leave(self, ctx):
        voice_state = ctx.author.voice
        if voice_state is None:
            await ctx.send('You must be connected to a voice channel to use this command.')
        elif ctx.guild.voice_client not in self.bot.voice_clients:
            await ctx.send('I am not connected to any channels.')
        else:
            await ctx.voice_client.disconnect()

    @commands.command(name='play', help='plays audio of a youtube video based on keyword/url.')
    async def play(self, ctx, *, url):
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
        await ctx.send('Now playing: {}'.format(player.title))

    @commands.command(name='pause', help='Pauses any audio playing from the bot.')
    async def pause(self, ctx):
        vc = ctx.message.guild.voice_client
        vc.pause()
        await ctx.send('Bot is paused.')

    @commands.command(name='resume', help='Resumes playing audio if paused.')
    async def resume(self, ctx):
        vc = ctx.message.guild.voice_client
        vc.resume()
        await ctx.send('Bot has resumed playing.')

    @commands.command(name='stop', help='Stops any audio playing from bot.')
    async def stop(self, ctx):
        vc = ctx.message.guild.voice_client
        vc.stop()
        await ctx.send('Bot has stopped playing.')

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

def setup(bot):
    bot.add_cog(Music(bot))