"""
Bot de Telegram para el chatbot
"""

from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters
from conversation import ConversationManager
from config import logger

class TelegramBot:
    def __init__(self, token: str, conversation_manager: ConversationManager):
        self.token = token
        self.conversation_manager = conversation_manager
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Configura los handlers del bot"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el comando /start"""
        telegram_id = str(update.effective_user.id)
        response = await self.conversation_manager.process_message(
            telegram_id, 
            "Hola, quiero información sobre maquinaria"
        )
        await update.message.reply_text(response)
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para reiniciar conversación"""
        telegram_id = str(update.effective_user.id)
        await self.conversation_manager.reset_conversation_with_new_contact(telegram_id)
        await update.message.reply_text(
            "Conversación reiniciada. Se ha creado un nuevo contacto en el CRM. Puedes comenzar de nuevo con /start"
        )
     
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para mensajes de texto"""
        telegram_id = str(update.effective_user.id)
        message = update.message.text
        
        try:
            response = await self.conversation_manager.process_message(telegram_id, message)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await update.message.reply_text(
                "Disculpa, hubo un problema técnico. ¿Podrías repetir tu mensaje?"
            )
    
    def run(self):
        """Inicia el bot"""
        logger.info("Iniciando bot de Telegram...")
        self.application.run_polling()
    
    def stop(self):
        """Detiene el bot"""
        logger.info("Deteniendo bot de Telegram...")
        self.application.stop() 