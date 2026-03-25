import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request
from datetime import datetime
import asyncio

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = "https://contador-marcos.onrender.com"

flask_app = Flask(__name__)

def get_hoja():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Finanzas Marcos").worksheet("Movimientos")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola Marcos! Soy tu Contador Virtual 🧮\n\n"
        "Comandos disponibles:\n"
        "👉 /sueldo [monto]\n"
        "👉 /gasto [monto] [concepto]\n"
        "👉 /balance\n"
        "👉 /servicios\n"
        "👉 /consejo"
    )

async def sueldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usá: /sueldo 600000")
        return
    monto = float(context.args[0])
    get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Sueldo", monto, "Ingreso mensual"])
    await update.message.reply_text(f"✅ Sueldo cargado: ${monto:,.0f}\n¡A administrarlo bien, Marcos!")

async def gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usá: /gasto 1500 café")
        return
    monto = float(context.args[0])
    concepto = " ".join(context.args[1:])
    get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, concepto])
    await update.message.reply_text(f"💸 Gasto anotado: ${monto:,.0f} en {concepto}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = get_hoja().get_all_values()
    total_sueldo = 0
    total_gastos = 0
    for fila in datos[1:]:
        try:
            valor = float(fila[2])
            if fila[1] == "Sueldo":
                total_sueldo += valor
            elif fila[1] == "Gasto":
                total_gastos += valor
        except:
            pass
    disponible = total_sueldo - total_gastos
    await update.message.reply_text(
        f"📊 BALANCE ACTUAL 📊\n\n"
        f"🟢 Ingresos: ${total_sueldo:,.0f}\n"
        f"🔴 Gastos: ${total_gastos:,.0f}\n\n"
        f"💰 Disponible: ${disponible:,.0f}"
    )

async def servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💧 Marcar AGUA", callback_data="pagar_Agua")],
        [InlineKeyboardButton("💡 Marcar LUZ", callback_data="pagar_Luz")],
        [InlineKeyboardButton("🔥 Marcar GAS", callback_data="pagar_Gas")],
        [InlineKeyboardButton("🌐 Marcar INTERNET", callback_data="pagar_Internet")]
    ]
    await update.message.reply_text(
        "🔔 CONTROL DE SERVICIOS 🔔\n\nTocá el botón cuando pagues una boleta:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def consejo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = get_hoja().get_all_values()
    total_sueldo = 0
    total_gastos = 0
    for fila in datos[1:]:
        try:
            valor = float(fila[2])
            if fila[1] == "Sueldo":
                total_sueldo += valor
            elif fila[1] == "Gasto":
                total_gastos += valor
        except:
            pass
    disponible = total_sueldo - total_gastos
    if disponible > 150000:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Pasá ${disponible*0.6:,.0f} a Mercado Pago o Personal Pay para ganar intereses diarios. Con lo que quede, evaluá comprar Dólar MEP.")
    elif disponible > 0:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada hasta el próximo gasto grande.")
    else:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    await update.message.reply_text(texto)

async def boton_servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    servicio = query.data.split("_")[1]
    await query.edit_message_text(
        f"✅ Marcaste {servicio} como PAGADO.\n\n"
        f"👉 Anotá cuánto dolió copiando esto:\n/gasto 0000 {servicio}"
    )

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def get_telegram_app():
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sueldo", sueldo))
    app.add_handler(CommandHandler("gasto", gasto))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("servicios", servicios))
    app.add_handler(CommandHandler("consejo", consejo))
    app.add_handler(CallbackQueryHandler(boton_servicios))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_desconocido))
    return app

@flask_app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    app = get_telegram_app()
    data = request.get_json()
    async with app:
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
    return "Bot activo ✅", 200

async def set_webhook():
    app = get_telegram_app()
    async with app:
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/{TOKEN}",
            drop_pending_updates=True
        )
    print(f"Webhook configurado: {WEBHOOK_URL}/{TOKEN}")

if __name__ == "__main__":
    asyncio.run(set_webhook())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
