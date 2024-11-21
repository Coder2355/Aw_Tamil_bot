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



@Client.on_message(filters.private & (filters.document | filters.video) & filters.user(Config.ADMIN))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name
    user_id = message.from_user.id
    file_id = file.file_id
	
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("❌ Sorry, this bot doesn't support files larger than 2GB.")
    if user_id not in user_details:
        user_details[user_id] = {}

    user_details[user_id]["filename"] = filename
    user_details[user_id]["file_id"] = file_id

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
async def doc(client, update):  
    global TARGET_CHANNEL_ID, custom_name
    user_id = update.message.chat.id
    user_data = user_details.get(user_id)
    if not user_data or "filename" not in user_data or "file_id" not in user_data:
        return await update.message.edit("❌ Error: Missing file information. Please restart the process.")

    filename = user_data["filename"]
    file_id = user_data["file_id"]
    episode = extract_episode_number(filename)
    quality = extract_quality(filename)
	
    # Creating Directory for Metadata
    if not os.path.isdir("Metadata"):
        os.mkdir("Metadata")
        
    # Extracting necessary information    
    prefix = await jishubotz.get_prefix(update.message.chat.id)
    suffix = await jishubotz.get_suffix(update.message.chat.id)
    new_name = update.message.text
    if ":-" in new_name and len(new_name.split(":-")) > 1:
        new_filename_ = new_name.split(":-")[1]
    else:
        return await update.message.edit("❌ Error: Invalid filename format. Ensure the name contains ':-'.")
    
    if file_id in user_details:
        elapsed_time = (datetime.now() - user_details[file_id]).seconds
        if elapsed_time < 10:
            print("File is being ignored as it is currently being renamed or was renamed recently.")
            return
	
    try:
        new_filename = add_prefix_suffix(new_filename_, prefix, suffix)
    except Exception as e:
        return await update.message.edit(f"Something Went Wrong Can't Able To Set Prefix Or Suffix 🥺 \n\n**Contact My Creator :** @CallAdminRobot\n\n**Error :** `{e}`")
    
    file_path = f"downloads/{update.from_user.id}/{new_filename}"
    file = message 
    data = f" {custom_name} -S01 - EP{episode} - {quality} Tamil "

    if not TARGET_CHANNEL_ID:
        await message.reply("**Error:** Target channel not set. Use /set_target to set the channel.")
        return

    ms = await client.send_message(chat_id=TARGET_CHANNEL_ID, text=data + "🚀 Start Downloading From the Website ⚡")
    try:
     	path = await client.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram,progress_args=(data, "🚀  Downloading Anime From the Website ⚡", ms, time.time()))                    
    except Exception as e:
     	return await ms.edit(e)
    

    # Metadata Adding Code
    _bool_metadata = await jishubotz.get_metadata(update.message.chat.id) 
    
    if _bool_metadata:
        metadata = await jishubotz.get_metadata_code(update.message.chat.id)
        metadata_path = f"Metadata/{new_filename}"
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("⏳ Mode Changing...  ⚡")

    duration = 0
    try:
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        if metadata.has("duration"):
           duration = metadata.get('duration').seconds
        parser.close()   
    except:
        pass
        
    ph_path = None
    user_id = int(update.message.chat.id) 
    media = getattr(file, file.media.value)
    c_caption = await jishubotz.get_caption(update.message.chat.id)
    c_thumb = await jishubotz.get_thumbnail(update.message.chat.id)

    if c_caption:
         try:
             caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
         except Exception as e:
             return await ms.edit(text=f"Your Caption Error Except Keyword Argument: ({e})")             
    else:
         caption = f"**{new_filename}**"
 
    if (media.thumbs or c_thumb):
         if c_thumb:
             ph_path = await client.download_media(c_thumb)
             width, height, ph_path = await fix_thumb(ph_path)
         else:
             try:
                 ph_path_ = await take_screen_shot(file_path, os.path.dirname(os.path.abspath(file_path)), random.randint(0, duration - 1))
                 width, height, ph_path = await fix_thumb(ph_path_)
             except Exception as e:
                 ph_path = None
                 print(e)  


    await ms.edit("💠 Try To Upload...  ⚡")
    type = update.data.split("_")[1]
    try:
        if type == "document":
            await bot.send_document(
                chat_id=TARGET_CHANNEL_ID,
                document=metadata_path if _bool_metadata else file_path,
                thumb=ph_path, 
                caption=caption, 
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading...  ⚡", ms, time.time()))

        elif type == "video": 
            await bot.send_video(
                chat_id=TARGET_CHANNEL_ID,
                video=metadata_path if _bool_metadata else file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading...  ⚡", ms, time.time()))

        elif type == "audio": 
            await bot.send_audio(
                chat_id=TARGET_CHANNEL_ID,
                audio=metadata_path if _bool_metadata else file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading...  ⚡", ms, time.time()))


    except Exception as e:          
        os.remove(file_path)
        if ph_path:
            os.remove(ph_path)
        return await ms.edit(f"**Error :** `{e}`")    
 
    await ms.delete() 
    if ph_path:
        os.remove(ph_path)
    if file_path:
        os.remove(file_path)




# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @JishuBotz
# Developer @JishuDeveloper
