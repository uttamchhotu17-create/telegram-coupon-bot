import sqlite3
import uuid
from telegram import *
from telegram.ext import *

TOKEN = "8271855633:AAEOQ0ymg-NFiXHhIu2QtNC3dL_cWtmTwxQ"
ADMIN_ID = 7662708655
SUPPORT_USERNAME = "@Ark456781"

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
    proof TEXT,
    status TEXT
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
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
            ["👥 Users","📢 Broadcast"]
        ]
        await update.message.reply_text("👑 Admin Panel",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    else:
        keyboard = [
            ["🛒 Buy Product"],
            ["📜 My Orders","🔍 Check Order"],
            ["📞 Support"]
        ]
        await update.message.reply_text(
            "Welcome to Digital Store.\nSelect option:",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )

# ---------------- USER BUY ---------------- #

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT name FROM products")
    products = cursor.fetchall()

    buttons = [[InlineKeyboardButton(p[0],callback_data=f"buy_{p[0]}")] for p in products]

    await update.message.reply_text("Select Product:",
        reply_markup=InlineKeyboardMarkup(buttons))

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product = query.data.replace("buy_","")

    cursor.execute("SELECT COUNT(*) FROM stock WHERE product=?",(product,))
    stock = cursor.fetchone()[0]

    if stock == 0:
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

    qty = int(query.data.replace("qty_",""))
    user_id = query.from_user.id

    product = user_state[user_id]["product"]
    price = user_state[user_id]["price"]
    total = price * qty
    order_id = "ORD"+str(uuid.uuid4())[:8]

    user_state[user_id].update({
        "qty":qty,
        "order_id":order_id,
        "total":total
    })

    await query.message.reply_photo(
        photo=open("qr.jpg","rb"),
        caption=f"Order ID: {order_id}\nPay ₹{total}\nSend payment screenshot",
        reply_markup=ReplyKeyboardMarkup(
            [["📤 Upload Payment Screenshot","❌ Cancel"]],
            resize_keyboard=True
        )
    )

# ---------------- PAYMENT PROOF ---------------- #

async def ask_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id]["waiting_proof"] = True
    await update.message.reply_text("Upload payment screenshot")

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_state:
        return
    if "waiting_proof" not in user_state[user_id]:
        return

    file_id = update.message.photo[-1].file_id
    order = user_state[user_id]

    cursor.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)",
        (order["order_id"],user_id,order["product"],
         order["qty"],order["total"],file_id,"pending"))
    conn.commit()

    buttons = [[
        InlineKeyboardButton("✅ Approve",
            callback_data=f"approve_{order['order_id']}"),
        InlineKeyboardButton("❌ Reject",
            callback_data=f"reject_{order['order_id']}")
    ]]

    await context.bot.send_photo(
        ADMIN_ID,
        file_id,
        caption=f"New Order\nOrder ID: {order['order_id']}\nUser: {user_id}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    await update.message.reply_text("Order submitted. Waiting approval.")
    user_state.pop(user_id)

# ---------------- ADMIN ACTION ---------------- #

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, order_id = query.data.split("_",1)

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

        await context.bot.send_message(user_id,
            "✅ Payment Approved\nYour Codes:\n"+ "\n".join(codes))

        await query.message.edit_caption("Order Approved")

    else:
        cursor.execute("UPDATE orders SET status='rejected' WHERE order_id=?",(order_id,))
        conn.commit()

        await context.bot.send_message(order[1],"❌ Payment Rejected")
        await query.message.edit_caption("Order Rejected")

# ---------------- USER EXTRA ---------------- #

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT order_id,product,qty,amount,status FROM orders WHERE user_id=?",(user_id,))
    orders = cursor.fetchall()

    if not orders:
        await update.message.reply_text("No orders found.")
        return

    msg = ""
    for o in orders:
        msg += f"Order: {o[0]}\nProduct: {o[1]}\nQty: {o[2]}\nAmount: ₹{o[3]}\nStatus: {o[4]}\n\n"

    await update.message.reply_text(msg)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"https://t.me/{SUPPORT_USERNAME}")

# ---------------- MAIN ---------------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(MessageHandler(filters.Text("🛒 Buy Product"),buy))
app.add_handler(CallbackQueryHandler(select_product,pattern="^buy_"))
app.add_handler(CallbackQueryHandler(select_qty,pattern="^qty_"))
app.add_handler(MessageHandler(filters.Text("📤 Upload Payment Screenshot"),ask_proof))
app.add_handler(MessageHandler(filters.PHOTO,receive_photo))
app.add_handler(CallbackQueryHandler(admin_action,pattern="^(approve_|reject_)"))
app.add_handler(MessageHandler(filters.Text("📜 My Orders"),my_orders))
app.add_handler(MessageHandler(filters.Text("📞 Support"),support))

app.run_polling()
