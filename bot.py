import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# Estado conversacional en memoria
estado_usuario = {}

def get_hoja(nombre="Movimientos"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Finanzas Marcos").worksheet(nombre)

MEDIOS_PAGO = ["Mercado Pago", "Naranja X", "Personal Pay", "Efectivo"]
TIPOS_AUTO = ["Nafta", "GNC", "Aceite", "VTV", "Oblea Gas", "Seguro", "Patente", "Parche/Rueda", "Repuesto", "Service", "Peaje/Estacionamiento", "Otro"]
CATEGORIAS_COMIDA = ["Supermercado", "Panadería", "Almacén", "Pollería", "Carnicería", "Verdulería", "Kiosco", "Delivery", "Restaurante", "Cafetería", "Mercado Libre"]
SERVICIOS_LISTA = ["Luz", "Agua", "Gas", "Internet", "Tarjeta", "Alquiler", "Expensas", "Celular"]
PLATAFORMAS = ["YouTube", "Spotify", "Google One", "HBO Max", "Netflix", "Disney+", "Prime Video", "Flow"]
LIMITE_COMIDA = 150000

def teclado_fijo():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📋 Menú")]],
        resize_keyboard=True,
        persistent=True
    )

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("💰 Finanzas", callback_data="menu_finanzas"),
         InlineKeyboardButton("🔔 Servicios", callback_data="menu_servicios")],
        [InlineKeyboardButton("🚗 Auto", callback_data="menu_auto"),
         InlineKeyboardButton("🛒 Comida", callback_data="menu_comida")],
        [InlineKeyboardButton("📺 Streaming", callback_data="menu_streaming"),
         InlineKeyboardButton("📊 Balance", callback_data="accion_balance")],
        [InlineKeyboardButton("🧠 Consejo", callback_data="accion_consejo"),
         InlineKeyboardButton("🗂 Corregir", callback_data="accion_corregir")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_finanzas():
    keyboard = [
        [InlineKeyboardButton("💵 Cargar Sueldo", callback_data="accion_sueldo")],
        [InlineKeyboardButton("💸 Cargar Gasto", callback_data="accion_gasto")],
        [InlineKeyboardButton("📊 Ver Balance", callback_data="accion_balance")],
        [InlineKeyboardButton("🧠 Consejo", callback_data="accion_consejo")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_servicios():
    keyboard = [
        [InlineKeyboardButton("📋 Ver Servicios", callback_data="accion_ver_servicios")],
        [InlineKeyboardButton("➕ Nuevo Servicio", callback_data="accion_nuevo_servicio")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_auto():
    keyboard = [
        [InlineKeyboardButton("🚗 Ver Resumen", callback_data="accion_ver_auto")],
        [InlineKeyboardButton("⛽ Nafta", callback_data="auto_tipo_Nafta"),
         InlineKeyboardButton("🔵 GNC", callback_data="auto_tipo_GNC")],
        [InlineKeyboardButton("🔧 Aceite", callback_data="auto_tipo_Aceite"),
         InlineKeyboardButton("📋 VTV", callback_data="auto_tipo_VTV")],
        [InlineKeyboardButton("🔥 Oblea Gas", callback_data="auto_tipo_ObleaGas"),
         InlineKeyboardButton("🛡 Seguro", callback_data="auto_tipo_Seguro")],
        [InlineKeyboardButton("📄 Patente", callback_data="auto_tipo_Patente"),
         InlineKeyboardButton("🔩 Repuesto", callback_data="auto_tipo_Repuesto")],
        [InlineKeyboardButton("🔨 Service", callback_data="auto_tipo_Service"),
         InlineKeyboardButton("🅿️ Peaje", callback_data="auto_tipo_Peaje")],
        [InlineKeyboardButton("📅 Cargar Vencimiento", callback_data="accion_vencimiento_auto")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_comida():
    keyboard = [
        [InlineKeyboardButton("📊 Ver Gastos", callback_data="accion_ver_comida")],
        [InlineKeyboardButton("🏪 Supermercado", callback_data="comida_cat_Supermercado"),
         InlineKeyboardButton("🥖 Panadería", callback_data="comida_cat_Panadería")],
        [InlineKeyboardButton("🏬 Almacén", callback_data="comida_cat_Almacén"),
         InlineKeyboardButton("🍗 Pollería", callback_data="comida_cat_Pollería")],
        [InlineKeyboardButton("🥩 Carnicería", callback_data="comida_cat_Carnicería"),
         InlineKeyboardButton("🥦 Verdulería", callback_data="comida_cat_Verdulería")],
        [InlineKeyboardButton("🍬 Kiosco", callback_data="comida_cat_Kiosco"),
         InlineKeyboardButton("🛵 Delivery", callback_data="comida_cat_Delivery")],
        [InlineKeyboardButton("🍽 Restaurante", callback_data="comida_cat_Restaurante"),
         InlineKeyboardButton("☕ Cafetería", callback_data="comida_cat_Cafetería")],
        [InlineKeyboardButton("📦 Mercado Libre", callback_data="comida_cat_MercadoLibre")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_streaming():
    keyboard = [
        [InlineKeyboardButton("📺 Ver Suscripciones", callback_data="accion_ver_streaming")],
        [InlineKeyboardButton("➕ Nueva Suscripción", callback_data="accion_nueva_suscripcion")],
        [InlineKeyboardButton("💵 Actualizar Dólar", callback_data="accion_dolar")],
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_medios(prefijo):
    keyboard = [
        [InlineKeyboardButton("📱 Mercado Pago", callback_data=f"{prefijo}_MercadoPago"),
         InlineKeyboardButton("🟠 Naranja X", callback_data=f"{prefijo}_NaranjaX")],
        [InlineKeyboardButton("💙 Personal Pay", callback_data=f"{prefijo}_PersonalPay"),
         InlineKeyboardButton("💵 Efectivo", callback_data=f"{prefijo}_Efectivo")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_plataformas():
    keyboard = [
        [InlineKeyboardButton("▶️ YouTube", callback_data="stream_plat_YouTube"),
         InlineKeyboardButton("🎵 Spotify", callback_data="stream_plat_Spotify")],
        [InlineKeyboardButton("☁️ Google One", callback_data="stream_plat_GoogleOne"),
         InlineKeyboardButton("🎬 HBO Max", callback_data="stream_plat_HBOMax")],
        [InlineKeyboardButton("🎥 Netflix", callback_data="stream_plat_Netflix"),
         InlineKeyboardButton("✨ Disney+", callback_data="stream_plat_Disney+")],
        [InlineKeyboardButton("📦 Prime Video", callback_data="stream_plat_PrimeVideo"),
         InlineKeyboardButton("📡 Flow", callback_data="stream_plat_Flow")],
        [InlineKeyboardButton("🔙 Volver", callback_data="menu_streaming")]
    ]
    return InlineKeyboardMarkup(keyboard)

def obtener_tipo_cambio():
    try:
        for fila in get_hoja("Streaming").get_all_values()[1:]:
            if fila[0] == "DOLAR" and len(fila) > 3 and fila[3]:
                return float(fila[3])
        return 1200
    except:
        return 1200

# =====================
# START Y MENÚ
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    estado_usuario.pop(chat_id, None)
    await update.message.reply_text(
        "¡Hola Marcos! Soy tu Contador Virtual 🧮\n\nElegí una opción:",
        reply_markup=teclado_fijo()
    )
    await update.message.reply_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())

async def mostrar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    estado_usuario.pop(chat_id, None)
    await update.message.reply_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())

# =====================
# BALANCE Y CONSEJO
# =====================
async def mostrar_balance(chat_id, bot):
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
    mes_actual = datetime.now().strftime("%m/%Y")
    total_comida_mes = 0
    try:
        for fila in get_hoja("Comida").get_all_values()[1:]:
            if fila[0][3:10] == mes_actual:
                total_comida_mes += float(fila[2])
    except:
        pass
    total_auto_mes = 0
    try:
        for fila in get_hoja("Auto").get_all_values()[1:]:
            if fila[0][3:10] == mes_actual:
                total_auto_mes += float(fila[2])
    except:
        pass
    tc = obtener_tipo_cambio()
    total_streaming_mes = 0
    try:
        for fila in get_hoja("Streaming").get_all_values()[1:]:
            if fila[0] != "DOLAR" and (len(fila) <= 6 or fila[6] != "Cancelado"):
                precio_usd = float(fila[1]) if fila[1] else 0
                periodicidad = fila[4] if len(fila) > 4 else "mensual"
                total_streaming_mes += (precio_usd * tc / 12) if periodicidad == "anual" else (precio_usd * tc)
    except:
        pass
    texto = (
        f"📊 <b>BALANCE ACTUAL</b> 📊\n\n"
        f"🟢 Ingresos: ${total_sueldo:,.0f}\n"
        f"🔴 Gastos generales: ${total_gastos:,.0f}\n\n"
        f"🛒 Comida este mes: ${total_comida_mes:,.0f}\n"
        f"🚗 Auto este mes: ${total_auto_mes:,.0f}\n"
        f"📺 Streaming este mes: ${total_streaming_mes:,.0f}\n\n"
        f"💰 <b>Disponible: ${disponible:,.0f}</b>"
    )
    if total_comida_mes >= LIMITE_COMIDA:
        texto += f"\n\n⚠️ <b>¡Superaste el límite de comida!</b>"
    keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]]
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def mostrar_consejo(chat_id, bot):
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
    mes_actual = datetime.now().strftime("%m/%Y")
    cat_gastos = {}
    total_comida_mes = 0
    try:
        for fila in get_hoja("Comida").get_all_values()[1:]:
            if fila[0][3:10] == mes_actual:
                monto = float(fila[2])
                total_comida_mes += monto
                cat_gastos[fila[1]] = cat_gastos.get(fila[1], 0) + monto
    except:
        pass
    if disponible > 150000:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b>\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Pasá ${disponible*0.6:,.0f} a Mercado Pago o Personal Pay para ganar intereses diarios.")
    elif disponible > 0:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b>\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada.")
    else:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b>\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    if cat_gastos:
        top = sorted(cat_gastos.items(), key=lambda x: x[1], reverse=True)[:3]
        texto += f"\n\n🛒 <b>Top 3 gastos de comida:</b>\n"
        for cat, monto in top:
            texto += f"• {cat}: ${monto:,.0f}\n"
    keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]]
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# CORREGIR
# =====================
async def mostrar_corregir(chat_id, bot):
    hoja = get_hoja()
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await bot.send_message(chat_id=chat_id, text="❌ No hay registros todavía.")
        return
    ultimos = list(enumerate(datos[1:], start=2))[-8:]
    keyboard = []
    texto = "🗂 <b>ÚLTIMOS REGISTROS</b>\nElegí cuál querés eliminar:\n\n"
    for idx, fila in ultimos:
        try:
            emoji = "🟢" if fila[1] == "Sueldo" else "🔴"
            monto = float(fila[2])
            texto += f"{emoji} {fila[1]} ${monto:,.0f} - {fila[3]} ({fila[0][:10]})\n"
            keyboard.append([InlineKeyboardButton(
                f"❌ {fila[1]} ${monto:,.0f} - {fila[3]}",
                callback_data=f"eliminar_{idx}"
            )])
        except:
            pass
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# VER SERVICIOS
# =====================
async def mostrar_servicios(chat_id, bot):
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        keyboard = [
            [InlineKeyboardButton("➕ Agregar Servicio", callback_data="accion_nuevo_servicio")],
            [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]
        ]
        await bot.send_message(chat_id=chat_id, text="📋 Sin servicios cargados.", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    texto = "📋 <b>TUS SERVICIOS</b>\n\n"
    keyboard = []
    for i, fila in enumerate(datos[1:], start=2):
        try:
            estado = fila[4] if len(fila) > 4 else "Pendiente"
            emoji = "✅" if estado == "Pagado" else "⏳"
            texto += f"{emoji} <b>{fila[0]}</b> — {fila[1]} | ${fila[2]}\n"
            if estado == "Pagado" and len(fila) > 6:
                texto += f"   💳 {fila[3]} el {fila[6]}\n"
            texto += "\n"
            if estado != "Pagado":
                keyboard.append([InlineKeyboardButton(
                    f"💳 Pagar {fila[0]} (${fila[2]})",
                    callback_data=f"iniciar_pago_{i}_{fila[0]}_{fila[2]}"
                )])
        except:
            pass
    keyboard.append([InlineKeyboardButton("➕ Nuevo Servicio", callback_data="accion_nuevo_servicio")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")])
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# VER AUTO
# =====================
async def mostrar_auto(chat_id, bot):
    datos = get_hoja("Auto").get_all_values()
    datos_mov = get_hoja().get_all_values()
    mes_actual = datetime.now().strftime("%m/%Y")
    total_auto_mes = 0
    total_sueldo = 0
    for fila in datos_mov[1:]:
        try:
            valor = float(fila[2])
            if fila[1] == "Sueldo":
                total_sueldo += valor
            if fila[1] == "Gasto" and fila[3] in TIPOS_AUTO and fila[0][3:10] == mes_actual:
                total_auto_mes += valor
        except:
            pass
    porcentaje = (total_auto_mes / total_sueldo * 100) if total_sueldo > 0 else 0
    texto = "🚗 <b>RESUMEN DEL AUTO</b>\n\n"
    texto += f"💸 Este mes: ${total_auto_mes:,.0f}"
    if total_sueldo > 0:
        texto += f" ({porcentaje:.1f}% del sueldo)"
    if porcentaje > 30:
        texto += " ⚠️"
    texto += "\n\n📅 <b>VENCIMIENTOS</b>\n"
    vencimientos = {}
    for fila in datos[1:]:
        try:
            prox = fila[5] if len(fila) > 5 else ""
            if prox and not prox.startswith("Próximo") and fila[1] not in vencimientos:
                vencimientos[fila[1]] = prox
        except:
            pass
    for tipo in ["VTV", "Oblea Gas", "Seguro", "Patente", "Aceite"]:
        if tipo in vencimientos:
            try:
                fecha = datetime.strptime(vencimientos[tipo], "%d/%m/%Y")
                dias = (fecha - datetime.now()).days
                emoji = "🔴" if dias < 0 else "🚨" if dias <= 7 else "⚠️" if dias <= 30 else "✅"
                estado = "¡VENCIDO!" if dias < 0 else f"vence en {dias} días" if dias <= 30 else f"vence el {vencimientos[tipo]}"
                texto += f"{emoji} <b>{tipo}:</b> {estado}\n"
            except:
                texto += f"📌 <b>{tipo}:</b> {vencimientos[tipo]}\n"
        else:
            texto += f"❓ <b>{tipo}:</b> sin fecha\n"
    texto += "\n📋 <b>ÚLTIMOS GASTOS</b>\n"
    for fila in (datos[1:][-5:] if len(datos) > 1 else []):
        try:
            texto += f"• {fila[1]}: ${float(fila[2]):,.0f} ({fila[0][:10]})\n"
        except:
            pass
    keyboard = [[InlineKeyboardButton("🔙 Volver al Auto", callback_data="menu_auto")]]
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# VER COMIDA
# =====================
async def mostrar_comida(chat_id, bot):
    datos = get_hoja("Comida").get_all_values()
    if len(datos) <= 1:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_comida")]]
        await bot.send_message(chat_id=chat_id, text="🛒 Sin gastos de comida registrados.", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    mes_actual = datetime.now().strftime("%m/%Y")
    cat_gastos = {}
    total_mes = 0
    ultimos = []
    for fila in datos[1:]:
        try:
            if fila[0][3:10] == mes_actual:
                monto = float(fila[2])
                total_mes += monto
                cat_gastos[fila[1]] = cat_gastos.get(fila[1], 0) + monto
            ultimos.append(fila)
        except:
            pass
    texto = f"🛒 <b>GASTOS DE COMIDA</b> — {mes_actual}\n\n"
    texto += f"💰 <b>Total: ${total_mes:,.0f}</b> / límite ${LIMITE_COMIDA:,.0f}\n\n"
    texto += "<b>Por categoría:</b>\n"
    for cat, monto in sorted(cat_gastos.items(), key=lambda x: x[1], reverse=True):
        barra = "█" * int(monto / LIMITE_COMIDA * 10)
        texto += f"• {cat}: ${monto:,.0f} {barra}\n"
    texto += "\n<b>Últimos 5:</b>\n"
    for fila in ultimos[-5:]:
        try:
            texto += f"• {fila[1]}: ${float(fila[2]):,.0f} ({fila[0][:10]})\n"
        except:
            pass
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_comida")]]
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# VER STREAMING
# =====================
async def mostrar_streaming(chat_id, bot):
    hoja = get_hoja("Streaming")
    datos = hoja.get_all_values()
    tc = obtener_tipo_cambio()
    suscripciones = [f for f in datos[1:] if f[0] != "DOLAR" and len(f) > 5 and (len(f) <= 6 or f[6] != "Cancelado")]
    if not suscripciones:
        keyboard = [
            [InlineKeyboardButton("➕ Nueva Suscripción", callback_data="accion_nueva_suscripcion")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu_streaming")]
        ]
        await bot.send_message(chat_id=chat_id, text="📺 Sin suscripciones cargadas.", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    texto = f"📺 <b>TUS SUSCRIPCIONES</b>\n💵 Dólar: ${tc:,.0f}\n\n"
    total_mensual_usd = 0
    total_mensual_ars = 0
    hoy = datetime.now()
    keyboard = []
    for i, fila in enumerate(datos[1:], start=2):
        if fila[0] == "DOLAR" or (len(fila) > 6 and fila[6] == "Cancelado"):
            continue
        try:
            plataforma = fila[0]
            precio_usd = float(fila[1])
            periodicidad = fila[4] if len(fila) > 4 else "mensual"
            prox_pago = fila[5] if len(fila) > 5 else ""
            precio_ars_actual = precio_usd * tc
            emoji = "✅"
            aviso = ""
            if prox_pago:
                try:
                    dias = (datetime.strptime(prox_pago, "%d/%m/%Y") - hoy).days
                    if dias < 0:
                        emoji = "🔴"
                        aviso = " ¡VENCIDO!"
                    elif dias <= 1:
                        emoji = "🚨"
                        aviso = " ¡mañana!"
                    elif dias <= 7:
                        emoji = "⚠️"
                        aviso = f" {dias}d"
                except:
                    pass
            if periodicidad == "anual":
                mensual_usd = precio_usd / 12
                mensual_ars = precio_ars_actual / 12
                texto += f"{emoji} <b>{plataforma}</b>{aviso} — USD{precio_usd:.2f}/año ≈ ${mensual_ars:,.0f}/mes\n📅 {prox_pago}\n\n"
                total_mensual_usd += mensual_usd
                total_mensual_ars += mensual_ars
            else:
                texto += f"{emoji} <b>{plataforma}</b>{aviso} — USD{precio_usd:.2f} = ${precio_ars_actual:,.0f}/mes\n📅 {prox_pago}\n\n"
                total_mensual_usd += precio_usd
                total_mensual_ars += precio_ars_actual
            keyboard.append([InlineKeyboardButton(f"❌ Cancelar {plataforma}", callback_data=f"cancelar_stream_{i}_{plataforma}")])
        except:
            pass
    texto += f"📊 <b>TOTAL MENSUAL: USD{total_mensual_usd:.2f} = ${total_mensual_ars:,.0f}</b>"
    keyboard.append([InlineKeyboardButton("➕ Nueva Suscripción", callback_data="accion_nueva_suscripcion")])
    keyboard.append([InlineKeyboardButton("💵 Actualizar Dólar", callback_data="accion_dolar")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_streaming")])
    await bot.send_message(chat_id=chat_id, text=texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# MANEJADOR DE BOTONES
# =====================
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    bot = context.bot
    data = query.data

    # NAVEGACIÓN
    if data == "volver_menu":
        estado_usuario.pop(chat_id, None)
        await query.edit_message_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())
    elif data == "menu_finanzas":
        await query.edit_message_text("💰 <b>FINANZAS</b>", parse_mode="HTML", reply_markup=menu_finanzas())
    elif data == "menu_servicios":
        await query.edit_message_text("🔔 <b>SERVICIOS</b>", parse_mode="HTML", reply_markup=menu_servicios())
    elif data == "menu_auto":
        await query.edit_message_text("🚗 <b>AUTO</b>\n\nElegí el tipo de gasto o acción:", parse_mode="HTML", reply_markup=menu_auto())
    elif data == "menu_comida":
        await query.edit_message_text("🛒 <b>COMIDA</b>\n\nElegí la categoría:", parse_mode="HTML", reply_markup=menu_comida())
    elif data == "menu_streaming":
        await query.edit_message_text("📺 <b>STREAMING</b>", parse_mode="HTML", reply_markup=menu_streaming())

    # ACCIONES DIRECTAS
    elif data == "accion_balance":
        await query.delete_message()
        await mostrar_balance(chat_id, bot)
    elif data == "accion_consejo":
        await query.delete_message()
        await mostrar_consejo(chat_id, bot)
    elif data == "accion_corregir":
        await query.delete_message()
        await mostrar_corregir(chat_id, bot)
    elif data == "accion_ver_servicios":
        await query.delete_message()
        await mostrar_servicios(chat_id, bot)
    elif data == "accion_ver_auto":
        await query.delete_message()
        await mostrar_auto(chat_id, bot)
    elif data == "accion_ver_comida":
        await query.delete_message()
        await mostrar_comida(chat_id, bot)
    elif data == "accion_ver_streaming":
        await query.delete_message()
        await mostrar_streaming(chat_id, bot)

    # INICIAR CONVERSACIÓN SUELDO
    elif data == "accion_sueldo":
        estado_usuario[chat_id] = {"paso": "esperando_sueldo"}
        await query.edit_message_text("💵 <b>CARGAR SUELDO</b>\n\nEscribí el monto:", parse_mode="HTML")

    # INICIAR CONVERSACIÓN GASTO
    elif data == "accion_gasto":
        estado_usuario[chat_id] = {"paso": "esperando_gasto_monto"}
        await query.edit_message_text("💸 <b>CARGAR GASTO</b>\n\nEscribí el monto y concepto separados por espacio:\nEjemplo: <code>1500 café</code>", parse_mode="HTML")

    # COMIDA - elegir categoría
    elif data.startswith("comida_cat_"):
        categoria = data.replace("comida_cat_", "").replace("MercadoLibre", "Mercado Libre")
        estado_usuario[chat_id] = {"paso": "esperando_comida_monto", "categoria": categoria}
        await query.edit_message_text(
            f"🛒 <b>{categoria}</b>\n\nEscribí el monto (y opcionalmente el detalle):\nEjemplo: <code>15000 compras semana</code>",
            parse_mode="HTML"
        )

    # AUTO - elegir tipo
    elif data.startswith("auto_tipo_"):
        tipo = data.replace("auto_tipo_", "").replace("ObleaGas", "Oblea Gas")
        estado_usuario[chat_id] = {"paso": "esperando_auto_monto", "tipo": tipo}
        await query.edit_message_text(
            f"🚗 <b>{tipo}</b>\n\nEscribí el monto (y opcionalmente el detalle):\nEjemplo: <code>15000 cargué full</code>",
            parse_mode="HTML"
        )

    # AUTO - vencimiento
    elif data == "accion_vencimiento_auto":
        keyboard = [
            [InlineKeyboardButton("📋 VTV", callback_data="venc_auto_VTV"),
             InlineKeyboardButton("🔥 Oblea Gas", callback_data="venc_auto_ObleaGas")],
            [InlineKeyboardButton("🛡 Seguro", callback_data="venc_auto_Seguro"),
             InlineKeyboardButton("📄 Patente", callback_data="venc_auto_Patente")],
            [InlineKeyboardButton("🔧 Aceite", callback_data="venc_auto_Aceite")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu_auto")]
        ]
        await query.edit_message_text("📅 ¿Para qué querés cargar el vencimiento?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("venc_auto_"):
        tipo = data.replace("venc_auto_", "").replace("ObleaGas", "Oblea Gas")
        estado_usuario[chat_id] = {"paso": "esperando_vencimiento_auto", "tipo": tipo}
        await query.edit_message_text(
            f"📅 <b>Vencimiento: {tipo}</b>\n\nEscribí la fecha en formato DD/MM/AAAA:\nEjemplo: <code>30/06/2026</code>",
            parse_mode="HTML"
        )

    # SERVICIOS - nuevo
    elif data == "accion_nuevo_servicio":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"serv_tipo_{s}")] for s in SERVICIOS_LISTA]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_servicios")])
        await query.edit_message_text("🔔 ¿Qué servicio querés cargar?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("serv_tipo_"):
        servicio = data.replace("serv_tipo_", "")
        estado_usuario[chat_id] = {"paso": "esperando_servicio_fecha", "servicio": servicio}
        await query.edit_message_text(
            f"🔔 <b>{servicio}</b>\n\nEscribí la fecha de vencimiento (DD/MM/AAAA):\nEjemplo: <code>15/04/2026</code>",
            parse_mode="HTML"
        )

    # SERVICIOS - pagar
    elif data.startswith("iniciar_pago_"):
        partes = data.split("_")
        fila_num = partes[2]
        servicio = partes[3]
        monto = partes[4]
        keyboard = [
            [InlineKeyboardButton("📱 Mercado Pago", callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_MercadoPago")],
            [InlineKeyboardButton("🟠 Naranja X", callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_NaranjaX")],
            [InlineKeyboardButton("💙 Personal Pay", callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_PersonalPay")],
            [InlineKeyboardButton("💵 Efectivo", callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_Efectivo")]
        ]
        await query.edit_message_text(
            f"💳 Pagando <b>{servicio}</b> (${monto})\n\n¿Con qué medio?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("confirmar_"):
        partes = data.split("_")
        fila_num = int(partes[1])
        servicio = partes[2]
        monto = partes[3]
        medio = partes[4].replace("MercadoPago", "Mercado Pago").replace("NaranjaX", "Naranja X").replace("PersonalPay", "Personal Pay")
        hoja = get_hoja("Servicios")
        hoja.update_cell(fila_num, 4, medio)
        hoja.update_cell(fila_num, 5, "Pagado")
        hoja.update_cell(fila_num, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
        get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", float(monto), servicio])
        keyboard = [[InlineKeyboardButton("🔙 Ver Servicios", callback_data="accion_ver_servicios")]]
        await query.edit_message_text(
            f"✅ <b>{servicio} PAGADO</b>\n💳 {medio} | 💰 ${float(monto):,.0f}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # STREAMING - nueva suscripción
    elif data == "accion_nueva_suscripcion":
        await query.edit_message_text("📺 ¿Qué plataforma querés agregar?", reply_markup=menu_plataformas())

    elif data.startswith("stream_plat_"):
        plataforma = data.replace("stream_plat_", "").replace("GoogleOne", "Google One").replace("HBOMax", "HBO Max").replace("PrimeVideo", "Prime Video")
        estado_usuario[chat_id] = {"paso": "esperando_stream_precio", "plataforma": plataforma}
        await query.edit_message_text(
            f"📺 <b>{plataforma}</b>\n\nEscribí el precio en dólares:\nEjemplo: <code>6.99</code>",
            parse_mode="HTML"
        )

    # STREAMING - actualizar dólar
    elif data == "accion_dolar":
        estado_usuario[chat_id] = {"paso": "esperando_dolar"}
        tc_actual = obtener_tipo_cambio()
        await query.edit_message_text(
            f"💵 Tipo de cambio actual: <b>${tc_actual:,.0f}</b>\n\nEscribí el nuevo valor:",
            parse_mode="HTML"
        )

    # CANCELAR STREAMING
    elif data.startswith("cancelar_stream_"):
        partes = data.split("_")
        fila_num = int(partes[2])
        plataforma = partes[3]
        get_hoja("Streaming").update_cell(fila_num, 7, "Cancelado")
        keyboard = [[InlineKeyboardButton("🔙 Ver Streaming", callback_data="accion_ver_streaming")]]
        await query.edit_message_text(f"✅ {plataforma} cancelada.", reply_markup=InlineKeyboardMarkup(keyboard))

    # ELIMINAR REGISTRO
    elif data.startswith("eliminar_"):
        fila_num = int(data.split("_")[1])
        hoja = get_hoja()
        datos = hoja.get_all_values()
        if fila_num <= len(datos):
            fila = datos[fila_num - 1]
            hoja.delete_rows(fila_num)
            keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]]
            await query.edit_message_text(
                f"✅ Eliminado: {fila[1]} | ${fila[2]} | {fila[3]}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # MEDIO DE PAGO AUTO
    elif data.startswith("auto_medio_"):
        partes = data.split("_")
        medio = partes[2].replace("MercadoPago", "Mercado Pago").replace("NaranjaX", "Naranja X").replace("PersonalPay", "Personal Pay")
        if chat_id in estado_usuario:
            estado_usuario[chat_id]["medio"] = medio
            estado_usuario[chat_id]["paso"] = "esperando_auto_detalle"
            await query.edit_message_text(
                f"✅ Medio: <b>{medio}</b>\n\nEscribí el detalle (o mandá <code>-</code> para saltearlo):",
                parse_mode="HTML"
            )

    # MEDIO DE PAGO COMIDA
    elif data.startswith("comida_medio_"):
        medio = data.replace("comida_medio_", "").replace("MercadoPago", "Mercado Pago").replace("NaranjaX", "Naranja X").replace("PersonalPay", "Personal Pay")
        if chat_id in estado_usuario:
            estado = estado_usuario[chat_id]
            categoria = estado.get("categoria")
            monto = estado.get("monto")
            detalle = estado.get("detalle", "")
            fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
            get_hoja("Comida").append_row([fecha_hoy, categoria, monto, medio, detalle])
            get_hoja().append_row([fecha_hoy, "Gasto", monto, categoria])
            mes_actual = datetime.now().strftime("%m/%Y")
            total_mes = sum(float(f[2]) for f in get_hoja("Comida").get_all_values()[1:] if f[0][3:10] == mes_actual)
            estado_usuario.pop(chat_id, None)
            respuesta = f"✅ <b>{categoria}</b> | ${monto:,.0f} | {medio}\n📊 Total comida este mes: ${total_mes:,.0f}"
            if total_mes >= LIMITE_COMIDA:
                respuesta += f"\n⚠️ <b>¡Superaste el límite!</b>"
            elif total_mes >= LIMITE_COMIDA * 0.8:
                respuesta += f"\n⚠️ Vas por el 80% del límite."
            keyboard = [
                [InlineKeyboardButton("🛒 Seguir cargando", callback_data="menu_comida")],
                [InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]
            ]
            await query.edit_message_text(respuesta, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    # PERIODICIDAD STREAMING
    elif data.startswith("stream_period_"):
        periodicidad = data.replace("stream_period_", "")
        if chat_id in estado_usuario:
            estado_usuario[chat_id]["periodicidad"] = periodicidad
            estado_usuario[chat_id]["paso"] = "esperando_stream_fecha"
            await query.edit_message_text(
                f"✅ Periodicidad: <b>{periodicidad}</b>\n\nEscribí la fecha del próximo pago (DD/MM/AAAA):\nEjemplo: <code>15/05/2026</code>",
                parse_mode="HTML"
            )

# =====================
# MANEJADOR DE TEXTO
# =====================
async def manejar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()

    if texto == "📋 Menú":
        estado_usuario.pop(chat_id, None)
        await update.message.reply_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())
        return

    if chat_id not in estado_usuario:
        await update.message.reply_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())
        return

    estado = estado_usuario[chat_id]
    paso = estado.get("paso")

    # SUELDO
    if paso == "esperando_sueldo":
        try:
            monto = float(texto.replace(".", "").replace(",", "."))
            get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Sueldo", monto, "Ingreso mensual"])
            estado_usuario.pop(chat_id, None)
            keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]]
            await update.message.reply_text(
                f"✅ <b>Sueldo cargado: ${monto:,.0f}</b>\n¡A administrarlo bien, Marcos!",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí solo el número. Ejemplo: 600000")

    # GASTO GENERAL
    elif paso == "esperando_gasto_monto":
        try:
            partes = texto.split(" ", 1)
            monto = float(partes[0].replace(".", "").replace(",", "."))
            concepto = partes[1] if len(partes) > 1 else "Gasto"
            get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", monto, concepto])
            estado_usuario.pop(chat_id, None)
            keyboard = [[InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]]
            await update.message.reply_text(
                f"💸 <b>Gasto anotado:</b> ${monto:,.0f} en {concepto}",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí: monto concepto\nEjemplo: <code>1500 café</code>", parse_mode="HTML")

    # COMIDA - monto y detalle
    elif paso == "esperando_comida_monto":
        try:
            partes = texto.split(" ", 1)
            monto = float(partes[0].replace(".", "").replace(",", "."))
            detalle = partes[1] if len(partes) > 1 else ""
            estado["monto"] = monto
            estado["detalle"] = detalle
            estado["paso"] = "esperando_comida_medio"
            keyboard = [
                [InlineKeyboardButton("📱 Mercado Pago", callback_data="comida_medio_MercadoPago"),
                 InlineKeyboardButton("🟠 Naranja X", callback_data="comida_medio_NaranjaX")],
                [InlineKeyboardButton("💙 Personal Pay", callback_data="comida_medio_PersonalPay"),
                 InlineKeyboardButton("💵 Efectivo", callback_data="comida_medio_Efectivo")]
            ]
            await update.message.reply_text(
                f"💰 ${monto:,.0f} — {detalle}\n\n¿Con qué medio pagaste?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí el monto. Ejemplo: <code>15000 compras semana</code>", parse_mode="HTML")

    # AUTO - monto y detalle
    elif paso == "esperando_auto_monto":
        try:
            partes = texto.split(" ", 1)
            monto = float(partes[0].replace(".", "").replace(",", "."))
            detalle = partes[1] if len(partes) > 1 else ""
            estado["monto"] = monto
            estado["detalle"] = detalle
            estado["paso"] = "esperando_auto_medio"
            keyboard = [
                [InlineKeyboardButton("📱 Mercado Pago", callback_data="auto_medio_MercadoPago"),
                 InlineKeyboardButton("🟠 Naranja X", callback_data="auto_medio_NaranjaX")],
                [InlineKeyboardButton("💙 Personal Pay", callback_data="auto_medio_PersonalPay"),
                 InlineKeyboardButton("💵 Efectivo", callback_data="auto_medio_Efectivo")]
            ]
            await update.message.reply_text(
                f"🚗 {estado['tipo']} | ${monto:,.0f}\n\n¿Con qué medio pagaste?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí el monto. Ejemplo: <code>15000</code>", parse_mode="HTML")

    # AUTO - detalle (después del medio)
    elif paso == "esperando_auto_detalle":
        detalle = "" if texto == "-" else texto
        estado["detalle"] = detalle
        tipo = estado.get("tipo")
        monto = estado.get("monto")
        medio = estado.get("medio")
        prox_venc = "Próximo en 10.000 km" if tipo == "Aceite" else ""
        fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
        get_hoja("Auto").append_row([fecha_hoy, tipo, monto, medio, detalle, prox_venc])
        get_hoja().append_row([fecha_hoy, "Gasto", monto, tipo])
        estado_usuario.pop(chat_id, None)
        respuesta = f"✅ <b>🚗 {tipo}</b> | ${monto:,.0f} | {medio}"
        if detalle:
            respuesta += f"\n📝 {detalle}"
        if tipo in ["Aceite", "VTV", "Seguro", "Oblea Gas", "Patente"]:
            respuesta += f"\n\n⏰ Recordá cargar el vencimiento desde el menú Auto → 📅 Cargar Vencimiento"
        keyboard = [
            [InlineKeyboardButton("🚗 Seguir cargando", callback_data="menu_auto")],
            [InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]
        ]
        await update.message.reply_text(respuesta, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    # AUTO - vencimiento
    elif paso == "esperando_vencimiento_auto":
        try:
            fecha = datetime.strptime(texto, "%d/%m/%Y")
            tipo = estado.get("tipo")
            hoja = get_hoja("Auto")
            datos = hoja.get_all_values()
            actualizado = False
            for i, fila in enumerate(datos[1:], start=2):
                if fila[1].lower() == tipo.lower():
                    hoja.update_cell(i, 6, texto)
                    actualizado = True
                    break
            if not actualizado:
                hoja.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), tipo, 0, "", "Vencimiento", texto])
            dias = (fecha - datetime.now()).days
            estado_usuario.pop(chat_id, None)
            estado_str = "⚠️ ¡Ya vencido!" if dias < 0 else f"⚠️ Vence en {dias} días" if dias <= 30 else f"✅ Faltan {dias} días"
            keyboard = [[InlineKeyboardButton("🔙 Auto", callback_data="menu_auto")]]
            await update.message.reply_text(
                f"📅 <b>{tipo}:</b> {texto} — {estado_str}",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA\nEjemplo: <code>30/06/2026</code>", parse_mode="HTML")

    # SERVICIO - fecha
    elif paso == "esperando_servicio_fecha":
        try:
            datetime.strptime(texto, "%d/%m/%Y")
            estado["fecha"] = texto
            estado["paso"] = "esperando_servicio_monto"
            await update.message.reply_text(
                f"✅ Fecha: <b>{texto}</b>\n\nEscribí el monto a pagar:",
                parse_mode="HTML"
            )
        except:
            await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA\nEjemplo: <code>15/04/2026</code>", parse_mode="HTML")

    # SERVICIO - monto
    elif paso == "esperando_servicio_monto":
        try:
            monto = float(texto.replace(".", "").replace(",", "."))
            servicio = estado.get("servicio")
            fecha = estado.get("fecha")
            get_hoja("Servicios").append_row([servicio, fecha, monto, "", "Pendiente", "", ""])
            estado_usuario.pop(chat_id, None)
            keyboard = [
                [InlineKeyboardButton("🔔 Ver Servicios", callback_data="accion_ver_servicios")],
                [InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]
            ]
            await update.message.reply_text(
                f"✅ <b>{servicio}</b> | 📅 {fecha} | 💰 ${monto:,.0f}",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí solo el número. Ejemplo: <code>25000</code>", parse_mode="HTML")

    # STREAMING - precio USD
    elif paso == "esperando_stream_precio":
        try:
            precio_usd = float(texto.replace(",", "."))
            estado["precio_usd"] = precio_usd
            estado["paso"] = "esperando_stream_periodicidad"
            keyboard = [
                [InlineKeyboardButton("🔄 Mensual", callback_data="stream_period_mensual"),
                 InlineKeyboardButton("📅 Anual", callback_data="stream_period_anual")]
            ]
            await update.message.reply_text(
                f"💵 USD {precio_usd:.2f}\n\n¿Es mensual o anual?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí solo el número. Ejemplo: <code>6.99</code>", parse_mode="HTML")

    # STREAMING - fecha
    elif paso == "esperando_stream_fecha":
        try:
            datetime.strptime(texto, "%d/%m/%Y")
            plataforma = estado.get("plataforma")
            precio_usd = estado.get("precio_usd")
            periodicidad = estado.get("periodicidad")
            tc = obtener_tipo_cambio()
            precio_ars = precio_usd * tc
            fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
            get_hoja("Streaming").append_row([plataforma, precio_usd, precio_ars, tc, periodicidad, texto, "Activa", fecha_hoy])
            get_hoja().append_row([fecha_hoy, "Gasto", precio_ars, f"Streaming {plataforma}"])
            estado_usuario.pop(chat_id, None)
            keyboard = [
                [InlineKeyboardButton("📺 Ver Streaming", callback_data="accion_ver_streaming")],
                [InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")]
            ]
            await update.message.reply_text(
                f"✅ <b>{plataforma}</b> | USD{precio_usd:.2f} = ${precio_ars:,.0f} | {periodicidad}\n📅 Próximo: {texto}",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA\nEjemplo: <code>15/05/2026</code>", parse_mode="HTML")

    # DÓLAR
    elif paso == "esperando_dolar":
        try:
            valor = float(texto.replace(".", "").replace(",", "."))
            hoja = get_hoja("Streaming")
            datos = hoja.get_all_values()
            actualizado = False
            for i, fila in enumerate(datos[1:], start=2):
                if fila[0] == "DOLAR":
                    hoja.update_cell(i, 4, valor)
                    actualizado = True
                    break
            if not actualizado:
                hoja.append_row(["DOLAR", "", "", valor, "", "", "", datetime.now().strftime("%d/%m/%Y")])
            estado_usuario.pop(chat_id, None)
            keyboard = [[InlineKeyboardButton("🔙 Streaming", callback_data="menu_streaming")]]
            await update.message.reply_text(
                f"✅ Dólar actualizado: <b>${valor:,.0f}</b>",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Escribí solo el número. Ejemplo: <code>1200</code>", parse_mode="HTML")

    else:
        await update.message.reply_text("📋 <b>MENÚ PRINCIPAL</b>", parse_mode="HTML", reply_markup=menu_principal())

# =====================
# AVISOS AUTOMÁTICOS
# =====================
def chequear_vencimientos():
    while True:
        try:
            if CHAT_ID:
                hoy = datetime.now()
                avisos = []
                try:
                    for fila in get_hoja("Servicios").get_all_values()[1:]:
                        if len(fila) > 4 and fila[4] == "Pagado":
                            continue
                        try:
                            dias = (datetime.strptime(fila[1], "%d/%m/%Y") - hoy).days
                            if dias in [7, 1]:
                                avisos.append(f"🔔 <b>{fila[0]}</b> vence en {dias} día{'s' if dias > 1 else ''} — ${fila[2]}")
                            elif dias == 0:
                                avisos.append(f"🚨 <b>{fila[0]}</b> vence <b>HOY</b> — ${fila[2]}")
                        except:
                            pass
                except:
                    pass
                try:
                    for fila in get_hoja("Auto").get_all_values()[1:]:
                        prox = fila[5] if len(fila) > 5 else ""
                        if not prox or prox.startswith("Próximo"):
                            continue
                        try:
                            dias = (datetime.strptime(prox, "%d/%m/%Y") - hoy).days
                            if dias in [7, 1]:
                                avisos.append(f"🚗 <b>{fila[1]}</b> vence en {dias} día{'s' if dias > 1 else ''}")
                            elif dias == 0:
                                avisos.append(f"🚨 <b>{fila[1]}</b> del auto vence <b>HOY</b>")
                        except:
                            pass
                except:
                    pass
                try:
                    tc = obtener_tipo_cambio()
                    for fila in get_hoja("Streaming").get_all_values()[1:]:
                        if fila[0] == "DOLAR" or (len(fila) > 6 and fila[6] == "Cancelado"):
                            continue
                        prox = fila[5] if len(fila) > 5 else ""
                        if not prox:
                            continue
                        try:
                            dias = (datetime.strptime(prox, "%d/%m/%Y") - hoy).days
                            precio_ars = float(fila[1]) * tc if fila[1] else 0
                            if dias in [7, 1]:
                                avisos.append(f"📺 <b>{fila[0]}</b> renueva en {dias} día{'s' if dias > 1 else ''} — ${precio_ars:,.0f}")
                            elif dias == 0:
                                avisos.append(f"📺 <b>{fila[0]}</b> renueva <b>HOY</b> — ${precio_ars:,.0f}")
                        except:
                            pass
                except:
                    pass
                if avisos:
                    asyncio.run(
                        Application.builder().token(TOKEN).build().bot.send_message(
                            chat_id=CHAT_ID,
                            text="⚠️ <b>AVISOS DEL DÍA</b> ⚠️\n\n" + "\n".join(avisos),
                            parse_mode="HTML"
                        )
                    )
        except:
            pass
        time.sleep(43200)

def build_app():
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(manejar_botones))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_texto))
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
    t = threading.Thread(target=chequear_vencimientos, daemon=True)
    t.start()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
