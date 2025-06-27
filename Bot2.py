#============================================================================================================================================================================
# ==================================================================== CONFIGURACIÓN INICIAL Y LIBRERÍAS =================================================================
#==========================================================================================================================================================================

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
import pyodbc
import logging
from datetime import datetime
import pandas as pd
import os

PHOTO_DIR = r"C:\Users\Especialista de Data\Documents\Bot_telegram\fotos_prueba"
os.makedirs(PHOTO_DIR, exist_ok=True)


#===========================================================================================================================================================================
# ======================================================================== CONFIGURACIÓN DEL LOGGING =======================================================================
#===========================================================================================================================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


#=======================================================================================================================================================================
# =============================================================== CONFIGURACIÓN DE LA BASE DE DATOS Y TOKEN ============================================================
#=======================================================================================================================================================================

SERVER = 'LAPTOP-HUI4E4B7'
DATABASE = 'EPRAN'
USERNAME = 'usuario_sql'
PASSWORD = 'abcd1234*'
TOKEN = "8115542729:AAGUkGUXSV5bcNxGeT2uZwBK6TgkustIm8o"


#=======================================================================================================================================================================
# ================================================================= DEFINICIÓN DE ESTADOS DE CONVERSA ==================================================================
#=======================================================================================================================================================================

(ASK_NAME,
 SELECTING_DEPTO,
 SELECTING_CIUDAD,
 SELECTING_POI,
 CONFIRM_SELECTION,
 SELECTING_CLIENTE,
 FINAL_CONFIRMATION,
 SELECTING_PHOTOS,
 FINISH_MESSAGE) = range(9)


#=========================================================================================================================================================================
# ============================================================= CLASE DatabaseManager PARA MANEJO DE BD ==================================================================
#==========================================================================================================================================================================

