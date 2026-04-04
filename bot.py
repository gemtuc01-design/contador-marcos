import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from flask import Flask, request
from datetime import datetime, timedelta
import asyncio
import threading
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = "https://contador-marcos.onrender.com"
CHAT_ID = os.environ.get("CHAT_ID")

flask_app = Flask(__name__)

# --- ESTADOS DEL CONVERSATION HANDLER ---
ELIGIENDO_SERVICIO, CARGANDO_VENCIMIENTO, CARGANDO_MONTO, ELIGIENDO_MEDIO, CARGANDO_COMPROBANTE = range(5)

# --- GOOGLE SHEETS ---
def get_hoja(nombre="Movimientos"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Finanzas Marcos").worksheet(nombre)

SERVICIOS_LISTA = ["Luz", "Agua", "Gas", "Internet", "Tarjeta", "Alquiler", "Expensas", "Celular"]
MEDIOS_PAGO = ["Mercado Pago", "Naranja X", "Personal Pay", "Efectivo"]

# --- COMANDOS BÁSICOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola Marcos! Soy tu Contador Virtual 🧮\n\n"
        "Comandos disponibles:\n"
        "👉 /sueldo [monto]\n"
        "👉 /gasto [monto] [concepto]\n"
        "👉 /balance\n"
        "👉 /servicios - Ver y pagar boletas\n"
        "👉 /cargar_servicio - Cargar nueva boleta\n"
        "👉 /consejo\n"
        "👉 /corregir - Eliminar registro mal cargado"
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
                 f"💡 Pasá ${disponible*0.6:,.0f} a Mercado Pago o Personal Pay para ganar intereses diarios.")
    elif disponible > 0:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada.")
    else:
        texto = (f"👨‍💼 TU ASESOR FINANCIERO 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    await update.message.reply_text(texto)

# --- VER SERVICIOS ---
async def servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text(
            "📋 No tenés servicios cargados todavía.\n\nUsá /cargar_servicio para agregar uno."
        )
        return
    texto = "📋 <b>TUS SERVICIOS</b>\n\n"
    keyboard = []
    for i, fila in enumerate(datos[1:], start=2):
        try:
            servicio = fila[0]
            vencimiento = fila[1]
            monto = fila[2]
            medio = fila[3]
            estado = fila[4] if len(fila) > 4 else "Pendiente"
            emoji = "✅" if estado == "Pagado" else "⏳"
            texto += f"{emoji} <b>{servicio}</b> - Vence: {vencimiento} - ${monto} - {estado}\n"
            if estado != "Pagado":
                keyboard.append([InlineKeyboardButton(
                    f"💳 Pagar {servicio} (${monto})",
                    callback_data=f"pagar_servicio_{i}"
                )])
        except:
            pass
    keyboard.append([InlineKeyboardButton("➕ Cargar nuevo servicio", callback_data="nuevo_servicio")])
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# --- CARGAR NUEVO SERVICIO (CONVERSACIÓN) ---
async def cargar_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(s, callback_data=f"serv_{s}")] for s in SERVICIOS_LISTA]
    await update.message.reply_text(
        "📝 <b>CARGAR NUEVO SERVICIO</b>\n\n¿Qué servicio querés cargar?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ELIGIENDO_SERVICIO

async def elegir_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    servicio = query.data.replace("serv_", "")
    context.user_data["servicio"] = servicio
    await query.edit_message_text(
        f"✅ Servicio: <b>{servicio}</b>\n\n"
        f"📅 ¿Cuál es la fecha de vencimiento?\n"
        f"Escribila en formato <b>DD/MM/AAAA</b>\nEjemplo: 15/04/2026",
        parse_mode="HTML"
    )
    return CARGANDO_VENCIMIENTO

async def cargar_vencimiento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fecha = update.message.text.strip()
    try:
        datetime.strptime(fecha, "%d/%m/%Y")
        context.user_data["vencimiento"] = fecha
        await update.message.reply_text(
            f"✅ Vencimiento: <b>{fecha}</b>\n\n"
            f"💰 ¿Cuánto tenés que pagar? (solo el número)\nEjemplo: 25000",
            parse_mode="HTML"
        )
        return CARGANDO_MONTO
    except:
        await update.message.reply_text("❌ Formato incorrecto. Usá DD/MM/AAAA\nEjemplo: 15/04/2026")
        return CARGANDO_VENCIMIENTO

async def cargar_monto_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        monto = float(update.message.text.strip())
        context.user_data["monto"] = monto
        keyboard = [[InlineKeyboardButton(m, callback_data=f"medio_{m}")] for m in MEDIOS_PAGO]
        await update.message.reply_text(
            f"✅ Monto: <b>${monto:,.0f}</b>\n\n"
            f"💳 ¿Con qué medio vas a pagar?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ELIGIENDO_MEDIO
    except:
        await update.message.reply_text("❌ Escribí solo el número. Ejemplo: 25000")
        return CARGANDO_MONTO

async def elegir_medio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    medio = query.data.replace("medio_", "")
    context.user_data["medio"] = medio
    servicio = context.user_data["servicio"]
    vencimiento = context.user_data["vencimiento"]
    monto = context.user_data["monto"]
    hoja = get_hoja("Servicios")
    hoja.append_row([servicio, vencimiento, monto, medio, "Pendiente", "", ""])
    await query.edit_message_text(
        f"✅ <b>Servicio cargado correctamente</b>\n\n"
        f"📌 {servicio}\n"
        f"📅 Vence: {vencimiento}\n"
        f"💰 Monto: ${monto:,.0f}\n"
        f"💳 Medio: {medio}\n"
        f"📊 Estado: Pendiente\n\n"
        f"Cuando lo pagues usá /servicios para marcarlo como pagado y subir el comprobante.",
        parse_mode="HTML"
    )
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# --- BOTONES GENERALES ---
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Pagar servicio
    if query.data.startswith("pagar_servicio_"):
        fila_num = int(query.data.split("_")[2])
        context.user_data["fila_servicio"] = fila_num
        keyboard = [[InlineKeyboardButton(m, callback_data=f"confirmar_pago_{fila_num}_{m.replace(' ', '_')}")] for m in MEDIOS_PAGO]
        await query.edit_message_text(
            "💳 ¿Con qué medio pagaste?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Confirmar pago con medio
    elif query.data.startswith("confirmar_pago_"):
        partes = query.data.split("_")
        fila_num = int(partes[2])
        medio = "_".join(partes[3:]).replace("_", " ")
        context.user_data["fila_servicio"] = fila_num
        context.user_data["medio_pago"] = medio
        await query.edit_message_text(
            f"✅ Medio de pago: <b>{medio}</b>\n\n"
            f"📎 Ahora enviame el comprobante:\n"
            f"• Una <b>foto</b> del comprobante, o\n"
            f"• El <b>número de comprobante</b> en texto\n\n"
            f"O escribí /sin_comprobante si no tenés.",
            parse_mode="HTML"
        )

    elif query.data == "nuevo_servicio":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"serv_{s}")] for s in SERVICIOS_LISTA]
        await query.edit_message_text(
            "¿Qué servicio querés cargar?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- RECIBIR COMPROBANTE (FOTO O TEXTO) ---
async def recibir_comprobante_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "fila_servicio" not in context.user_data:
        return
    fila_num = context.user_data["fila_servicio"]
    medio = context.user_data.get("medio_pago", "")
    foto = update.message.photo[-1]
    file_id = foto.file_id
    hoja = get_hoja("Servicios")
    hoja.update_cell(fila_num, 5, "Pagado")
    hoja.update_cell(fila_num, 4, medio)
    hoja.update_cell(fila_num, 6, f"Foto:{file_id}")
    hoja.update_cell(fila_num, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
    datos = hoja.get_all_values()
    fila = datos[fila_num - 1]
    monto = fila[2] if len(fila) > 2 else "?"
    servicio = fila[0] if len(fila) > 0 else "?"
    get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, servicio])
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ <b>Pago registrado</b>\n\n"
        f"📌 Servicio: {servicio}\n"
        f"💳 Medio: {medio}\n"
        f"📎 Comprobante: foto guardada\n"
        f"💰 Gasto de ${monto} anotado en tu balance.",
        parse_mode="HTML"
    )

