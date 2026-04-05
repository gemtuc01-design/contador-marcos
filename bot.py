import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask, request
from datetime import datetime, timedelta
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

MEDIOS_PAGO = ["Mercado Pago", "Naranja X", "Personal Pay", "Efectivo"]
TIPOS_AUTO = ["Nafta", "GNC", "Aceite", "VTV", "Oblea Gas", "Seguro", "Patente", "Parche/Rueda", "Repuesto", "Service", "Peaje/Estacionamiento", "Otro"]
CATEGORIAS_COMIDA = ["Supermercado", "Panadería", "Almacén", "Pollería", "Carnicería", "Verdulería", "Kiosco", "Delivery", "Restaurante", "Cafetería", "Mercado Libre"]
SERVICIOS_LISTA = ["Luz", "Agua", "Gas", "Internet", "Tarjeta", "Alquiler", "Expensas", "Celular"]
PLATAFORMAS = ["YouTube", "Spotify", "Google One", "HBO Max", "Netflix", "Disney+", "Prime Video", "Flow"]
LIMITE_COMIDA = 500000

# =====================
# INICIO Y AYUDA
# =====================
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
        "👉 /servicios\n"
        "👉 /nuevo_servicio [servicio] [DD/MM/AAAA] [monto]\n"
        "👉 /pagar [servicio] [medio] [comprobante]\n\n"
        "🚗 <b>Auto:</b>\n"
        "👉 /auto\n"
        "👉 /gasto_auto [tipo] [monto] [medio] [detalle]\n"
        "👉 /vencimiento_auto [tipo] [DD/MM/AAAA]\n\n"
        "🛒 <b>Comida:</b>\n"
        "👉 /comida\n"
        "👉 /gasto_comida [categoría] [monto] [medio] [detalle]\n\n"
        "📺 <b>Streaming:</b>\n"
        "👉 /streaming — ver todas las suscripciones\n"
        "👉 /nueva_suscripcion [plataforma] [USD] [DD/MM/AAAA] [mensual/anual]\n"
        "    Ejemplo: /nueva_suscripcion Netflix 6.99 15/05/2026 mensual\n"
        "👉 /actualizar_precio [plataforma] [USD]\n"
        "    Ejemplo: /actualizar_precio Netflix 7.99\n"
        "👉 /dolar [valor]\n"
        "    Ejemplo: /dolar 1200",
        parse_mode="HTML"
    )

# =====================
# FINANZAS BÁSICAS
# =====================
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
    total_streaming_mes = 0
    try:
        tc = obtener_tipo_cambio()
        for fila in get_hoja("Streaming").get_all_values()[1:]:
            if len(fila) > 5 and fila[6] != "Cancelado":
                periodicidad = fila[4] if len(fila) > 4 else "mensual"
                precio_usd = float(fila[1]) if fila[1] else 0
                if periodicidad == "anual":
                    total_streaming_mes += (precio_usd * tc) / 12
                else:
                    total_streaming_mes += precio_usd * tc
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
    await update.message.reply_text(texto, parse_mode="HTML")

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
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Pasá ${disponible*0.6:,.0f} a Mercado Pago o Personal Pay para ganar intereses diarios.")
    elif disponible > 0:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"💡 Estás en positivo pero ajustado. Dejá esa plata en tu billetera virtual remunerada.")
    else:
        texto = (f"👨‍💼 <b>TU ASESOR FINANCIERO</b> 👨‍💼\n\n💰 Saldo: ${disponible:,.0f}\n\n"
                 f"⚠️ ¡Ojo, Marcos! Estás en rojo. Revisá el Excel y cortá los gastos hormiga.")
    if cat_gastos:
        top = sorted(cat_gastos.items(), key=lambda x: x[1], reverse=True)[:3]
        texto += f"\n\n🛒 <b>Top 3 gastos de comida:</b>\n"
        for cat, monto in top:
            texto += f"• {cat}: ${monto:,.0f}\n"
    if total_comida_mes >= LIMITE_COMIDA:
        texto += f"\n⚠️ Llevás ${total_comida_mes:,.0f} en comida este mes."
    await update.message.reply_text(texto, parse_mode="HTML")

# =====================
# STREAMING
# =====================
def obtener_tipo_cambio():
    try:
        hoja = get_hoja("Streaming")
        datos = hoja.get_all_values()
        for fila in datos[1:]:
            if len(fila) > 3 and fila[3] and fila[0] == "DOLAR":
                return float(fila[3])
        return 1200
    except:
        return 1200

