from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import os, random, string, html
from io import BytesIO

TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

user_active_ticket = {}
ticket_status = {}
ticket_user = {}
ticket_username = {}
ticket_messages = {}
user_tickets = {}
group_message_map = {}

def generate_ticket_id(length=8):
    chars = string.ascii_letters + string.digits + "*#@$&"
    return "BV-" + "".join(random.choice(chars) for _ in range(length))

def format_ticket_message(tid, status, user):
    """Format ticket message with easy copy option"""
    # Create a monospace formatted ID that's easy to copy
    ticket_display = f"""
┌─────────────────────────┐
│ 🎫 TICKET: {tid} │
└─────────────────────────┘

📋 *Click and hold the Ticket ID above to copy*

*Status:* {status}
*User ID:* {user.id}
*Username:* @{user.username or 'N/A'}
*Name:* {user.first_name or ''} {user.last_name or ''}

"""
    return ticket_display

def format_short_ticket(tid, status):
    """Format short ticket display for easy copy"""
    return f"""
🎫 `{tid}` ← Tap & hold to copy

Status: {status}
"""

async def start(update: Update, context):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎟️ Create Ticket", callback_data="create")]])
    await update.message.reply_text("Welcome to BlockVeil Support.", reply_markup=kb)

async def create_ticket(update: Update, context):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    
    if u.id in user_active_ticket:
        existing_tid = user_active_ticket[u.id]
        # Send ticket in easy-to-copy format
        await q.message.reply_text(
            format_short_ticket(existing_tid, ticket_status[existing_tid]),
            parse_mode="Markdown"
        )
        return
    
    tid = generate_ticket_id()
    user_active_ticket[u.id] = tid
    ticket_status[tid] = "Pending"
    ticket_user[tid] = u.id
    ticket_username[tid] = u.username or ""
    ticket_messages[tid] = []
    user_tickets.setdefault(u.id, []).append(tid)
    
    # Send with clear copy instructions
    await q.message.reply_text(
        f"""
✅ *Ticket Created Successfully!*

{format_ticket_message(tid, "Pending", u)}
📝 *Now you can send your message/question.*
        """,
        parse_mode="Markdown"
    )

