from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from asyncio import sleep
from PIL import Image
from config import Config
import os, time, re, random, asyncio


user_details = {}

TARGET_CHANNEL_ID = None

custom_name = ""
        
# Pattern 1: S01E02 or S01EP02
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
# Pattern 2: S01 E02 or S01 EP02 or S01 - E01 or S01 - EP02
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
# Pattern 3: Episode Number After "E" or "EP"
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
# Pattern 3_2: episode number after - [hyphen]
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
# Pattern 4: S2 09 ex.
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
# Pattern X: Standalone Episode Number
patternX = re.compile(r'(\d+)')
#QUALITY PATTERNS 
# Pattern 5: 3-4 digits before 'p' as quality
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
# Pattern 6: Find 4k in brackets or parentheses
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
# Pattern 7: Find 2k in brackets or parentheses
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
# Pattern 8: Find HdRip without spaces
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
# Pattern 9: Find 4kX264 in brackets or parentheses
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
# Pattern 10: Find 4kx265 in brackets or parentheses
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)


@Client.on_message(filters.command("set_target") & filters.user(Config.ADMIN))
async def set_target_channel(client , message):
    global TARGET_CHANNEL_ID

    # Extract channel ID from the message
    if len(message.command) > 1:
        channel_id = message.command[1]
        try:
            TARGET_CHANNEL_ID = int(channel_id)
            await message.reply("Target channel added successfully ✅")
        except ValueError:
            await message.reply("Invalid channel ID. Please provide a valid channel ID.")
    else:
        await message.reply("Please provide a channel ID after the command. Example: /set_target 123456789")


@Client.on_message(filters.command("set_name") & filters.user(Config.ADMIN))
async def set_name(client, message):
    global custom_name

    if len(message.command) > 1:
        custom_name = " ".join(message.command[1:])
        await message.reply(f"Name added successfully ✅\nThe name was set to: {custom_name}")
    else:
        await message.reply("Please provide a name after the command. Example: /set_name MyCustomName")

def extract_quality(filename):
    # Try Quality Patterns
    match5 = re.search(pattern5, filename)
    if match5:
        print("Matched Pattern 5")
        quality5 = match5.group(1) or match5.group(2)  # Extracted quality from both patterns
        print(f"Quality: {quality5}")
        return quality5

    match6 = re.search(pattern6, filename)
    if match6:
        print("Matched Pattern 6")
        quality6 = "4k"
        print(f"Quality: {quality6}")
        return quality6

    match7 = re.search(pattern7, filename)
    if match7:
        print("Matched Pattern 7")
        quality7 = "2k"
        print(f"Quality: {quality7}")
        return quality7

    match8 = re.search(pattern8, filename)
    if match8:
        print("Matched Pattern 8")
        quality8 = "HdRip"
        print(f"Quality: {quality8}")
        return quality8

    match9 = re.search(pattern9, filename)
    if match9:
        print("Matched Pattern 9")
        quality9 = "4kX264"
        print(f"Quality: {quality9}")
        return quality9

    match10 = re.search(pattern10, filename)
    if match10:
        print("Matched Pattern 10")
        quality10 = "4kx265"
        print(f"Quality: {quality10}")
        return quality10    

    # Return "Unknown" if no pattern matches
    unknown_quality = "Unknown"
    print(f"Quality: {unknown_quality}")
    return unknown_quality
    

def extract_episode_number(filename):    
    # Try Pattern 1
    match = re.search(pattern1, filename)
    if match:
        print("Matched Pattern 1")
        return match.group(2)  # Extracted episode number
    
    # Try Pattern 2
    match = re.search(pattern2, filename)
    if match:
        print("Matched Pattern 2")
        return match.group(2)  # Extracted episode number

    # Try Pattern 3
    match = re.search(pattern3, filename)
    if match:
        print("Matched Pattern 3")
        return match.group(1)  # Extracted episode number

    # Try Pattern 3_2
    match = re.search(pattern3_2, filename)
    if match:
        print("Matched Pattern 3_2")
        return match.group(1)  # Extracted episode number
        
    # Try Pattern 4
    match = re.search(pattern4, filename)
    if match:
        print("Matched Pattern 4")
        return match.group(2)  # Extracted episode number

    # Try Pattern X
    match = re.search(patternX, filename)
    if match:
        print("Matched Pattern X")
        return match.group(1)  # Extracted episode number
        
    # Return None if no pattern matches
    return None

