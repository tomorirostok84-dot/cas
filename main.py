import asyncio, random, sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton as KB, InlineKeyboardMarkup as IK, InlineKeyboardButton as IB
from aiocryptopay import AioCryptoPay, Networks

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8758272443:AAF-M75An8MgY8Ow4DLXJbzIwXMfbiUhHGg"
CRYPTO_TOKEN = "568188:AAUDXUkbQ5RQnBcnPwXmjyS3uXfuAgG3yLT"
ADMIN_ID = 8777986259  # Твой ID установлен
CHANNEL_ID = -1003906163769

bot = Bot(token=TOKEN)
dp = Dispatcher()
crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)

# --- БАЗА ДАННЫХ ---
db = sqlite3.connect("wesbet.db", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, admin INTEGER DEFAULT 0, banned INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val REAL)")
cur.execute("INSERT OR IGNORE INTO settings VALUES ('treasury', 0.0)")
db.commit()

def get_u(uid):
    cur.execute("SELECT balance, admin, banned FROM users WHERE id = ?", (uid,))
    res = cur.fetchone()
    if not res:
        is_adm = 1 if uid == ADMIN_ID else 0
        cur.execute("INSERT INTO users (id, balance, admin, banned) VALUES (?, ?, ?, 0)", (uid, 100.0, is_adm, 0))
        db.commit()
        return [100.0, is_adm, 0]
    if res[2] == 1: return None # Если забанен
    return list(res)

async def log_bet(user, game, bet, win_res):
    status = "✅ ВИН" if win_res > 0 else "❌ ЛОЗ"
    # Для логов: если лоз, пишем просто сумму ставки, если вин - общую сумму выплаты
    display_sum = round(win_res, 2) if win_res > 0 else bet
    text = (f"🎰 **СТАВКА**\n👤 {user.mention_html()}\n"
            f"🎮 {game}\n💰 {bet}$ -> {status} ({display_sum}$)\n\n"
            f"<a href='https://t.me{(await bot.get_me()).username}'>👉 ИГРАТЬ В WESBET</a>")
    try: await bot.send_message(CHANNEL_ID, text, parse_mode="HTML", disable_web_page_preview=True)
    except: pass

# --- КЛАВИАТУРЫ ---
main_kb = ReplyKeyboardMarkup(keyboard=,], resize_keyboard=True)
game_kb = ReplyKeyboardMarkup(keyboard=,,,], resize_keyboard=True)

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def start(m: types.Message):
    u = get_u(m.from_user.id)
    if u is None: return await m.answer("🚫 Вы заблокированы в Wesbet Casino.")
    text = (f"👋 Приветствую, вы попали в **Wesbet Casino**!\n\n"
            f"💰 Баланс: {round(u[0], 2)}$\n"
            f"🆔 ID: `{m.from_user.id}`\n"
            f"👤 Юзер: @{m.from_user.username}")
    await m.answer(text, reply_markup=main_kb, parse_mode="Markdown")

@dp.message(F.text == "🎮 Играть")
async def play(m: types.Message):
    if get_u(m.from_user.id) is None: return
    await m.answer("Выберите режим игры:", reply_markup=game_kb)

@dp.message(F.text == "⬅️ Назад")
async def back(m: types.Message):
    await start(m)

@dp.message(F.text == "📲 Профиль")
async def profile(m: types.Message):
    u = get_u(m.from_user.id)
    if u is None: return
    await m.answer(f"👤 **ПРОФИЛЬ**\n\n🆔 ID: `{m.from_user.id}`\n💰 Баланс: {round(u[0], 2)}$\n👑 Статус: {'Администратор' if u[1] else 'Игрок'}", parse_mode="Markdown")

# --- ИГРЫ ---
@dp.message(F.text == "🎲 Кубик")
async def cube(m: types.Message):
    kb = IK(inline_keyboard=])
    await m.answer("Ставка: 10$. Выберите исход:", reply_markup=kb)

@dp.callback_query(F.data.startswith("c_"))
async def cube_res(c: types.CallbackQuery):
    u = get_u(c.from_user.id)
    if u[0] < 10: return await c.answer("Недостаточно средств!", show_alert=True)
    res = await c.message.answer_dice(emoji="🎲")
    await asyncio.sleep(3.5)
    val = res.dice.value
    win = (val % 2 == 0 and c.data == "c_e") or (val % 2 != 0 and c.data == "c_o")
    profit = 8.5 if win else -10
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (profit, c.from_user.id))
    db.commit()
    await c.message.answer(f"📈 Выпало {val}: Выигрыш 18.5$!" if win else f"📉 Выпало {val}: Проигрыш 10$")
    await log_bet(c.from_user, "Кубик", 10, 18.5 if win else 0)