class DatabaseManager:
    def __init__(self):
        self.connection_string = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={SERVER};'
            f'DATABASE={DATABASE};'
            f'UID={USERNAME};'
            f'PWD={PASSWORD}'
        )
    
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def execute_query(self, query, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchall()
        finally:
            conn.close()


#===========================================================================================================================================================================
# ================================================================= FLUJO PRINCIPAL: INICIO Y PREGUNTAR NOMBRE =============================================================
#===========================================================================================================================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el bot y pasa a preguntar el nombre"""
    context.user_data.clear()
    return await ask_name(update, context)

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pregunta el nombre del usuario al inicio"""
    await update.message.reply_text(
        "👤 ¿Cómo te llamas?",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_NAME


#============================================================================================================================================================================
# ======================================================================== SELECCIÓN DE DEPARTAMENTO ========================================================================
#============================================================================================================================================================================

async def start_departamentos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nombre y empieza con departamentos"""
    nombre = update.message.text.strip()
    if not nombre:
        await update.message.reply_text("Por favor, escribe tu nombre.")
        return ASK_NAME
    context.user_data['nombre'] = nombre
    try:
        db = DatabaseManager()
        departamentos = [depto[0] for depto in db.execute_query(
            'SELECT DISTINCT departamento FROM dbo.PUNTOS_INTERES ORDER BY departamento')]
        if not departamentos:
            await update.message.reply_text("ℹ️ No hay departamentos registrados.")
            return ConversationHandler.END
        botones = []
        for i in range(0, len(departamentos), 3):
            fila = departamentos[i:i + 3]
            botones.append([KeyboardButton(depto) for depto in fila])
        await update.message.reply_text(
            "🏢 *SELECCIONA UN DEPARTAMENTO:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(botones, resize_keyboard=True, one_time_keyboard=False)
        )
        return SELECTING_DEPTO
    except Exception as e:
        logger.error(f"Error al cargar departamentos: {str(e)}")
        await update.message.reply_text("⚠️ Error al cargar departamentos. Usa /start")
        return SELECTING_DEPTO


#============================================================================================================================================================================
# ============================================================================= SELECCIÓN DE CIUDAD =========================================================================
#============================================================================================================================================================================

async def handle_depto_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de departamento y muestra ciudades"""
    departamento = update.message.text
    context.user_data['departamento'] = departamento
    try:
        db = DatabaseManager()
        if not db.execute_query('SELECT 1 FROM dbo.PUNTOS_INTERES WHERE departamento = ?', departamento):
            await update.message.reply_text("⚠️ Departamento no válido. Usa /start para ver las opciones.",
                                            reply_markup=ReplyKeyboardRemove())
            return SELECTING_DEPTO
        ciudades = [ciudad[0] for ciudad in db.execute_query(
            'SELECT DISTINCT ciudad FROM dbo.PUNTOS_INTERES WHERE departamento = ? ORDER BY ciudad', departamento)]
        if not ciudades:
            await update.message.reply_text(f"ℹ️ No hay ciudades en {departamento}")
            return SELECTING_DEPTO
        botones = []
        for i in range(0, len(ciudades), 3):
            fila = ciudades[i:i + 3]
            botones.append([KeyboardButton(ciudad) for ciudad in fila])
        botones.append(["🏢 CAMBIAR DEPARTAMENTO"])
        await update.message.reply_text(
            f"🏙️ *CIUDADES EN {departamento.upper()}:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(botones, resize_keyboard=True)
        )
        return SELECTING_CIUDAD
    except Exception as e:
        logger.error(f"Error al manejar departamento: {str(e)}")
        await update.message.reply_text("⚠️ Error al cargar ciudades. Usa /start si necesitas reiniciar.")
        return SELECTING_DEPTO


#============================================================================================================================================================================
# ===================================================================== SELECCIÓN DE PUNTO DE INTERÉS =======================================================================
#============================================================================================================================================================================

async def handle_ciudad_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra puntos de interés de la ciudad seleccionada"""
    ciudad = update.message.text
    if ciudad == "🏢 CAMBIAR DEPARTAMENTO":
        return await go_back_to_deptos(update, context)
    context.user_data['ciudad'] = ciudad
    try:
        db = DatabaseManager()
        puntos_interes = [row[0] for row in db.execute_query(
            'SELECT DISTINCT punto_de_interes FROM dbo.PUNTOS_INTERES WHERE ciudad = ?', ciudad)]
        if not puntos_interes:
            await update.message.reply_text(f"ℹ️ No hay puntos de interés en {ciudad}")
            return SELECTING_CIUDAD
        botones = []
        for i in range(0, len(puntos_interes), 3):
            fila = puntos_interes[i:i + 3]
            botones.append([KeyboardButton(poi) for poi in fila])
        botones.append(["🏢 CAMBIAR DEPARTAMENTO"])
        await update.message.reply_text(
            f"📍 *PUNTOS DE INTERÉS EN {ciudad.upper()}:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(botones, resize_keyboard=True)
        )
        return SELECTING_POI
    except Exception as e:
        logger.error(f"Error al cargar POIs: {str(e)}")
        await update.message.reply_text("⚠️ Error al cargar puntos de interés. Usa /start")
        return SELECTING_CIUDAD


#=============================================================================================================================================================================
# =================================================================== FILTRO DE PUNTOS DE INTERÉS POR TEXTO ==================================================================
#=============================================================================================================================================================================

async def handle_poi_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Filtra y muestra puntos de interés según texto introducido"""
    user_input = update.message.text
    ciudad = context.user_data.get('ciudad', 'desconocida')
    if user_input == "🏢 CAMBIAR DEPARTAMENTO":
        return await go_back_to_deptos(update, context)
    try:
        db = DatabaseManager()
        resultados = [row[0] for row in db.execute_query(
            'SELECT DISTINCT punto_de_interes FROM dbo.PUNTOS_INTERES '
            'WHERE ciudad = ? AND punto_de_interes LIKE ?',
            (ciudad, f'%{user_input}%'))]
        if not resultados:
            await update.message.reply_text("🔍 No se encontraron coincidencias.")
            return SELECTING_POI
        botones = []
        for i in range(0, len(resultados), 3):
            fila = resultados[i:i + 3]
            botones.append([KeyboardButton(text=p) for p in fila])
        botones.append(["🏢 CAMBIAR DEPARTAMENTO"])
        if user_input in resultados:
            context.user_data['punto_interes'] = user_input
            return await confirm_selection(update, context)
        await update.message.reply_text(
            f"🔍 Resultados para '{user_input}' en {ciudad}:",
            reply_markup=ReplyKeyboardMarkup(botones, resize_keyboard=True)
        )
        return SELECTING_POI
    except Exception as e:
        logger.error(f"Error al filtrar POIs: {str(e)}")
        await update.message.reply_text("⚠️ Error al filtrar. Usa /start si necesitas reiniciar.")
        return SELECTING_POI


#=============================================================================================================================================================================
# ===================================================================== CONFIRMACIÓN DE DATOS INICIALES ======================================================================
#=============================================================================================================================================================================

async def confirm_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el primer resumen y pregunta si desea continuar"""
    nombre = context.user_data.get('nombre', 'No proporcionado')
    depto = context.user_data.get('departamento', 'No seleccionado')
    ciudad = context.user_data.get('ciudad', 'No seleccionada')
    poi = context.user_data.get('punto_interes', 'No seleccionado')
    now = datetime.now().strftime("📅 %d/%m/%Y - ⏰ %H:%M")
    summary = (
        "📄 *Resumen de tu selección:*\n"
        f"👤 Nombre: {nombre}\n"
        f"🏢 Departamento: {depto}\n"
        f"🏙️ Ciudad: {ciudad}\n"
        f"📍 Punto de Interés: {poi}\n"
        f"{now}\n"
        "¿Deseas continuar?"
    )
    buttons = [[KeyboardButton("✅ Sí"), KeyboardButton("❌ No")]]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    )
    return CONFIRM_SELECTION