# Example Usage:
filename = "Naruto Shippuden S01 - EP07 - 1080p [Dual Audio] @Madflix_Bots.mkv"
episode_number = extract_episode_number(filename)
print(f"Extracted Episode Number: {episode_number}")



# Handle File Upload and Rename
@Client.on_message(filters.private & (filters.document | filters.video) & filters.user(Config.ADMIN))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("❌ Sorry, this bot doesn't support files larger than 2GB.")

    user_id = message.chat.id
    user_details[user_id] = {"filename": filename, "file_id": file.file_id}

    try:
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name:** `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply):
        user_id = message.chat.id
        new_name = message.text

        if not "." in new_name:
            ext = os.path.splitext(user_details[user_id]["filename"])[-1]
            new_name = new_name + ext

        user_details[user_id]["new_name"] = new_name
        await reply_message.delete()

        buttons = [
            [InlineKeyboardButton("📁 Document", callback_data="upload_document")],
            [InlineKeyboardButton("🎥 Video", callback_data="upload_video")]
        ]
        await message.reply(
            text=f"**Select the Output File Type**\n\n**File Name:** `{new_name}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Client.on_callback_query(filters.regex("upload"))
async def upload_file(client, query):
    global TARGET_CHANNEL_ID

    user_id = query.message.chat.id
    user_data = user_details.get(user_id)

    if not user_data or "filename" not in user_data or "file_id" not in user_data:
        return await query.message.edit("❌ Error: Missing file information. Please restart the process.")

    old_filename = user_data["filename"]
    new_filename = user_data.get("new_name", old_filename)
    file_id = user_data["file_id"]
    file_path = f"downloads/{user_id}/{new_filename}"

    # Notify Target Channel
    if not TARGET_CHANNEL_ID:
        return await query.message.edit("❌ Error: Target channel not set. Use `/set_target` to set the channel.")

    target_msg = await client.send_message(
        chat_id=TARGET_CHANNEL_ID,
        text=f"⬇️ **Starting download...**\n\n📁 **Filename:** `{new_filename}`"
    )

    # Retry Logic for Downloading
    for attempt in range(3):  # Retry up to 3 times
        try:
            start_time = time.time()
            downloaded_path = await client.download_media(
                file_id,
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=("⬇️ **Downloading...**", target_msg, start_time)
            )
            # Verify File Size
            if os.path.exists(downloaded_path) and os.path.getsize(downloaded_path) == user_data["file_size"]:
                break  # Exit retry loop if successful
        except Exception as e:
            if attempt == 2:  # Final attempt failed
                return await target_msg.edit(f"❌ Download failed: `{str(e)}`")
            await target_msg.edit(f"⚠️ Retrying download ({attempt + 1}/3)...")

    # Notify Completion
    await target_msg.edit("✅ **Download complete! Proceeding to upload...**")

    # Upload File
    await query.message.edit("⬆️ **Uploading file...**")
    upload_type = query.data.split("_")[1]

    try:
        if upload_type == "document":
            await client.send_document(
                chat_id=TARGET_CHANNEL_ID,
                document=downloaded_path,
                caption=f"**{new_filename}**",
                progress=progress_for_pyrogram,
                progress_args=("⬆️ **Uploading...**", target_msg, start_time)
            )
        elif upload_type == "video":
            await client.send_video(
                chat_id=TARGET_CHANNEL_ID,
                video=downloaded_path,
                caption=f"**{new_filename}**",
                progress=progress_for_pyrogram,
                progress_args=("⬆️ **Uploading...**", target_msg, start_time)
            )
    except Exception as e:
        await target_msg.edit(f"❌ Upload failed: `{str(e)}`")
    else:
        await target_msg.edit("✅ **Upload complete!**")
    finally:
        if os.path.exists(downloaded_path):
            os.remove(downloaded_path)