@dp.message(F.text.in_(["⚽ Футбол", "🏀 Баскетбол"]))
async def ball(m: types.Message):
    u = get_u(m.from_user.id)
    if u[0] < 10: return await m.answer("Минимальная ставка 10$")
    em = "⚽" if "Футбол" in m.text else "🏀"
    res = await m.answer_dice(emoji=em)
    await asyncio.sleep(3.5)
    goal = res.dice.value >= 3 # Условный гол для анимации
    if em == "⚽":
        profit = 8.5 if goal else 15.0 # Гол 0.85x, Мимо 1.5x по заказу
    else:
        profit = 12.5 if goal else 8.5 # Баскет гол 1.25x / мимо 0.85x
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (profit, m.from_user.id))
    db.commit()
    await m.answer(f"{'✅ ГОЛ!' if goal else '❌ МИМО!'} Начислено: {profit}$")
    await log_bet(m.from_user, m.text, 10, profit)

@dp.message(F.text == "💣 Мины")
async def mn_st(m: types.Message):
    kb = IK(inline_keyboard=])
    await m.answer("💣 **МИНЫ** (Ставка 20$)\nВыберите количество мин:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("m_"))
async def mn_pl(c: types.CallbackQuery):
    cnt = int(c.data.split("_"))
    if random.randint(1, 25) > cnt:
        win = round(20 * (1 + (cnt * 0.05)), 2)
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (win, c.from_user.id))
        await c.answer(f"💎 Успех! Выигрыш: {win}$", show_alert=True)
        await log_bet(c.from_user, f"Мины ({cnt})", 20, win)
    else:
        cur.execute("UPDATE users SET balance = balance - 20 WHERE id = ?", (c.from_user.id,))
        await c.answer("💥 БА-БАХ! Проигрыш 20$", show_alert=True)
        await log_bet(c.from_user, f"Мины ({cnt})", 20, 0)
    db.commit()

# --- CRYPTOBOT ---
@dp.message(F.text == "💳 Пополнить")
async def dep(m: types.Message):
    inv = await crypto.create_invoice(asset='USDT', amount=10)
    kb = IK(inline_keyboard=,])
    await m.answer("💎 Пополнение баланса на 10$ через CryptoBot:", reply_markup=kb)

@dp.callback_query(F.data.startswith("chk_"))
async def chk(c: types.CallbackQuery):
    inv_id = int(c.data.split("_"))
    invoices = await crypto.get_invoices(invoice_ids=inv_id)
    if invoices.status == 'paid':
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (invoices.amount, c.from_user.id))
        cur.execute("UPDATE settings SET val = val + ? WHERE key = 'treasury'", (invoices.amount,))
        db.commit()
        await c.message.answer("✅ Баланс успешно пополнен!")
    else: await c.answer("❌ Оплата не найдена!", show_alert=True)

# --- АДМИНКА ---
@dp.message(F.text == "👨‍💻 Админка")
async def adm_p(m: types.Message):
    u = get_u(m.from_user.id)
    if not u or u[1] == 0: return
    cur.execute("SELECT val FROM settings WHERE key = 'treasury'")
    tr = cur.fetchone()[0]
    await m.answer(f"⚙️ **АДМИН-ПАНЕЛЬ**\n\n💰 Казна: {round(tr, 2)}$\n\n**Команды:**\n`+бал [ID] [СУММА]`\n`-бал [ID] [СУММА]`\n`+адм [ID]`\n`+бан [ID]`\n`рассылка [ТЕКСТ]`", parse_mode="Markdown")

@dp.message(F.text.startswith("+бал"))
async def a_b(m: types.Message):
    if not get_u(m.from_user.id)[1]: return
    try:
        _, uid, am = m.text.split()
        cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (float(am), int(uid)))
        db.commit()
        await m.answer("✅ Баланс выдан.")
    except: await m.answer("Ошибка формата.")

@dp.message(F.text.startswith("+бан"))
async def a_ban(m: types.Message):
    if not get_u(m.from_user.id)[1]: return
    uid = m.text.split()[1]
    cur.execute("UPDATE users SET banned = 1 WHERE id = ?", (int(uid),))
    db.commit()
    await m.answer(f"🚫 Пользователь {uid} забанен.")

@dp.message(F.text.startswith("рассылка"))
async def a_mail(m: types.Message):
    if not get_u(m.from_user.id)[1]: return
    txt = m.text.replace("рассылка", "").strip()
    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    count = 0
    for u in users:
        try: 
            await bot.send_message(u[0], txt)
            count += 1
        except: pass
    await m.answer(f"📢 Рассылка завершена. Получили {count} чел.")

async def main():
    print(">>> Бот WESBET запущен. Канал подключен! <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
      
