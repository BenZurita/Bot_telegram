import re
import os
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# Configuración
TOKEN = "7683666857:AAFKKwsLSn5iPBVvVKsplh8v7Oh8LGZq9wQ"
RUTA_GUARDADO = r"C:\Users\Especialista de Data\Documents\Balance gestión"
ARCHIVO_EXCEL = os.path.join(RUTA_GUARDADO, "registros_gestion.xlsx")

# Lista global para almacenar todos los registros
registros_completos = []

def limpiar_valor(valor):
    """Limpia símbolos innecesarios y estandariza decimales."""
    if valor:
        return valor.strip().replace(",", ".").replace("$", "").replace("unid.", "").replace("bulto", "").replace("bultos", "")
    return ""

def validar_fecha(fecha_str):
    """Valida y formatea fechas en formato DD/MM/AAAA"""
    match = re.match(r'^(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})$', fecha_str)
    if match:
        dia = match.group(1).zfill(2)
        mes = match.group(2).zfill(2)
        anio = match.group(3)
        return f"{dia}/{mes}/{anio}"
    return ""

def procesar_mensaje_balance(texto):
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    
    # Campos generales del encabezado (se detectan automáticamente)
    data_general = {}

    i = 0
    while i < len(lineas):
        linea = lineas[i]

        # Si empieza un producto, dejamos de leer encabezado
        if linea.startswith("Producto:"):
            break

        # Detectar campos generales (clave: valor)
        match = re.match(r'^([^:]+):\s*(.+)$', linea)
        if match:
            clave = match.group(1).strip()
            valor = limpiar_valor(match.group(2))
            if clave.lower() == "fecha":
                valor = validar_fecha(valor)
            data_general[clave] = valor

        i += 1

    registros = []
    
    # Procesar productos uno por uno
    while i < len(lineas):
        linea = lineas[i]
        if not linea.startswith("Producto:"):
            i += 1
            continue

        # Inicio de un producto
        nombre_producto = linea.replace("Producto:", "").strip()
        registro = data_general.copy()
        registro["Producto"] = nombre_producto
        registro["Categoría"] = ""

        j = i + 1
        while j < len(lineas):
            sublinea = lineas[j]
            if sublinea.startswith("Producto:"): break  # Nuevo producto

            # Extraer campos específicos del producto
            match = re.match(r'^([^:]+):\s*(.+)$', sublinea)
            if match:
                clave = match.group(1).strip()
                valor = limpiar_valor(match.group(2))

                if clave.lower() == "tipo de producto":
                    registro["Categoría"] = valor
                elif clave.lower() == "inventario en exhibición":
                    registro["Inv. Exhibición"] = valor
                elif clave.lower() == "inventario en depósito":
                    registro["Inv. Depósito Inicial"] = valor
                elif clave.lower() == "inventario final":
                    registro["Final Exhibición"] = valor
                elif clave.lower() == "número de caras":
                    registro["Caras"] = valor
                elif clave.lower() == "precio":
                    registro["Precio"] = valor.replace(",", ".")
                else:
                    registro[clave] = valor  # Campo adicional dinámico (ej: Fabricante)

            j += 1

        # Rellenar valores vacíos con "0" en campos numéricos
        campos_numericos = [
            "Inv. Exhibición",
            "Inv. Depósito Inicial",
            "Final Exhibición",
            "Caras",
            "Precio"
        ]
        for campo in campos_numericos:
            if campo not in registro or not registro[campo]:
                registro[campo] = "0"

        registros.append(registro)
        i = j

    return registros

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_recibido = update.message.text
    nuevos_registros = procesar_mensaje_balance(texto_recibido)
    registros_completos.extend(nuevos_registros)
    await update.message.reply_text("✅ Mensaje recibido y procesado correctamente. Usa /exportar para generar el archivo.")

async def exportar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not registros_completos:
        await update.message.reply_text("⚠️ No hay datos para exportar.")
        return

    df = pd.DataFrame(registros_completos)
    os.makedirs(RUTA_GUARDADO, exist_ok=True)
    df.to_excel(ARCHIVO_EXCEL, index=False)

    with open(ARCHIVO_EXCEL, 'rb') as f:
        await update.message.reply_document(document=f)

    await update.message.reply_text(f"📄 Archivo generado exitosamente.\nGuardado en:\n{RUTA_GUARDADO}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    app.add_handler(CommandHandler("exportar", exportar_excel))
    print("🚀 Bot iniciado. Esperando mensajes...")
    app.run_polling()

if __name__ == "__main__":
    main()