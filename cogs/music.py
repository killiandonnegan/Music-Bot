import os
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests
import urllib.parse
from bs4 import BeautifulSoup
import asyncio
from random import shuffle
from dotenv import load_dotenv
load_dotenv()


class Music(commands.Cog):
    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
        "executable": "./ffmpeg.exe"
    }
    YDL_OPTIONS = {
        "format": "bestaudio",
        "quiet": False,
        "playlistend": 100
    }
    loop = asyncio.get_event_loop()
    client_credentials_manager = SpotifyClientCredentials(client_id=os.environ.get('SPOTIFY_ID'), client_secret=os.environ.get('SPOTIFY_TOKEN'))
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    USED_DATA = ['spotify_info', 'title', 'formats', 'webpage_url', 'track', 'artist']

    def __init__(self, bot):
        self.bot = bot
        self.paused = False
        self.message = None
        self.videos_list = []
        self.current_video = None
        self.previous_video = None
        self.ctx = None

    async def check_playlist(self, ctx: commands.Context):
        try:
            if self.ctx.voice_client.is_playing():
                return None
        except AttributeError:
            return None
        if not self.videos_list:
            self.previous_video = self.current_video
            self.current_video = None
            return None
        self.ctx = ctx
        self.previous_video = self.current_video
        self.current_video = self.videos_list.pop(0)
        url2 = self.current_video["sound_url"]
        source = discord.FFmpegPCMAudio(url2)
        ctx.voice_client.play(source,
                              after=lambda error: self.loop.create_task(self.check_playlist(ctx)))
        try:
            desc = self.current_video['spotify_info']
        except KeyError:
            desc = self.current_video['title']

        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass
        emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.pink())
        self.message = await ctx.channel.send(" ", embed=emb)
        await self.message.add_reaction("⏮")
        await self.message.add_reaction("⏯")
        await self.message.add_reaction("⏭")

    @staticmethod
    def swap_order(list: list, x: int, y: int):
        """
        swaps the order of two elements in a list

        :return: the modified list or None if some error occurs

        used to swap position of two songs in queue x = first song/arg, y = second song/arg

        """
        x -= 1
        y -= 1
        try:
            if x == y:
                return list
            elif x < y:
                return [*list[:x], list[y], *list[x + 1:y], list[x], *list[y + 1:]]
            else:
                return [*list[:y], list[x], *list[y + 1:x], list[y], *list[x + 1:]]
        except IndexError:
            return None

    def compress_data(self, yt_data: dict, songname: str = None, is_given_by_user: bool = False):
        """
        Compresses the data extracted by yt-dlp, getting rid of unused data.

        :return: Compressed data
        """
        final = {}

        if 'title' in yt_data:
            final['title'] = yt_data['title']

        if 'uploader' in yt_data:
            final['artist'] = yt_data['uploader']

        # If both 'artist' and 'title' are present, combine them into 'spotify_info'
        if 'artist' in final and 'title' in final:
            final['spotify_info'] = f"{final['artist']} - {final['title']}"
            del final['artist']
            del final['title']

        if 'url' in yt_data:
            final['sound_url'] = yt_data['url']

        if 'webpage_url' in yt_data:
            final['webpage_url'] = yt_data['webpage_url']

        return final

    @commands.command(hidden=True)
    async def py(self, ctx: commands.Context, *args: str):
        """
        python interpreter [eval(args)]

        """
        if str(ctx.author) == "klgrm":
            code = " ".join(args)
            try:
                output = str(eval(code, globals()))
                await ctx.message.add_reaction("✅")
            except Exception as exep:
                output = str(exep)
                await ctx.message.add_reaction("❌")
            print(output)
            try:
                await ctx.reply(output)
            except discord.DiscordException:
                try:
                    emb = discord.Embed(title="Error: output too big for a message", description=output,color=discord.Color.dark_blue())
                    emb.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar)
                    await ctx.reply(" ", embed=emb)
                except discord.DiscordException:
                    await ctx.reply("Error: impossible to send output to a discord text channel")
        else:
            await ctx.reply(f"Error: User {ctx.author} doesn't have permission to use this command...")
            await ctx.message.add_reaction("❌")

    @commands.command(
            help="Shows the current latency of the bot in ms",
            brief="- [!ping] Shows the current latency (ping) of the bot (ms)"
    )
    async def ping(self, ctx: commands.Context):
        emb = discord.Embed(title="Latency: ", description=f"{round(self.bot.latency * 1000)}ms", color=discord.Color.dark_blue())
        emb.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar)
        await ctx.reply("", embed=emb)
        await ctx.message.add_reaction("✅")

    @commands.command(
            aliases=["die", "dc"], 
            brief="- [!disconnect/!dc/!die] Disconnects the bot from the voice channel",
            help="Disconnects the bot from the voice channel and clears the music queue"
    )
    async def disconnect(self, ctx: commands.Context):
        await ctx.voice_client.disconnect()
        await ctx.message.add_reaction("👋")
        await self.message.delete()
        self.paused = False
        self.videos_list.clear()
        self.current_video = None
        self.previous_video = None
        self.ctx = None
        self.message = None

    @commands.command(
        brief="- [!stop] Stops the bot, clearing the queue and current song",
        help="Stops the bot, clearing the queue and currently playing song"
    )
    async def stop(self, ctx: commands.Context):
        self.ctx.voice_client.stop()
        await ctx.message.add_reaction("🛑")
        await self.message.delete()
        self.paused = False
        self.videos_list.clear()
        self.current_video = None
        self.previous_video = None
        self.ctx = None
        self.message = None

    @commands.command(
        aliases=["p"],
        brief="- [!play/!p] Plays the song/playlist passed as an argument",
        help="Plays the song/playlist passed as an argument [link] (accepts both Spotify and Youtube "
                "links) or searches the text after '-p ' on Youtube and plays whatever it finds first. "
                "If already playing, it adds to the end of the queue. If you pass a link to a playlist, "
                "you can pass the number of songs to add to the queue in the second argument (separated by "
                "a space)",
        usage="<Spotify/Youtube link or Youtube search query> <Optional[number of playlist items (YT)]>"
    )
    async def play(self, ctx: commands.Context, *args: str):
        if ctx.author.voice is None:
            await ctx.message.add_reaction("❌")
            await ctx.reply("User not in a voice channel!")
            return
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

        vc = ctx.voice_client
        self.paused = False


        if args[0].startswith("https://www.you"):
            try:
                plist_n = int(args[1])
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }

            except Exception:
                ydl_opts = self.YDL_OPTIONS

            url = args[0]

            if self.current_video:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    def get_info():
                        return yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)

                    info = await self.loop.run_in_executor(None, get_info)
                    try:
                        if info['_type'] == 'playlist':
                            for video in info["entries"]:
                                video_ = self.compress_data(video)
                                self.videos_list.append(video_)
                    except KeyError:
                        self.videos_list.append(self.compress_data(info))
                emb = self.message.embeds[0]
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    def get_info():
                        return yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)

                    info = await self.loop.run_in_executor(None, get_info)
                    try:
                        if info['_type'] == 'playlist':
                            self.videos_list = [self.compress_data(entry) for entry in info["entries"]]
                            self.current_video = self.videos_list.pop(0)
                            url2 = self.current_video["sound_url"]
                            source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                            vc.play(source, after=lambda error: self.loop.create_task(self.check_playlist(ctx)))
                            try:
                                desc = self.current_video['spotify_info']
                            except KeyError:
                                desc = self.current_video['title']
                    except KeyError:
                        info = self.compress_data(info)
                        self.current_video = info
                        url2 = info["sound_url"]
                        source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                        vc.play(source, after=lambda error: self.loop.create_task(self.check_playlist(ctx)))
                        try:
                            desc = info['spotify_info']
                        except KeyError:
                            desc = info['title']

                emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.pink())
        elif args[0].startswith("https://open.spo"):
            split = args[0].split("/")
            sf_type = split[-2]
            uri = split[-1].split("?")[0]
            if sf_type == "track":
                items_ = self.sp.track(uri)
            elif sf_type == "playlist":
                try:
                    plist_n = int(args[1])
                except Exception:
                    plist_n = 100
                items_ = self.get_sf_playlist_items(uri, plist_n)
            elif sf_type == "album":
                items_ = self.sp.album_tracks(uri, limit=50)["items"]
            else:
                await ctx.message.add_reaction("❌")
                await ctx.message.reply("Unsupported link, try an album, track or playlist one")

            songs = []
            if sf_type == "track":
                songs.append(f"{items_['artists'][0]['name']} - {items_['name']}")
            elif sf_type == "playlist":
                for track in items_:
                    track_name = track["track"]["name"]
                    artist_name = track["track"]["artists"][0]["name"]

                    songs.append(f"{artist_name} - {track_name}")
            elif sf_type == "album":
                for track in items_:
                    track_name = track["name"]
                    artist_name = track["artists"][0]["name"]

                    songs.append(f"{artist_name} - {track_name}")

            url = songs[0]
            emb = await self.search_and_add(url, vc, ctx)
            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass
            self.ctx = ctx
            self.message = await ctx.send(" ", embed=emb)
            await self.message.add_reaction("⏮")
            await self.message.add_reaction("⏯")
            await self.message.add_reaction("⏭")
            await ctx.message.add_reaction("✅")

            if len(songs) > 1:
                for url in songs[1:]:
                    emb = await self.search_and_add(url, vc, ctx)
        else:
            url = " ".join(args)
            emb = await self.search_and_add(url, vc, ctx, True)
        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass
        self.ctx = ctx
        self.message = await ctx.send(" ", embed=emb)
        await self.message.add_reaction("⏮")
        await self.message.add_reaction("⏯")
        await self.message.add_reaction("⏭")
        await ctx.message.add_reaction("✅")

    async def search_and_add(self, song_name: str, vc, ctx: commands.Context, is_given_by_user=False):
        """
        searches a string on Youtube and ads the first video found to the queue

        :param song_name: string to search
        :param vc: voice_client
        :param ctx: context
        :param is_given_by_user: to distinguish those given by Spotify links from those by the user

        """
        with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
            def get_info():
                return ydl.extract_info(f"ytsearch:{song_name}" if is_given_by_user else f"ytsearch:{song_name} audio", download=False)

            info = await self.loop.run_in_executor(None, get_info)
            if self.current_video:
                try:
                    if info['_type'] == 'playlist':
                        for video in info["entries"]:
                            video_c = self.compress_data(video, song_name, is_given_by_user)
                            self.videos_list.append(video_c)
                except KeyError:
                    self.videos_list.append(self.compress_data(info, song_name, is_given_by_user))

                if self.message is not None:
                    emb = self.message.embeds[0]
                else:
                    try:
                        desc = self.current_video['spotify_info']
                    except KeyError:
                        desc = self.current_video['title']
                    emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.pink())
            else:
                try:
                    if info['_type'] == 'playlist':
                        self.videos_list = [self.compress_data(entry, song_name, is_given_by_user)
                                            for entry in info["entries"]]
                        self.current_video = self.videos_list.pop(0)

                        url2 = self.current_video["sound_url"]
                        source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                        vc.play(source, after=lambda error: self.loop.create_task(self.check_playlist(ctx)))
                        desc = self.current_video['spotify_info']

                except KeyError:
                    info = self.compress_data(info, song_name, is_given_by_user)
                    self.current_video = info

                    url2 = info["sound_url"]
                    source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                    vc.play(source, after=lambda error: self.loop.create_task(self.check_playlist(ctx)))
                    desc = info['spotify_info']

                emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.pink())
        return emb

    def get_sf_playlist_items(self, uri, items=100):
        info_ = []
        stop = (items // 100) * 100
        if stop >= 100:
            for offset in range(0, stop, 100):
                info_.extend(self.sp.playlist_items(uri, limit=100, offset=offset)["items"])

        resto = items % 100
        if resto:
            info_.extend(self.sp.playlist_items(uri, limit=resto, offset=offset + 100)["items"])

        return info_

    @commands.command(
        aliases=["pn"],
        brief="- [!playnow/!pn] Makes the specified song play right now ignoring the queue",
        help="If given a search query as an argument, this behaves the same as -play but plays the song right after the current one, but if given the index (number) of a song in the queue, it "
                "moves it to be the next one to play (indexes can be negative, '-1' being the last song in "
                "the queue, '-2' second to last and so on)",
        usage="<index (position in queue) of the song>"
        )
    async def playnow(self, ctx: commands.Context, *args: str):
        try:
            index = int(args[0])
            video = self.videos_list.pop(index - 1 if index > 0 else index)
            self.videos_list = [video, *self.videos_list]
            await ctx.message.add_reaction("✅")
        except IndexError:
            await ctx.reply("Index of queue out of range")
            await ctx.message.add_reaction("❌")
        except ValueError:
            vc = ctx.voice_client
            if vc is None:
                await ctx.message.add_reaction("❌")
                await ctx.reply("Bot not in voice chat, connect it first with '-play <url>'")
                return

            self.paused = False
            url = " ".join(args)
            if self.videos_list and self.current_video:
                emb = await self.search_and_add(url, vc, ctx)
                video = self.videos_list.pop(-1)
                self.videos_list = [video, *self.videos_list]
            else:
                emb = await self.search_and_add(url, vc, ctx)

            try:
                if self.message:
                    await self.message.delete()
            except discord.NotFound:
                pass
            self.ctx = ctx
            self.message = await ctx.send(" ", embed=emb)
            await self.message.add_reaction("⏮")
            await self.message.add_reaction("⏯")
            await self.message.add_reaction("⏭")
            await ctx.message.add_reaction("✅")

    @commands.command(
        brief="- [!pause] Pauses the music player",
        help="Pauses the music player"
    )
    async def pause(self, ctx: commands.Context):
        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            self.paused = True
            await ctx.message.add_reaction("✅")
        else:
            await ctx.send("There's no music playing to pause.")

    @commands.command(
        aliases=["unpause"],
        brief="- [!resume/!unpause] Unpauses the music player"
    )
    async def resume(self, ctx: commands.Context):
        vc = ctx.voice_client

        if vc.is_paused():
            vc.resume()
            await ctx.message.add_reaction("✅")
        else:
            await ctx.reply("The bot is not currently paused.")

    @commands.command(
        aliases=["back", "b", "pr"],
        brief="- [!previous/!back/!b/!pr] Plays the last played song again",
        help="Plays the last played song again"
    )
    async def previous(self, ctx: commands.Context):
        if not self.previous_video:
            return None
        self.videos_list.insert(0, self.current_video)
        self.current_video = self.previous_video
        self.previous_video = None

        url2 = self.current_video["sound_url"]
        source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
        ctx.voice_client.stop()
        ctx.voice_client.play(source,
                              after=lambda error: self.loop.create_task(self.check_playlist(self.ctx)))
        try:
            desc = self.current_video['spotify_info']
        except KeyError:
            desc = self.current_video['title']

        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass
        emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.dark_blue())
        self.message = await ctx.send(" ", embed=emb)
        await self.message.add_reaction("⏮")
        await self.message.add_reaction("⏯")
        await self.message.add_reaction("⏭")
        await ctx.message.add_reaction("✅")

    @commands.command(
        aliases=["n", "skip"],
        brief="- [!next/!skip/!n] Skips the current song",
        help="Skips the current song and starts playing the next one in queue"
    )
    async def next(self, ctx: commands.Context):
        if not self.videos_list:
            return None
        self.previous_video = None
        self.previous_video = self.current_video
        self.current_video = self.videos_list.pop(0)
        url2 = self.current_video["sound_url"]
        source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
        ctx.voice_client.stop()
        ctx.voice_client.play(source,
                              after=lambda error: self.loop.create_task(self.check_playlist(self.ctx)))
        try:
            desc = self.current_video['spotify_info']
        except KeyError:
            desc = self.current_video['title']

        try:
            if self.message:
                await self.message.delete()
        except discord.NotFound:
            pass
        emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.dark_blue())
        self.message = await ctx.send(" ", embed=emb)
        await self.message.add_reaction("⏮")
        await self.message.add_reaction("⏯")
        await self.message.add_reaction("⏭")
        await ctx.message.add_reaction("✅")

    @commands.command(
        aliases=["q"],
        brief="- [!queue/!q] Lists 20 songs in queue",
        help="Lists 20 songs in queue, depending on the page number arguement given",
        usage="<page number>"
    )
    async def queue(self, ctx: commands.Context, pag=1):
        desc_list = []
        
        if not self.videos_list:
            emb = discord.Embed(title="Song Queue:", description="The queue is currently empty.", color=discord.Color.pink())
            emb.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar)
            await ctx.reply(" ", embed=emb)
            await ctx.message.add_reaction("✅")
            return

        for i, video in enumerate(self.videos_list[(pag - 1) * 20:], (pag - 1) * 20):
            try:
                desc_list.append(f"{i+1}) {video['spotify_info']} \n")
            except KeyError:
                desc_list.append(f"{i+1}) {video['title']} \n")
            if i == (pag * 20) - 1:
                break

        desc = " ".join(desc_list)
        emb = discord.Embed(title="Song Queue:", description=desc, color=discord.Color.pink())
        emb.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar)
        await ctx.reply(" ", embed=emb)
        await ctx.message.add_reaction("✅")



    @commands.command(
        aliases=["ql", "qlength"],
        brief="- [!queued/!ql/!qlength] Shows how many songs are in queue",
        help="Shows how many songs are in queue"
    )
    async def queued(self, ctx: commands.Context):
        await ctx.reply(f"There are currently **{len(self.videos_list)}** songs queued to play!")
        await ctx.message.add_reaction("✅")

    @commands.command(
        aliases=["clr"], 
        brief="- [!clear/!clr] Clears the queue", 
        help="Clears the queue"
    )
    async def clear(self, ctx: commands.Context):
        self.videos_list = []
        await ctx.message.add_reaction("✅")

    @commands.command(
        aliases=["s"], 
        brief="- [!shuffle/!shuf/!s] Shuffles the queue", 
        help="Shuffles the queue"
    )
    async def shuffle(self, ctx: commands.Context):
        shuffle(self.videos_list)
        await ctx.message.add_reaction("✅")

    @commands.command(
            aliases=["sw"], 
            brief="- [!swap/!sw] Swaps two songs in the queue",
            help="Swaps two songs in the queue using their queue indexes (position in queue) (indexes can be negative, '-1' being the last song in the queue, '-2' second to last and so on)",
            usage="<index of song 1> <index of song 2>"
    )
    async def swap(self, ctx: commands.Context, um: str, dois: str):
        order = self.swap_order(self.videos_list, int(um), int(dois))
        if order is None:
            await ctx.message.add_reaction("❌")
        else:
            self.videos_list = order
            await ctx.message.add_reaction("✅")

    @commands.command(
        aliases=["url"], brief="- [!link/!url] Returns the link of the currently playing song", 
        help="Returns the link of the currently playing song"
    )
    async def link(self, ctx: commands.Context):
        await ctx.reply(self.current_video['webpage_url'])
        await ctx.message.add_reaction("✅")

    @commands.command(
        brief="- [!lyrics] Returns the lyrics of the song",
        help="Returns the lyrics of the currently playing song or if an index (position in the queue) is passed as an argument, it returns the lyrics of that song in the queue (indexes can be negative, '-1' being the last song in the queue, '-2' second to last and so on)",
        usage="<Optional[index of song]>"
    )
    async def lyrics(self, ctx, index=None):
        lyrics = ""  # Initialize with an empty string

        if index is None:
            try:
                song_name = self.current_video['spotify_info']
            except KeyError:
                song_name = self.current_video['title']
        else:
            try:
                song_name = self.videos_list[int(index) + 1]['spotify_info']
            except KeyError:
                song_name = self.videos_list[int(index) + 1]['title']

        # Prepare the search query for AzLyrics
        search_query = urllib.parse.quote(song_name, safe='')
        lyrics_url = f"https://search.azlyrics.com/search.php?q={search_query}"

        page2 = requests.get(lyrics_url)
        soup2 = BeautifulSoup(page2.content, 'html.parser')

        lyrics_links = soup2.find_all("div", class_="panel")
        if len(lyrics_links) > 0:
            first_lyrics_link = lyrics_links[0].find("a")["href"]
            page3 = requests.get(first_lyrics_link, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/55.0.2883.75 Safari/537.36'})
            soup3 = BeautifulSoup(page3.content, 'html.parser')
            lyrics = soup3.find('div', class_=None).get_text()

            emb = discord.Embed(title=f"{song_name} lyrics:", description=lyrics, color=discord.Color.pink())
            emb.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar)
            await ctx.reply("", embed=emb)
        else:
            await ctx.reply(f"Sorry, the lyrics for '**{song_name}**' couldn't be found")

        await ctx.message.add_reaction("✅")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """
        checks for message reactions, if the messsage is self.message it checks the desired control and
        controls the player accordingly, pause/unpause/skip/previous

        :param reaction: reaction added
        :param user: user that added the reaction
        """
        message = reaction.message
        if message != self.message:
            return None
        if user.bot:
            return None
        else:
            if str(reaction.emoji) == "⏯":
                if self.paused:
                    self.paused = False
                    try:
                        await user.guild.voice_client.resume()
                    except TypeError:
                        pass
                else:
                    self.paused = True
                    try:
                        await user.guild.voice_client.pause()
                    except TypeError:
                        pass
                emb = message.embeds[0]
                await message.delete()
                self.message = await message.channel.send(" ", embed=emb)
                await self.message.add_reaction("⏮")
                await self.message.add_reaction("⏯")
                await self.message.add_reaction("⏭")

            elif str(reaction.emoji) == "⏮":
                if not self.previous_video:
                    return None
                self.videos_list.insert(0, self.current_video)
                self.current_video = self.previous_video
                self.previous_video = None
                url2 = self.current_video["sound_url"]
                source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                user.guild.voice_client.stop()
                user.guild.voice_client.play(source,
                                             after=lambda error: self.loop.create_task(self.check_playlist(self.ctx)))
                try:
                    desc = self.current_video['spotify_info']
                except KeyError:
                    desc = self.current_video['title']

                try:
                    if self.message:
                        await self.message.delete()
                except discord.NotFound:
                    pass
                emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.dark_blue())
                self.message = await message.channel.send(" ", embed=emb)
                await self.message.add_reaction("⏮")
                await self.message.add_reaction("⏯")
                await self.message.add_reaction("⏭")

            elif str(reaction.emoji) == "⏭":
                if not self.videos_list:
                    return None
                self.previous_video = None
                self.previous_video = self.current_video
                self.current_video = self.videos_list.pop(0)
                url2 = self.current_video["sound_url"]
                source = discord.FFmpegPCMAudio(url2, **self.FFMPEG_OPTIONS)
                user.guild.voice_client.stop()
                user.guild.voice_client.play(source, after=lambda error: self.loop.create_task(self.check_playlist(self.ctx)))
                try:
                    desc = self.current_video['spotify_info']
                except KeyError:
                    desc = self.current_video['title']

                try:
                    if self.message:
                        await self.message.delete()
                except discord.NotFound:
                    pass
                emb = discord.Embed(title="Now Playing:", description=desc, color=discord.Color.dark_blue())
                self.message = await message.channel.send(" ", embed=emb)
                await self.message.add_reaction("⏮")
                await self.message.add_reaction("⏯")
                await self.message.add_reaction("⏭")
            else:
                return None

async def setup(bot):
    await bot.add_cog(Music(bot))
    print("Setup Done!")