async def dolar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        tc_actual = obtener_tipo_cambio()
        await update.message.reply_text(
            f"💵 Tipo de cambio actual: <b>${tc_actual:,.0f}</b>\n\n"
            f"Para actualizarlo: /dolar 1250",
            parse_mode="HTML"
        )
        return
    try:
        valor = float(context.args[0])
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
        await update.message.reply_text(
            f"✅ Tipo de cambio actualizado: <b>${valor:,.0f}</b>\n\n"
            f"Todas las conversiones ya usan este valor.",
            parse_mode="HTML"
        )
    except:
        await update.message.reply_text("❌ Usá: /dolar 1200")

async def nueva_suscripcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4:
        await update.message.reply_text(
            "❌ Usá: /nueva_suscripcion [plataforma] [USD] [DD/MM/AAAA] [mensual/anual]\n\n"
            "Ejemplos:\n"
            "<code>/nueva_suscripcion Netflix 6.99 15/05/2026 mensual</code>\n"
            "<code>/nueva_suscripcion Spotify 2.99 01/06/2026 mensual</code>\n\n"
            "Plataformas: " + ", ".join(PLATAFORMAS),
            parse_mode="HTML"
        )
        return
    plataforma = context.args[0]
    try:
        precio_usd = float(context.args[1])
    except:
        await update.message.reply_text("❌ El precio debe ser un número. Ejemplo: 6.99")
        return
    fecha_str = context.args[2]
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
    except:
        await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA")
        return
    periodicidad = context.args[3].lower()
    if periodicidad not in ["mensual", "anual"]:
        await update.message.reply_text("❌ Periodicidad debe ser 'mensual' o 'anual'")
        return
    tc = obtener_tipo_cambio()
    precio_ars = precio_usd * tc
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    get_hoja("Streaming").append_row([
        plataforma, precio_usd, precio_ars, tc,
        periodicidad, fecha_str, "Activa", fecha_hoy
    ])
    get_hoja().append_row([fecha_hoy, "Gasto", precio_ars, f"Streaming {plataforma}"])
    await update.message.reply_text(
        f"✅ <b>Suscripción cargada</b>\n\n"
        f"📺 {plataforma}\n"
        f"💵 USD {precio_usd:.2f} = ${precio_ars:,.0f}\n"
        f"📅 Próximo pago: {fecha_str}\n"
        f"🔄 {periodicidad.capitalize()}\n\n"
        f"💡 Si el precio cambia usá:\n"
        f"<code>/actualizar_precio {plataforma} nuevo_precio</code>",
        parse_mode="HTML"
    )