#================================================================================================================================================================================
# ============================================================================ MANEJO DE CONFIRMACIÓN INICIAL ===================================================================
#================================================================================================================================================================================

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    response = update.message.text
    if response == "✅ Sí":
        await update.message.reply_text(
            "👥 Ahora selecciona un cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return await handle_cliente_selection(update, context)
    elif response == "❌ No":
        await update.message.reply_text("❌ Has cancelado la gestión.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        await update.message.reply_text("Por favor, selecciona '✅ Sí' o '❌ No'.")
        return CONFIRM_SELECTION


#=================================================================================================================================================================================
# =========================================================================== SELECCIÓN DE CLIENTE ==============================================================================
#================================================================================================================================================================================

async def handle_cliente_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Selecciona un cliente desde la tabla CLIENTES"""
    try:
        db = DatabaseManager()
        clientes = [row[0] for row in db.execute_query(
            'SELECT DISTINCT cliente FROM dbo.CLIENTES ORDER BY cliente')]
        if not clientes:
            await update.message.reply_text("ℹ️ No hay clientes registrados.")
            return ConversationHandler.END
        botones = []
        for i in range(0, len(clientes), 3):
            fila = clientes[i:i + 3]
            botones.append([KeyboardButton(c) for c in fila])
        botones.append(["🏠 INICIO"])
        await update.message.reply_text(
            "👥 *SELECCIONA UN CLIENTE:*",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(botones, resize_keyboard=True)
        )
        return SELECTING_CLIENTE
    except Exception as e:
        logger.error(f"Error al cargar clientes: {str(e)}")
        await update.message.reply_text("⚠️ Error al cargar clientes. Usa /start para reiniciar.")
        return SELECTING_CLIENTE


#=================================================================================================================================================================================
# ========================================================================== CONFIRMACIÓN FINAL ANTES DE FOTOS ===================================================================
#=================================================================================================================================================================================

async def handle_cliente_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el cliente y muestra confirmación final"""
    cliente = update.message.text
    if cliente == "🏠 INICIO":
        return await start(update, context)
    context.user_data['cliente'] = cliente
    nombre = context.user_data.get('nombre', 'No proporcionado')
    depto = context.user_data.get('departamento', 'No seleccionado')
    ciudad = context.user_data.get('ciudad', 'No seleccionada')
    poi = context.user_data.get('punto_interes', 'No seleccionado')
    now = datetime.now().strftime("📅 %d/%m/%Y - ⏰ %H:%M")
    summary = (
        "📄 *Resumen FINAL de tu selección:*\n"
        f"👤 Nombre: {nombre}\n"
        f"🏢 Departamento: {depto}\n"
        f"🏙️ Ciudad: {ciudad}\n"
        f"📍 Punto de Interés: {poi}\n"
        f"👥 Cliente: {cliente}\n"
        f"{now}\n"
        "¿Deseas continuar definitivamente?"
    )
    buttons = [[KeyboardButton("✅ Sí"), KeyboardButton("❌ No")]]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    )
    return FINAL_CONFIRMATION


#==================================================================================================================================================================================
# ===================================================================================== RECEPCIÓN DE FOTOS ========================================================================
#==================================================================================================================================================================================

async def show_final_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra mensaje final y permite recibir fotos"""
    response = update.message.text
    if response == "✅ Sí":
        await update.message.reply_text(
            "📷 Carga las fotos de tu gestión.\n"
            "Puedes enviar varias en un mismo mensaje.\n"
            "Escribe /continuar cuando hayas terminado.",
            reply_markup=ReplyKeyboardRemove()
        )
        return SELECTING_PHOTOS
    elif response == "❌ No":
        await update.message.reply_text(
            "❌ Has cancelado la gestión.\nUsa /start si deseas reiniciar.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("Por favor, selecciona '✅ Sí' o '❌ No'.")
        return FINAL_CONFIRMATION


#=====================================================================================================================================================================
# ========================================================================= MANEJO DE LAS FOTOS RECIBIDAS ============================================================
#=====================================================================================================================================================================

async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja y descarga fotos al momento, conservando solo versiones únicas"""
    if not update.message.photo:
        await update.message.reply_text("Por favor, envía una o más fotos.")
        return SELECTING_PHOTOS

    if 'fotos' not in context.user_data:
        context.user_data['fotos'] = {}

    new_photos = []

    for photo in update.message.photo:
        unique_id = photo.file_unique_id

        # Si ya fue guardada, saltar
        if unique_id in context.user_data['fotos']:
            continue

        try:
            # Seleccionar la foto de mayor resolución (última en la lista)
            file = await context.bot.get_file(photo.file_id)

            # Definir ruta local
            file_name = f"{unique_id}.jpg"  # Puedes usar .jpeg o .png también
            file_path = os.path.join(PHOTO_DIR, file_name)

            # Descargar foto
            await file.download_to_drive(file_path)

            # Guardar datos
            context.user_data['fotos'][unique_id] = {
                "file_id": photo.file_id,
                "file_path": file_path
            }

            new_photos.append(file_name)

        except Exception as e:
            logger.error(f"Error al descargar foto {unique_id}: {str(e)}")
            continue

    if new_photos:
        await update.message.reply_text(f"📥 {len(new_photos)} nueva(s) foto(s) descargada(s).")
    else:
        await update.message.reply_text("ℹ️ No se han añadido nuevas fotos.")

    return SELECTING_PHOTOS
#==============================================================================================================================================================================
# ======================================================================= MENSAJE FINAL Y OPCIONES FINALES ===================================================================
#==============================================================================================================================================================================

async def show_final_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra mensaje final con opción de guardar, reiniciar o cancelar"""
    await update.message.reply_text(
        "📷 Fotos cargadas con éxito.\n"
        "¿Qué deseas hacer ahora?"
    )
    buttons = [
        [KeyboardButton("💾 Guardar y finalizar")],
        [KeyboardButton("🔄 Cargar otra gestión en este punto")],
        [KeyboardButton("❌ Cancelar todo")]
    ]
    await update.message.reply_text(
        "📌 Elige una opción:",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    )
    return FINISH_MESSAGE


#==============================================================================================================================================================================
# =============================================================== MANEJO DE ACCIÓN FINAL: GUARDAR, REINICIAR O CANCELAR =======================================================
#==============================================================================================================================================================================

async def finish_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finaliza el proceso o inicia uno nuevo, guardando solo las fotos en FOTOS_TOTALES"""
    response = update.message.text

    if response == "💾 Guardar y finalizar":
        try:
            db = DatabaseManager()

            # Obtener fotos del contexto
            fotos = context.user_data.get('fotos', {})
            if not fotos:
                await update.message.reply_text("ℹ️ No hay fotos para guardar.")
                return FINISH_MESSAGE

            conn = db.get_connection()
            cursor = conn.cursor()

            # Insertar cada foto en la tabla FOTOS_TOTALES
            for data in fotos.values():
                file_path = data["file_path"]
                cursor.execute("""
                    INSERT INTO FOTOS_TOTALES (FILE_PATH, FECHA_REGISTRO)
                    VALUES (?, ?)
                """, (file_path, datetime.now()))

            conn.commit()
            conn.close()

            # Mensaje de éxito
            await update.message.reply_text(
                "✅ Fotos guardadas exitosamente.",
                reply_markup=ReplyKeyboardRemove()
            )

            # Opciones finales
            buttons = [
                [KeyboardButton("🔄 Cargar otra gestión")],
                [KeyboardButton("🔚 Finalizar conversación")]
            ]
            await update.message.reply_text(
                "📌 ¿Deseas cargar otra gestión o finalizar la conversación?",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            )
            return FINISH_MESSAGE

        except Exception as e:
            logger.error(f"Error al guardar las fotos: {str(e)}", exc_info=True)
            buttons = [[KeyboardButton("🔄 Reintentar"), KeyboardButton("❌ Cancelar")]]
            await update.message.reply_text(
                "⚠️ Ocurrió un error al guardar las fotos.\n"
                "¿Qué deseas hacer ahora?",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            )
            return FINISH_MESSAGE

    elif response == "🔄 Cargar otra gestión":
        # Limpiar fotos y volver a seleccionar cliente
        context.user_data.pop('fotos', None)
        return await handle_cliente_selection(update, context)

    elif response == "🔚 Finalizar conversación":
        await update.message.reply_text(
            "✅ Registro guardado correctamente.\n"
            "🔚 Proceso finalizado. Usa /start cuando necesites comenzar de nuevo.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    elif response == "🔄 Cargar otra gestión en este punto":
        context.user_data.pop('fotos', None)
        await update.message.reply_text(
            "🔄 Reiniciando gestión...\n"
            "👥 Ahora selecciona un cliente:",
            reply_markup=ReplyKeyboardRemove()
        )
        return SELECTING_CLIENTE

    elif response == "❌ Cancelar todo":
        await update.message.reply_text(
            "❌ Gestión cancelada. No se ha guardado ningún registro.\n"
            "Usa /start para comenzar de nuevo.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text("Por favor, selecciona una opción válida.")
        return FINISH_MESSAGE

#================================================================================================================================================================================
# ================================================================= FUNCIONES AUXILIARES: Volver, Ayuda, Cancelar, etc. =========================================================
#================================================================================================================================================================================

async def go_back_to_deptos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reinicia el flujo"""
    await update.message.reply_text("🔄 Reiniciando...", reply_markup=ReplyKeyboardRemove())
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela cualquier operación en curso"""
    await update.message.reply_text(
        "❌ Operación cancelada. Usa /start para comenzar de nuevo.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra ayuda sobre cómo usar el bot"""
    help_text = """
🤖 *Bot de Registro de Visitas* 🤖
Comandos disponibles:
/start - Inicia el proceso de registro
/cancel - Cancela el proceso actual
/help - Muestra esta ayuda
Flujo del bot:
1. Ingresa tu nombre
2. Selecciona departamento, ciudad y punto de interés
3. Confirma los datos
4. Selecciona un cliente
5. Envía fotos (todas las que necesites)
6. Confirma para finalizar
Durante el proceso puedes usar:
/continuar - Para pasar a la siguiente etapa
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "⚠️ Error inesperado. Por favor usa /start",
            reply_markup=ReplyKeyboardRemove()
        )


#==================================================================================================================================================================================
# ===================================================================== FUNCIÓN PRINCIPAL: INICIALIZACIÓN DEL BOT =================================================================
#==================================================================================================================================================================================

def main() -> None:
    """Inicia el bot"""
    application = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_departamentos)],
            SELECTING_DEPTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_depto_selection),
                MessageHandler(filters.Regex(r'^🏢 CAMBIAR DEPARTAMENTO$'), lambda u, c: start(u, c))
            ],
            SELECTING_CIUDAD: [
                MessageHandler(filters.Regex(r'^🏢 CAMBIAR DEPARTAMENTO$'), go_back_to_deptos),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ciudad_selection)
            ],
            SELECTING_POI: [
                MessageHandler(filters.Regex(r'^🏢 CAMBIAR DEPARTAMENTO$'), go_back_to_deptos),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_poi_selection),
            ],
            CONFIRM_SELECTION: [MessageHandler(filters.Regex(r'^(✅ Sí|❌ No)$'), handle_confirmation)],
            SELECTING_CLIENTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cliente_selected),
                MessageHandler(filters.Regex(r'^🏠 INICIO$'), start)
            ],
            FINAL_CONFIRMATION: [MessageHandler(filters.Regex(r'^(✅ Sí|❌ No)$'), show_final_message)],
            SELECTING_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_photos),
                CommandHandler('continuar', show_final_summary),
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               lambda u, c: u.message.reply_text("Envía fotos o usa /continuar"))
            ],
            FINISH_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_gestion)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_error_handler(error_handler)
    print("✅ Bot activo. Usa /start para iniciar.")
    application.run_polling()


#==================================================================================================================================================================================
# ============================================================================== EJECUCIÓN DEL BOT ================================================================================
#==================================================================================================================================================================================

if __name__ == '__main__':
    main()