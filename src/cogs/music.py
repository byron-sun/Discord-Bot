import asyncio

import discord
import youtube_dl

from discord.ext import commands

from datastore import data_store

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

async def play_next(self, ctx):
    data = data_store.get()
    queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
    vc = ctx.message.guild.voice_client
    # Pops the first item from the queue
    video_data = queue.pop(0)
    player_data = await YTDLSource.from_url(video_data['title'], loop=self.bot.loop, stream=True)
    player = player_data['player']
    data_store.set(data)
    embed = discord.Embed(title='NOW PLAYING', description=f'{player.title} **[{video_data["duration"]}]**', color=discord.Color.blurple())
    await ctx.send(embed=embed)
    print(f'Now playing in {ctx.guild.name} (id: {ctx.guild.id}): {player.title} [{video_data["duration"]}]')
    vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(self, ctx), self.bot.loop))
    if data['guilds'][f'{ctx.message.guild.id}']['loop'] is True:
        queue.append(video_data)

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
            # if the first item is a playlist, then return only the first item
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return {'player': cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data), 'duration': data['duration']}


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='join', help='Joins the voice channel you are currently in.')
    async def join(self, ctx):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send('You must be connected to a voice channel to use this command.')
        voice_channel = ctx.author.voice.channel
        # Checks if the bot_id is in the list of user_ids connected to the author's voice channel.
        if self.bot.user.id in ctx.author.voice.channel.voice_states.keys():
            return await ctx.send('I am already connected to your voice channel. Check again!')
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)
            ctx.voice_client

    @commands.command(name='leave', help='Disconnects bot from the voice channel if connected.')
    async def leave(self, ctx):
        voice_state = ctx.author.voice
        if voice_state is None:
            await ctx.send('You must be connected to a voice channel to use this command.')
        elif ctx.guild.voice_client not in self.bot.voice_clients:
            await ctx.send('I am not connected to any channels.')
        else:
            await ctx.voice_client.disconnect()
            await ctx.message.add_reaction("👋")

    @commands.command(name='play', help='Searches and plays audio from YouTube.')
    async def play(self, ctx, *, url):
        data = data_store.get()
        queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
        vc = ctx.message.guild.voice_client
        if vc.is_playing():
            if len(queue) == 50:
                await ctx.send('The queue for this server is full. Wait for so'
                               'ngs to play before adding more.')
            video_data = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            # If the video is longer than 60 minutes, cancel download and return with error message.
            if video_data['duration'] > 3600:
                await ctx.send('Sorry, but the video you are trying to pla'
                                   'y is longer than 60 minutes. Try using !pl'
                                   'ay again but this time with a video of a s'
                                   'horter length.')
                return
            player = video_data['player']
            duration = f'{str(int(video_data["duration"]) // 60)}:{"%02d" % (int(video_data["duration"]) % 60)}'
            await ctx.send(f'**Added:** {format(player.title)} **[{duration}]** at position {str(len(queue) + 1)} in queue.')
            queue.append({'title': player.title, 'duration': duration})
        else:
            async with ctx.typing():
                video_data = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                if video_data['duration'] > 3600:
                    await ctx.send('Sorry, but the video you are trying to pla'
                                    'y is longer than 60 minutes. Try using !pl'
                                    'ay again but this time with a video of a s'
                                    'horter length.')
                    return
                player = video_data['player']
                duration = f'{str(int(video_data["duration"]) // 60)}:{"%02d" % (int(video_data["duration"]) % 60)}'
                queue.append({'title': player.title, 'duration': duration})
                vc.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(self, ctx), self.bot.loop))
                embed = discord.Embed(title='NOW PLAYING', description=f'{player.title} **[{duration}]**', color=discord.Color.blurple())
            await ctx.send(embed=embed)
            print(f'Now playing in {ctx.guild.name} (id: {ctx.guild.id}): {player.title} [{duration}]')
            # Removes the first item from the queue
            video_data = queue.pop(0)
            if data['guilds'][f'{ctx.message.guild.id}']['loop'] is True:
                queue.append(video_data)
        data_store.set(data)

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

    @commands.command(name='stop', help='Stops any audio playing from bot and clears queue.')
    async def stop(self, ctx):
        data = data_store.get()
        queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
        queue.clear()
        data_store.set(data)
        vc = ctx.message.guild.voice_client
        vc.stop()
        await ctx.send('Bot has stopped playing.')

    @commands.command(name='skip', help='Skips the current-playing song.')
    async def skip(self, ctx):
        vc = ctx.message.guild.voice_client
        # Stops the current song from playing.
        vc.pause()
        await ctx.send('Skipped.')
        # Loads a new player from the queue and starts playing it.
        await play_next(self, ctx)

    @commands.command(name='clear', help='Clears the existing queue.')
    async def clear(self, ctx):
        data = data_store.get()
        queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
        queue.clear()
        data_store.set(data)
        await ctx.send('The queue has been cleared.')

    @commands.command(name='remove', help='Removes a song from the queue.')
    async def remove(self, ctx, item=None):
        data = data_store.get()
        queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
        if item is None or item.isdigit() is False or int(item) > len(queue):
            await ctx.send('Please give a valid number of an item from the queue.')
            return
        video = queue.pop(int(item) - 1)
        data_store.set(data)
        await ctx.send(f'{video["title"]} has been removed from queue.')

    @commands.command(name='loop', help='Loops the current queue.')
    async def loop(self, ctx):
        data = data_store.get()
        guild = data['guilds'][f'{ctx.message.guild.id}']
        if guild['loop'] is True:
            await ctx.send('The queue is already looping!')
            return
        guild['loop'] = True
        data_store.set(data)
        await ctx.send('The queue has been set to loop.')

    @commands.command(name='unloop', help='Stops looping the current queue.')
    async def unloop(self, ctx):
        data = data_store.get()
        guild = data['guilds'][f'{ctx.message.guild.id}']
        if guild['loop'] is False:
            await ctx.send('The queue is not currently looping!')
            return
        guild['loop'] = False
        data_store.set(data)
        await ctx.send('The queue is no longer looping.')

    @commands.command(aliases=['q'], help='Prints the currently queued songs.')
    async def queue(self, ctx):
        data = data_store.get()
        queue = data['guilds'][f'{ctx.message.guild.id}']['queue']
        queue_pages = []
        duration_pages = []
        queue_list = duration_list = ''
        for count, item in enumerate(queue, 1):
            # Limits the number of items on each page to 5 maximum.
            if count != 1 and count % 5 == 1:
                queue_pages.append(queue_list)
                duration_pages.append(duration_list)
                queue_list = duration_list = ''
            queue_list += f'**[{count}]**:    {item["title"]}\n\n'
            duration_list += f'**[{item["duration"]}]**\n\n'
            if len(item['title']) > 65:
                duration_list += '\n'
        # If there are still items that have not been added, append them all onto a new page.
        if queue_list != '':
            queue_pages.append(queue_list)
            duration_pages.append(duration_list)
        if queue_pages == []:
            queue_pages.append('The queue is currently empty! Add more songs using ?play.')
        page_len = len(queue_pages)
        embed = discord.Embed(title=f'QUEUE', color=discord.Color.blurple())
        embed.add_field(name=f'Page 1 out of {page_len}', value=queue_pages[0], inline=True)
        if duration_pages == []:
            msg = await ctx.send(embed=embed)
            return
        embed.add_field(name='\u200b', value=duration_pages[0], inline=True)
        msg = await ctx.send(embed=embed)
        if page_len > 1:
            await msg.add_reaction("⬅")
            await msg.add_reaction("➡")
            index = 0
            # Hangs on after the queue display has been created to check for user reactions.
            # Acts as a scrolling mechanism for the pages of the queue display, and times out after 1 minute.
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬅", "➡"]

            while True:
                try:
                    reaction, user = await ctx.bot.wait_for("reaction_add", timeout=60, check=check)
                    if str(reaction.emoji) == "➡" and index != page_len:
                        index += 1
                        new_embed = discord.Embed(title=f'QUEUE', color=discord.Color.blurple())
                        new_embed.add_field(name=f'Page {index + 1} out of {page_len}', value=queue_pages[index], inline=True)
                        if duration_pages != []:
                            new_embed.add_field(name='\u200b', value=duration_pages[index], inline=True)
                        await msg.edit(embed=new_embed)
                        await msg.remove_reaction(reaction, user)

                    elif str(reaction.emoji) == "⬅" and index > 0:
                        index -= 1
                        new_embed = discord.Embed(title=f'QUEUE', color=discord.Color.blurple())
                        new_embed.add_field(name=f'Page {index + 1} out of {page_len}', value=queue_pages[index], inline=True)
                        if duration_pages != []:
                            new_embed.add_field(name='\u200b', value=duration_pages[index], inline=True)
                        await msg.edit(embed=new_embed)
                        await msg.remove_reaction(reaction, user)
                    else:
                        await msg.remove_reaction(reaction, user)
                except asyncio.TimeoutError:
                    await ctx.send("The queue display has timed out.")
                    break

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnects the bot from the voice channel if it is idle for
        more than 5 minutes.
        """
        if not member.id == self.bot.user.id:
            return

        elif before.channel is None:
            voice = after.channel.guild.voice_client
            time = 0
            while True:
                # Increments the timer by one for every second the bot is inactive.
                await asyncio.sleep(1)
                time = time + 1
                if voice.is_playing() and not voice.is_paused():
                    time = 0
                if time == 300:
                    await voice.disconnect()
                if not voice.is_connected():
                    break

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send('You are not connected to a voice channel.')
                raise commands.CommandError('Author not connected to a voice channel.')

def setup(bot):
    bot.add_cog(Music(bot))