from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)
import os
import random
import string

# ================= ENV =================
TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

# ================= STORAGE =================
user_active_ticket = {}
ticket_status = {}
ticket_user = {}
ticket_username = {}
ticket_messages = {}
user_tickets = {}
group_message_map = {}

# ================= HELPERS =================
def generate_ticket_id(length=8):
    chars = string.ascii_letters + string.digits + "*#@$&"
    return "BV-" + "".join(random.choice(chars) for _ in range(length))

def ticket_header(ticket_id, status):
    return f"🎫 Ticket ID: {ticket_id}\nStatus: {status}\n\n"

def user_info_block(user):
    return (
        "User Information\n"
        f"• User ID   : {user.id}\n"
        f"• Username  : @{user.username}\n"
        f"• Full Name : {user.first_name}\n\n"
    )

# ================= /start =================
async def start(update: Update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎟️ Create Ticket", callback_data="create_ticket")]
    ])
    await update.message.reply_text(
        "Hello Sir/Mam 👋\n\n"
        "Welcome to BlockVeil Support.\n"
        "Use the button below to create a support ticket.\n\n"
        "📧 support.blockveil@protonmail.com\n\n"
        "— BlockVeil Support Team",
        reply_markup=keyboard
    )

# ================= CREATE TICKET =================
async def create_ticket(update: Update, context):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if user.id in user_active_ticket:
        await query.message.reply_text(
            f"🎫 You already have an active ticket:\n{user_active_ticket[user.id]}"
        )
        return

    ticket_id = generate_ticket_id()
    user_active_ticket[user.id] = ticket_id
    ticket_status[ticket_id] = "Pending"
    ticket_user[ticket_id] = user.id
    ticket_username[ticket_id] = user.username
    ticket_messages[ticket_id] = []
    user_tickets.setdefault(user.id, []).append(ticket_id)

    await query.message.reply_text(
        f"🎫 Ticket Created: {ticket_id}\n"
        "Status: Pending\n\n"
        "Please send your message."
    )

# ================= USER MESSAGE =================
async def user_message(update: Update, context):
    user = update.message.from_user

    if user.id not in user_active_ticket:
        await update.message.reply_text(
            "❗ Please create a ticket first.\n\n"
            "Click /start to submit a new support ticket.\n\n"
            "To track an existing ticket, please use the /status command to view its current status."
        )
        return

    ticket_id = user_active_ticket[user.id]

    if ticket_status[ticket_id] == "Pending":
        ticket_status[ticket_id] = "Processing"

    header = ticket_header(ticket_id, ticket_status[ticket_id]) + user_info_block(user) + "Message:\n"

    if update.message.text:
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=header + update.message.text
        )
        group_message_map[sent.message_id] = ticket_id
        ticket_messages[ticket_id].append((user.first_name, update.message.text))

# ================= GROUP REPLY =================
async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return

    reply_id = update.message.reply_to_message.message_id
    if reply_id not in group_message_map:
        return

    ticket_id = group_message_map[reply_id]
    user_id = ticket_user[ticket_id]

    if update.message.text:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎫 Ticket ID: {ticket_id}\n\n{update.message.text}"
        )
        ticket_messages[ticket_id].append(("BlockVeil Support", update.message.text))

# ================= /close (ARG OR REPLY) =================
async def close_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    ticket_id = None

    # Case 1: /close BV-XXXXX
    if context.args:
        ticket_id = context.args[0]

    # Case 2: reply + /close
    elif update.message.reply_to_message:
        reply_id = update.message.reply_to_message.message_id
        ticket_id = group_message_map.get(reply_id)

    if not ticket_id or ticket_id not in ticket_status:
        await update.message.reply_text(
            "❌ Ticket not found.\nUse /close BV-XXXXX or reply with /close"
        )
        return

    if ticket_status[ticket_id] == "Closed":
        await update.message.reply_text("⚠️ Ticket already closed.")
        return

    user_id = ticket_user[ticket_id]
    ticket_status[ticket_id] = "Closed"
    user_active_ticket.pop(user_id, None)

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"🎫 Ticket ID: {ticket_id}\n"
            "Status: Closed\n\n"
            "Thank you for contacting BlockVeil Support."
        )
    )
    await update.message.reply_text(f"✅ Ticket {ticket_id} closed.")

# ================= /open =================
async def open_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        return

    ticket_id = context.args[0]
    if ticket_id not in ticket_status:
        await update.message.reply_text("❌ Ticket not found.")
        return

    if ticket_status[ticket_id] != "Closed":
        await update.message.reply_text("⚠️ Ticket already open.")
        return

    ticket_status[ticket_id] = "Processing"
    user_id = ticket_user[ticket_id]
    user_active_ticket[user_id] = ticket_id

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎫 Ticket ID: {ticket_id}\nStatus: Reopened"
    )
    await update.message.reply_text(f"✅ Ticket {ticket_id} reopened.")

# ================= /status =================
async def status_ticket(update: Update, context):
    if not context.args or context.args[0] not in ticket_status:
        await update.message.reply_text(
            "By entering /status BV-XXXXX (replace with your own Ticket ID), "
            "the user can check the current status of their support ticket."
        )
        return

    ticket_id = context.args[0]
    text = f"🎫 Ticket ID: {ticket_id}\nStatus: {ticket_status[ticket_id]}"

    if update.effective_chat.id == GROUP_ID:
        text += f"\nUser: @{ticket_username.get(ticket_id)}"

    await update.message.reply_text(text)

# ================= /list =================
async def list_tickets(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        return

    mode = context.args[0].lower()
    items = []

    for tid, status in ticket_status.items():
        if mode == "open" and status != "Closed":
            items.append((tid, ticket_username.get(tid)))
        elif mode == "close" and status == "Closed":
            items.append((tid, ticket_username.get(tid)))

    if not items:
        await update.message.reply_text("No tickets found.")
        return

    title = "📂 Open Tickets\n\n" if mode == "open" else "📁 Closed Tickets\n\n"
    text = title
    for i, (tid, uname) in enumerate(items, 1):
        text += f"{i}. {tid} – @{uname}\n"

    await update.message.reply_text(text)

# ================= INIT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("close", close_ticket))
app.add_handler(CommandHandler("open", open_ticket))
app.add_handler(CommandHandler("status", status_ticket))
app.add_handler(CommandHandler("list", list_tickets))
app.add_handler(CallbackQueryHandler(create_ticket, pattern="create_ticket"))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_reply))

app.run_polling()
