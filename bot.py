import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request
from datetime import datetime
import asyncio
import threading
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = "https://contador-marcos.onrender.com"
CHAT_ID = os.environ.get("CHAT_ID")

flask_app = Flask(__name__)

def get_hoja(nombre="Movimientos"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Finanzas Marcos").worksheet(nombre)

SERVICIOS_LISTA = ["Luz", "Agua", "Gas", "Internet", "Tarjeta", "Alquiler", "Expensas", "Celular"]
MEDIOS_PAGO = ["Mercado Pago", "Naranja X", "Personal Pay", "Efectivo"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola Marcos! Soy tu Contador Virtual 🧮\n\n"
        "📌 <b>COMANDOS DISPONIBLES</b>\n\n"
        "💰 <b>Finanzas:</b>\n"
        "👉 /sueldo [monto]\n"
        "👉 /gasto [monto] [concepto]\n"
        "👉 /balance\n"
        "👉 /consejo\n"
        "👉 /corregir\n\n"
        "🔔 <b>Servicios:</b>\n"
        "👉 /servicios — ver estado de boletas\n"
        "👉 /nuevo_servicio [servicio] [DD/MM/AAAA] [monto]\n"
        "    Ejemplo: /nuevo_servicio Luz 15/04/2026 25000\n\n"
        "👉 /pagar [servicio] [medio] [comprobante]\n"
        "    Ejemplo: /pagar Luz MercadoPago 12345678",
        parse_mode="HTML"
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
        f"📊 <b>BALANCE ACTUAL</b> 📊\n\n"
        f"🟢 Ingresos: ${total_sueldo:,.0f}\n"
        f"🔴 Gastos: ${total_gastos:,.0f}\n\n"
        f"💰 <b>Disponible: ${disponible:,.0f}</b>",
        parse_mode="HTML"
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
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Pasá ${disponible*0.6:,.0f} a Mercado Pago o Personal Pay para ganar intereses diarios.")
    elif disponible > 0:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada.")
    else:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    await update.message.reply_text(texto, parse_mode="HTML")

async def nuevo_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Formato incorrecto.\n\n"
            "Usá: /nuevo_servicio [servicio] [DD/MM/AAAA] [monto]\n"
            "Ejemplo: /nuevo_servicio Luz 15/04/2026 25000\n\n"
            "Servicios disponibles:\n" + ", ".join(SERVICIOS_LISTA)
        )
        return
    servicio = context.args[0].capitalize()
    fecha_str = context.args[1]
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
    except:
        await update.message.reply_text("❌ Fecha incorrecta. Usá formato DD/MM/AAAA\nEjemplo: 15/04/2026")
        return
    try:
        monto = float(context.args[2])
    except:
        await update.message.reply_text("❌ Monto incorrecto. Usá solo números.\nEjemplo: 25000")
        return
    hoja = get_hoja("Servicios")
    hoja.append_row([servicio, fecha_str, monto, "", "Pendiente", "", ""])
    await update.message.reply_text(
        f"✅ <b>Servicio cargado</b>\n\n"
        f"📌 {servicio}\n"
        f"📅 Vence: {fecha_str}\n"
        f"💰 Monto: ${monto:,.0f}\n"
        f"📊 Estado: Pendiente\n\n"
        f"Cuando lo pagues usá:\n"
        f"<code>/pagar {servicio} MercadoPago 12345678</code>",
        parse_mode="HTML"
    )

async def servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text(
            "📋 No tenés servicios cargados todavía.\n\n"
            "Usá: /nuevo_servicio Luz 15/04/2026 25000"
        )
        return
    texto = "📋 <b>TUS SERVICIOS</b>\n\n"
    keyboard = []
    for i, fila in enumerate(datos[1:], start=2):
        try:
            servicio = fila[0]
            vencimiento = fila[1]
            monto = fila[2]
            estado = fila[4] if len(fila) > 4 else "Pendiente"
            medio = fila[3] if len(fila) > 3 else ""
            comprobante = fila[5] if len(fila) > 5 else ""
            fecha_pago = fila[6] if len(fila) > 6 else ""
            emoji = "✅" if estado == "Pagado" else "⏳"
            texto += f"{emoji} <b>{servicio}</b>\n"
            texto += f"   📅 Vence: {vencimiento} | 💰 ${monto}\n"
            if estado == "Pagado":
                texto += f"   💳 Pagado con {medio} el {fecha_pago}\n"
                if comprobante:
                    texto += f"   📎 Comprobante: {comprobante}\n"
            texto += "\n"
            if estado != "Pagado":
                keyboard.append([InlineKeyboardButton(
                    f"💳 Pagar {servicio} (${monto})",
                    callback_data=f"iniciar_pago_{i}_{servicio}_{monto}"
                )])
        except:
            pass
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def pagar_servicio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Formato incorrecto.\n\n"
            "Usá: /pagar [servicio] [medio] [comprobante]\n"
            "Ejemplo: /pagar Luz MercadoPago 12345678\n\n"
            "Medios: " + ", ".join(MEDIOS_PAGO)
        )
        return
    servicio = context.args[0].capitalize()
    medio = context.args[1]
    comprobante = " ".join(context.args[2:]) if len(context.args) > 2 else "Sin comprobante"
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    encontrado = False
    for i, fila in enumerate(datos[1:], start=2):
        if fila[0].lower() == servicio.lower() and (len(fila) <= 4 or fila[4] != "Pagado"):
            hoja.update_cell(i, 4, medio)
            hoja.update_cell(i, 5, "Pagado")
            hoja.update_cell(i, 6, comprobante)
            hoja.update_cell(i, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
            monto = fila[2]
            get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", float(monto), servicio])
            encontrado = True
            await update.message.reply_text(
                f"✅ <b>Pago registrado</b>\n\n"
                f"📌 Servicio: {servicio}\n"
                f"💳 Medio: {medio}\n"
                f"📎 Comprobante: {comprobante}\n"
                f"💰 Gasto de ${float(monto):,.0f} anotado en tu balance.",
                parse_mode="HTML"
            )
            break
    if not encontrado:
        await update.message.reply_text(
            f"❌ No encontré el servicio <b>{servicio}</b> pendiente de pago.\n"
            f"Verificá con /servicios qué tenés cargado.",
            parse_mode="HTML"
        )

async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("iniciar_pago_"):
        partes = query.data.split("_")
        fila_num = partes[2]
        servicio = partes[3]
        monto = partes[4]
        keyboard = [[InlineKeyboardButton(m, callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_{m.replace(' ', '-')}")] for m in MEDIOS_PAGO]
        await query.edit_message_text(
            f"💳 Pagando <b>{servicio}</b> (${monto})\n\n¿Con qué medio pagaste?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data.startswith("confirmar_"):
        partes = query.data.split("_")
        fila_num = int(partes[1])
        servicio = partes[2]
        monto = partes[3]
        medio = partes[4].replace("-", " ")
        hoja = get_hoja("Servicios")
        hoja.update_cell(fila_num, 4, medio)
        hoja.update_cell(fila_num, 5, "Pagado")
        hoja.update_cell(fila_num, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
        get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", float(monto), servicio])
        await query.edit_message_text(
            f"✅ <b>{servicio} marcado como PAGADO</b>\n\n"
            f"💳 Medio: {medio}\n"
            f"💰 Gasto de ${float(monto):,.0f} anotado.\n\n"
            f"📎 Si tenés comprobante mandalo con:\n"
            f"<code>/pagar {servicio} {medio} NUMERO_COMPROBANTE</code>",
            parse_mode="HTML"
        )

async def corregir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja()
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text("❌ No hay registros cargados todavía.")
        return
    ultimos = list(enumerate(datos[1:], start=2))[-8:]
    keyboard = []
    texto = "🗂 <b>ÚLTIMOS REGISTROS</b>\nElegí cuál querés eliminar:\n\n"
    for idx, fila in ultimos:
        try:
            fecha = fila[0]
            tipo = fila[1]
            monto = float(fila[2])
            concepto = fila[3]
            emoji = "🟢" if tipo == "Sueldo" else "🔴"
            texto += f"{emoji} Fila {idx}: {tipo} ${monto:,.0f} - {concepto} ({fecha})\n"
            keyboard.append([InlineKeyboardButton(
                f"❌ Eliminar: {tipo} ${monto:,.0f} - {concepto}",
                callback_data=f"eliminar_{idx}"
            )])
        except:
            pass
    texto += "\n⚠️ <i>Al eliminar, cargá el valor correcto con /sueldo o /gasto</i>"
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def manejar_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("eliminar_"):
        fila_num = int(query.data.split("_")[1])
        hoja = get_hoja()
        datos = hoja.get_all_values()
        if fila_num <= len(datos):
            fila = datos[fila_num - 1]
            hoja.delete_rows(fila_num)
            await query.edit_message_text(
                f"✅ Registro eliminado:\n"
                f"{fila[1]} | ${fila[2]} | {fila[3]}\n\n"
                f"👉 Cargá el valor correcto con /sueldo o /gasto"
            )

async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 Foto recibida.\n\n"
        "Para asociarla a un servicio usá:\n"
        "<code>/pagar [servicio] [medio] [descripcion]</code>\n"
        "Ejemplo: /pagar Luz MercadoPago comprobante-foto",
        parse_mode="HTML"
    )

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def build_app():
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sueldo", sueldo))
    app.add_handler(CommandHandler("gasto", gasto))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("servicios", servicios))
    app.add_handler(CommandHandler("nuevo_servicio", nuevo_servicio))
    app.add_handler(CommandHandler("pagar", pagar_servicio_cmd))
    app.add_handler(CommandHandler("consejo", consejo))
    app.add_handler(CommandHandler("corregir", corregir))
    app.add_handler(CallbackQueryHandler(manejar_eliminar, pattern="^eliminar_"))
    app.add_handler(CallbackQueryHandler(manejar_botones))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje_desconocido))
    return app

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    app = build_app()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def process():
        async with app:
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
    loop.run_until_complete(process())
    loop.close()
    return "OK", 200

@flask_app.route("/", methods=["GET"])
def index():
    return "Bot activo ✅", 200

if __name__ == "__main__":
    async def set_webhook():
        app = build_app()
        async with app:
            await app.bot.set_webhook(
                url=f"{WEBHOOK_URL}/{TOKEN}",
                drop_pending_updates=True
            )
        print("Webhook configurado!")
    asyncio.run(set_webhook())
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