async def streaming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja("Streaming")
    datos = hoja.get_all_values()
    tc = obtener_tipo_cambio()
    suscripciones = [f for f in datos[1:] if f[0] != "DOLAR" and len(f) > 5]
    if not suscripciones:
        await update.message.reply_text(
            "📺 No tenés suscripciones cargadas.\n\n"
            "Usá: /nueva_suscripcion Netflix 6.99 15/05/2026 mensual"
        )
        return
    texto = f"📺 <b>TUS SUSCRIPCIONES</b>\n💵 Dólar: ${tc:,.0f}\n\n"
    total_mensual_usd = 0
    total_mensual_ars = 0
    hoy = datetime.now()
    keyboard = []
    for i, fila in enumerate(suscripciones, start=2):
        try:
            plataforma = fila[0]
            precio_usd = float(fila[1])
            periodicidad = fila[4] if len(fila) > 4 else "mensual"
            prox_pago = fila[5] if len(fila) > 5 else ""
            estado = fila[6] if len(fila) > 6 else "Activa"
            precio_ars_actual = precio_usd * tc
            if estado == "Cancelado":
                continue
            emoji = "✅"
            aviso = ""
            if prox_pago:
                try:
                    fecha_pago = datetime.strptime(prox_pago, "%d/%m/%Y")
                    dias = (fecha_pago - hoy).days
                    if dias < 0:
                        emoji = "🔴"
                        aviso = " — ¡VENCIDO!"
                    elif dias <= 1:
                        emoji = "🚨"
                        aviso = f" — ¡mañana!"
                    elif dias <= 7:
                        emoji = "⚠️"
                        aviso = f" — {dias} días"
                except:
                    pass
            if periodicidad == "anual":
                mensual_usd = precio_usd / 12
                mensual_ars = precio_ars_actual / 12
                texto += (f"{emoji} <b>{plataforma}</b> {aviso}\n"
                         f"   💵 USD {precio_usd:.2f}/año (≈ USD {mensual_usd:.2f}/mes)\n"
                         f"   💰 ${precio_ars_actual:,.0f}/año (≈ ${mensual_ars:,.0f}/mes)\n"
                         f"   📅 Próximo: {prox_pago} | 🔄 Anual\n\n")
                total_mensual_usd += mensual_usd
                total_mensual_ars += mensual_ars
            else:
                texto += (f"{emoji} <b>{plataforma}</b> {aviso}\n"
                         f"   💵 USD {precio_usd:.2f}/mes\n"
                         f"   💰 ${precio_ars_actual:,.0f}/mes\n"
                         f"   📅 Próximo: {prox_pago} | 🔄 Mensual\n\n")
                total_mensual_usd += precio_usd
                total_mensual_ars += precio_ars_actual
            keyboard.append([InlineKeyboardButton(
                f"❌ Cancelar {plataforma}",
                callback_data=f"cancelar_stream_{i}_{plataforma}"
            )])
        except:
            pass
    texto += (f"📊 <b>TOTAL MENSUAL</b>\n"
              f"💵 USD {total_mensual_usd:.2f}\n"
              f"💰 ${total_mensual_ars:,.0f}\n\n"
              f"💡 Para actualizar tipo de cambio: /dolar [valor]")
    await update.message.reply_text(
        texto, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def actualizar_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usá: /actualizar_precio [plataforma] [nuevo precio USD]\n"
            "Ejemplo: /actualizar_precio Netflix 7.99"
        )
        return
    plataforma = context.args[0]
    try:
        nuevo_precio = float(context.args[1])
    except:
        await update.message.reply_text("❌ El precio debe ser un número.")
        return
    tc = obtener_tipo_cambio()
    nuevo_ars = nuevo_precio * tc
    hoja = get_hoja("Streaming")
    datos = hoja.get_all_values()
    encontrado = False
    for i, fila in enumerate(datos[1:], start=2):
        if fila[0].lower() == plataforma.lower() and fila[0] != "DOLAR":
            precio_viejo = fila[1]
            hoja.update_cell(i, 2, nuevo_precio)
            hoja.update_cell(i, 3, nuevo_ars)
            hoja.update_cell(i, 4, tc)
            encontrado = True
            await update.message.reply_text(
                f"✅ <b>Precio actualizado: {plataforma}</b>\n\n"
                f"💵 Antes: USD {precio_viejo}\n"
                f"💵 Ahora: USD {nuevo_precio:.2f}\n"
                f"💰 En pesos: ${nuevo_ars:,.0f}\n"
                f"📊 Tipo de cambio usado: ${tc:,.0f}",
                parse_mode="HTML"
            )
            break
    if not encontrado:
        await update.message.reply_text(
            f"❌ No encontré {plataforma}.\n"
            f"Verificá con /streaming qué tenés cargado."
        )

# =====================
# COMIDA
# =====================
async def gasto_comida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usá: /gasto_comida [categoría] [monto] [medio] [detalle]\n"
            "Ejemplo: /gasto_comida Supermercado 15000 Efectivo compras semana\n\n"
            "Categorías: " + ", ".join(CATEGORIAS_COMIDA)
        )
        return
    categoria = context.args[0].capitalize()
    try:
        monto = float(context.args[1])
    except:
        await update.message.reply_text("❌ El monto debe ser un número.")
        return
    medio = context.args[2] if len(context.args) > 2 else "Efectivo"
    detalle = " ".join(context.args[3:]) if len(context.args) > 3 else ""
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    get_hoja("Comida").append_row([fecha_hoy, categoria, monto, medio, detalle])
    get_hoja().append_row([fecha_hoy, "Gasto", monto, categoria])
    mes_actual = datetime.now().strftime("%m/%Y")
    total_mes = 0
    for fila in get_hoja("Comida").get_all_values()[1:]:
        try:
            if fila[0][3:10] == mes_actual:
                total_mes += float(fila[2])
        except:
            pass
    respuesta = (
        f"🛒 <b>Gasto de comida registrado</b>\n\n"
        f"📌 {categoria} | 💰 ${monto:,.0f} | 💳 {medio}\n"
    )
    if detalle:
        respuesta += f"📝 {detalle}\n"
    respuesta += f"\n📊 Total comida este mes: ${total_mes:,.0f}"
    if total_mes >= LIMITE_COMIDA:
        respuesta += f"\n⚠️ <b>¡Superaste el límite de ${LIMITE_COMIDA:,.0f}!</b>"
    elif total_mes >= LIMITE_COMIDA * 0.8:
        respuesta += f"\n⚠️ Vas por el 80% del límite mensual."
    await update.message.reply_text(respuesta, parse_mode="HTML")

