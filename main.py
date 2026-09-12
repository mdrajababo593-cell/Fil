import os
import json
import threading
import telebot
from telebot import types

# ================= কনফিগারেশন =================
BOT_TOKEN = "8704973744:"   # BotFather থেকে পাওয়া টোকেন
ADMIN_ID = 6805684286                # আপনার টেলিগ্রাম আইডি (সংখ্যায়)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=40)

USERS_FILE = "users.json"
POSTS_FILE = "posts.json"

file_lock = threading.Lock()

ADMIN_STATE = {}
# কোন ইউজার কোন কোন চ্যানেলের বাটনে ক্লিক করেছে তা ট্র্যাকিং
USER_CLICKED_BUTTONS = {} 
# ভেরিফাই ক্লিক ট্র্যাকার (১ম ক্লিক vs ২য় ক্লিক)
USER_VERIFY_ATTEMPTS = {} 

# ================= ডাটাবেজ হ্যান্ডলার =================
def load_data(file_name):
    with file_lock:
        if not os.path.exists(file_name):
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump({}, f)
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}

def save_data(file_name, data):
    with file_lock:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# প্রিমিয়াম বক্স UI
def royal_box(title, text):
    return (
        f"╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"        🌟 <b>{title.upper()}</b> 🌟\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"{text}\n"
        f"─────────────────────────────"
    )

# ডায়নামিক কিবোর্ড জেনারেটর (যে বাটনে ক্লিক করবে সেটা সরে যাবে)
def generate_task_keyboard(user_id, post_id, channels):
    user_key = f"{user_id}_{post_id}"
    clicked = USER_CLICKED_BUTTONS.get(user_key, set())

    keyboard = types.InlineKeyboardMarkup()
    # শুধুমাত্র যে বাটনগুলোতে এখনো ক্লিক করেনি সেগুলো দেখাবে (বাকিগুলো গায়েব)
    for idx, url in enumerate(channels):
        if idx not in clicked:
            keyboard.add(types.InlineKeyboardButton(text=f"📢 চ্যানেল {idx+1} এ জয়েন করুন", callback_data=f"click_ch:{post_id}:{idx}"))

    # ভেরিফাই বাটন সবসময় নিচে থাকবে
    keyboard.add(types.InlineKeyboardButton(text="🔄 ভেরিফাই করুন", callback_data=f"verify:{post_id}"))
    return keyboard

# ফাইল পাঠানো
def send_user_file(chat_id, post):
    file_type = post["file_type"]
    file_id = post["file_id"]
    caption = royal_box("VERIFIED SUCCESSFUL", "🎉 <b>আপনার ভেরিফিকেশন সফল হয়েছে!</b>\n\n📂 নিচে আপনার কাঙ্ক্ষিত ফাইল দেওয়া হলো:")

    try:
        if file_type == 'document':
            bot.send_document(chat_id, file_id, caption=caption)
        elif file_type == 'video':
            bot.send_video(chat_id, file_id, caption=caption)
        elif file_type == 'audio':
            bot.send_audio(chat_id, file_id, caption=caption)
        elif file_type == 'photo':
            bot.send_photo(chat_id, file_id, caption=caption)
    except Exception:
        bot.send_message(chat_id, "❌ ফাইলটি পাঠাতে সমস্যা হয়েছে। অ্যাডমিনের সাথে যোগাযোগ করুন।")

