import re
import os
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# Configuración
TOKEN = "7683666857:AAFKKwsLSn5iPBVvVKsplh8v7Oh8LGZq9wQ"
RUTA_GUARDADO = r"C:\Users\Especialista de Data\Documents\Balance gestión"
ARCHIVO_EXCEL = os.path.join(RUTA_GUARDADO, "registros_gestion.xlsx")

# Lista global para almacenar todos los productos extraídos
registros_completos = []

def limpiar_valor(valor):
    """Limpia valores innecesarios como signos o unidades."""
    if valor:
        return valor.strip().replace(",", ".").replace("$", "").replace("unid.", "").replace("bulto", "").replace("bultos", "")
    return ""

def procesar_mensaje_balance(texto):
    """Procesa el mensaje y devuelve una lista de diccionarios con los datos de cada producto."""
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]

    # Extraer datos generales
    proyecto_match = re.search(r'PROYECTO\s*(.+)', texto)
    fecha_match = re.search(r'FECHA:\s*([\d\/\-\.]+)', texto)
    ciudad_match = re.search(r'CIUDAD:\s*([^\\r\\n]+)', texto)
    pdv_match = re.search(r'PDV:\s*([^\\r\\n]+)', texto)
    mercaderista_match = re.search(r'Mercaderista:\s*([^\\r\\n]+)', texto)
    encargado_match = re.search(r'Encargado:\s*([^\\r\\n]+)', texto)

    data_general = {
        "Proyecto": limpiar_valor(proyecto_match.group(1)) if proyecto_match else "",
        "Fecha": limpiar_valor(fecha_match.group(1)) if fecha_match else "",
        "Ciudad": limpiar_valor(ciudad_match.group(1)) if ciudad_match else "",
        "PDV": limpiar_valor(pdv_match.group(1)) if pdv_match else "",
        "Mercaderista": limpiar_valor(mercaderista_match.group(1)) if mercaderista_match else "",
        "Encargado": limpiar_valor(encargado_match.group(1)) if encargado_match else "",
        "Categoría": ""
    }

    categoria_actual = ""
    registros = []
    i = 0

    while i < len(lineas):
        linea = lineas[i]

        # Detectar nueva categoría
        if re.fullmatch(r'[A-ZÁÉÍÓÚÑ\s]{3,}', linea):
            categoria_actual = linea
            i += 1
            continue

        # Es nombre de producto
        if not re.match(r'(Inv\.|N\. De caras:|Precio:|Final:|Inicial:)', linea):
            producto = linea
            registro = data_general.copy()
            registro["Producto"] = producto
            registro["Categoría"] = categoria_actual

            # Inicializar campos vacíos
            registro.update({
                "Inv. Exhibición": "", "Final Exhibición": "",
                "Inv. Depósito Inicial": "", "Inv. Depósito Final": "",
                "Caras": "", "Precio": ""
            })

            # Buscar datos relacionados al producto
            j = i + 1
            while j < len(lineas):
                sublinea = lineas[j]
                if re.fullmatch(r'[A-ZÁÉÍÓÚÑ\s]{3,}', sublinea): break  # nueva categoría

                if re.match(r'Inv\.? Exhibición:?[\s\d]', sublinea):
                    match = re.search(r'[\d\.]+$', sublinea)
                    registro["Inv. Exhibición"] = limpiar_valor(match.group()) if match else ""
                elif re.match(r'Final:?[\s\d]', sublinea):
                    match = re.search(r'[\d\.]+$', sublinea)
                    registro["Final Exhibición"] = limpiar_valor(match.group()) if match else ""
                elif re.match(r'Inv\.? en Depósito.*Inicial:?[\s\d]', sublinea):
                    match = re.search(r'[\d\.]+$', sublinea)
                    registro["Inv. Depósito Inicial"] = limpiar_valor(match.group()) if match else ""
                elif re.match(r'Final:?[\s\d]', sublinea) and "Depósito" in sublinea:
                    match = re.search(r'[\d\.]+$', sublinea)
                    registro["Inv. Depósito Final"] = limpiar_valor(match.group()) if match else ""
                elif re.match(r'N\.? De caras:?[\s\d]', sublinea):
                    match = re.search(r'[\d\.]+$', sublinea)
                    registro["Caras"] = limpiar_valor(match.group()) if match else ""
                elif re.match(r'Precio:?[\s\d]', sublinea):
                    match = re.search(r'[\d\.\,]+$', sublinea)
                    registro["Precio"] = limpiar_valor(match.group()) if match else ""

                j += 1

            registros.append(registro)

        i += 1

    return registros


async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_recibido = update.message.text

    # Procesar mensaje y añadir registros
    nuevos_registros = procesar_mensaje_balance(texto_recibido)
    registros_completos.extend(nuevos_registros)

    await update.message.reply_text("✅ Mensaje recibido y procesado correctamente. Usa /exportar para generar el archivo.")


async def exportar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not registros_completos:
        await update.message.reply_text("⚠️ No hay datos para exportar.")
        return

    df = pd.DataFrame(registros_completos)

    # Crear carpeta si no existe
    os.makedirs(RUTA_GUARDADO, exist_ok=True)

    # Guardar archivo Excel
    df.to_excel(ARCHIVO_EXCEL, index=False)

    # Enviar archivo por Telegram
    with open(ARCHIVO_EXCEL, 'rb') as f:
        await update.message.reply_document(document=f)

    await update.message.reply_text(f"📄 Archivo generado exitosamente.\nGuardado en:\n{RUTA_GUARDADO}")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    app.add_handler(CommandHandler("exportar", exportar_excel))

    print("🚀 Bot iniciado. Esperando mensajes...")
    app.run_polling()


if __name__ == "__main__":
    main()