async def recibir_comprobante_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "fila_servicio" not in context.user_data:
        await mensaje_desconocido(update, context)
        return
    fila_num = context.user_data["fila_servicio"]
    medio = context.user_data.get("medio_pago", "")
    comprobante = update.message.text.strip()
    hoja = get_hoja("Servicios")
    hoja.update_cell(fila_num, 5, "Pagado")
    hoja.update_cell(fila_num, 4, medio)
    hoja.update_cell(fila_num, 6, comprobante)
    hoja.update_cell(fila_num, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
    datos = hoja.get_all_values()
    fila = datos[fila_num - 1]
    monto = fila[2] if len(fila) > 2 else "?"
    servicio = fila[0] if len(fila) > 0 else "?"
    get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, servicio])
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ <b>Pago registrado</b>\n\n"
        f"📌 Servicio: {servicio}\n"
        f"💳 Medio: {medio}\n"
        f"📎 Comprobante N°: {comprobante}\n"
        f"💰 Gasto de ${monto} anotado en tu balance.",
        parse_mode="HTML"
    )

async def sin_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "fila_servicio" not in context.user_data:
        return
    fila_num = context.user_data["fila_servicio"]
    medio = context.user_data.get("medio_pago", "")
    hoja = get_hoja("Servicios")
    hoja.update_cell(fila_num, 5, "Pagado")
    hoja.update_cell(fila_num, 4, medio)
    hoja.update_cell(fila_num, 6, "Sin comprobante")
    hoja.update_cell(fila_num, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
    datos = hoja.get_all_values()
    fila = datos[fila_num - 1]
    monto = fila[2] if len(fila) > 2 else "?"
    servicio = fila[0] if len(fila) > 0 else "?"
    get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, servicio])
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ <b>Pago registrado sin comprobante</b>\n\n"
        f"📌 Servicio: {servicio}\n"
        f"💳 Medio: {medio}\n"
        f"💰 Gasto de ${monto} anotado en tu balance.",
        parse_mode="HTML"
    )

