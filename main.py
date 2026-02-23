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
import html
from io import BytesIO
from datetime import datetime

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
ticket_created_at = {}

# ================= HELPERS =================
def generate_ticket_id(length=8):
    chars = string.ascii_letters + string.digits + "*#@$&"
    return "BV-" + "".join(random.choice(chars) for _ in range(length))

def code(tid):
    """Format ticket ID in code tags for easy copying"""
    return f"<code>{html.escape(tid)}</code>"

def ticket_header(ticket_id, status):
    return f"🎫 Ticket ID: {code(ticket_id)}\nStatus: {status}\n\n"

def user_info_block(user):
    return (
        "User Information\n"
        f"• User ID   : {user.id}\n"
        f"• Username  : @{user.username or ''}\n"
        f"• Full Name : {user.first_name or ''}\n\n"
    )

# ================= /start =================
async def start(update: Update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎟️ Create Ticket", callback_data="create_ticket")]
    ])
    await update.message.reply_text(
        "Hey Sir/Mam 👋\n\n"
        "Welcome to BlockVeil Support.\n"
        "You can contact the BlockVeil team using this bot.\n\n"
        "🔐 Privacy Notice\n"
        "Your information is kept strictly confidential.\n\n"
        "Use the button below to create a support ticket.\n\n"
        "📧 support.blockveil@protonmail.com\n\n"
        "— BlockVeil Support Team",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ================= CREATE TICKET =================
async def create_ticket(update: Update, context):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if user.id in user_active_ticket:
        await query.message.reply_text(
            f"🎫 You already have an active ticket:\n{code(user_active_ticket[user.id])}",
            parse_mode="HTML"
        )
        return

    ticket_id = generate_ticket_id()
    user_active_ticket[user.id] = ticket_id
    ticket_status[ticket_id] = "Pending"
    ticket_user[ticket_id] = user.id
    ticket_username[ticket_id] = user.username or ""
    ticket_messages[ticket_id] = []
    ticket_created_at[ticket_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_tickets.setdefault(user.id, []).append(ticket_id)

    await query.message.reply_text(
        f"🎫 Ticket Created: {code(ticket_id)}\n"
        "Status: Pending\n\n"
        "Please write and submit your issue or suggestion here in a clear and concise manner.\n"
        "Our support team will review it as soon as possible.",
        parse_mode="HTML"
    )

# ================= USER MESSAGE (TEXT + MEDIA) =================
async def user_message(update: Update, context):
    user = update.message.from_user

    if user.id not in user_active_ticket:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎟️ Create Ticket", callback_data="create_ticket")]
        ])
        await update.message.reply_text(
            "❗ Please create a ticket first.\n\n"
            "Click the button below to submit a new support ticket.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    ticket_id = user_active_ticket[user.id]
    if ticket_status[ticket_id] == "Pending":
        ticket_status[ticket_id] = "Processing"

    header = ticket_header(ticket_id, ticket_status[ticket_id]) + user_info_block(user) + "Message:\n"

    sent = None
    log_text = ""

    if update.message.text:
        log_text = html.escape(update.message.text)
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=header + log_text,
            parse_mode="HTML"
        )

    elif update.message.photo:
        log_text = "[Photo]"
        sent = await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=update.message.photo[-1].file_id,
            caption=header + log_text,
            parse_mode="HTML"
        )

    elif update.message.voice:
        log_text = "[Voice Message]"
        sent = await context.bot.send_voice(
            chat_id=GROUP_ID,
            voice=update.message.voice.file_id,
            caption=header + log_text,
            parse_mode="HTML"
        )

    elif update.message.video:
        log_text = "[Video]"
        sent = await context.bot.send_video(
            chat_id=GROUP_ID,
            video=update.message.video.file_id,
            caption=header + log_text,
            parse_mode="HTML"
        )

    elif update.message.document:
        log_text = "[Document]"
        sent = await context.bot.send_document(
            chat_id=GROUP_ID,
            document=update.message.document.file_id,
            caption=header + log_text,
            parse_mode="HTML"
        )

    if sent:
        group_message_map[sent.message_id] = ticket_id
        # Store user's actual username
        sender_name = f"@{user.username}" if user.username else user.first_name or "User"
        ticket_messages[ticket_id].append((sender_name, log_text))

