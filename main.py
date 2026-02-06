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
import os, random, string
from io import BytesIO

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

def mono(tid):
    return f"`{tid}`"

def ticket_header(tid, status):
    return f"🎫 Ticket ID: {mono(tid)}\nStatus: {status}\n\n"

# ================= /start =================
async def start(update: Update, context):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎟️ Create Ticket", callback_data="create_ticket")]
    ])
    await update.message.reply_text(
        "Welcome to BlockVeil Support.\n\nClick below to create a support ticket.",
        reply_markup=kb
    )

# ================= CREATE =================
async def create_ticket(update: Update, context):
    q = update.callback_query
    await q.answer()
    u = q.from_user

    if u.id in user_active_ticket:
        await q.message.reply_text(
            f"You already have an active ticket:\n{mono(user_active_ticket[u.id])}",
            parse_mode="Markdown"
        )
        return

    tid = generate_ticket_id()
    user_active_ticket[u.id] = tid
    ticket_status[tid] = "Pending"
    ticket_user[tid] = u.id
    ticket_username[tid] = u.username
    ticket_messages[tid] = []
    user_tickets.setdefault(u.id, []).append(tid)

    await q.message.reply_text(
        f"🎫 Ticket Created: {mono(tid)}\nStatus: Pending",
        parse_mode="Markdown"
    )

# ================= USER MSG =================
async def user_message(update: Update, context):
    u = update.message.from_user

    if u.id not in user_active_ticket:
        await update.message.reply_text(
            "❗ Please create a ticket first.\n\nClick /start to submit a new support ticket.\nUse /status to track tickets."
        )
        return

    tid = user_active_ticket[u.id]
    if ticket_status[tid] == "Pending":
        ticket_status[tid] = "Processing"

    text = update.message.text or "[Media]"
    sent = await context.bot.send_message(
        GROUP_ID,
        ticket_header(tid, ticket_status[tid]) + text,
        parse_mode="Markdown"
    )

    group_message_map[sent.message_id] = tid
    ticket_messages[tid].append((u.first_name, text))

# ================= GROUP REPLY =================
async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return

    mid = update.message.reply_to_message.message_id
    if mid not in group_message_map:
        return

    tid = group_message_map[mid]
    uid = ticket_user[tid]

    msg = update.message.text or "[Media]"
    await context.bot.send_message(
        uid,
        f"🎫 Ticket ID: {mono(tid)}\n\n{msg}",
        parse_mode="Markdown"
    )
    ticket_messages[tid].append(("BlockVeil Support", msg))

# ================= /status =================
async def status_ticket(update: Update, context):
    if not context.args or context.args[0] not in ticket_status:
        await update.message.reply_text("Usage: /status BV-XXXXX")
        return

    tid = context.args[0]
    text = f"🎫 Ticket ID: {mono(tid)}\nStatus: {ticket_status[tid]}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ================= /list =================
async def list_tickets(update: Update, context):
    if update.effective_chat.id != GROUP_ID or not context.args:
        return

    mode = context.args[0].lower()
    open_alias = ["open", "opened"]
    close_alias = ["close", "closed"]

    data = []
    for tid, st in ticket_status.items():
        if mode in open_alias and st != "Closed":
            data.append(tid)
        elif mode in close_alias and st == "Closed":
            data.append(tid)

    if not data:
        await update.message.reply_text("No tickets found.")
        return

    text = ""
    for i, tid in enumerate(data, 1):
        text += f"{i}. {mono(tid)}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ================= /send =================
async def send_direct(update: Update, context):
    if update.effective_chat.id != GROUP_ID or len(context.args) < 2:
        return

    target = context.args[0]
    msg = " ".join(context.args[1:])

    targets = set()

    if target == "@all":
        targets = set(ticket_user.values())

    elif target.startswith("BV-"):
        if target in ticket_status and ticket_status[target] != "Closed":
            targets.add(ticket_user[target])

    elif target.startswith("@"):
        for tid, uname in ticket_username.items():
            if uname == target[1:]:
                targets.add(ticket_user[tid])

    else:
        try:
            targets.add(int(target))
        except:
            pass

    if not targets:
        await update.message.reply_text("❌ No valid user found.")
        return

    for uid in targets:
        await context.bot.send_message(
            uid,
            f"📩 BlockVeil Support:\n\n{msg}"
        )

    await update.message.reply_text("✅ Message sent.")

# ================= /export =================
async def export_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID or not context.args:
        return

    tid = context.args[0]
    if tid not in ticket_messages:
        return

    buf = BytesIO()
    buf.write(f"Ticket ID: {tid}\nStatus: {ticket_status[tid]}\n\n".encode())
    for a, b in ticket_messages[tid]:
        buf.write(f"{a}: {b}\n\n".encode())

    buf.seek(0)
    buf.name = f"{tid}.txt"
    await context.bot.send_document(GROUP_ID, buf)

# ================= INIT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status_ticket))
app.add_handler(CommandHandler("list", list_tickets))
app.add_handler(CommandHandler("send", send_direct))
app.add_handler(CommandHandler("export", export_ticket))
app.add_handler(CallbackQueryHandler(create_ticket))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_reply))

app.run_polling()
