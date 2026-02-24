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
import time

# ================= ENV =================
TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))

# ================= STORAGE =================
user_active_ticket = {}
ticket_status = {}
ticket_user = {}
ticket_username = {}
# ticket_messages now stores (sender, message, timestamp)
ticket_messages = {}
user_tickets = {}
group_message_map = {}
ticket_created_at = {}

# নতুন: ইউজারের সর্বশেষ ইউজারনেম সংরক্ষণ (বাগ ২২)
user_latest_username = {}

# নতুন: রেট লিমিটিং এর জন্য (বাগ ১৮)
user_message_timestamps = {}  # user_id -> list of timestamps (seconds)

# ================= HELPERS =================
def generate_ticket_id(length=8):
    chars = string.ascii_letters + string.digits + "*#@$&"
    # বাগ ২৫: ডুপ্লিকেট আইডি এড়াতে লুপ
    while True:
        tid = "BV-" + "".join(random.choice(chars) for _ in range(length))
        if tid not in ticket_status:  # যদি আগে না থাকে
            return tid

def code(tid):
    """Format ticket ID in code tags for easy copying"""
    return f"<code>{html.escape(tid)}</code>"

def ticket_header(ticket_id, status):
    return f"🎫 Ticket ID: {code(ticket_id)}\nStatus: {status}\n\n"

def user_info_block(user):
    # বাগ ৭: first_name এস্কেপ করা হয়েছে
    safe_first_name = html.escape(user.first_name or "")
    return (
        "User Information\n"
        f"• User ID   : {user.id}\n"
        f"• Username  : @{html.escape(user.username or '')}\n"
        f"• Full Name : {safe_first_name}\n\n"
    )