async def comida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    datos = get_hoja("Comida").get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text("🛒 No tenés gastos de comida.\n\nUsá: /gasto_comida Supermercado 15000 Efectivo")
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
    await update.message.reply_text(texto, parse_mode="HTML")

# =====================
# AUTO
# =====================
async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(texto, parse_mode="HTML")

async def gasto_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usá: /gasto_auto [tipo] [monto] [medio] [detalle]\n"
            "Ejemplo: /gasto_auto Nafta 15000 Efectivo cargué full\n\n"
            "Tipos: " + ", ".join(TIPOS_AUTO)
        )
        return
    tipo = context.args[0].capitalize()
    try:
        monto = float(context.args[1])
    except:
        await update.message.reply_text("❌ El monto debe ser un número.")
        return
    medio = context.args[2]
    detalle = " ".join(context.args[3:]) if len(context.args) > 3 else ""
    prox_venc = "Próximo en 10.000 km" if tipo == "Aceite" else ""
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    get_hoja("Auto").append_row([fecha_hoy, tipo, monto, medio, detalle, prox_venc])
    get_hoja().append_row([fecha_hoy, "Gasto", monto, tipo])
    respuesta = f"🚗 <b>{tipo}</b> | 💰 ${monto:,.0f} | 💳 {medio}\n"
    if detalle:
        respuesta += f"📝 {detalle}\n"
    if tipo in ["Aceite", "VTV", "Seguro", "Oblea Gas", "Patente"]:
        respuesta += f"\n⏰ Cargá el vencimiento:\n<code>/vencimiento_auto {tipo} DD/MM/AAAA</code>"
    await update.message.reply_text(f"✅ <b>Gasto del auto registrado</b>\n\n{respuesta}", parse_mode="HTML")

async def vencimiento_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usá: /vencimiento_auto VTV 30/06/2026")
        return
    tipo = context.args[0].capitalize()
    if tipo == "Gas":
        tipo = "Oblea Gas"
    fecha_str = context.args[1]
    try:
        fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
    except:
        await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA")
        return
    hoja = get_hoja("Auto")
    datos = hoja.get_all_values()
    actualizado = False
    for i, fila in enumerate(datos[1:], start=2):
        if fila[1].lower() == tipo.lower():
            hoja.update_cell(i, 6, fecha_str)
            actualizado = True
            break
    if not actualizado:
        hoja.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), tipo, 0, "", "Vencimiento", fecha_str])
    dias = (fecha - datetime.now()).days
    estado = "⚠️ ¡Ya vencido!" if dias < 0 else f"⚠️ Vence en {dias} días" if dias <= 30 else f"✅ Faltan {dias} días"
    await update.message.reply_text(f"📅 <b>{tipo}:</b> {fecha_str} — {estado}", parse_mode="HTML")

# =====================
# SERVICIOS
# =====================
async def nuevo_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("❌ Usá: /nuevo_servicio Luz 15/04/2026 25000")
        return
    servicio = context.args[0].capitalize()
    fecha_str = context.args[1]
    try:
        datetime.strptime(fecha_str, "%d/%m/%Y")
    except:
        await update.message.reply_text("❌ Fecha incorrecta. Usá DD/MM/AAAA")
        return
    try:
        monto = float(context.args[2])
    except:
        await update.message.reply_text("❌ Monto incorrecto.")
        return
    get_hoja("Servicios").append_row([servicio, fecha_str, monto, "", "Pendiente", "", ""])
    await update.message.reply_text(
        f"✅ <b>{servicio}</b> | 📅 {fecha_str} | 💰 ${monto:,.0f}\n\n"
        f"Cuando pagues: <code>/pagar {servicio} MercadoPago 12345678</code>",
        parse_mode="HTML"
    )