# ================= /START হ্যান্ডলার =================
@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    first_name = message.from_user.first_name

    # ইউজার সেভ
    users = load_data(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {"name": first_name, "username": message.from_user.username}
        save_data(USERS_FILE, users)

    # অ্যাডমিন প্যানেল
    if user_id == ADMIN_ID and text == "/start":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ নতুন পোস্ট তৈরি", "⚙️ পোস্ট কাস্টমাইজ")
        markup.row("📢 নোটিশ পাঠান", "📊 মোট ইউজার")
        
        bot.send_message(
            ADMIN_ID,
            royal_box("ADMIN DASHBOARD", f"স্বাগতম বস <b>{first_name}</b>!\nনিচের মেনু থেকে কাজ পরিচালনা করুন:"),
            reply_markup=markup
        )
        return

    # সাধারণ ভিজিটর (প্রোফাইল পিকচার ওয়েলকাম)
    parts = text.split()
    if len(parts) == 1:
        welcome_text = (
            f"👋 হ্যালো প্রিয় <b>{first_name}</b>,\n\n"
            f"👑 আমাদের ফাইল স্টোর বটে আপনাকে স্বাগতম!\n"
            f"⚡ এখানে সব ফাইল সুরক্ষিত ও সহজে পাবেন।\n\n"
            f"📌 <i>ফাইল পেতে নির্দিষ্ট প্রজেক্ট লিংকে ক্লিক করে আসুন।</i>"
        )
        try:
            photos = bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                bot.send_photo(chat_id, file_id, caption=royal_box("WELCOME USER", welcome_text))
            else:
                bot.send_message(chat_id, royal_box("WELCOME USER", welcome_text))
        except Exception:
            bot.send_message(chat_id, royal_box("WELCOME USER", welcome_text))
        return

    # ইউনিক লিংকে আসা ইউজার (/start post_1)
    post_id = parts[1]
    posts = load_data(POSTS_FILE)

    if post_id not in posts:
        bot.send_message(chat_id, "❌ এই পোস্ট বা ফাইলটি খুঁজে পাওয়া যায়নি!")
        return

    post = posts[post_id]
    channels = post.get("channels", [])

    if not channels:
        send_user_file(chat_id, post)
        return

    # ইউজার স্টেট ফ্রেশ করা
    user_key = f"{user_id}_{post_id}"
    USER_CLICKED_BUTTONS[user_key] = set()
    USER_VERIFY_ATTEMPTS.pop(user_key, None)

    keyboard = generate_task_keyboard(user_id, post_id, channels)

    guide_msg = (
        "⚠️ <b>ফাইলটি আনলক করার প্রয়োজনীয় নিয়মাবলী:</b>\n\n"
        "১️⃣ নিচের প্রতিটি চ্যানেলের বাটনে ক্লিক করুন।\n"
        "২️⃣ ক্লিক করার পর চ্যানেলে জয়েন করুন (চ্যানেলে চাপ দিলে বাটনটি তালিকা থেকে সরে যাবে)।\n"
        "৩️⃣ সব বাটনে ক্লিক শেষ হলে নিচে <b>ভেরিফাই করুন</b> বাটনে চাপ দিন।"
    )
    bot.send_message(chat_id, royal_box("REQUIRED TASKS", guide_msg), reply_markup=keyboard)

# ================= বাটন ক্লিক ও সরাসরি চ্যানেলে যাওয়া =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("click_ch:"))
def callback_channel_click(call):
    _, post_id, idx_str = call.data.split(":")
    idx = int(idx_str)
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    posts = load_data(POSTS_FILE)
    if post_id not in posts:
        bot.answer_callback_query(call.id, "❌ পোস্টটি পাওয়া যায়নি!", show_alert=True)
        return

    post = posts[post_id]
    channels = post.get("channels", [])
    target_url = channels[idx]

    user_key = f"{user_id}_{post_id}"
    if user_key not in USER_CLICKED_BUTTONS:
        USER_CLICKED_BUTTONS[user_key] = set()

    # এই চ্যানেলটিতে ক্লিক করা সম্পন্ন হয়েছে হিসেবে ট্র্যাকিং
    USER_CLICKED_BUTTONS[user_key].add(idx)

    # মূল মেসেজ থেকে এই বাটনটিকে চিরতরে মুছে (সরিয়) ফেলা
    new_keyboard = generate_task_keyboard(user_id, post_id, channels)
    try:
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=new_keyboard)
    except Exception:
        pass

    bot.answer_callback_query(call.id, f"✅ চ্যানেল {idx+1} এর লিংক নিচে দেওয়া হলো!", show_alert=False)

    # সরাসরি চ্যানেলে ঢুকে জয়েন হওয়ার বাটন
    open_markup = types.InlineKeyboardMarkup()
    open_markup.add(types.InlineKeyboardButton(text=f"🚀 চ্যানেল {idx+1} এ প্রবেশ করুন ↗️", url=target_url))
    bot.send_message(
        chat_id,
        f"👉 <b>চ্যানেল {idx+1} এ জয়েন করতে নিচের বাটনে চাপ দিন:</b>",
        reply_markup=open_markup
    )