# ================= GROUP REPLY (TEXT + MEDIA) =================
async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return

    reply_id = update.message.reply_to_message.message_id
    if reply_id not in group_message_map:
        return

    ticket_id = group_message_map[reply_id]
    user_id = ticket_user[ticket_id]

    prefix = f"🎫 Ticket ID: {code(ticket_id)}\n\n"
    log_text = ""

    if update.message.text:
        log_text = html.escape(update.message.text)
        await context.bot.send_message(
            chat_id=user_id,
            text=prefix + log_text,
            parse_mode="HTML"
        )

    elif update.message.photo:
        log_text = "[Photo]"
        await context.bot.send_photo(
            chat_id=user_id,
            photo=update.message.photo[-1].file_id,
            caption=prefix,
            parse_mode="HTML"
        )

    elif update.message.voice:
        log_text = "[Voice Message]"
        await context.bot.send_voice(
            chat_id=user_id,
            voice=update.message.voice.file_id,
            caption=prefix,
            parse_mode="HTML"
        )

    elif update.message.video:
        log_text = "[Video]"
        await context.bot.send_video(
            chat_id=user_id,
            video=update.message.video.file_id,
            caption=prefix,
            parse_mode="HTML"
        )

    elif update.message.document:
        log_text = "[Document]"
        await context.bot.send_document(
            chat_id=user_id,
            document=update.message.document.file_id,
            caption=prefix,
            parse_mode="HTML"
        )

    ticket_messages[ticket_id].append(("BlockVeil Support", log_text))

# ================= /close (ARG OR REPLY) =================
async def close_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    ticket_id = None

    if context.args:
        ticket_id = context.args[0]
    elif update.message.reply_to_message:
        ticket_id = group_message_map.get(update.message.reply_to_message.message_id)

    if not ticket_id or ticket_id not in ticket_status:
        await update.message.reply_text(
            "❌ Ticket not found.\nUse /close BV-XXXXX or reply with /close",
            parse_mode="HTML"
        )
        return

    if ticket_status[ticket_id] == "Closed":
        await update.message.reply_text("⚠️ Ticket already closed.", parse_mode="HTML")
        return

    user_id = ticket_user[ticket_id]
    ticket_status[ticket_id] = "Closed"
    user_active_ticket.pop(user_id, None)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"🎫 Ticket ID: {code(ticket_id)}\nStatus: Closed",
        parse_mode="HTML"
    )
    await update.message.reply_text(f" Ticket {code(ticket_id)} closed.", parse_mode="HTML")

# ================= /requestclose (NEW) =================
async def request_close(update: Update, context):
    """User command to request ticket closure"""
    user = update.message.from_user
    
    # Check if user has arguments
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a ticket ID.\n"
            "Usage: /requestclose BV-XXXXX",
            parse_mode="HTML"
        )
        return
    
    ticket_id = context.args[0]
    
    # Verify ticket exists
    if ticket_id not in ticket_status:
        await update.message.reply_text(
            f"❌ Ticket {code(ticket_id)} not found.",
            parse_mode="HTML"
        )
        return
    
    # Verify ticket belongs to this user
    if ticket_user.get(ticket_id) != user.id:
        await update.message.reply_text(
            "❌ This ticket does not belong to you.",
            parse_mode="HTML"
        )
        return
    
    # Check if ticket is already closed
    if ticket_status[ticket_id] == "Closed":
        await update.message.reply_text(
            f"⚠️ Ticket {code(ticket_id)} is already closed.",
            parse_mode="HTML"
        )
        return
    
    # Send notification to management group
    username = f"@{user.username}" if user.username else "N/A"
    notification = (
        f"🔔 <b>Ticket Close Request</b>\n\n"
        f"User {username} {user.id} has requested to close ticket ID {code(ticket_id)}.\n\n"
        f"Please review and properly close the ticket."
    )
    
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=notification,
        parse_mode="HTML"
    )
    
    # Confirm to user
    await update.message.reply_text(
        f"✅ Your request to close ticket {code(ticket_id)} has been sent to the support team.\n"
        f"They will review and close it shortly.",
        parse_mode="HTML"
    )

