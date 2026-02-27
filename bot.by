import sqlite3
import uuid
from telegram import *
from telegram.ext import *

TOKEN = "8271855633:AAEOQ0ymg-NFiXHhIu2QtNC3dL_cWtmTwxQ"
ADMIN_ID = 7662708655  # apni Telegram numeric ID

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS products(
    name TEXT PRIMARY KEY,
    price INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS stock(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT,
    code TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS orders(
    order_id TEXT PRIMARY KEY,
    user_id INTEGER,
    product TEXT,
    qty INTEGER,
    amount INTEGER,
    utr TEXT,
    status TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS used_utrs(
    utr TEXT PRIMARY KEY
)""")

conn.commit()

# Default products
cursor.execute("INSERT OR IGNORE INTO products VALUES('500',20)")
cursor.execute("INSERT OR IGNORE INTO products VALUES('1000',110)")
conn.commit()

user_state = {}

# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("INSERT OR IGNORE INTO users VALUES(?)",(user_id,))
    conn.commit()

    if user_id == ADMIN_ID:
        keyboard = [
            ["📦 Add Product","➕ Add Stock"],
            ["💰 Set Price","📊 View Products"],
            ["🧾 Pending Orders","📈 Sales Report"],
            ["👥 Users","📢 Broadcast"],
            ["🖼 Change QR"]
        ]
        await update.message.reply_text(
            "Admin Panel",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
    else:
        keyboard = [["🛒 Buy Product"]]
        await update.message.reply_text(
            "⚠ Use at your own risk.\nInstant use only.\nNo replacement.",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )

# ---------------- BUY ---------------- #

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name FROM products")
    products = cursor.fetchall()

    buttons = [[InlineKeyboardButton(p[0],callback_data=f"buy_{p[0]}")] for p in products]

    await update.message.reply_text(
        "Select Product:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product = query.data.split("_")[1]

    cursor.execute("SELECT COUNT(*) FROM stock WHERE product=?",(product,))
    stock_count = cursor.fetchone()[0]

    if stock_count == 0:
        await query.message.reply_text("❌ Out of Stock")
        return

    cursor.execute("SELECT price FROM products WHERE name=?",(product,))
    price = cursor.fetchone()[0]

    user_state[query.from_user.id] = {"product":product,"price":price}

    buttons = [
        [InlineKeyboardButton("1",callback_data="qty_1"),
         InlineKeyboardButton("2",callback_data="qty_2"),
         InlineKeyboardButton("5",callback_data="qty_5")]
    ]

    await query.message.reply_text(
        f"Price: ₹{price}\nSelect Quantity:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def select_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    qty = int(query.data.split("_")[1])
    user_id = query.from_user.id

    product = user_state[user_id]["product"]
    price = user_state[user_id]["price"]

    total = price * qty
    order_id = "ORD"+str(uuid.uuid4())[:8]

    user_state[user_id]["qty"] = qty
    user_state[user_id]["order_id"] = order_id
    user_state[user_id]["total"] = total

    await query.message.reply_photo(
        photo=open("qr.jpg","rb"),
        caption=f"Order ID: {order_id}\nPay ₹{total}\nSend UTR after payment",
        reply_markup=ReplyKeyboardMarkup(
            [["📨 Send UTR","❌ Cancel"]],
            resize_keyboard=True
        )
    )

# ---------------- UTR ---------------- #

async def ask_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id]["waiting_utr"] = True
    await update.message.reply_text("Send your UTR number")

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_state:
        return

    if "waiting_utr" not in user_state[user_id]:
        return

    cursor.execute("SELECT * FROM used_utrs WHERE utr=?",(text,))
    if cursor.fetchone():
        await update.message.reply_text("❌ Duplicate UTR")
        return

    cursor.execute("INSERT INTO used_utrs VALUES(?)",(text,))
    conn.commit()

    order = user_state[user_id]

    cursor.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)",
        (order["order_id"],user_id,order["product"],
         order["qty"],order["total"],text,"pending"))
    conn.commit()

    buttons = [[
        InlineKeyboardButton("✅ Approve",
            callback_data=f"approve_{order['order_id']}"),
        InlineKeyboardButton("❌ Reject",
            callback_data=f"reject_{order['order_id']}")
    ]]

    await context.bot.send_message(
        ADMIN_ID,
        f"New Order\nOrder ID: {order['order_id']}\nUser: {user_id}\nUTR: {text}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    await update.message.reply_text("Order submitted. Waiting for admin approval.")
    user_state.pop(user_id)

# ---------------- ADMIN APPROVE / REJECT ---------------- #

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action,order_id = query.data.split("_")

    cursor.execute("SELECT * FROM orders WHERE order_id=?",(order_id,))
    order = cursor.fetchone()

    if not order:
        return

    if action == "approve":
        product = order[2]
        qty = order[3]
        user_id = order[1]

        cursor.execute("SELECT id,code FROM stock WHERE product=? LIMIT ?",
            (product,qty))
        items = cursor.fetchall()

        codes = []
        for item in items:
            codes.append(item[1])
            cursor.execute("DELETE FROM stock WHERE id=?",(item[0],))

        cursor.execute("UPDATE orders SET status='approved' WHERE order_id=?",(order_id,))
        conn.commit()

        await context.bot.send_message(
            user_id,
            "✅ Payment Approved\nYour Codes:\n"+ "\n".join(codes)
        )

        await query.message.edit_text("Order Approved")

    else:
        cursor.execute("UPDATE orders SET status='rejected' WHERE order_id=?",(order_id,))
        conn.commit()

        await context.bot.send_message(order[1],"❌ Payment Rejected")
        await query.message.edit_text("Order Rejected")

# ---------------- MAIN ---------------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(MessageHandler(filters.Text("🛒 Buy Product"),buy))
app.add_handler(CallbackQueryHandler(select_product,pattern="buy_"))
app.add_handler(CallbackQueryHandler(select_qty,pattern="qty_"))
app.add_handler(MessageHandler(filters.Text("📨 Send UTR"),ask_utr))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,receive_text))
app.add_handler(CallbackQueryHandler(admin_action,pattern="approve_|reject_"))

app.run_polling()
