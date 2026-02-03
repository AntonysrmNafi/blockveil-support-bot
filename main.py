
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters
)
import os

TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

message_map = {}


def build_header(user):
    username = f"@{user.username}" if user.username else "N/A"
    return (
        "NEW SUPPORT MESSAGE RECEIVED\n"
        "───────────────────────────\n\n"
        "User Information\n"
        f"• User ID   : {user.id}\n"
        f"• Username  : {username}\n"
        f"• Full Name : {user.first_name}\n\n"
        "───────────────────────────\n"
    )


async def start(update: Update, context):
    await update.message.reply_text(
        "Hello Sir/Mam 👋\n\n"
        "Welcome to BlockVeil Support.\n"
        "You can use this bot to contact the BlockVeil team for support, "
        "questions, or assistance. Simply send your message here and our team "
        "will respond as soon as possible.\n\n"
        "🔐 Privacy Notice\n"
        "Your information is kept strictly confidential. We do not share or "
        "disclose user data with any third party. All details are used only for "
        "support and communication purposes.\n\n"
        "📧 Alternative Contact\n"
        "If needed, you may also contact us via email for further assistance:\n"
        "support.blockveil@protonmail.com\n\n"
        "———\n\n"
        "BlockVeil Support Team"
    )


async def user_message(update: Update, context):
    user = update.message.from_user
    header = build_header(user)

    if update.message.text:
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=header +
                 "Message Content\n"
                 "───────────────────────────\n"
                 f"{update.message.text}"
        )

    elif update.message.photo:
        sent = await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=update.message.photo[-1].file_id,
            caption=header +
                    "Message Content\n"
                    "───────────────────────────\n"
                    "[Photo]"
        )

    elif update.message.video:
        sent = await context.bot.send_video(
            chat_id=GROUP_ID,
            video=update.message.video.file_id,
            caption=header +
                    "Message Content\n"
                    "───────────────────────────\n"
                    "[Video]"
        )

    elif update.message.document:
        sent = await context.bot.send_document(
            chat_id=GROUP_ID,
            document=update.message.document.file_id,
            caption=header +
                    "Message Content\n"
                    "───────────────────────────\n"
                    "[File]"
        )

    elif update.message.voice:
        sent = await context.bot.send_voice(
            chat_id=GROUP_ID,
            voice=update.message.voice.file_id,
            caption=header +
                    "Message Content\n"
                    "───────────────────────────\n"
                    "[Voice Message]"
        )
    else:
        return

    message_map[sent.message_id] = user.id


async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return

    replied_id = update.message.reply_to_message.message_id
    if replied_id not in message_map:
        return

    user_id = message_map[replied_id]

    if update.message.text:
        await context.bot.send_message(chat_id=user_id, text=update.message.text)

    elif update.message.photo:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=update.message.photo[-1].file_id,
            caption=update.message.caption or ""
        )

    elif update.message.video:
        await context.bot.send_video(
            chat_id=user_id,
            video=update.message.video.file_id,
            caption=update.message.caption or ""
        )

    elif update.message.document:
        await context.bot.send_document(
            chat_id=user_id,
            document=update.message.document.file_id,
            caption=update.message.caption or ""
        )

    elif update.message.voice:
        await context.bot.send_voice(
            chat_id=user_id,
            voice=update.message.voice.file_id,
            caption=update.message.caption or ""
        )


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_reply))

app.run_polling()