# ================= /send =================
async def send_direct(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n"
            "/send @all <message>\n"
            "/send BV-XXXXX <message>\n"
            "/send @username <message>\n"
            "/send user_id <message>",
            parse_mode="HTML"
        )
        return

    target = context.args[0]
    message = html.escape(" ".join(context.args[1:]))
    
    # Handle @all broadcast
    if target == "@all":
        sent_count = 0
        failed_count = 0
        unique_users = set()
        
        # Get all unique users from ticket_user
        for user_id in ticket_user.values():
            unique_users.add(user_id)
        
        total_users = len(unique_users)
        await update.message.reply_text(f"📢 Broadcasting to {total_users} users...", parse_mode="HTML")
        
        for user_id in unique_users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Announcement from BlockVeil Support:\n\n{message}",
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Failed to send to {user_id}: {e}")
        
        await update.message.reply_text(
            f"📊 Broadcast Complete:\n"
            f"✅ Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"👥 Total: {total_users}",
            parse_mode="HTML"
        )
        return
    
    # Handle individual messages (existing code)
    user_id = None
    ticket_id = None

    if target.startswith("BV-"):
        ticket_id = target
        if ticket_id not in ticket_status:
            await update.message.reply_text("❌ Ticket not found.", parse_mode="HTML")
            return
        if ticket_status[ticket_id] == "Closed":
            await update.message.reply_text("⚠️ Ticket is closed.", parse_mode="HTML")
            return
        user_id = ticket_user[ticket_id]
        # Include ticket ID in message
        message = f"🎫 Ticket ID: {code(ticket_id)}\n\n{message}"

    elif target.startswith("@"):
        username = target[1:]
        for tid, uname in ticket_username.items():
            if uname == username:
                user_id = ticket_user[tid]
                ticket_id = tid
                if ticket_id:
                    message = f"🎫 Ticket ID: {code(ticket_id)}\n\n{message}"
                break

    else:
        try:
            user_id = int(target)
        except:
            return

    if not user_id:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return

    await context.bot.send_message(
        chat_id=user_id,
        text=f"📩 BlockVeil Support:\n\n{message}",
        parse_mode="HTML"
    )
    await update.message.reply_text(" Message sent Successfully.", parse_mode="HTML")

# ================= /open =================
async def open_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        return

    ticket_id = context.args[0]
    if ticket_id not in ticket_status:
        await update.message.reply_text("❌ Ticket not found.", parse_mode="HTML")
        return

    if ticket_status[ticket_id] != "Closed":
        await update.message.reply_text("⚠️ Ticket already open.", parse_mode="HTML")
        return

    ticket_status[ticket_id] = "Processing"
    user_active_ticket[ticket_user[ticket_id]] = ticket_id
    await update.message.reply_text(f" Ticket {code(ticket_id)} reopened.", parse_mode="HTML")

# ================= /status =================
async def status_ticket(update: Update, context):
    if not context.args or context.args[0] not in ticket_status:
        await update.message.reply_text(
            "Use /status BV-XXXXX to check your ticket status.",
            parse_mode="HTML"
        )
        return

    ticket_id = context.args[0]
    text = f"🎫 Ticket ID: {code(ticket_id)}\nStatus: {ticket_status[ticket_id]}"
    if update.effective_chat.id == GROUP_ID:
        text += f"\nUser: @{ticket_username.get(ticket_id, 'N/A')}"

    await update.message.reply_text(text, parse_mode="HTML")

