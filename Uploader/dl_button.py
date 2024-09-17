from PIL import Image
from Uploader.functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from Uploader.utitles import *
from Uploader.script import Translation
from Uploader.config import Config
from datetime import datetime
import time
import shutil
import os
import math
import json
import aiohttp
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


async def ddl_call_back(bot, update):
    try:
        cb_data = update.data
        tg_send_type, youtube_dl_format, youtube_dl_ext = cb_data.split("=")
        youtube_dl_url = update.message.reply_to_message.text
        thumb_image_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ".jpg"
        custom_file_name = os.path.basename(youtube_dl_url)
        
        if " " in youtube_dl_url:
            url_parts = youtube_dl_url.split(" * ")
            if len(url_parts) == 2:
                youtube_dl_url = url_parts[0]
                custom_file_name = url_parts[1]
            else:
                for entity in update.message.reply_to_message.entities:
                    if entity.type == "text_link":
                        youtube_dl_url = entity.url
                    elif entity.type == "url":
                        o = entity.offset
                        l = entity.length
                        youtube_dl_url = youtube_dl_url[o:o + l]
        
        youtube_dl_url = youtube_dl_url.strip() if youtube_dl_url else ""
        custom_file_name = custom_file_name.strip() if custom_file_name else ""
        
        if f".{youtube_dl_ext}" not in custom_file_name:
            custom_file_name += f'.{youtube_dl_ext}'
        
        logger.info(youtube_dl_url)
        logger.info(custom_file_name)
        
        start = datetime.now()
        await bot.edit_message_text(
            text=Translation.DOWNLOAD_START.format(custom_file_name),
            chat_id=update.message.chat.id,
            message_id=update.message.id
        )
        
        tmp_directory_for_each_user = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id)
        if not os.path.isdir(tmp_directory_for_each_user):
            os.makedirs(tmp_directory_for_each_user)
        
        download_directory = f"{tmp_directory_for_each_user}/{custom_file_name}"
        async with aiohttp.ClientSession() as session:
            c_time = time.time()
            try:
                await download_coroutine(
                    bot,
                    session,
                    youtube_dl_url,
                    download_directory,
                    update.message.chat.id,
                    update.message.id,
                    c_time
                )
            except asyncio.TimeoutError:
                await bot.edit_message_text(
                    text=Translation.SLOW_URL_DECED,
                    chat_id=update.message.chat.id,
                    message_id=update.message.id
                )
                return False
        
        if os.path.exists(download_directory):
            save_ytdl_json_path = Config.DOWNLOAD_LOCATION + "/" + str(update.message.chat.id) + ".json"
            if os.path.exists(save_ytdl_json_path):
                os.remove(save_ytdl_json_path)
            
            end_one = datetime.now()
            await bot.edit_message_text(
                text=Translation.UPLOAD_START,
                chat_id=update.message.chat.id,
                message_id=update.message.id
            )
            
            file_size = Config.TG_MAX_FILE_SIZE + 1
            try:
                file_size = os.stat(download_directory).st_size
            except FileNotFoundError:
                download_directory = os.path.splitext(download_directory)[0] + "." + "mkv"
                file_size = os.stat(download_directory).st_size
            
            if file_size > Config.TG_MAX_FILE_SIZE:
                await bot.edit_message_text(
                    chat_id=update.message.chat.id,
                    text=Translation.RCHD_TG_API_LIMIT,
                    message_id=update.message.id
                )
            else:
                start_time = time.time()
                if tg_send_type == "video":
                    width, height, duration = await Mdata01(download_directory)
                    await bot.send_video(
                        chat_id=update.message.chat.id,
                        video=download_directory,
                        caption=custom_file_name,
                        duration=duration,
                        width=width,
                        height=height,
                        supports_streaming=True,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.UPLOAD_START,
                            update.message,
                            start_time
                        )
                    )
                elif tg_send_type == "audio":
                    duration = await Mdata03(download_directory)
                    await bot.send_audio(
                        chat_id=update.message.chat.id,
                        audio=download_directory,
                        caption=custom_file_name,
                        duration=duration,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.UPLOAD_START,
                            update.message,
                            start_time
                        )
                    )
                elif tg_send_type == "vm":
                    width, duration = await Mdata02(download_directory)
                    await bot.send_video_note(
                        chat_id=update.message.chat.id,
                        video_note=download_directory,
                        duration=duration,
                        length=width,
                        thumb=thumb_image_path,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.UPLOAD_START,
                            update.message,
                            start_time
                        )
                    )
                else:
                    await bot.send_document(
                        chat_id=update.message.chat.id,
                        document=download_directory,
                        caption=custom_file_name,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.UPLOAD_START,
                            update.message,
                            start_time
                        )
                    )
                
                if os.path.exists(download_directory):
                    os.remove(download_directory)
                if os.path.exists(thumb_image_path):
                    os.remove(thumb_image_path)
                
                end_two = datetime.now()
                time_taken_for_download = (end_one - start).seconds
                time_taken_for_upload = (end_two - end_one).seconds
                
                await bot.edit_message_text(
                    text=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(
                        time_taken_for_download, time_taken_for_upload),
                    chat_id=update.message.chat.id,
                    message_id=update.message.id,
                    disable_web_page_preview=True
                )
                
                logger.info(f"[OK] Downloaded in: {str(time_taken_for_download)}")
                logger.info(f"[OK] Uploaded in: {str(time_taken_for_upload)}")
        else:
            await bot.edit_message_text(
                text=Translation.NO_VOID_FORMAT_FOUND.format("Incorrect Link"),
                chat_id=update.message.chat.id,
                message_id=update.message.id,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if update.message:
            await bot.edit_message_text(
                text="An error occurred while processing your request.",
                chat_id=update.message.chat.id,
                message_id=update.message.id
            )


async def download_coroutine(bot, session, url, file_name, chat_id, message_id, start):
    downloaded = 0
    display_message = ""
    try:
        async with session.get(url, timeout=Config.PROCESS_MAX_TIMEOUT) as response:
            total_length = int(response.headers.get("Content-Length", 0))
            content_type = response.headers.get("Content-Type", "")
            if "text" in content_type and total_length < 500:
                return await response.release()
            with open(file_name, "wb") as f_handle:
                while True:
                    chunk = await response.content.read(Config.CHUNK_SIZE)
                    if not chunk:
                        break
                    f_handle.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    diff = now - start
                    if round(diff % 5.00) == 0 or downloaded == total_length:
                        percentage = downloaded * 100 / total_length
                        speed = downloaded / diff
                        elapsed_time = round(diff) * 1000
                        time_to_completion = round((total_length - downloaded) / speed) * 1000
                        estimated_total_time = elapsed_time + time_to_completion
                        try:
                            current_message = """**Download Status**
URL: {}
File Size: {}
Downloaded: {}
ETA: {}""".format(
                                url,
                                humanbytes(total_length),
                                humanbytes(downloaded),
                                TimeFormatter(estimated_total_time)
                            )
                            if current_message != display_message:
                                await bot.edit_message_text(
                                    chat_id,
                                    message_id,
                                    text=current_message
                                )
                                display_message = current_message
                        except Exception as e:
                            logger.info(str(e))
    except Exception as e:
        logger.error(f"Download error: {e}")
    finally:
        await response.release()