async def user_message(update: Update, context):
    u = update.message.from_user
    if u.id not in user_active_ticket:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎟️ Create Ticket", callback_data="create")]])
        await update.message.reply_text(
            "❗ *Please create a ticket first.*\n\nTap the button below:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return
    
    tid = user_active_ticket[u.id]
    if ticket_status[tid] == "Pending":
        ticket_status[tid] = "Processing"
    
    m = update.message
    
    # Create a clean, copy-friendly message for group
    user_info = f"""
┌─────────────────────────┐
│ 🎫 TICKET: {tid} │
└─────────────────────────┘

*Status:* {ticket_status[tid]}
*User ID:* {u.id}
*Username:* @{u.username or 'N/A'}
*Name:* {u.first_name or ''}

*Message:*
"""
    
    sent = None
    
    if m.text:
        full_message = user_info + m.text
        sent = await context.bot.send_message(
            GROUP_ID, 
            full_message,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append((u.first_name, m.text))
    elif m.photo:
        sent = await context.bot.send_photo(
            GROUP_ID, m.photo[-1].file_id,
            caption=user_info + "[Photo]",
            parse_mode="Markdown"
        )
        ticket_messages[tid].append((u.first_name, "[Photo]"))
    elif m.voice:
        sent = await context.bot.send_voice(
            GROUP_ID, m.voice.file_id,
            caption=user_info + "[Voice]",
            parse_mode="Markdown"
        )
        ticket_messages[tid].append((u.first_name, "[Voice]"))
    elif m.video:
        sent = await context.bot.send_video(
            GROUP_ID, m.video.file_id,
            caption=user_info + "[Video]",
            parse_mode="Markdown"
        )
        ticket_messages[tid].append((u.first_name, "[Video]"))
    elif m.document:
        sent = await context.bot.send_document(
            GROUP_ID, m.document.file_id,
            caption=user_info + "[Document]",
            parse_mode="Markdown"
        )
        ticket_messages[tid].append((u.first_name, "[Document]"))
    
    if sent:
        group_message_map[sent.message_id] = tid
        # Also send confirmation to user with their ticket ID
        await update.message.reply_text(
            f"📤 *Message sent to support!*\n\nYour Ticket ID: `{tid}`\n\nTap and hold the ID above to copy.",
            parse_mode="Markdown"
        )

async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return
    mid = update.message.reply_to_message.message_id
    if mid not in group_message_map:
        return
    
    tid = group_message_map[mid]
    uid = ticket_user[tid]
    m = update.message
    
    reply_prefix = f"""
┌─────────────────────────┐
│ 🎫 TICKET: {tid} │
└─────────────────────────┘

📋 *Reply from Support Team:*
"""
    
    if m.text:
        await context.bot.send_message(
            uid, 
            reply_prefix + m.text,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append(("BlockVeil Support", m.text))
    elif m.photo:
        await context.bot.send_photo(
            uid, m.photo[-1].file_id, 
            caption=reply_prefix,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append(("BlockVeil Support", "[Photo]"))
    elif m.voice:
        await context.bot.send_voice(
            uid, m.voice.file_id, 
            caption=reply_prefix,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append(("BlockVeil Support", "[Voice]"))
    elif m.video:
        await context.bot.send_video(
            uid, m.video.file_id, 
            caption=reply_prefix,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append(("BlockVeil Support", "[Video]"))
    elif m.document:
        await context.bot.send_document(
            uid, m.document.file_id, 
            caption=reply_prefix,
            parse_mode="Markdown"
        )
        ticket_messages[tid].append(("BlockVeil Support", "[Document]"))

async def status_cmd(update: Update, context):
    if not context.args or context.args[0] not in ticket_status:
        await update.message.reply_text(
            "❌ *Ticket not found.*\n\nUsage: `/status BV-XXXXXXX`",
            parse_mode="Markdown"
        )
        return
    
    tid = context.args[0]
    await update.message.reply_text(
        format_short_ticket(tid, ticket_status[tid]),
        parse_mode="Markdown"
    )

async def send_cmd(update: Update, context):
    if update.effective_chat.id != GROUP_ID or len(context.args) < 2:
        return
    
    target = context.args[0]
    text = " ".join(context.args[1:])
    targets = set()
    
    if target == "@all":
        targets = set(user_tickets.keys())
    elif target.startswith("BV-") and target in ticket_status and ticket_status[target] != "Closed":
        targets.add(ticket_user[target])
    elif target.startswith("@"):
        for t, u in ticket_username.items():
            if u.lower() == target[1:].lower():
                targets.add(ticket_user[t])
    else:
        try:
            targets.add(int(target))
        except:
            pass
    
    for uid in targets:
        # Find user's active ticket for reference
        active_tid = None
        for tid, user_id in ticket_user.items():
            if user_id == uid and ticket_status[tid] != "Closed":
                active_tid = tid
                break
        
        if active_tid:
            message = f"""
📢 *Message from Support Team*

`{active_tid}` ← Your Ticket ID

{text}
"""
            await context.bot.send_message(uid, message, parse_mode="Markdown")
        else:
            await context.bot.send_message(uid, f"📢 *Message from Support Team*\n\n{text}", parse_mode="Markdown")

async def close_cmd(update: Update, context):
    tid = None
    if context.args:
        tid = context.args[0]
    elif update.message.reply_to_message:
        tid = group_message_map.get(update.message.reply_to_message.message_id)
    
    if not tid or tid not in ticket_status:
        await update.message.reply_text("❌ *Ticket not found.*", parse_mode="Markdown")
        return
    
    ticket_status[tid] = "Closed"
    uid = ticket_user[tid]
    user_active_ticket.pop(uid, None)
    
    close_message = f"""
✅ *Ticket Closed*

`{tid}` ← Ticket ID

Your ticket has been marked as resolved. 
If you have further questions, please create a new ticket.
"""
    
    await context.bot.send_message(uid, close_message, parse_mode="Markdown")
    await update.message.reply_text(f"✅ *Ticket {tid} closed.*", parse_mode="Markdown")

async def open_cmd(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: `/open BV-XXXXXXX`", parse_mode="Markdown")
        return
    
    tid = context.args[0]
    if tid in ticket_status and ticket_status[tid] == "Closed":
        ticket_status[tid] = "Processing"
        user_active_ticket[ticket_user[tid]] = tid
        
        await update.message.reply_text(
            f"✅ *Ticket Reopened*\n\n`{tid}` ← Ticket ID",
            parse_mode="Markdown"
        )

async def export_cmd(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: `/export BV-XXXXXXX`", parse_mode="Markdown")
        return
    
    tid = context.args[0]
    buf = BytesIO()
    buf.write(f"Ticket ID: {tid}\n".encode())
    buf.write(f"Status: {ticket_status.get(tid, 'Unknown')}\n".encode())
    buf.write(f"User ID: {ticket_user.get(tid, 'Unknown')}\n".encode())
    buf.write(f"Username: @{ticket_username.get(tid, 'Unknown')}\n".encode())
    buf.write("-" * 50 + "\n\n".encode())
    
    for sender, message in ticket_messages.get(tid, []):
        buf.write(f"{sender}: {message}\n".encode())
    
    buf.seek(0)
    buf.name = f"{tid}.txt"
    await context.bot.send_document(GROUP_ID, buf)

async def history_cmd(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: `/history @username` or `/history USER_ID`", parse_mode="Markdown")
        return
    
    target = context.args[0]
    uid = int(target) if target.isdigit() else None
    
    if target.startswith("@"):
        for t, u in ticket_username.items():
            if u.lower() == target[1:].lower():
                uid = ticket_user[t]
                break
    
    if uid not in user_tickets:
        await update.message.reply_text("❌ *User not found.*", parse_mode="Markdown")
        return
    
    text = f"📋 *Ticket History for {target}*\n\n"
    
    # Format each ticket for easy copying
    for i, t in enumerate(user_tickets[uid], 1):
        status = ticket_status.get(t, "Unknown")
        text += f"{i}. `{t}` - {status}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def user_cmd(update: Update, context):
    buf = BytesIO()
    seen = set()
    i = 1
    for tid, uid in ticket_user.items():
        if uid in seen:
            continue
        seen.add(uid)
        buf.write(f"{i} : @{ticket_username[tid]} — {uid}\n".encode())
        i += 1
    buf.seek(0)
    buf.name = "users.txt"
    await context.bot.send_document(GROUP_ID, buf)

async def list_cmd(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/list open` - Show open tickets\n`/list closed` - Show closed tickets",
            parse_mode="Markdown"
        )
        return
    
    mode = context.args[0].lower()
    out = []
    
    for t, s in ticket_status.items():
        if mode in ["open", "opened"] and s != "Closed":
            out.append(t)
        elif mode in ["close", "closed"] and s == "Closed":
            out.append(t)
    
    if not out:
        await update.message.reply_text(f"*No {mode} tickets found.*", parse_mode="Markdown")
        return
    
    # Format for easy copying
    text = f"📋 *{mode.upper()} TICKETS*\n\n"
    for i, tid in enumerate(out, 1):
        text += f"{i}. `{tid}`\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(create_ticket, pattern="create"))
app.add_handler(CommandHandler("status", status_cmd))
app.add_handler(CommandHandler("send", send_cmd))
app.add_handler(CommandHandler("close", close_cmd))
app.add_handler(CommandHandler("open", open_cmd))
app.add_handler(CommandHandler("export", export_cmd))
app.add_handler(CommandHandler("history", history_cmd))
app.add_handler(CommandHandler("user", user_cmd))
app.add_handler(CommandHandler("list", list_cmd))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_reply))

app.run_polling()