# ================= ১০০% সিকিউর ভেরিফাই বাটন =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("verify:"))
def callback_verify(call):
    post_id = call.data.split("verify:")[1]
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    posts = load_data(POSTS_FILE)
    if post_id not in posts:
        bot.answer_callback_query(call.id, "❌ পোস্টটি ডাটাবেজে নেই!", show_alert=True)
        return

    post = posts[post_id]
    channels = post.get("channels", [])
    user_key = f"{user_id}_{post_id}"
    clicked = USER_CLICKED_BUTTONS.get(user_key, set())

    # শর্ত ১: কোনো বাটন কি এখনো ক্লিক করা বাকি আছে?
    unclicked = [i for i in range(len(channels)) if i not in clicked]

    if unclicked:
        # ইউজার যে বাটনে এখনো ক্লিক করেনি সেটির কথা উল্লেখ করে আটকে দেবে
        next_channel = unclicked[0] + 1
        bot.answer_callback_query(
            call.id,
            f"❌ আপনি এখনো চ্যানেল {next_channel}-এ ক্লিক করেননি!\n\nদয়া করে বাকি থাকা চ্যানেল {next_channel} বাটনে ক্লিক করে জয়েন হন।",
            show_alert=True
        )
        return

    # শর্ত ২: সবগুলো বাটনে ক্লিক শেষ হলে ২-ক্লিক ভেরিফিকেশন ফ্লো
    attempts = USER_VERIFY_ATTEMPTS.get(user_key, 0)

    if attempts == 0:
        USER_VERIFY_ATTEMPTS[user_key] = 1
        bot.answer_callback_query(
            call.id,
            "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!\n\nদয়া করে চ্যানেলে জয়েন নিশ্চিত করে আরেকবার 'ভেরিফাই করুন' বাটনে চাপুন।",
            show_alert=True
        )
    else:
        # ২য় বার চাপার সাথে সাথে ফাইল আনলক!
        USER_VERIFY_ATTEMPTS.pop(user_key, None)
        USER_CLICKED_BUTTONS.pop(user_key, None)

        bot.answer_callback_query(call.id, "✅ ভেরিফিকেশন সফল হয়েছে!", show_alert=False)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_user_file(chat_id, post)

# ================= অ্যাডমিন মেনু =================
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and msg.text in ["➕ নতুন পোস্ট তৈরি", "⚙️ পোস্ট কাস্টমাইজ", "📢 নোটিশ পাঠান", "📊 মোট ইউজার"])
def admin_menu(message):
    text = message.text

    if text == "➕ নতুন পোস্ট তৈরি":
        ADMIN_STATE[ADMIN_ID] = {"step": "WAIT_FILE"}
        bot.send_message(ADMIN_ID, royal_box("STEP 1: SEND FILE", "📂 <b>যে ফাইলটি দিতে চান সেটি পাঠান:</b>\n(APK, Video, Audio, Zip ইত্যাদি)"))

    elif text == "⚙️ পোস্ট কাস্টমাইজ":
        posts = load_data(POSTS_FILE)
        if not posts:
            bot.send_message(ADMIN_ID, "❌ বর্তমানে কাস্টমাইজ করার মতো কোনো পোস্ট নেই।")
            return
        
        keyboard = types.InlineKeyboardMarkup()
        for p_id in posts.keys():
            keyboard.add(types.InlineKeyboardButton(f"📝 {p_id} কাস্টমাইজ করুন", callback_data=f"manage:{p_id}"))
        
        bot.send_message(ADMIN_ID, royal_box("POST CUSTOMIZER", "যে পোস্টটি এডিট বা কাস্টমাইজ করতে চান সেটিতে চাপুন:"), reply_markup=keyboard)

    elif text == "📢 নোটিশ পাঠান":
        ADMIN_STATE[ADMIN_ID] = {"step": "WAIT_BROADCAST"}
        bot.send_message(ADMIN_ID, royal_box("BROADCAST", "📝 <b>সব ইউজারের জন্য নোটিশ মেসেজটি লিখে পাঠান:</b>"))

    elif text == "📊 মোট ইউজার":
        users = load_data(USERS_FILE)
        bot.send_message(ADMIN_ID, royal_box("STATISTICS", f"📈 <b>বটের মোট ইউজার:</b> <code>{len(users)}</code> জন।"))

