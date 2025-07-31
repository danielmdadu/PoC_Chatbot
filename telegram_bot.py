"""
Bot de Telegram para el chatbot
"""

import logging
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
        self.application.add_handler(CommandHandler("humano", self.human_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el comando /start"""
        telegram_id = str(update.effective_user.id)
        response = await self.conversation_manager.process_message(
            telegram_id, 
            "Hola, quiero información sobre maquinaria"
        )
        await update.message.reply_text(response)
    
    async def human_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para escalar a humano"""
        await update.message.reply_text(
            "Perfecto, te voy a conectar con uno de nuestros especialistas. "
            "Un miembro de nuestro equipo se pondrá en contacto contigo pronto. "
            "¡Gracias por tu interés!"
        )
        # Aquí podrías enviar una notificación al equipo de ventas
        logger.info(f"Usuario {update.effective_user.id} solicitó contacto humano")
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para reiniciar conversación"""
        telegram_id = str(update.effective_user.id)
        self.conversation_manager.reset_conversation(telegram_id)
        await update.message.reply_text(
            "Conversación reiniciada. Puedes comenzar de nuevo con /start"
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para mostrar estadísticas de conversaciones guardadas"""
        stats = self.conversation_manager.get_saved_conversations_stats()
        current_stats = self.conversation_manager.get_conversation_stats()
        
        message = f"""📊 **ESTADÍSTICAS DEL BOT**

💾 **Conversaciones Guardadas:**
- Archivos totales: {stats['total_files']}
- Tamaño total: {stats['total_size_mb']} MB

🔄 **Conversaciones Activas:**
- Total: {current_stats['total']}
- Activas: {current_stats['active']}
- Completadas: {current_stats['completed']}

📁 **Últimos archivos:**
"""
        
        for file in stats['files'][:5]:  # Mostrar solo los últimos 5
            message += f"- {file}\n"
        
        await update.message.reply_text(message)
    
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