# --- CORREGIR ---
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
                f"❌ Eliminar fila {idx}: {tipo} ${monto:,.0f} - {concepto}",
                callback_data=f"eliminar_{idx}"
            )])
        except:
            pass
    texto += "\n⚠️ <i>Al eliminar, cargá el valor correcto con /sueldo o /gasto</i>"
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# --- AVISOS AUTOMÁTICOS DE VENCIMIENTO ---
def chequear_vencimientos(app_telegram):
    while True:
        try:
            hoja = get_hoja("Servicios")
            datos = hoja.get_all_values()
            hoy = datetime.now()
            for fila in datos[1:]:
                try:
                    servicio = fila[0]
                    vencimiento_str = fila[1]
                    monto = fila[2]
                    estado = fila[4] if len(fila) > 4 else "Pendiente"
                    if estado == "Pagado":
                        continue
                    vencimiento = datetime.strptime(vencimiento_str, "%d/%m/%Y")
                    dias_restantes = (vencimiento - hoy).days
                    if dias_restantes in [3, 1, 0]:
                        if dias_restantes == 0:
                            msg = f"🚨 <b>¡HOY VENCE {servicio.upper()}!</b>\nMonto: ${monto}\n¡Pagalo hoy para evitar corte!"
                        elif dias_restantes == 1:
                            msg = f"⚠️ <b>MAÑANA VENCE {servicio.upper()}</b>\nMonto: ${monto}\nNo te olvides de pagarlo."
                        else:
                            msg = f"🔔 <b>{servicio} vence en 3 días</b>\nFecha: {vencimiento_str}\nMonto: ${monto}"
                        if CHAT_ID:
                            asyncio.run(app_telegram.bot.send_message(
                                chat_id=CHAT_ID,
                                text=msg,
                                parse_mode="HTML"
                            ))
                except:
                    pass
        except:
            pass
        time.sleep(43200)

async def mensaje_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def build_app():
    app = Application.builder().token(TOKEN).updater(None).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("cargar_servicio", cargar_servicio),
            CallbackQueryHandler(elegir_servicio, pattern="^serv_")
        ],
        states={
            ELIGIENDO_SERVICIO: [CallbackQueryHandler(elegir_servicio, pattern="^serv_")],
            CARGANDO_VENCIMIENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cargar_vencimiento)],
            CARGANDO_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cargar_monto_servicio)],
            ELIGIENDO_MEDIO: [CallbackQueryHandler(elegir_medio, pattern="^medio_")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sueldo", sueldo))
    app.add_handler(CommandHandler("gasto", gasto))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("servicios", servicios))
    app.add_handler(CommandHandler("consejo", consejo))
    app.add_handler(CommandHandler("corregir", corregir))
    app.add_handler(CommandHandler("sin_comprobante", sin_comprobante))
    app.add_handler(CallbackQueryHandler(manejar_botones))
    app.add_handler(MessageHandler(filters.PHOTO, recibir_comprobante_foto))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_comprobante_texto))
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
