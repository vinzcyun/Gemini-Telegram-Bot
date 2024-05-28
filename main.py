import argparse
import traceback
import asyncio
import google.generativeai as genai
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import  Message

gemini_player_dict = {}
gemini_pro_player_dict = {}
default_model_dict = {}

error_info="⚠️⚠️⚠️\nDịch vụ không khả dụng !\nVui lòng nhập lại hoặc liên hệ quản trị viên!\nNguyên nhân: Có thể đang bị tràn ram hoặc không có mạng😵😵.\nĐã tự động liên hệ Admin👩‍💻."
before_generate_info="Đang trả lời...Đợi xíu nhó🤪😮‍💨"
download_pic_notify="Đang tải ảnh... Đợi xíu nha😋😋"

n = 30  #Number of historical records to keep

generation_config = {
    "temperature": 1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 8191,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {   "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

def find_all_index(str, pattern):
    index_list = [0]
    for match in re.finditer(pattern, str, re.MULTILINE):
        if match.group(1) != None:
            start = match.start(1)
            end = match.end(1)
            index_list += [start, end]
    index_list.append(len(str))
    return index_list

def replace_all(text, pattern, function):
    poslist = [0]
    strlist = []
    originstr = []
    poslist = find_all_index(text, pattern)
    for i in range(1, len(poslist[:-1]), 2):
        start, end = poslist[i : i + 2]
        strlist.append(function(text[start:end]))
    for i in range(0, len(poslist), 2):
        j, k = poslist[i : i + 2]
        originstr.append(text[j:k])
    if len(strlist) < len(originstr):
        strlist.append("")
    else:
        originstr.append("")
    new_list = [item for pair in zip(originstr, strlist) for item in pair]
    return "".join(new_list)

def escapeshape(text):
    return "▎*" + text.split()[1] + "*"

def escapeminus(text):
    return "\\" + text

def escapebackquote(text):
    return r"\`\`"

def escapeplus(text):
    return "\\" + text

def escape(text, flag=0):
    # In all other places characters
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    # must be escaped with the preceding character '\'.
    text = re.sub(r"\\\[", "@->@", text)
    text = re.sub(r"\\\]", "@<-@", text)
    text = re.sub(r"\\\(", "@-->@", text)
    text = re.sub(r"\\\)", "@<--@", text)
    if flag:
        text = re.sub(r"\\\\", "@@@", text)
    text = re.sub(r"\\", r"\\\\", text)
    if flag:
        text = re.sub(r"\@{3}", r"\\\\", text)
    text = re.sub(r"_", "\_", text)
    text = re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text = re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text = re.sub(r"\*", "\*", text)
    text = re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text = re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text = re.sub(r"\[", "\[", text)
    text = re.sub(r"\]", "\]", text)
    text = re.sub(r"\(", "\(", text)
    text = re.sub(r"\)", "\)", text)
    text = re.sub(r"\@\-\>\@", "\[", text)
    text = re.sub(r"\@\<\-\@", "\]", text)
    text = re.sub(r"\@\-\-\>\@", "\(", text)
    text = re.sub(r"\@\<\-\-\@", "\)", text)
    text = re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text = re.sub(r"~", "\~", text)
    text = re.sub(r">", "\>", text)
    text = replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text = re.sub(r"#", "\#", text)
    text = replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text = re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text = re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text = replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text = re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text = replace_all(text, r"(``)", escapebackquote)
    text = re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text = re.sub(r"=", "\=", text)
    text = re.sub(r"\|", "\|", text)
    text = re.sub(r"{", "\{", text)
    text = re.sub(r"}", "\}", text)
    text = re.sub(r"\.", "\.", text)
    text = re.sub(r"!", "\!", text)
    return text

# Prevent "create_convo" function from blocking the event loop.
async def make_new_gemini_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    # Run the synchronous "create_convo" function in a thread pool
    convo = await loop.run_in_executor(None, create_convo)
    return convo

async def make_new_gemini_pro_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    # Run the synchronous "create_convo" function in a thread pool
    convo = await loop.run_in_executor(None, create_convo)
    return convo

# Prevent "send_message" function from blocking the event loop.
async def send_message(player, message):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, player.send_message, message)

# Prevent "model.generate_content" function from blocking the event loop.
async def async_generate_content(model, contents):
    loop = asyncio.get_running_loop()

    def generate():
        return model.generate_content(contents=contents)

    response = await loop.run_in_executor(None, generate)
    return response

async def gemini(bot,message,m):
    player = None
    if str(message.from_user.id) not in gemini_player_dict:
        player = await make_new_gemini_convo()
        gemini_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        user_intro = f"Tôi là {message.from_user.first_name}, tôi muốn hỏi😊: {m}"
        await send_message(player, user_intro)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

async def gemini_pro(bot,message,m):
    player = None
    if str(message.from_user.id) not in gemini_pro_player_dict:
        player = await make_new_gemini_pro_convo()
        gemini_pro_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_pro_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        user_intro = f"Tôi là {message.from_user.first_name}, tôi muốn hỏi😊: {m}"
        await send_message(player, user_intro)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

async def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="telegram token")
    parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
    options = parser.parse_args()
    print("Đã thêm câu lệnh.")

    genai.configure(api_key=options.GOOGLE_GEMINI_KEY)

    # Init bot
    bot = AsyncTeleBot(options.tg_token)
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("start", "Bắt đầu"),
            telebot.types.BotCommand("gemini", "Gemini 1.5 Vision"),
            telebot.types.BotCommand("pro", "Gemini 1.5 Pro"),
            telebot.types.BotCommand("clear", "Xoá toàn bộ lịch sử trò chuyện"),
            telebot.types.BotCommand("switch","Chuyển đổi nhanh mô hình AI (chỉ dành cho trò chuyện riêng tư) ")
        ],
    )
    print("Bot init done.")

    # Init commands
    @bot.message_handler(commands=["start"])
    async def gemini_handler(message: Message):
        try:
            await bot.reply_to( message , escape("Xin chào, tôi là Gemini. Tôi là một mô hình ngôn ngữ được huấn luyện bởi VinZ và Google. Bạn muốn tôi giúp gì nào ?. \nCâu hỏi ví dụ: `Bạn ăn cơm chưa ?🤔🤔`"), parse_mode="MarkdownV2")
        except IndexError:
            await bot.reply_to(message, error_info)

    @bot.message_handler(commands=["gemini"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
            user_intro = f"Tôi là {message.from_user.first_name} , tôi muốn nói😊: {m}"
        except IndexError:
            await bot.reply_to( message , escape("Hãy bổ sung điều bạn muốn nói sau /gemini. \nVí dụ: `/gemini Cách để thoát ế ?🤪😜`"), parse_mode="MarkdownV2")
            return
        await gemini(bot,message,user_intro)

    @bot.message_handler(commands=["pro"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
            user_intro = f"Tôi là {message.from_user.first_name}, tôi muốn nói😊: {m}"
        except IndexError:
            await bot.reply_to( message , escape("Hãy bổ sung điều bạn muốn nói sau /pro. \nVí dụ: `/pro Bạn có thể làm gì ?😬😬`"), parse_mode="MarkdownV2")
            return
        await gemini_pro(bot,message,user_intro)

    @bot.message_handler(commands=["clear"])
    async def gemini_handler(message: Message):
        # Check if the player is already in gemini_player_dict.
        if (str(message.from_user.id) in gemini_player_dict):
            del gemini_player_dict[str(message.from_user.id)]
        if (str(message.from_user.id) in gemini_pro_player_dict):
            del gemini_pro_player_dict[str(message.from_user.id)]
        await bot.reply_to(message, "Ok, đã xoá lịch sử chat🥲🥹")

    @bot.message_handler(commands=["switch"])
    async def gemini_handler(message: Message):
        if message.chat.type != "private":
            await bot.reply_to( message , "Oh no, lệnh này chỉ dành cho trò chuyện riêng tư !🥱🤨")
            return
        # Check if the player is already in default_model_dict.
        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to( message , "Được rồi, bây giờ bạn đang dùng Gemini 1.5 Pro🙄🙄")
            return
        if default_model_dict[str(message.from_user.id)] == True:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to( message , "Được rồi, bây giờ bạn đang dùng Gemini 1.5 Pro😮‍💨🙄")
        else:
            default_model_dict[str(message.from_user.id)] = True
            await bot.reply_to( message , "Được rồi, bây giờ bạn đang dùng Gemini 1.5 Vision😋⚡")



    @bot.message_handler(func=lambda message: message.chat.type == "private", content_types=['text'])
    async def gemini_private_handler(message: Message):
        m = message.text.strip()
        user_intro = f"Tôi là {message.from_user.first_name} , tôi muốn nói😊: {m}"

        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = True
            await gemini(bot,message,user_intro)
        else:
            if default_model_dict[str(message.from_user.id)]:
                await gemini(bot,message,user_intro)
            else:
                await gemini_pro(bot,message,user_intro)


    @bot.message_handler(content_types=["photo"])
    async def gemini_photo_handler(message: Message) -> None:
        if message.chat.type != "private":
            s = message.caption
            if not s or not (s.startswith("/gemini")):
                return
            try:
                prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            s = message.caption if message.caption else ""
            try:
                prompt = s.strip()
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-pro-vision")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    # Start bot
    print("Starting Gemini_Telegram_Bot.")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())