from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from hachoir.metadata import extractMetadata
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from asyncio import sleep
import os, time, random, asyncio


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name  
    if file.file_size > 2000 * 1024 * 1024:
         return await message.reply_text("Sorry Bro This Bot Doesn't Support Uploading Files Bigger Than 2GB")

    try:
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id
        )       
        await sleep(30)
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**Please Enter New Filename**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id
        )
    except:
        pass


@Client.on_message(filters.private & filters.text)
async def process_filename(client, message):
    if message.reply_to_message:
        # Check if the message is a reply to the previous media message
        original_message = message.reply_to_message
        if original_message.media:
            file = getattr(original_message, original_message.media.value)
            file_id = file.file_id  # Get the file_id
            new_name = message.text  # Get the new name from the user input
            
            # If no extension provided, assume the original file extension
            if not "." in new_name:
                extn = file.file_name.rsplit('.', 1)[-1] if "." in file.file_name else "mkv"
                new_name = new_name + "." + extn
            
            await message.reply_text(f"Renaming to `{new_name}`...")
            # Start downloading the file
            file_path = f"downloads/{message.from_user.id}/{new_name}"
            ms = await message.reply_text("🚀 Downloading...  ⚡")
            
            try:
                path = await client.download_media(
                    file_id,
                    file_name=file_path,
                    progress=progress_for_pyrogram,
                    progress_args=("🚀 Downloading...  ⚡", ms, time.time())
                )
            except Exception as e:
                return await ms.edit(f"Error while downloading: {e}")

            # After downloading, proceed with metadata, thumbnail, etc.
            await ms.edit("Download completed! Processing...")
            _bool_metadata = await jishubotz.get_metadata(message.chat.id) 
            if _bool_metadata:
                metadata = await jishubotz.get_metadata_code(message.chat.id)
                metadata_path = f"Metadata/{new_name}"
                await add_metadata(path, metadata_path, metadata, ms)
            
            duration = 0
            try:
                parser = createParser(file_path)
                metadata = extractMetadata(parser)
                if metadata.has("duration"):
                    duration = metadata.get('duration').seconds
                parser.close()   
            except:
                pass

            # Create thumbnail and prepare caption
            ph_path = None
            c_caption = await jishubotz.get_caption(message.chat.id)
            c_thumb = await jishubotz.get_thumbnail(message.chat.id)

            if c_caption:
                caption = c_caption.format(filename=new_name, filesize=humanbytes(file.file_size), duration=convert(duration))
            else:
                caption = f"**{new_name}**"

            if c_thumb:
                ph_path = await client.download_media(c_thumb)
                width, height, ph_path = await fix_thumb(ph_path)
            else:
                try:
                    ph_path_ = await take_screen_shot(file_path, os.path.dirname(file_path), random.randint(0, duration - 1))
                    width, height, ph_path = await fix_thumb(ph_path_)
                except Exception as e:
                    ph_path = None
                    print(e)

            # Process upload
            await ms.edit("💠 Uploading...  ⚡")
            
            try:
                # Upload the file as a document (always)
                await client.send_document(
                    message.chat.id,
                    document=metadata_path if _bool_metadata else path,
                    caption=caption,
                    thumb=ph_path,
                    progress=progress_for_pyrogram,
                    progress_args=("💠 Uploading...  ⚡", ms, time.time())
                )
            except Exception as e:
                await ms.edit(f"Error while uploading: {e}")
                return

            await ms.delete()
            if ph_path:
                os.remove(ph_path)
            if path:
                os.remove(path)
