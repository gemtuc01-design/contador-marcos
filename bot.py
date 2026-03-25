import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime

# --- GOOGLE SHEETS ---
def get_hoja():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Finanzas Marcos").worksheet("Movimientos")
    return sheet

# --- COMANDOS ---
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "¡Hola Marcos! Soy tu Contador Virtual 🧮\n\n"
        "Comandos disponibles:\n"
        "👉 /sueldo [monto]\n"
        "👉 /gasto [monto] [concepto]\n"
        "👉 /balance\n"
        "👉 /servicios\n"
        "👉 /consejo"
    )

def sueldo(update: Update, context: CallbackContext):
    if len(context.args) < 1:
        update.message.reply_text("❌ Usá: /sueldo 600000")
        return
    monto = float(context.args[0])
    hoja = get_hoja()
    hoja.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Sueldo", monto, "Ingreso mensual"])
    update.message.reply_text(f"✅ Sueldo cargado: ${monto:,.0f}\n¡A administrarlo bien, Marcos!")

def gasto(update: Update, context: CallbackContext):
    if len(context.args) < 2:
        update.message.reply_text("❌ Usá: /gasto 1500 café")
        return
    monto = float(context.args[0])
    concepto = " ".join(context.args[1:])
    hoja = get_hoja()
    hoja.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, concepto])
    update.message.reply_text(f"💸 Gasto anotado: ${monto:,.0f} en {concepto}")

def balance(update: Update, context: CallbackContext):
    hoja = get_hoja()
    datos = hoja.get_all_values()
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
    update.message.reply_text(
        f"📊 BALANCE ACTUAL 📊\n\n"
        f"🟢 Ingresos: ${total_sueldo:,.0f}\n"
        f"🔴 Gastos: ${total_gastos:,.0f}\n\n"
        f"💰 Disponible: ${disponible:,.0f}"
    )

def servicios(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("💧 Marcar AGUA", callback_data="pagar_Agua")],
        [InlineKeyboardButton("💡 Marcar LUZ", callback_data="pagar_Luz")],
        [InlineKeyboardButton("🔥 Marcar GAS", callback_data="pagar_Gas")],
        [InlineKeyboardButton("🌐 Marcar INTERNET", callback_data="pagar_Internet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔔 CONTROL DE SERVICIOS 🔔\n\nTocá el botón cuando pagues una boleta:", reply_markup=reply_markup)

def consejo(update: Update, context: CallbackContext):
    hoja = get_hoja()
    datos = hoja.get_all_values()
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
                 f"💡 Consejo: Te sobró un buen margen. Pasá ${disponible*0.6:,.0f} a Mercado Pago "
                 f"o Personal Pay para ganar intereses diarios. Con lo que quede, evaluá comprar Dólar MEP.")
    elif disponible > 0:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Consejo: Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada hasta el próximo gasto grande.")
    else:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    update.message.reply_text(texto)

def boton_servicios(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    servicio = query.data.split("_")[1]
    query.edit_message_text(
        f"✅ Marcaste {servicio} como PAGADO.\n\n"
        f"👉 Anotá cuánto dolió copiando esto:\n/gasto 0000 {servicio}"
    )

def mensaje_desconocido(update: Update, context: CallbackContext):
    start(update, context)

# --- MAIN ---
def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    updater = Updater(token)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("sueldo", sueldo))
    dp.add_handler(CommandHandler("gasto", gasto))
    dp.add_handler(CommandHandler("balance", balance))
    dp.add_handler(CommandHandler("servicios", servicios))
    dp.add_handler(CommandHandler("consejo", consejo))
    dp.add_handler(CallbackQueryHandler(boton_servicios))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, mensaje_desconocido))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