# ================= /list =================
async def list_tickets(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return
    if not context.args:
        return

    mode = context.args[0].lower()
    data = []

    for tid, st in ticket_status.items():
        if mode == "open" and st != "Closed":
            data.append((tid, ticket_username.get(tid)))
        elif mode == "close" and st == "Closed":
            data.append((tid, ticket_username.get(tid)))

    if not data:
        await update.message.reply_text("No tickets found.", parse_mode="HTML")
        return

    text = "📂 Open Tickets\n\n" if mode == "open" else "📁 Closed Tickets\n\n"
    for i, (tid, uname) in enumerate(data, 1):
        text += f"{i}. {code(tid)} – @{uname or 'N/A'}\n"

    await update.message.reply_text(text, parse_mode="HTML")

# ================= /export (FIXED FORMAT) =================
async def export_ticket(update: Update, context):
    if update.effective_chat.id != GROUP_ID or not context.args:
        return
    
    ticket_id = context.args[0]
    if ticket_id not in ticket_messages:
        await update.message.reply_text("❌ Ticket not found.", parse_mode="HTML")
        return
    
    buf = BytesIO()
    buf.write("BlockVeil Support Messages\n\n".encode())
    
    for sender, message in ticket_messages[ticket_id]:
        if sender == "BlockVeil Support":
            label = "blockveil support team"
        else:
            # Use the actual username stored (which already includes @ if available)
            label = sender
        
        buf.write(f"{label} : {message}\n".encode())
    
    buf.seek(0)
    buf.name = f"{ticket_id}.txt"
    await context.bot.send_document(GROUP_ID, document=buf)

# ================= /history =================
async def ticket_history(update: Update, context):
    if update.effective_chat.id != GROUP_ID or not context.args:
        return
    
    target = context.args[0]
    user_id = None
    
    if target.startswith("@"):
        username = target[1:]
        for tid, uname in ticket_username.items():
            if uname == username:
                user_id = ticket_user[tid]
                break
    else:
        try:
            user_id = int(target)
        except:
            pass
    
    if user_id not in user_tickets:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return
    
    text = f"📋 Ticket History for {target}\n\n"
    for i, tid in enumerate(user_tickets[user_id], 1):
        status = ticket_status.get(tid, "Unknown")
        text += f"{i}. {code(tid)} - {status}\n"
    
    await update.message.reply_text(text, parse_mode="HTML")

# ================= /user =================
async def user_list(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return
    
    buf = BytesIO()
    seen_users = set()
    count = 1
    
    # Iterate through all tickets to get unique users
    for tid, user_id in ticket_user.items():
        if user_id in seen_users:
            continue
            
        seen_users.add(user_id)
        username = ticket_username.get(tid, "N/A")
        buf.write(f"{count} - @{username} - {user_id}\n".encode())
        count += 1
    
    if count == 1:
        await update.message.reply_text("❌ No users found.", parse_mode="HTML")
        return
    
    buf.seek(0)
    buf.name = "users_list.txt"
    await context.bot.send_document(GROUP_ID, document=buf)

# ================= /which =================
async def which_user(update: Update, context):
    if update.effective_chat.id != GROUP_ID or not context.args:
        return
    
    target = context.args[0]
    user_id = None
    username = None
    
    # Determine target type
    if target.startswith("@"):
        # Username
        username_target = target[1:]
        for tid, uname in ticket_username.items():
            if uname == username_target:
                user_id = ticket_user[tid]
                username = uname
                break
    
    elif target.startswith("BV-"):
        # Ticket ID
        ticket_id = target
        if ticket_id in ticket_user:
            user_id = ticket_user[ticket_id]
            username = ticket_username.get(ticket_id, "N/A")
    
    else:
        # User ID
        try:
            user_id = int(target)
            # Find username for this user_id
            for tid, uid in ticket_user.items():
                if uid == user_id:
                    username = ticket_username.get(tid, "N/A")
                    break
        except:
            pass
    
    if not user_id:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return
    
    # Get all tickets for this user
    user_ticket_list = user_tickets.get(user_id, [])
    
    if not user_ticket_list:
        await update.message.reply_text("❌ No tickets found for this user.", parse_mode="HTML")
        return
    
    # Prepare response
    response = f"👤 <b>User Information</b>\n\n"
    response += f"• User ID : {user_id}\n"
    response += f"• Username : @{username or 'N/A'}\n\n"
    response += f"📊 <b>Created total {len(user_ticket_list)} tickets.</b>\n\n"
    
    for i, ticket_id in enumerate(user_ticket_list, 1):
        status = ticket_status.get(ticket_id, "Unknown")
        response += f"{i}. {code(ticket_id)} - {status}\n"
    
    await update.message.reply_text(response, parse_mode="HTML")

# ================= INIT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("close", close_ticket))
app.add_handler(CommandHandler("open", open_ticket))
app.add_handler(CommandHandler("send", send_direct))
app.add_handler(CommandHandler("status", status_ticket))
app.add_handler(CommandHandler("list", list_tickets))
app.add_handler(CommandHandler("export", export_ticket))
app.add_handler(CommandHandler("history", ticket_history))
app.add_handler(CommandHandler("user", user_list))
app.add_handler(CommandHandler("which", which_user))
app.add_handler(CommandHandler("requestclose", request_close))  # New command
app.add_handler(CallbackQueryHandler(create_ticket, pattern="create_ticket"))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_reply))

app.run_polling()
