import asyncio
import os
import random
from asyncio import QueueEmpty

from config import get_queue
from pyrogram import filters
from pyrogram.types import (CallbackQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, KeyboardButton, Message,
                            ReplyKeyboardMarkup, ReplyKeyboardRemove)
from pytgcalls import StreamType
from pytgcalls.types.input_stream import InputAudioStream, InputStream

from Yukki import BOT_USERNAME, MUSIC_BOT_NAME, app, db_mem
from Yukki.Core.PyTgCalls import Queues, Yukki
from Yukki.Core.PyTgCalls.Converter import convert
from Yukki.Core.PyTgCalls.Downloader import download
from Yukki.Database import (is_active_chat, is_music_playing, music_off,
                            music_on, remove_active_chat)
from Yukki.Decorators.admins import AdminRightsCheck
from Yukki.Decorators.checker import checker, checkerCB
from Yukki.Inline import audio_markup, primary_markup
from Yukki.Utilities.changers import time_to_seconds
from Yukki.Utilities.chat import specialfont_to_normal
from Yukki.Utilities.theme import check_theme
from Yukki.Utilities.thumbnails import gen_thumb
from Yukki.Utilities.timer import start_timer
from Yukki.Utilities.youtube import get_yt_info_id

loop = asyncio.get_event_loop()


__MODULE__ = "Sesli Sohbet"
__HELP__ = """


/pause
- Sesli sohbette müzik çalmayı duraklatın.

/resume
- Sesli sohbette duraklatılmış müziği devam ettirin.

/skip
- Sesli sohbette geçerli çalınan müziği atla

/end or /stop
- Müziği Kapatın.

/queue
- Sıra listesini kontrol et.


**Not:**
Sadece Sudo Kullanıcıları için

/activevc
- Bottaki aktif sesli sohbetleri kontrol edin.

"""


@app.on_message(
    filters.command(["pause", "skip", "resume", "stop", "end"])
    & filters.group
)
@AdminRightsCheck
@checker
async def admins(_, message: Message):
    global get_queue
    if not len(message.command) == 1:
        return await message.reply_text("Hata! Yanlış Komut Kullanımı.")
    if not await is_active_chat(message.chat.id):
        return await message.reply_text("Sesli sohbette hiçbir şey çalmıyor.")
    chat_id = message.chat.id
    if message.command[0][1] == "a":
        if not await is_music_playing(message.chat.id):
            return await message.reply_text("MMüzik zaten Duraklatıldı.")
        await music_off(chat_id)
        await Yukki.pytgcalls.pause_stream(chat_id)
        await message.reply_text(
            f"🎧 Sesli sohbet Duraklatıldı {message.from_user.mention}!"
        )
    if message.command[0][1] == "e":
        if await is_music_playing(message.chat.id):
            return await message.reply_text("Müzik zaten Çalıyor.")
        await music_on(chat_id)
        await Yukki.pytgcalls.resume_stream(message.chat.id)
        await message.reply_text(
            f"🎧 Sesli sohbet Devam etti {message.from_user.mention}!"
        )
    if message.command[0][1] == "t" or message.command[0][1] == "n":
        try:
            Queues.clear(message.chat.id)
        except QueueEmpty:
            pass
        await remove_active_chat(chat_id)
        await Yukki.pytgcalls.leave_group_call(message.chat.id)
        await message.reply_text(
            f"🎧 Sesli sohbeti Sonlandırıldı {message.from_user.mention}!"
        )
    if message.command[0][1] == "k":
        Queues.task_done(chat_id)
        if Queues.is_empty(chat_id):
            await remove_active_chat(chat_id)
            await message.reply_text(
                "Sırada artık müzik __Yok__ \n\nSesli Sohbetten Ayrılıyorum"
            )
            await Yukki.pytgcalls.leave_group_call(message.chat.id)
            return
        else:
            videoid = Queues.get(chat_id)["file"]
            got_queue = get_queue.get(chat_id)
            if got_queue:
                got_queue.pop(0)
            finxx = f"{videoid[0]}{videoid[1]}{videoid[2]}"
            aud = 0
            if str(finxx) != "raw":
                mystic = await message.reply_text(
                    f"**{MUSIC_BOT_NAME} Çalma listesi İşlevi**\n\n__Bir Sonraki Müziği Çalma Listesinden İndirme....__"
                )
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                ) = get_yt_info_id(videoid)
                await mystic.edit(
                    f"**{MUSIC_BOT_NAME} İndiriyor**\n\n**Başlık:** {title[:50]}\n\n0% ▓▓▓▓▓▓▓▓▓▓▓▓ 100%"
                )
                downloaded_file = await loop.run_in_executor(
                    None, download, videoid, mystic, title
                )
                raw_path = await convert(downloaded_file)
                await Yukki.pytgcalls.change_stream(
                    chat_id,
                    InputStream(
                        InputAudioStream(
                            raw_path,
                        ),
                    ),
                )
                theme = await check_theme(chat_id)
                chat_title = await specialfont_to_normal(message.chat.title)
                thumb = await gen_thumb(
                    thumbnail, title, message.from_user.id, theme, chat_title
                )
                buttons = primary_markup(
                    videoid, message.from_user.id, duration_min, duration_min
                )
                await mystic.delete()
                mention = db_mem[videoid]["username"]
                final_output = await message.reply_photo(
                    photo=thumb,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    caption=(
                        f"<b>__Atlanan Sesli Sohbet__</b>\n\n🎥<b>__Oynamaya başladı:__ </b>[{title[:25]}](https://www.youtube.com/watch?v={videoid}) \n⏳<b>__Süre:__</b> {duration_min} Dakika\n👤**__Tarafından Talep edildi:__** {mention}"
                    ),
                )
                os.remove(thumb)
            else:
                await Yukki.pytgcalls.change_stream(
                    chat_id,
                    InputStream(
                        InputAudioStream(
                            videoid,
                        ),
                    ),
                )
                afk = videoid
                title = db_mem[videoid]["title"]
                duration_min = db_mem[videoid]["duration"]
                duration_sec = int(time_to_seconds(duration_min))
                mention = db_mem[videoid]["username"]
                videoid = db_mem[videoid]["videoid"]
                if str(videoid) == "smex1":
                    buttons = buttons = audio_markup(
                        videoid,
                        message.from_user.id,
                        duration_min,
                        duration_min,
                    )
                    thumb = "Utils/Telegram.JPEG"
                    aud = 1
                else:
                    _path_ = _path_ = (
                        (str(afk))
                        .replace("_", "", 1)
                        .replace("/", "", 1)
                        .replace(".", "", 1)
                    )
                    thumb = f"cache/{_path_}final.png"
                    buttons = primary_markup(
                        videoid,
                        message.from_user.id,
                        duration_min,
                        duration_min,
                    )
                final_output = await message.reply_photo(
                    photo=thumb,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    caption=f"<b>__Atlanan Sesli Sohbet__</b>\n\n🎥<b>__Oynamaya Başladı:__</b> {title} \n⏳<b>__Süre:__</b> {duration_min} \n👤<b>__Tarafından Talep edildi:__ </b> {mention}",
                )
            await start_timer(
                videoid,
                duration_min,
                duration_sec,
                final_output,
                message.chat.id,
                message.from_user.id,
                aud,
            )