"""
Configuración del chatbot
"""

import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
HUBSPOT_ACCESS_TOKEN = os.getenv('HUBSPOT_ACCESS_TOKEN')
INVENTORY_CSV_PATH = os.getenv('INVENTORY_CSV_PATH', 'inventario_maquinaria.csv')

def validate_environment():
    """Valida que todas las variables de entorno requeridas estén presentes"""
    required_vars = ['TELEGRAM_BOT_TOKEN', 'GROQ_API_KEY', 'HUBSPOT_ACCESS_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Variables de entorno faltantes: {missing_vars}")
        return False
    
    return True 