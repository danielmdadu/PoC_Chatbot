"""
Gestión de conversaciones del chatbot
"""

from datetime import datetime
from typing import Dict
from models import Lead, ConversationState
from inventory import InventoryManager
from hubspot import HubSpotManager
from llm import LLMManager
from config import logger

class ConversationManager:
    def __init__(self, inventory_manager: InventoryManager, 
                 hubspot_manager: HubSpotManager,
                 llm_manager: LLMManager):
        self.inventory = inventory_manager
        self.hubspot = hubspot_manager
        self.llm = llm_manager
        self.conversations: Dict[str, Dict] = {}
    
    def get_conversation(self, telegram_id: str) -> Dict:
        """Obtiene o crea una conversación"""
        if telegram_id not in self.conversations:
            self.conversations[telegram_id] = {
                'state': ConversationState.INITIAL,
                'lead': Lead(telegram_id=telegram_id, created_at=datetime.now().isoformat()),
                'history': [],
                'inventory_results': []
            }
        return self.conversations[telegram_id]
    
    async def process_message(self, telegram_id: str, message: str) -> str:
        """Procesa un mensaje y genera respuesta"""
        conv = self.get_conversation(telegram_id)
        current_state = conv['state']
        lead = conv['lead']

        # Agregar mensaje del usuario al historial
        conv['history'].append({"role": "user", "content": message})
        
        # Procesar según el estado actual
        logger.info(f"Procesando mensaje en estado: {current_state.value}")
        if current_state == ConversationState.INITIAL:
            # En el estado inicial, solo cambiar a WAITING_NAME después de generar la respuesta
            pass

        elif current_state == ConversationState.WAITING_NAME:
            lead.name = await self.llm.extract_field(message, "name")
            logger.info(f"Nombre extraído: {lead.name}")
            if lead.name:
                conv['state'] = ConversationState.WAITING_EQUIPMENT
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_EQUIPMENT:
            lead.equipment_interest = await self.llm.extract_field(message, "equipment")
            logger.info(f"Equipo de interés extraído: {lead.equipment_interest}")
            if lead.equipment_interest:
                conv['inventory_results'] = self.inventory.search_equipment(message)
                conv['state'] = ConversationState.WAITING_PHONE
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_PHONE:
            lead.phone = await self.llm.extract_field(message, "phone")
            logger.info(f"Teléfono extraído: {lead.phone}")
            if lead.phone:
                conv['state'] = ConversationState.WAITING_EMAIL
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_EMAIL:
            lead.email = await self.llm.extract_field(message, "email")
            logger.info(f"Email extraído: {lead.email}")
            if lead.email:
                conv['state'] = ConversationState.WAITING_LOCATION
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_LOCATION:
            lead.location = await self.llm.extract_field(message, "location")
            logger.info(f"Ubicación extraída: {lead.location}")
            if lead.location:
                conv['state'] = ConversationState.WAITING_COMPANY
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_COMPANY:
            lead.company = await self.llm.extract_field(message, "company")
            logger.info(f"Empresa extraída: {lead.company}")
            if lead.company:
                conv['state'] = ConversationState.WAITING_USE_TYPE
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_USE_TYPE:
            # Clasificar tipo de cliente
            message_lower = message.lower()
            if any(word in message_lower for word in ['propio', 'uso', 'empresa', 'final']):
                lead.use_type = 'cliente_final'
            elif any(word in message_lower for word in ['reventa', 'renta', 'distribuir', 'vender']):
                lead.use_type = 'distribuidor'
            else:
                lead.use_type = ''
            if lead.use_type:
                conv['state'] = ConversationState.WAITING_MODEL
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_MODEL:
            # Intentar extraer el modelo específico
            lead.specific_model = await self.llm.extract_field(message, "equipment")
            logger.info(f"Modelo específico extraído: {lead.specific_model}")
            
            # Si no se extrajo con el LLM, usar el mensaje completo como modelo
            if not lead.specific_model:
                lead.specific_model = message.strip()
                logger.info(f"Usando mensaje completo como modelo: {lead.specific_model}")
            
            # Marcar como completado y generar cotización
            conv['state'] = ConversationState.COMPLETED
            await self._sync_to_hubspot(lead)
            # Generar cotización automáticamente
            quotation = self.generate_quotation(lead)
            conv['quotation'] = quotation

        # Si la conversación está completada, enviar cotización directamente
        if conv['state'] == ConversationState.COMPLETED and 'quotation' in conv:
            response = f"¡Perfecto! Aquí tienes tu cotización:\n\n{conv['quotation']}\n\nUn asesor se pondrá en contacto contigo pronto para dar seguimiento a tu solicitud. ¡Gracias por tu interés!"
        else:
            # Generar respuesta con LLM para otros estados
            response = await self.llm.generate_response(
                conv['history'], 
                conv['state'], 
                conv.get('inventory_results')
            )

        # Agregar respuesta al historial
        conv['history'].append({"role": "assistant", "content": response})

        # Cambiar estado después de generar respuesta en estado inicial
        if current_state == ConversationState.INITIAL:
            conv['state'] = ConversationState.WAITING_NAME
            logger.info(f"Estado cambiado de INITIAL a WAITING_NAME")

        # Limpiar historial si es muy largo
        if len(conv['history']) > 20:
            conv['history'] = conv['history'][-10:]

        return response
    
    async def _sync_to_hubspot(self, lead: Lead):
        """Sincroniza el lead con HubSpot"""
        try:
            lead.updated_at = datetime.now().isoformat()
            contact_id = await self.hubspot.create_or_update_contact(lead)
            if contact_id:
                lead.hubspot_contact_id = contact_id
                logger.info(f"Lead sincronizado exitosamente con HubSpot. Contact ID: {contact_id}")
            else:
                logger.warning(f"No se pudo sincronizar el lead con HubSpot para Telegram ID: {lead.telegram_id}")
        except Exception as e:
            logger.error(f"Error sincronizando con HubSpot: {e}")
    
    def reset_conversation(self, telegram_id: str):
        """Reinicia una conversación"""
        if telegram_id in self.conversations:
            del self.conversations[telegram_id]
            logger.info(f"Conversación reiniciada para usuario {telegram_id}")
    
    def get_conversation_stats(self) -> Dict:
        """Obtiene estadísticas de las conversaciones"""
        total_conversations = len(self.conversations)
        active_conversations = sum(
            1 for conv in self.conversations.values() 
            if conv['state'] != ConversationState.COMPLETED
        )
        completed_conversations = sum(
            1 for conv in self.conversations.values() 
            if conv['state'] == ConversationState.COMPLETED
        )
        
        return {
            'total': total_conversations,
            'active': active_conversations,
            'completed': completed_conversations
        }
    
    def generate_quotation(self, lead: Lead) -> str:
        """Genera una cotización simple con la información del lead"""
        quotation = f"""
📋 **COTIZACIÓN**

👤 **Cliente:** {lead.name or 'No especificado'}
🏢 **Empresa:** {lead.company or 'No especificada'}
📞 **Teléfono:** {lead.phone or 'No especificado'}
📧 **Email:** {lead.email or 'No especificado'}
📍 **Ubicación:** {lead.location or 'No especificada'}

🔧 **Equipo de interés:** {lead.equipment_interest or 'No especificado'}
📋 **Modelo específico:** {lead.specific_model or 'No especificado'}
👥 **Tipo de cliente:** {lead.use_type or 'No especificado'}

💰 **PRECIO:** $10,000.00 MXN

---
*Cotización generada automáticamente*
*Precio fijo aplicable a todos los equipos*
        """
        return quotation.strip() 