"""
Chatbot automatizado para calificación de leads de maquinaria ligera
Integra Telegram + Groq LLM + HubSpot CRM + inventario CSV
"""

from inventory import InventoryManager
from hubspot import HubSpotManager
from llm import LLMManager
from conversation import ConversationManager
from telegram_bot import TelegramBot
from config import (
    TELEGRAM_BOT_TOKEN, 
    GROQ_API_KEY, 
    HUBSPOT_ACCESS_TOKEN, 
    INVENTORY_CSV_PATH,
    validate_environment,
    logger
)

def main():
    """Función principal"""
    # Validar variables de entorno
    if not validate_environment():
        return
    
    try:
        # Inicializar componentes
        inventory_manager = InventoryManager(INVENTORY_CSV_PATH)
        hubspot_manager = HubSpotManager(HUBSPOT_ACCESS_TOKEN)
        llm_manager = LLMManager(GROQ_API_KEY)
        
        conversation_manager = ConversationManager(
            inventory_manager,
            hubspot_manager, 
            llm_manager
        )
        
        # Crear y ejecutar bot
        bot = TelegramBot(TELEGRAM_BOT_TOKEN, conversation_manager)
        bot.run()
        
    except Exception as e:
        logger.error(f"Error iniciando la aplicación: {e}")

if __name__ == "__main__":
    main()