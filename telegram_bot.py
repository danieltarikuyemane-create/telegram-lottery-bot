import random
import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIG ---
TOKEN = "7930881679:AAGFmtN3amkVzz-bd4C_uQW8qYbyoeUAOSM"
ADMIN_ID = 7742927843
CBE_ACCOUNT = "1000381194853"
ADMIN_USERNAME = "@zezitwa"
CHANNEL_ID = -1003876511084  
BOT_USERNAME = "AmuLottery_bot"

# --- PRIZES ---
WEEKLY_PRIZE = 2000
MONTHLY_PRIZE = 15000

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- DELETE OLD DATABASE TO START FRESH ---
if os.path.exists("lottery.db"):
    os.remove("lottery.db")
    print("✅ Old database deleted - Starting fresh!")
    print("   (This fixes any old pending requests issues)")

# --- DATABASE (FRESH) ---
conn = sqlite3.connect("lottery.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS participants (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    lottery TEXT,
    name TEXT,
    approved_at TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    lottery TEXT,
    name TEXT,
    requested_at TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS winners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    user_id INTEGER,
    name TEXT,
    lottery TEXT,
    prize_amount INTEGER,
    drawn_at TIMESTAMP
)
""")
conn.commit()

print("✅ Fresh database created!")

def is_admin(user_id):
    return user_id == ADMIN_ID

async def send_to_channel(context, message, button_text=None):
    keyboard = []
    if button_text:
        keyboard = [[InlineKeyboardButton(button_text, url=f"https://t.me/{BOT_USERNAME}")]]
    
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID, 
            text=message, 
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        print(f"Channel error: {e}")
        return False

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    cursor.execute("SELECT COUNT(*) FROM participants")
    total_participants = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pending")
    total_pending = cursor.fetchone()[0]
    
    keyboard = [
        [InlineKeyboardButton(f"📋 LIST PARTICIPANTS ({total_participants})", callback_data="admin_list")],
        [InlineKeyboardButton(f"⏳ PENDING APPROVALS ({total_pending})", callback_data="admin_pending")],
        [InlineKeyboardButton("🏆 DRAW WINNER", callback_data="admin_winner")],
        [InlineKeyboardButton("📢 POST TO CHANNEL", callback_data="admin_post")],
        [InlineKeyboardButton("🎟️ SEND CHANNEL BUTTON", callback_data="admin_channel_btn")],
        [InlineKeyboardButton("🔄 RESET DATABASE", callback_data="admin_reset")],
    ]
    
    await update.message.reply_text(
        f"👑 **ADMIN PANEL** 👑\n\n"
        f"✅ Active Tickets: {total_participants}\n"
        f"⏳ Pending: {total_pending}\n"
        f"💰 Weekly Prize: {WEEKLY_PRIZE} Birr\n"
        f"💰 Monthly Prize: {MONTHLY_PRIZE} Birr\n\n"
        f"Select an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    
    print(f"🔘 Button clicked: {query.data} by user {user.id}")
    
    # ============= ADMIN RESET =============
    if query.data == "admin_reset":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
        
        cursor.execute("DELETE FROM participants")
        cursor.execute("DELETE FROM pending")
        cursor.execute("DELETE FROM winners")
        cursor.execute("DELETE FROM sqlite_sequence")
        conn.commit()
        
        await query.edit_message_text(
            "✅ **DATABASE RESET!**\n\n"
            "All participants, pending requests, and winners have been cleared.\n\n"
            "The bot is now fresh and ready!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]),
            parse_mode="Markdown"
        )
        return
    
    # ============= ADMIN LIST =============
    if query.data == "admin_list":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        cursor.execute("SELECT ticket_id, user_id, name, lottery FROM participants ORDER BY ticket_id DESC")
        rows = cursor.fetchall()
        
        if not rows:
            await query.edit_message_text(
                "📋 No participants yet.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]])
            )
            return
        
        weekly = [r for r in rows if r[3] == "weekly"]
        monthly = [r for r in rows if r[3] == "monthly"]
        
        msg = f"📋 **PARTICIPANTS**\n\n"
        msg += f"🎟️ Total: {len(rows)}\n"
        msg += f"🟢 Weekly: {len(weekly)}\n"
        msg += f"🔴 Monthly: {len(monthly)}\n\n"
        
        if weekly:
            msg += "**Weekly Tickets:**\n"
            for r in weekly[:10]:
                msg += f"• #{r[0]} | {r[2]}\n"
            if len(weekly) > 10:
                msg += f"... +{len(weekly)-10} more\n"
        
        if monthly:
            msg += "\n**Monthly Tickets:**\n"
            for r in monthly[:10]:
                msg += f"• #{r[0]} | {r[2]}\n"
            if len(monthly) > 10:
                msg += f"... +{len(monthly)-10} more\n"
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]),
            parse_mode="Markdown"
        )
        return
    
    # ============= ADMIN PENDING =============
    if query.data == "admin_pending":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        cursor.execute("SELECT id, user_id, name, lottery FROM pending ORDER BY id ASC")
        pend = cursor.fetchall()
        
        print(f"📋 Pending requests found: {len(pend)}")
        
        if not pend:
            await query.edit_message_text(
                "✅ No pending approvals.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]])
            )
            return
        
        keyboard = []
        for p in pend:
            button_text = f"✅ APPROVE {p[2]} - {p[3].upper()}"
            callback_data = f"approve_{p[1]}_{p[3]}_{p[0]}"
            print(f"   Creating button: {button_text} -> {callback_data}")
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_admin")])
        
        await query.edit_message_text(
            f"⏳ **PENDING APPROVALS:** {len(pend)}\n\nClick a button to approve:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # ============= APPROVE SYSTEM (FIXED) =============
    if query.data.startswith("approve_"):
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
        
        print(f"📝 Processing approval: {query.data}")
        
        try:
            # Parse the callback data
            parts = query.data.split("_")
            print(f"   Parts: {parts}")
            
            if len(parts) != 4:
                await query.edit_message_text(f"❌ Invalid approval format! Got {len(parts)} parts")
                return
            
            target_user_id = int(parts[1])
            lottery_type = parts[2]
            pending_id = int(parts[3])
            
            print(f"   Target User: {target_user_id}")
            print(f"   Lottery: {lottery_type}")
            print(f"   Pending ID: {pending_id}")
            
            # Get the pending request
            cursor.execute("SELECT name, user_id FROM pending WHERE id = ?", (pending_id,))
            pending_data = cursor.fetchone()
            
            if not pending_data:
                await query.edit_message_text("❌ This pending request no longer exists!")
                return
            
            user_name = pending_data[0]
            print(f"   User Name: {user_name}")
            
            # Insert into participants
            cursor.execute("""
                INSERT INTO participants (user_id, lottery, name, approved_at) 
                VALUES (?, ?, ?, ?)
            """, (target_user_id, lottery_type, user_name, datetime.now()))
            conn.commit()
            
            ticket_id = cursor.lastrowid
            print(f"   Ticket #{ticket_id} created")
            
            # Remove from pending
            cursor.execute("DELETE FROM pending WHERE id = ?", (pending_id,))
            conn.commit()
            
            # Send message to USER
            prize = WEEKLY_PRIZE if lottery_type == "weekly" else MONTHLY_PRIZE
            user_message = (
                f"✅ **PAYMENT APPROVED!** ✅\n\n"
                f"🎟️ **Your Ticket:** `#{ticket_id}`\n"
                f"🎰 **Lottery:** {lottery_type.upper()}\n"
                f"💰 **Prize:** {prize} Birr\n\n"
                f"📅 **Draw Date:**\n"
                f"• Weekly: Sunday 8 PM\n"
                f"• Monthly: Month end\n\n"
                f"🍀 **Good luck!** 🍀\n\n"
                f"Contact {ADMIN_USERNAME} for questions."
            )
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=user_message,
                    parse_mode="Markdown"
                )
                print(f"   ✅ Message sent to user {target_user_id}")
            except Exception as e:
                print(f"   ❌ Failed to send to user: {e}")
            
            # Send confirmation to ADMIN
            await query.edit_message_text(
                f"✅ **APPROVED!**\n\n"
                f"👤 User: {user_name}\n"
                f"🎟️ Ticket: #{ticket_id}\n"
                f"🎰 Lottery: {lottery_type.upper()}\n\n"
                f"User has been notified!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Pending", callback_data="admin_pending")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="back_admin")]
                ]),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            print(f"❌ ERROR in approval: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
        return
    
    # ============= DRAW WINNER =============
    if query.data == "admin_winner":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        cursor.execute("SELECT lottery FROM participants")
        users = cursor.fetchall()
        
        if not users:
            await query.edit_message_text(
                "❌ No participants to draw from!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]])
            )
            return
        
        weekly_count = len([u for u in users if u[0] == "weekly"])
        monthly_count = len([u for u in users if u[0] == "monthly"])
        
        keyboard = []
        if weekly_count > 0:
            keyboard.append([InlineKeyboardButton(f"🎟️ WEEKLY ({weekly_count} tickets) - {WEEKLY_PRIZE} Birr", callback_data="draw_weekly")])
        if monthly_count > 0:
            keyboard.append([InlineKeyboardButton(f"💰 MONTHLY ({monthly_count} tickets) - {MONTHLY_PRIZE} Birr", callback_data="draw_monthly")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_admin")])
        
        await query.edit_message_text(
            f"🏆 **DRAW WINNER**\n\n"
            f"🟢 Weekly: {weekly_count} tickets (Prize: {WEEKLY_PRIZE} Birr)\n"
            f"🔴 Monthly: {monthly_count} tickets (Prize: {MONTHLY_PRIZE} Birr)\n\n"
            f"Select type:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "draw_weekly":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        cursor.execute("SELECT ticket_id, user_id, name FROM participants WHERE lottery = 'weekly'")
        users = cursor.fetchall()
        
        if not users:
            await query.edit_message_text("❌ No weekly participants!")
            return
        
        winner = random.choice(users)
        w_ticket, w_id, w_name = winner
        
        cursor.execute("DELETE FROM participants WHERE ticket_id = ?", (w_ticket,))
        conn.commit()
        
        announcement = (
            f"🏆 **WEEKLY WINNER!** 🏆\n\n"
            f"🎟️ Ticket: #{w_ticket}\n"
            f"👤 Winner: {w_name}\n"
            f"💰 Prize: {WEEKLY_PRIZE} Birr\n\n"
            f"🎉 CONGRATULATIONS! 🎉"
        )
        
        await send_to_channel(context, announcement)
        
        try:
            await context.bot.send_message(
                chat_id=w_id,
                text=f"🎉 **YOU WON {WEEKLY_PRIZE} BIRR!** 🎉\n\n{announcement}\n\nContact {ADMIN_USERNAME} to claim!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error notifying winner: {e}")
        
        await query.edit_message_text(
            f"✅ Winner drawn!\n\n{announcement}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "draw_monthly":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        cursor.execute("SELECT ticket_id, user_id, name FROM participants WHERE lottery = 'monthly'")
        users = cursor.fetchall()
        
        if not users:
            await query.edit_message_text("❌ No monthly participants!")
            return
        
        winner = random.choice(users)
        w_ticket, w_id, w_name = winner
        
        cursor.execute("DELETE FROM participants WHERE ticket_id = ?", (w_ticket,))
        conn.commit()
        
        announcement = (
            f"🏆 **MONTHLY WINNER!** 🏆\n\n"
            f"🎟️ Ticket: #{w_ticket}\n"
            f"👤 Winner: {w_name}\n"
            f"💰 Prize: {MONTHLY_PRIZE} Birr\n\n"
            f"🎉 CONGRATULATIONS! 🎉"
        )
        
        await send_to_channel(context, announcement)
        
        try:
            await context.bot.send_message(
                chat_id=w_id,
                text=f"🎉 **YOU WON {MONTHLY_PRIZE} BIRR!** 🎉\n\n{announcement}\n\nContact {ADMIN_USERNAME} to claim!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error notifying winner: {e}")
        
        await query.edit_message_text(
            f"✅ Winner drawn!\n\n{announcement}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_admin")]]),
            parse_mode="Markdown"
        )
        return
    
    # ============= POST TO CHANNEL =============
    if query.data == "admin_post":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        keyboard = [
            [InlineKeyboardButton("📢 WEEKLY LOTTERY", callback_data="post_weekly")],
            [InlineKeyboardButton("💰 MONTHLY LOTTERY", callback_data="post_monthly")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_admin")],
        ]
        
        await query.edit_message_text(
            "📢 **Post to Channel**\n\nSelect type:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "post_weekly":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        message = (
            f"🎟️ **WEEKLY LOTTERY OPEN!** 🎟️\n\n"
            f"💰 Price: 20 Birr\n"
            f"🏆 Prize: {WEEKLY_PRIZE} Birr\n\n"
            f"📌 Send 20 Birr to: `{CBE_ACCOUNT}`\n"
            f"📸 Send receipt to {ADMIN_USERNAME}\n\n"
            f"⏰ Draw: Sunday 8 PM\n"
            f"🍀 Good luck!"
        )
        
        success = await send_to_channel(context, message, "🎟️ JOIN NOW 🎟️")
        
        if success:
            await query.edit_message_text("✅ Weekly lottery posted to channel!")
        else:
            await query.edit_message_text("❌ Failed! Make bot admin in channel!")
        return
    
    if query.data == "post_monthly":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        message = (
            f"💰 **MONTHLY LOTTERY OPEN!** 💰\n\n"
            f"🎟️ Price: 50 Birr\n"
            f"🏆 Prize: {MONTHLY_PRIZE} Birr\n\n"
            f"📌 Send 50 Birr to: `{CBE_ACCOUNT}`\n"
            f"📸 Send receipt to {ADMIN_USERNAME}\n\n"
            f"⏰ Draw: Month end\n"
            f"💫 Bigger prize!"
        )
        
        success = await send_to_channel(context, message, "💰 JOIN NOW 💰")
        
        if success:
            await query.edit_message_text("✅ Monthly lottery posted to channel!")
        else:
            await query.edit_message_text("❌ Failed! Make bot admin in channel!")
        return
    
    if query.data == "admin_channel_btn":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
            
        message = (
            f"🎉 **AMU LOTTERY IS ACTIVE!** 🎉\n\n"
            f"💰 Weekly: 20 Birr → Win {WEEKLY_PRIZE} Birr\n"
            f"💰 Monthly: 50 Birr → Win {MONTHLY_PRIZE} Birr\n\n"
            f"👇 **CLICK TO JOIN** 👇"
        )
        
        success = await send_to_channel(context, message, "🎟️ JOIN LOTTERY 🎟️")
        
        if success:
            await query.edit_message_text("✅ Join button sent to channel!")
        else:
            await query.edit_message_text("❌ Failed! Make bot admin in channel!")
        return
    
    if query.data == "back_admin":
        if not is_admin(user.id):
            await query.edit_message_text("❌ Admin only!")
            return
        
        cursor.execute("SELECT COUNT(*) FROM participants")
        total_participants = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM pending")
        total_pending = cursor.fetchone()[0]
        
        keyboard = [
            [InlineKeyboardButton(f"📋 LIST PARTICIPANTS ({total_participants})", callback_data="admin_list")],
            [InlineKeyboardButton(f"⏳ PENDING APPROVALS ({total_pending})", callback_data="admin_pending")],
            [InlineKeyboardButton("🏆 DRAW WINNER", callback_data="admin_winner")],
            [InlineKeyboardButton("📢 POST TO CHANNEL", callback_data="admin_post")],
            [InlineKeyboardButton("🎟️ SEND CHANNEL BUTTON", callback_data="admin_channel_btn")],
            [InlineKeyboardButton("🔄 RESET DATABASE", callback_data="admin_reset")],
        ]
        
        await query.edit_message_text(
            f"👑 **ADMIN PANEL** 👑\n\n"
            f"✅ Active: {total_participants} | ⏳ Pending: {total_pending}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    # ============= USER BUTTONS =============
    
    if query.data == "weekly":
        context.user_data["lottery"] = "weekly"
        await query.edit_message_text(
            f"✅ **WEEKLY SELECTED** (20 Birr)\n\n"
            f"🏆 Prize: {WEEKLY_PRIZE} Birr\n\n"
            f"💰 Send 20 Birr to:\n`{CBE_ACCOUNT}`\n\n"
            f"📸 Send screenshot to {ADMIN_USERNAME}\n\n"
            f"👇 Click after sending:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I HAVE PAID", callback_data="confirm_pay")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "monthly":
        context.user_data["lottery"] = "monthly"
        await query.edit_message_text(
            f"✅ **MONTHLY SELECTED** (50 Birr)\n\n"
            f"🏆 Prize: {MONTHLY_PRIZE} Birr\n\n"
            f"💰 Send 50 Birr to:\n`{CBE_ACCOUNT}`\n\n"
            f"📸 Send screenshot to {ADMIN_USERNAME}\n\n"
            f"👇 Click after sending:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I HAVE PAID", callback_data="confirm_pay")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "confirm_pay":
        lottery = context.user_data.get("lottery", "weekly")
        price = "20" if lottery == "weekly" else "50"
        
        print(f"💰 User {user.id} ({user.first_name}) requesting payment for {lottery}")
        
        # Check for existing pending
        cursor.execute("SELECT id FROM pending WHERE user_id = ? AND lottery = ?", (user.id, lottery))
        existing = cursor.fetchone()
        
        if existing:
            await query.edit_message_text(
                f"⚠️ **You already have a pending request!**\n\n"
                f"Request ID: #{existing[0]}\n\n"
                f"Please wait for admin approval.\n\n"
                f"Contact admin: {ADMIN_USERNAME}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
                parse_mode="Markdown"
            )
            return
        
        # Add to pending
        cursor.execute("INSERT INTO pending (user_id, lottery, name, requested_at) VALUES (?, ?, ?, ?)",
                      (user.id, lottery, user.first_name, datetime.now()))
        conn.commit()
        pending_id = cursor.lastrowid
        
        print(f"   Created pending request #{pending_id}")
        
        # Message to USER
        await query.edit_message_text(
            f"✅ **PAYMENT REQUEST SENT!** ✅\n\n"
            f"🎰 **Lottery:** {lottery.upper()}\n"
            f"💰 **Amount:** {price} Birr\n"
            f"📝 **Request ID:** #{pending_id}\n\n"
            f"⏳ **What happens next?**\n"
            f"• Admin will review your payment\n"
            f"• You will receive your ticket number\n"
            f"• You'll get a confirmation message\n\n"
            f"📱 **Contact Admin:** {ADMIN_USERNAME}\n\n"
            f"Thank you for participating! Good luck! 🍀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
        )
        
        # Message to ADMIN with approve button
        keyboard = [[InlineKeyboardButton(
            f"✅ APPROVE {user.first_name}",
            callback_data=f"approve_{user.id}_{lottery}_{pending_id}"
        )]]
        
        admin_message = (
            f"🚨 **NEW PAYMENT REQUEST** 🚨\n\n"
            f"👤 **Name:** {user.first_name}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"🎰 **Lottery:** {lottery.upper()}\n"
            f"💰 **Amount:** {price} Birr\n"
            f"📝 **Request ID:** #{pending_id}\n"
            f"👤 **Username:** @{user.username if user.username else 'No username'}\n\n"
            f"✅ **Click the button below to approve this payment:**"
        )
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            print(f"   ✅ Admin notified for user {user.id}")
        except Exception as e:
            print(f"   ❌ Error notifying admin: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ User {user.first_name} (ID: {user.id}) requested {lottery} lottery.\nPending ID: {pending_id}\n\nUse /admin to approve manually.",
                parse_mode="Markdown"
            )
        return
    
    if query.data == "my_tickets":
        cursor.execute("SELECT ticket_id, lottery FROM participants WHERE user_id = ?", (user.id,))
        tickets = cursor.fetchall()
        
        if not tickets:
            await query.edit_message_text(
                "❌ **No tickets found.**\n\nBuy a ticket to play! 🎉",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
                parse_mode="Markdown"
            )
            return
        
        msg = f"🎟️ **YOUR TICKETS** 🎟️\n\n"
        for t in tickets:
            prize = WEEKLY_PRIZE if t[1] == "weekly" else MONTHLY_PRIZE
            msg += f"• Ticket #{t[0]} - {t[1].upper()} (Prize: {prize} Birr)\n"
        
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "rules":
        await query.edit_message_text(
            f"📜 **RULES** 📜\n\n"
            f"1️⃣ Select Weekly (20 Birr) or Monthly (50 Birr)\n"
            f"2️⃣ Send payment to CBE account\n"
            f"3️⃣ Take a screenshot of payment\n"
            f"4️⃣ Send screenshot to {ADMIN_USERNAME}\n"
            f"5️⃣ Click 'I HAVE PAID' button\n"
            f"6️⃣ Admin approves and gives ticket number\n"
            f"7️⃣ Winner drawn randomly\n\n"
            f"💰 **Weekly Prize:** {WEEKLY_PRIZE} Birr\n"
            f"💰 **Monthly Prize:** {MONTHLY_PRIZE} Birr\n\n"
            f"⏰ **Weekly Draw:** Sunday 8 PM\n"
            f"⏰ **Monthly Draw:** Month end\n\n"
            f"🍀 Good luck to all participants! 🍀",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )
        return
    
    if query.data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🎟️ WEEKLY (20 Birr)", callback_data="weekly")],
            [InlineKeyboardButton("💰 MONTHLY (50 Birr)", callback_data="monthly")],
            [InlineKeyboardButton("❓ RULES", callback_data="rules")],
            [InlineKeyboardButton("🎟️ MY TICKETS", callback_data="my_tickets")],
        ]
        
        await query.edit_message_text(
            f"🎉 **AMU LOTTERY** 🎉\n\n"
            f"💰 **Weekly:** 20 Birr → Win {WEEKLY_PRIZE} Birr\n"
            f"💰 **Monthly:** 50 Birr → Win {MONTHLY_PRIZE} Birr\n\n"
            f"🏆 **WIN BIG!** 🏆\n\n"
            f"Choose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"👤 New user started bot: {user.first_name} (ID: {user.id})")
    
    keyboard = [
        [InlineKeyboardButton("🎟️ WEEKLY (20 Birr)", callback_data="weekly")],
        [InlineKeyboardButton("💰 MONTHLY (50 Birr)", callback_data="monthly")],
        [InlineKeyboardButton("❓ RULES", callback_data="rules")],
        [InlineKeyboardButton("🎟️ MY TICKETS", callback_data="my_tickets")],
    ]
    
    await update.message.reply_text(
        f"🎉 **WELCOME TO AMU LOTTERY!** 🎉\n\n"
        f"💰 **Weekly:** 20 Birr → Win {WEEKLY_PRIZE} Birr\n"
        f"💰 **Monthly:** 50 Birr → Win {MONTHLY_PRIZE} Birr\n\n"
        f"🏆 **WIN BIG!** 🏆\n\n"
        f"**How to play:**\n"
        f"1. Select Weekly or Monthly\n"
        f"2. Send payment to CBE\n"
        f"3. Click 'I HAVE PAID'\n"
        f"4. Get your ticket number\n"
        f"5. Wait for the draw!\n\n"
        f"Select an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("=" * 60)
    print("🚀 AMU LOTTERY BOT RUNNING!")
    print("=" * 60)
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"💰 Weekly Prize: {WEEKLY_PRIZE} Birr")
    print(f"💰 Monthly Prize: {MONTHLY_PRIZE} Birr")
    print(f"📁 Database: lottery.db (fresh and clean)")
    print("\n📌 COMMANDS:")
    print("   /start - User menu")
    print("   /admin - Admin panel")
    print("\n📝 HOW TO TEST:")
    print("   1. Open a DIFFERENT Telegram account (not admin)")
    print("   2. Send /start to the bot")
    print("   3. Click WEEKLY or MONTHLY")
    print("   4. Click 'I HAVE PAID'")
    print("   5. User will get confirmation message")
    print("   6. Admin will get APPROVE button")
    print("   7. Click APPROVE - User gets ticket number")
    print("=" * 60)
    
    app.run_polling()

if __name__ == "__main__":
    main()