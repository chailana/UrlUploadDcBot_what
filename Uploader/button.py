import os
import json
import time
import shutil
import asyncio
import logging
from pyrogram.types import *
from datetime import datetime

from Uploader.utitles import *
from Uploader.config import Config
from Uploader.script import Translation
from Uploader.functions.ran_text import random_char
from Uploader.functions.display_progress import progress_for_pyrogram, humanbytes

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

async def youtube_dl_call_back(bot, update):
    cb_data = update.data
    tg_send_type, youtube_dl_format, youtube_dl_ext, ranom = cb_data.split("|")
    logger.info(f"Callback data: {cb_data}")

    random1 = random_char(5)
    save_ytdl_json_path = f"{Config.DOWNLOAD_LOCATION}/{update.from_user.id}{ranom}.json"

    try:
        with open(save_ytdl_json_path, "r", encoding="utf8") as f:
            response_json = json.load(f)
    except FileNotFoundError as e:
        logger.error(f"File not found: {save_ytdl_json_path}")
        await update.message.delete()
        return

    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = f"{response_json.get('title', 'default')}_{youtube_dl_format}.{youtube_dl_ext}"

    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        youtube_dl_url = url_parts[0]
        custom_file_name = url_parts[1] if len(url_parts) > 1 else custom_file_name
        youtube_dl_username = url_parts[2] if len(url_parts) > 2 else None
        youtube_dl_password = url_parts[3] if len(url_parts) > 3 else None
    else:
        for entity in update.message.reply_to_message.entities:
            if entity.type == "text_link":
                youtube_dl_url = entity.url
            elif entity.type == "url":
                o, l = entity.offset, entity.length
                youtube_dl_url = youtube_dl_url[o:o + l]

    youtube_dl_url = youtube_dl_url.strip() if youtube_dl_url else None
    custom_file_name = custom_file_name.strip() if custom_file_name else "default_file"

    await update.message.edit_caption(caption=Translation.DOWNLOAD_START.format(custom_file_name))
    description = response_json.get("fulltitle", Translation.CUSTOM_CAPTION_UL_FILE)[:1021]

    tmp_directory_for_each_user = f"{Config.DOWNLOAD_LOCATION}/{update.from_user.id}{random1}"
    os.makedirs(tmp_directory_for_each_user, exist_ok=True)
    download_directory = os.path.join(tmp_directory_for_each_user, custom_file_name)

    command_to_exec = [
        "yt-dlp",
        "-c",
        "--max-filesize", str(Config.TG_MAX_FILE_SIZE),
        "--embed-subs" if tg_send_type != "audio" else "--extract-audio",
        "-f", youtube_dl_format + "+bestaudio" if "youtu" in youtube_dl_url else youtube_dl_format,
        "--audio-multistreams", "--video-multistreams" if tg_send_type != "audio" else None,
        youtube_dl_url,
        "-o", download_directory
    ]

    if Config.HTTP_PROXY:
        command_to_exec += ["--proxy", Config.HTTP_PROXY]
    if youtube_dl_username:
        command_to_exec += ["--username", youtube_dl_username]
    if youtube_dl_password:
        command_to_exec += ["--password", youtube_dl_password]
    
    command_to_exec.append("--no-warnings")
    logger.info(f"Executing command: {' '.join(command_to_exec)}")

    start = datetime.now()
    try:
        process = await asyncio.create_subprocess_exec(
            *command_to_exec,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()
    except Exception as exc:
        logger.error(f"Error executing yt-dlp command: {exc}")
        await update.message.edit_caption(text="An error occurred while processing the request.")
        return

    if "please report this issue" in e_response:
        error_message = e_response.replace("please report this issue", "")
        await update.message.edit_caption(text=error_message)
        return

    if t_response:
        logger.info(f"yt-dlp output: {t_response}")
        try:
            os.remove(save_ytdl_json_path)
        except FileNotFoundError:
            pass

        end_one = datetime.now()
        time_taken_for_download = (end_one - start).seconds

        try:
            file_size = os.stat(download_directory).st_size
        except FileNotFoundError:
            download_directory = f"{os.path.splitext(download_directory)[0]}.mkv"
            file_size = os.stat(download_directory).st_size

        if file_size > Config.TG_MAX_FILE_SIZE:
            await update.message.edit_caption(caption=Translation.RCHD_TG_API_LIMIT.format(
                time_taken_for_download, humanbytes(file_size)))
        else:
            await update.message.edit_caption(caption=Translation.UPLOAD_START.format(custom_file_name))
            start_time = time.time()

            if tg_send_type == "video":
                width, height, duration = await Mdata01(download_directory)
                await update.message.reply_video(
                    video=download_directory,
                    caption=description,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    progress=progress_for_pyrogram,
                    progress_args=(Translation.UPLOAD_START, update.message, start_time)
                )
            elif tg_send_type == "audio":
                duration = await Mdata03(download_directory)
                await update.message.reply_audio(
                    audio=download_directory,
                    caption=description,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=(Translation.UPLOAD_START, update.message, start_time)
                )
            elif tg_send_type == "vm":
                width, duration = await Mdata02(download_directory)
                await update.message.reply_video_note(
                    video_note=download_directory,
                    duration=duration,
                    length=width,
                    progress=progress_for_pyrogram,
                    progress_args=(Translation.UPLOAD_START, update.message, start_time)
                )
            else:
                logger.info(f"[OK] {custom_file_name}")

            end_two = datetime.now()
            time_taken_for_upload = (end_two - end_one).seconds
            shutil.rmtree(tmp_directory_for_each_user, ignore_errors=True)
            await update.message.edit_caption(caption=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(
                time_taken_for_download, time_taken_for_upload))
            logger.info(f"[OK] Downloaded in: {time_taken_for_download} seconds")
            logger.info(f"[OK] Uploaded in: {time_taken_for_upload} seconds")