# নতুন: রেট লিমিট চেক (বাগ ১৮)
def check_rate_limit(user_id):
    now = time.time()
    if user_id not in user_message_timestamps:
        user_message_timestamps[user_id] = []
    # পুরনো টাইমস্ট্যাম্প বাদ দাও (60 সেকেন্ডের বেশি পুরনো)
    user_message_timestamps[user_id] = [t for t in user_message_timestamps[user_id] if now - t < 60]
    if len(user_message_timestamps[user_id]) >= 2:
        return False
    user_message_timestamps[user_id].append(now)
    return True

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
    # সর্বশেষ ইউজারনেম আপডেট
    user_latest_username[user.id] = user.username or ""

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

    # বাগ ১৮: রেট লিমিট চেক
    if not check_rate_limit(user.id):
        await update.message.reply_text(
            "⏱️ আপনি প্রতি মিনিটে সর্বোচ্চ ২টি মেসেজ পাঠাতে পারেন। দয়া করে একটু অপেক্ষা করুন।",
            parse_mode="HTML"
        )
        return

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

    # সর্বশেষ ইউজারনেম আপডেট (বাগ ২২)
    user_latest_username[user.id] = user.username or ""

    header = ticket_header(ticket_id, ticket_status[ticket_id]) + user_info_block(user) + "Message:\n"
    caption_text = update.message.caption or ""  # ক্যাপশন নিন (বাগ ৪)
    # ক্যাপশন HTML এস্কেপ
    safe_caption = html.escape(caption_text) if caption_text else ""

    sent = None
    log_text = ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # মেসেজের ধরণ অনুযায়ী হ্যান্ডেল (বাগ ৩)
    if update.message.text:
        log_text = html.escape(update.message.text)
        full_message = header + log_text
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=full_message,
            parse_mode="HTML"
        )

    elif update.message.photo:
        log_text = "[Photo]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=update.message.photo[-1].file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.voice:
        log_text = "[Voice Message]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_voice(
            chat_id=GROUP_ID,
            voice=update.message.voice.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.video:
        log_text = "[Video]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_video(
            chat_id=GROUP_ID,
            video=update.message.video.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.document:
        log_text = "[Document]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_document(
            chat_id=GROUP_ID,
            document=update.message.document.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.audio:
        log_text = "[Audio]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_audio(
            chat_id=GROUP_ID,
            audio=update.message.audio.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.sticker:
        log_text = "[Sticker]"
        # স্টিকারের জন্য ক্যাপশন আলাদাভাবে পাঠানো যায় না, তাই মেসেজ হিসেবে পাঠাই
        # প্রথমে স্টিকার পাঠাই, তারপর ক্যাপশন? অথবা ক্যাপশন ছাড়াই।
        # সহজ উপায়: স্টিকার + আলাদা টেক্সট মেসেজ
        sent = await context.bot.send_sticker(
            chat_id=GROUP_ID,
            sticker=update.message.sticker.file_id
        )
        # এরপর ক্যাপশন (যদি থাকে) আলাদা মেসেজে
        if safe_caption:
            await context.bot.send_message(
                chat_id=GROUP_ID,
                text=header + safe_caption,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=GROUP_ID,
                text=header + log_text,
                parse_mode="HTML"
            )
        # group_message_map এর জন্য আমরা শেষ স্টিকার মেসেজটির আইডি ব্যবহার করব? জটিল।
        # সহজ উপায়: স্টিকার পাঠানোর পরে আমরা আরেকটি মেসেজ পাঠাই, কিন্তু তখন group_message_map-এ দুটি আইডি চলে যাবে।
        # আমরা শুধু প্রথম মেসেজটি ট্র্যাক করব।
        # কিন্তু reply করার সময় যদি স্টিকারে রিপ্লাই দেয়, তাহলে স্টিকার মেসেজের আইডি থাকবে।
        # সুতরাং আমরা স্টিকার মেসেজকেই মূল হিসেবে রাখব।
        # ক্যাপশন আলাদা মেসেজ হিসেবে যাবে, কিন্তু সেটি টিকিটের অংশ হবে না? আমরা চাইলে ক্যাপশনও ট্র্যাক করতে পারি।
        # তবে এই উদাহরণে আমরা সহজ রাখি: ক্যাপশন আলাদা মেসেজ হিসেবে যাবে, কিন্তু তার আইডি ম্যাপে রাখব না।
        # তাহলে রিপ্লাই দিলে স্টিকার মেসেজে রিপ্লাই দিতে হবে।
        # আমরা স্টিকার মেসেজের আইডি সংরক্ষণ করি।
        if sent:
            group_message_map[sent.message_id] = ticket_id

    elif update.message.animation:
        log_text = "[Animation/GIF]"
        full_caption = header + (safe_caption if safe_caption else log_text)
        sent = await context.bot.send_animation(
            chat_id=GROUP_ID,
            animation=update.message.animation.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.video_note:
        log_text = "[Video Note]"
        # ভিডিও নোটের ক্যাপশন নেই, তাই শুধু পাঠাই
        sent = await context.bot.send_video_note(
            chat_id=GROUP_ID,
            video_note=update.message.video_note.file_id
        )
        if safe_caption:
            await context.bot.send_message(
                chat_id=GROUP_ID,
                text=header + safe_caption,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=GROUP_ID,
                text=header + log_text,
                parse_mode="HTML"
            )

    else:
        # অন্যান্য অসমর্থিত টাইপ (location, contact, poll ইত্যাদি)
        log_text = f"[Unsupported message type: {update.message.effective_attachment.__class__.__name__ if update.message.effective_attachment else 'Unknown'}]"
        await update.message.reply_text(
            "❌ এই ধরনের মেসেজ সমর্থিত নয়। দয়া করে টেক্সট, ফটো, ভিডিও, ডকুমেন্ট, অডিও, স্টিকার ইত্যাদি পাঠান।",
            parse_mode="HTML"
        )
        # তবুও লগে রাখি
        sent = await context.bot.send_message(
            chat_id=GROUP_ID,
            text=header + log_text,
            parse_mode="HTML"
        )

    if sent:
        group_message_map[sent.message_id] = ticket_id
        sender_name = f"@{user.username}" if user.username else user.first_name or "User"
        # টাইমস্ট্যাম্প সহ সংরক্ষণ (বাগ ১৪)
        ticket_messages[ticket_id].append((sender_name, log_text, timestamp))
    elif update.message.sticker or update.message.video_note:
        # আমরা ইতিমধ্যে sent পাইনি, কিন্তু group_message_map এড করেছি
        pass

# ================= GROUP REPLY (TEXT + MEDIA) =================
async def group_reply(update: Update, context):
    if not update.message.reply_to_message:
        return

    reply_id = update.message.reply_to_message.message_id
    if reply_id not in group_message_map:
        return

    ticket_id = group_message_map[reply_id]
    user_id = ticket_user[ticket_id]

    # বাগ ১১: টিকিট ক্লোজ থাকলে রিপ্লাই বন্ধ করুন
    if ticket_status.get(ticket_id) == "Closed":
        await update.message.reply_text(
            f"⚠️ টিকিট {code(ticket_id)} ইতিমধ্যে ক্লোজ করা আছে। রিপ্লাই পাঠানো সম্ভব নয়।",
            parse_mode="HTML"
        )
        return

    prefix = f"🎫 Ticket ID: {code(ticket_id)}\n\n"
    caption_text = update.message.caption or ""  # বাগ ৫: ক্যাপশন নিন
    safe_caption = html.escape(caption_text) if caption_text else ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_photo(
            chat_id=user_id,
            photo=update.message.photo[-1].file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.voice:
        log_text = "[Voice Message]"
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_voice(
            chat_id=user_id,
            voice=update.message.voice.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.video:
        log_text = "[Video]"
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_video(
            chat_id=user_id,
            video=update.message.video.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.document:
        log_text = "[Document]"
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_document(
            chat_id=user_id,
            document=update.message.document.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.audio:
        log_text = "[Audio]"
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_audio(
            chat_id=user_id,
            audio=update.message.audio.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.sticker:
        log_text = "[Sticker]"
        await context.bot.send_sticker(
            chat_id=user_id,
            sticker=update.message.sticker.file_id
        )
        if safe_caption:
            await context.bot.send_message(
                chat_id=user_id,
                text=prefix + safe_caption,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=prefix + log_text,
                parse_mode="HTML"
            )

    elif update.message.animation:
        log_text = "[Animation/GIF]"
        full_caption = prefix + (safe_caption if safe_caption else log_text)
        await context.bot.send_animation(
            chat_id=user_id,
            animation=update.message.animation.file_id,
            caption=full_caption,
            parse_mode="HTML"
        )

    elif update.message.video_note:
        log_text = "[Video Note]"
        await context.bot.send_video_note(
            chat_id=user_id,
            video_note=update.message.video_note.file_id
        )
        if safe_caption:
            await context.bot.send_message(
                chat_id=user_id,
                text=prefix + safe_caption,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=prefix + log_text,
                parse_mode="HTML"
            )

    else:
        log_text = f"[Unsupported message type]"
        await context.bot.send_message(
            chat_id=user_id,
            text=prefix + "সমর্থিত নয় এমন মেসেজ টাইপ।",
            parse_mode="HTML"
        )

    ticket_messages[ticket_id].append(("BlockVeil Support", log_text, timestamp))

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
    # বাগ ২৩: টিকিট আইডি সহ কনফার্মেশন
    await update.message.reply_text(f"✅ Ticket {code(ticket_id)} closed.", parse_mode="HTML")

# ================= /requestclose (NEW) =================
async def request_close(update: Update, context):
    """User command to request ticket closure"""
    # বাগ ১০: শুধু প্রাইভেট চ্যাটে অনুমতি দিন
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "❌ এই কমান্ড শুধু প্রাইভেট চ্যাটে ব্যবহার করুন।",
            parse_mode="HTML"
        )
        return

    user = update.message.from_user
    
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a ticket ID.\n"
            "Usage: /requestclose BV-XXXXX",
            parse_mode="HTML"
        )
        return
    
    ticket_id = context.args[0]
    
    if ticket_id not in ticket_status:
        await update.message.reply_text(
            f"❌ Ticket {code(ticket_id)} not found.",
            parse_mode="HTML"
        )
        return
    
    if ticket_user.get(ticket_id) != user.id:
        await update.message.reply_text(
            "❌ This ticket does not belong to you.",
            parse_mode="HTML"
        )
        return
    
    if ticket_status[ticket_id] == "Closed":
        await update.message.reply_text(
            f"⚠️ Ticket {code(ticket_id)} is already closed.",
            parse_mode="HTML"
        )
        return
    
    username = f"@{user.username}" if user.username else "N/A"
    notification = (
        f"🔔 <b>Ticket Close Request</b>\n\n"
        f"User {username} [ User ID : {user.id} ] has requested to close ticket ID {code(ticket_id)}\n\n"
        f"Please review and properly close the ticket."
    )
    
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=notification,
        parse_mode="HTML"
    )
    
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
    
    # Handle individual messages
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
        except ValueError:
            # বাগ ১২: ভিন্ন সংখ্যা হলে এরর মেসেজ
            await update.message.reply_text("❌ ভ্যালিড ইউজার আইডি বা টিকিট আইডি দিন।", parse_mode="HTML")
            return

    if not user_id:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 BlockVeil Support:\n\n{message}",
            parse_mode="HTML"
        )
        await update.message.reply_text("✅ Message sent successfully.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ পাঠানো সম্ভব হয়নি: {e}", parse_mode="HTML")

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
    await update.message.reply_text(f"✅ Ticket {code(ticket_id)} reopened.", parse_mode="HTML")

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
    # বাগ ২৮: creation time যোগ করুন
    if ticket_id in ticket_created_at:
        text += f"\nCreated at: {ticket_created_at[ticket_id]}"
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
    # বাগ ১৬: ভ্যালিড মোড চেক
    if mode not in ["open", "close"]:
        await update.message.reply_text(
            "❌ Invalid mode. Use /list open or /list close",
            parse_mode="HTML"
        )
        return

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
    
    # বাগ ১৪: টাইমস্ট্যাম্প সহ
    for sender, message, timestamp in ticket_messages[ticket_id]:
        # message ইতিমধ্যে HTML escaped, কিন্তু আমরা unescape করতে পারি? আমরা মূল টেক্সট সংরক্ষণ করিনি।
        # বর্তমানে message এ escaped version আছে। আমরা যদি আসল চাই, তাহলে unescape করতে হবে।
        # কিন্তু আমরা সহজভাবে unescape করতে পারি:
        import html as html_lib
        original_message = html_lib.unescape(message)
        line = f"[{timestamp}] {sender} : {original_message}\n"
        buf.write(line.encode())
    
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
        created = ticket_created_at.get(tid, "")
        text += f"{i}. {code(tid)} - {status}"
        if created:
            text += f" (Created: {created})"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode="HTML")

# ================= /user =================
async def user_list(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return
    
    buf = BytesIO()
    seen_users = set()
    count = 1
    
    for tid, user_id in ticket_user.items():
        if user_id in seen_users:
            continue
        seen_users.add(user_id)
        # সর্বশেষ ইউজারনেম ব্যবহার করুন (বাগ ২২)
        username = user_latest_username.get(user_id, ticket_username.get(tid, "N/A"))
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
    
    if target.startswith("@"):
        username_target = target[1:]
        # সর্বশেষ ইউজারনেম অনুসন্ধান (বাগ ২২)
        for uid, uname in user_latest_username.items():
            if uname == username_target:
                user_id = uid
                username = uname
                break
        # যদি না পাওয়া যায়, তাহলে ticket_username এ খুঁজি
        if not user_id:
            for tid, uname in ticket_username.items():
                if uname == username_target:
                    user_id = ticket_user[tid]
                    username = uname
                    break
    
    elif target.startswith("BV-"):
        ticket_id = target
        if ticket_id in ticket_user:
            user_id = ticket_user[ticket_id]
            username = user_latest_username.get(user_id, ticket_username.get(ticket_id, "N/A"))
    
    else:
        try:
            user_id = int(target)
            username = user_latest_username.get(user_id, "")
        except:
            pass
    
    if not user_id:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return
    
    user_ticket_list = user_tickets.get(user_id, [])
    
    if not user_ticket_list:
        await update.message.reply_text("❌ No tickets found for this user.", parse_mode="HTML")
        return
    
    response = f"👤 <b>User Information</b>\n\n"
    response += f"• User ID : {user_id}\n"
    response += f"• Username : @{html.escape(username) if username else 'N/A'}\n\n"
    response += f"📊 <b>Created total {len(user_ticket_list)} tickets.</b>\n\n"
    
    for i, ticket_id in enumerate(user_ticket_list, 1):
        status = ticket_status.get(ticket_id, "Unknown")
        created = ticket_created_at.get(ticket_id, "")
        response += f"{i}. {code(ticket_id)} - {status}"
        if created:
            response += f" (Created: {created})"
        response += "\n"
    
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
app.add_handler(CommandHandler("requestclose", request_close))
app.add_handler(CallbackQueryHandler(create_ticket, pattern="create_ticket"))
app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, user_message))
app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_reply))

app.run_polling()
