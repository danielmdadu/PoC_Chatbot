# Chatbot de Maquinaria Ligera

Chatbot automatizado para calificación de leads de maquinaria ligera que integra Telegram + Groq LLM + HubSpot CRM + inventario CSV.

## Estructura del Proyecto

El proyecto está organizado en módulos para mejor mantenibilidad y escalabilidad:

```
PoC_Chatbot/
├── app.py                 # Archivo principal (punto de entrada)
├── config.py              # Configuración y variables de entorno
├── models.py              # Modelos de datos (Lead, InventoryItem, ConversationState)
├── inventory.py           # Gestión del inventario de maquinaria
├── hubspot.py             # Integración con HubSpot CRM
├── llm.py                 # Gestión del LLM (Groq)
├── conversation.py        # Gestión de conversaciones
├── telegram_bot.py        # Bot de Telegram
├── requirements.txt       # Dependencias del proyecto
├── inventario_maquinaria.csv  # Archivo de inventario
└── README.md              # Documentación
```

## Módulos

### `config.py`
- Configuración de logging
- Variables de entorno
- Validación de configuración

### `models.py`
- `ConversationState`: Estados de la conversación
- `Lead`: Modelo de datos para leads
- `InventoryItem`: Modelo de datos para items del inventario

### `inventory.py`
- `InventoryManager`: Clase para gestionar el inventario
- Carga desde CSV
- Búsqueda de equipos
- Filtrado por disponibilidad

### `hubspot.py`
- `HubSpotManager`: Clase para integración con HubSpot
- Creación y actualización de contactos
- Búsqueda de contactos existentes
- Sincronización de datos

### `llm.py`
- `LLMManager`: Clase para gestión del LLM (Groq)
- Generación de respuestas
- Prompts contextuales
- Respuestas de respaldo

### `conversation.py`
- `ConversationManager`: Clase para gestión de conversaciones
- Manejo de estados de conversación
- Procesamiento de mensajes
- Sincronización con HubSpot
- Estadísticas de conversaciones

### `telegram_bot.py`
- `TelegramBot`: Clase para el bot de Telegram
- Handlers de comandos y mensajes
- Integración con el gestor de conversaciones
- Comandos adicionales (/reset, /stats, /humano)

### `app.py`
- Punto de entrada de la aplicación
- Inicialización de componentes
- Orquestación de módulos

## Comandos del Bot

- `/start` - Inicia una nueva conversación
- `/humano` - Solicita contacto con un especialista
- `/reset` - Reinicia la conversación actual
- `/stats` - Muestra estadísticas del bot (solo administradores)

## Configuración

### Variables de Entorno

Crear un archivo `.env` con las siguientes variables:

```env
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
GROQ_API_KEY=tu_api_key_de_groq
HUBSPOT_ACCESS_TOKEN=tu_access_token_de_hubspot
INVENTORY_CSV_PATH=inventario_maquinaria.csv
```

### Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecutar el bot:
```bash
python app.py
```

## Flujo de Conversación

1. **Inicial**: Saludo y solicitud de nombre
2. **Nombre**: Captura del nombre del usuario
3. **Equipo**: Consulta sobre tipo de maquinaria
4. **Empresa**: Nombre de la empresa
5. **Teléfono**: Número de contacto
6. **Email**: Correo electrónico
7. **Ubicación**: Ciudad o ubicación
8. **Tipo de Uso**: Cliente final o distribuidor
9. **Completado**: Lead calificado y sincronizado con HubSpot

### Estados de Conversación

- `INITIAL`: Estado inicial, saluda y pide el nombre
- `WAITING_NAME`: Esperando que el usuario proporcione su nombre
- `WAITING_EQUIPMENT`: Esperando información sobre el equipo de interés
- `WAITING_COMPANY`: Esperando el nombre de la empresa
- `WAITING_PHONE`: Esperando número de teléfono
- `WAITING_EMAIL`: Esperando correo electrónico
- `WAITING_LOCATION`: Esperando ubicación
- `WAITING_USE_TYPE`: Esperando clasificación del tipo de cliente
- `COMPLETED`: Conversación completada

## Ventajas de la Estructura Modular

- **Separación de responsabilidades**: Cada módulo tiene una función específica
- **Mantenibilidad**: Fácil de mantener y actualizar
- **Testabilidad**: Cada módulo puede ser probado independientemente
- **Escalabilidad**: Fácil agregar nuevas funcionalidades
- **Reutilización**: Los módulos pueden ser reutilizados en otros proyectos
- **Legibilidad**: Código más limpio y fácil de entender

## Extensibilidad

Para agregar nuevas funcionalidades:

1. **Nuevos comandos**: Agregar handlers en `telegram_bot.py`
2. **Nuevos estados**: Extender `ConversationState` en `models.py`
3. **Nuevas integraciones**: Crear nuevos módulos siguiendo el patrón existente
4. **Nuevos modelos**: Agregar clases en `models.py` 