async def servicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text("📋 Sin servicios.\n\nUsá: /nuevo_servicio Luz 15/04/2026 25000")
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
    await update.message.reply_text(
        texto, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def pagar_servicio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usá: /pagar Luz MercadoPago 12345678")
        return
    servicio = context.args[0].capitalize()
    medio = context.args[1]
    comprobante = " ".join(context.args[2:]) if len(context.args) > 2 else "Sin comprobante"
    hoja = get_hoja("Servicios")
    datos = hoja.get_all_values()
    for i, fila in enumerate(datos[1:], start=2):
        if fila[0].lower() == servicio.lower() and (len(fila) <= 4 or fila[4] != "Pagado"):
            monto = fila[2]
            hoja.update_cell(i, 4, medio)
            hoja.update_cell(i, 5, "Pagado")
            hoja.update_cell(i, 6, comprobante)
            hoja.update_cell(i, 7, datetime.now().strftime("%d/%m/%Y %H:%M"))
            get_hoja().append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), "Gasto", float(monto), servicio])
            await update.message.reply_text(
                f"✅ <b>{servicio} pagado</b> | 💳 {medio} | 📎 {comprobante}\n💰 ${float(monto):,.0f} anotado.",
                parse_mode="HTML"
            )
            return
    await update.message.reply_text(f"❌ No encontré {servicio} pendiente.")

# =====================
# CORREGIR
# =====================
async def corregir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoja = get_hoja()
    datos = hoja.get_all_values()
    if len(datos) <= 1:
        await update.message.reply_text("❌ No hay registros todavía.")
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
    texto += "\n⚠️ <i>Al eliminar, cargá el correcto con /sueldo o /gasto</i>"
    await update.message.reply_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# =====================
# BOTONES
# =====================
async def manejar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("eliminar_"):
        fila_num = int(query.data.split("_")[1])
        hoja = get_hoja()
        datos = hoja.get_all_values()
        if fila_num <= len(datos):
            fila = datos[fila_num - 1]
            hoja.delete_rows(fila_num)
            await query.edit_message_text(f"✅ Eliminado: {fila[1]} | ${fila[2]} | {fila[3]}")

    elif query.data.startswith("cancelar_stream_"):
        partes = query.data.split("_")
        fila_num = int(partes[2])
        plataforma = partes[3]
        hoja = get_hoja("Streaming")
        hoja.update_cell(fila_num, 7, "Cancelado")
        await query.edit_message_text(f"✅ {plataforma} marcada como cancelada.")

    elif query.data.startswith("iniciar_pago_"):
        partes = query.data.split("_")
        fila_num = partes[2]
        servicio = partes[3]
        monto = partes[4]
        keyboard = [[InlineKeyboardButton(m, callback_data=f"confirmar_{fila_num}_{servicio}_{monto}_{m.replace(' ', '-')}")] for m in MEDIOS_PAGO]
        await query.edit_message_text(
            f"💳 Pagando <b>{servicio}</b> (${monto})\n\n¿Con qué medio?",
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
            f"✅ <b>{servicio} PAGADO</b> | 💳 {medio} | 💰 ${float(monto):,.0f}\n\n"
            f"📎 Para agregar comprobante:\n<code>/pagar {servicio} {medio} NUMERO</code>",
            parse_mode="HTML"
        )

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
                                avisos.append(f"🚗 <b>{fila[1]}</b> vence en {dias} día{'s' if dias > 1 else ''} ({prox})")
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
    app.add_handler(CommandHandler("auto", auto))
    app.add_handler(CommandHandler("gasto_auto", gasto_auto))
    app.add_handler(CommandHandler("vencimiento_auto", vencimiento_auto))
    app.add_handler(CommandHandler("comida", comida))
    app.add_handler(CommandHandler("gasto_comida", gasto_comida))
    app.add_handler(CommandHandler("streaming", streaming))
    app.add_handler(CommandHandler("nueva_suscripcion", nueva_suscripcion))
    app.add_handler(CommandHandler("actualizar_precio", actualizar_precio))
    app.add_handler(CommandHandler("dolar", dolar))
    app.add_handler(CallbackQueryHandler(manejar_botones))
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
    t = threading.Thread(target=chequear_vencimientos, daemon=True)
    t.start()
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
