import os
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from mcrcon import MCRcon
from dotenv import load_dotenv

# --------------------
# ENV
# --------------------
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASS = os.getenv("RCON_PASS")

SERVER_IP = os.getenv("SERVER_IP")

ALLOWED_CHATS = {
    int(x.strip())
    for x in os.getenv("ALLOWED_CHATS", "").split(",")
    if x.strip()
}

if not all([TOKEN, RCON_HOST, RCON_PASS]):
    raise RuntimeError("Не заполнен .env")

# --------------------
# LOGGING
# --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# --------------------
# ACCESS CONTROL
# --------------------
def allowed_chat(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):

        if ALLOWED_CHATS and update.effective_chat.id not in ALLOWED_CHATS:
            return

        return await func(update, context)

    return wrapper


# --------------------
# RCON (FIXED - SYNC ONLY)
# --------------------
def rcon(command: str):

    with MCRcon(
        RCON_HOST,
        RCON_PASS,
        port=RCON_PORT,
        timeout=5
    ) as m:
        return m.command(command)


# --------------------
# COMMANDS
# --------------------
@allowed_chat
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")


@allowed_chat
async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        res = rcon("list")

        if ": " not in res:
            await update.message.reply_text("Не удалось получить список")
            return

        players = res.split(": ")[1].strip()

        if not players:
            await update.message.reply_text("Никого нет онлайн")
            return

        players = "\n".join(
            p.strip() for p in players.split(",") if p.strip()
        )

        await update.message.reply_text(
            f"Игроки онлайн:\n\n{players}"
        )

    except Exception as e:
        logging.warning(f"online error: {e}")
        await update.message.reply_text("Ошибка подключения")


@allowed_chat
async def say(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Использование: /say <текст>")
        return

    msg = " ".join(context.args).replace("\n", " ")

    try:
        rcon(f"say {msg}")
        await update.message.reply_text("Отправлено")

    except Exception as e:
        logging.warning(f"say error: {e}")
        await update.message.reply_text("Ошибка")


@allowed_chat
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Использование: /kick <ник> [причина]")
        return

    player = context.args[0]
    reason = " ".join(context.args[1:]) or "Кик через Telegram"

    try:
        res = rcon(f"kick {player} {reason}")

        if res and "no player was found" in res.lower():
            await update.message.reply_text(f"{player} не найден")
        else:
            await update.message.reply_text(f"{player} кикнут")

    except Exception as e:
        logging.warning(f"kick error: {e}")
        await update.message.reply_text("Ошибка")


@allowed_chat
async def exec_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.args:
        await update.message.reply_text("Использование: /exec <command>")
        return

    cmd = " ".join(context.args)

    try:
        res = rcon(cmd)
        await update.message.reply_text(res[:4000] if res else "OK")

    except Exception as e:
        logging.warning(f"exec error: {e}")
        await update.message.reply_text("Ошибка")


@allowed_chat
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        await update.message.reply_text("Сохраняю мир...")

        rcon("save-all")
        rcon("say Сервер перезапускается через Telegram")

        import asyncio
        await asyncio.sleep(10)

        rcon("stop")

        await update.message.reply_text("Сервер остановлен")

    except Exception as e:
        logging.warning(f"restart error: {e}")
        await update.message.reply_text("Ошибка")


@allowed_chat
async def ip(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not SERVER_IP:
        await update.message.reply_text("IP не задан в .env")
        return

    await update.message.reply_text(f"{SERVER_IP}")


@allowed_chat
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "/online\n/ping\n/say\n/kick\n/exec\n/restart\n/ip"
    )


@allowed_chat
async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        f"Chat ID: {update.effective_chat.id}"
    )


# --------------------
# ERROR HANDLER
# --------------------
async def error_handler(update, context):
    logging.error("Error:", exc_info=context.error)


# --------------------
# MAIN
# --------------------
if __name__ == "__main__":

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("say", say))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("exec", exec_cmd))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("ip", ip))
    app.add_handler(CommandHandler("getid", getid))

    app.add_error_handler(error_handler)

    logging.info("Bot started")
    app.run_polling()