# ================= পোস্ট কাস্টমাইজেশন মেনু =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("manage:"))
def manage_post_options(call):
    p_id = call.data.split("manage:")[1]
    posts = load_data(POSTS_FILE)

    if p_id not in posts:
        bot.answer_callback_query(call.id, "পোস্ট পাওয়া যায়নি!", show_alert=True)
        return

    post = posts[p_id]
    info = (
        f"📌 <b>পোস্ট আইডি:</b> <code>{p_id}</code>\n"
        f"📁 <b>ফাইলের ধরন:</b> {post.get('file_type', 'N/A')}\n"
        f"🔗 <b>চ্যানেল সংখ্যা:</b> {len(post.get('channels', []))} টি\n\n"
        "নিচের অপশন থেকে যা পরিবর্তন করতে চান নির্বাচন করুন:"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("🔄 ফাইল পরিবর্তন", callback_data=f"chfile:{p_id}"),
        types.InlineKeyboardButton("🔗 লিংক পরিবর্তন", callback_data=f"chlink:{p_id}")
    )
    keyboard.add(types.InlineKeyboardButton("🗑️ পোস্ট ডিলিট করুন", callback_data=f"del:{p_id}"))
    keyboard.add(types.InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_manage"))

    bot.edit_message_text(royal_box("CUSTOMIZE POST", info), ADMIN_ID, call.message.message_id, reply_markup=keyboard)

# কাস্টমাইজ অ্যাকশন
@bot.callback_query_handler(func=lambda call: call.data.startswith(("chfile:", "chlink:", "del:", "back_manage")))
def handle_customizer_actions(call):
    data = call.data

    if data == "back_manage":
        posts = load_data(POSTS_FILE)
        keyboard = types.InlineKeyboardMarkup()
        for p_id in posts.keys():
            keyboard.add(types.InlineKeyboardButton(f"📝 {p_id} কাস্টমাইজ করুন", callback_data=f"manage:{p_id}"))
        bot.edit_message_text(royal_box("POST CUSTOMIZER", "যেকোনো পোস্ট নির্বাচন করুন:"), ADMIN_ID, call.message.message_id, reply_markup=keyboard)
        return

    action, p_id = data.split(":")
    
    if action == "chfile":
        ADMIN_STATE[ADMIN_ID] = {"step": "EDIT_FILE", "post_id": p_id}
        bot.send_message(ADMIN_ID, royal_box("CHANGE FILE", f"📂 <code>{p_id}</code> এর জন্য <b>নতুন ফাইলটি</b> পাঠান:"))

    elif action == "chlink":
        ADMIN_STATE[ADMIN_ID] = {"step": "EDIT_LINKS", "post_id": p_id}
        bot.send_message(ADMIN_ID, royal_box("CHANGE LINKS", f"🔗 <code>{p_id}</code> এর জন্য <b>নতুন চ্যানেল লিংকগুলো</b> দিন (বা `skip` লিখুন):"))

    elif action == "del":
        posts = load_data(POSTS_FILE)
        if p_id in posts:
            del posts[p_id]
            save_data(POSTS_FILE, posts)
            bot.answer_callback_query(call.id, "✅ পোস্টটি সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
            bot.delete_message(ADMIN_ID, call.message.message_id)

# ================= অ্যাডমিন ফাইল হ্যান্ডলার =================
@bot.message_handler(content_types=['document', 'video', 'audio', 'photo'], func=lambda msg: msg.from_user.id == ADMIN_ID)
def admin_file_handler(message):
    step = ADMIN_STATE.get(ADMIN_ID, {}).get("step")

    if message.document:
        f_type, f_id = "document", message.document.file_id
    elif message.video:
        f_type, f_id = "video", message.video.file_id
    elif message.audio:
        f_type, f_id = "audio", message.audio.file_id
    elif message.photo:
        f_type, f_id = "photo", message.photo[-1].file_id
    else:
        return

    # নতুন পোস্টের ফাইল গ্রহণ
    if step == "WAIT_FILE":
        ADMIN_STATE[ADMIN_ID] = {
            "step": "WAIT_CHANNELS",
            "file_type": f_type,
            "file_id": f_id
        }
        guide = (
            "✅ <b>ফাইল গ্রহণ করা হয়েছে!</b>\n\n"
            "🔗 এবার যে চ্যানেলগুলোর লিংক দিতে চান, সেগুলো পেস্ট করুন।\n"
            "<i>(১টি, ২টি বা যত ইচ্ছা লিংক দিন)</i>\n\n"
            "👉 কোনো চ্যানেল না চাইলে লিখুন: <code>skip</code>"
        )
        bot.send_message(ADMIN_ID, royal_box("STEP 2: ADD LINKS", guide))

    # ফাইল পরিবর্তন (Customize)
    elif step == "EDIT_FILE":
        p_id = ADMIN_STATE[ADMIN_ID]["post_id"]
        posts = load_data(POSTS_FILE)
        if p_id in posts:
            posts[p_id]["file_type"] = f_type
            posts[p_id]["file_id"] = f_id
            save_data(POSTS_FILE, posts)
            bot.send_message(ADMIN_ID, royal_box("FILE UPDATED", f"✅ <b>{p_id}</b> এর ফাইল সফলভাবে পরিবর্তন করা হয়েছে!"))
        ADMIN_STATE.pop(ADMIN_ID, None)

# ================= অ্যাডমিন টেক্সট হ্যান্ডলার =================
@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and ADMIN_ID in ADMIN_STATE)
def admin_text_handler(message):
    state = ADMIN_STATE[ADMIN_ID].get("step")
    text = message.text.strip()

    # নতুন পোস্টের লিংক গ্রহণ
    if state == "WAIT_CHANNELS":
        channels = []
        if text.lower() != "skip":
            raw = text.split()
            for l in raw:
                l = l.strip()
                if l.startswith("http://") or l.startswith("https://") or l.startswith("t.me/"):
                    if not l.startswith("http"):
                        l = f"https://{l}"
                    channels.append(l)

        posts = load_data(POSTS_FILE)
        count = 1
        while f"post_{count}" in posts:
            count += 1
        post_id = f"post_{count}"

        posts[post_id] = {
            "file_type": ADMIN_STATE[ADMIN_ID]["file_type"],
            "file_id": ADMIN_STATE[ADMIN_ID]["file_id"],
            "channels": channels
        }
        save_data(POSTS_FILE, posts)

        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={post_id}"
        ADMIN_STATE.pop(ADMIN_ID, None)

        success_msg = (
            f"🎉 <b>আপনার পোস্ট সফলভাবে তৈরি হয়েছে!</b>\n\n"
            f"🔗 <b>পাবলিক শেয়ারিং লিংক:</b>\n<code>{link}</code>\n\n"
            f"📢 মোট যুক্ত চ্যানেল: <b>{len(channels)}</b> টি।"
        )
        bot.send_message(ADMIN_ID, royal_box("POST CREATED", success_msg))

    # লিংক পরিবর্তন (Customize)
    elif state == "EDIT_LINKS":
        p_id = ADMIN_STATE[ADMIN_ID]["post_id"]
        channels = []
        if text.lower() != "skip":
            raw = text.split()
            for l in raw:
                l = l.strip()
                if l.startswith("http://") or l.startswith("https://") or l.startswith("t.me/"):
                    if not l.startswith("http"):
                        l = f"https://{l}"
                    channels.append(l)

        posts = load_data(POSTS_FILE)
        if p_id in posts:
            posts[p_id]["channels"] = channels
            save_data(POSTS_FILE, posts)
            bot.send_message(ADMIN_ID, royal_box("LINKS UPDATED", f"✅ <b>{p_id}</b> এর চ্যানেল লিংক পরিবর্তন করা হয়েছে!\n📢 নতুন চ্যানেল সংখ্যা: <b>{len(channels)}</b> টি।"))
        ADMIN_STATE.pop(ADMIN_ID, None)

    # ব্রডকাস্ট নোটিশ
    elif state == "WAIT_BROADCAST":
        ADMIN_STATE.pop(ADMIN_ID, None)
        users = load_data(USERS_FILE)
        broadcast_text = message.text

        def run_broadcast():
            sent = 0
            for uid in list(users.keys()):
                try:
                    bot.send_message(
                        uid,
                        royal_box("OFFICIAL NOTICE", f"{broadcast_text}\n\n<i>💬 যেকোনো প্রয়োজনে সরাসরি মেসেজ দিন।</i>")
                    )
                    sent += 1
                    time.sleep(0.04)
                except Exception:
                    pass
            bot.send_message(ADMIN_ID, royal_box("COMPLETED", f"✅ মোট <b>{sent}</b> জন ইউজারের কাছে নোটিশ পৌঁছেছে!"))

        threading.Thread(target=run_broadcast).start()
        bot.send_message(ADMIN_ID, "🚀 ব্যাকগ্রাউন্ডে নোটিশ পাঠানো শুরু হয়েছে...")

# বট চালু
print("👑 [ULTIMATE 100% UNBYPASSABLE FILE STORE BOT] Running smoothly on Termux!")
bot.infinity_polling(timeout=15, long_polling_timeout=5)
