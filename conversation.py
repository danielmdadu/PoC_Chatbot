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
                conv['inventory_results'] = self.inventory.search_equipment()
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

        # Si la conversación está completada, enviar mensaje de despedida
        if conv['state'] == ConversationState.COMPLETED:
            response = f"Un asesor se pondrá en contacto contigo pronto para dar seguimiento a tu solicitud. ¡Gracias por tu interés!"
            
            # TODO: Guardar conversación completada
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
    
    async def reset_conversation_with_new_contact(self, telegram_id: str):
        """Reinicia una conversación y crea un nuevo contacto en HubSpot"""
        if telegram_id in self.conversations:
            # Reiniciar conversación
            del self.conversations[telegram_id]
            logger.info(f"Conversación reiniciada para usuario {telegram_id}")
        
        # Crear nueva conversación con nuevo lead
        new_lead = Lead(telegram_id=telegram_id, created_at=datetime.now().isoformat())
        
        # Crear nuevo contacto en HubSpot
        try:
            contact_id = await self.hubspot.create_new_contact(new_lead)
            if contact_id:
                new_lead.hubspot_contact_id = contact_id
                logger.info(f"Nuevo contacto creado en HubSpot para reset. Contact ID: {contact_id}")
            else:
                logger.warning(f"No se pudo crear nuevo contacto en HubSpot para reset. Telegram ID: {telegram_id}")
        except Exception as e:
            logger.error(f"Error creando nuevo contacto en HubSpot para reset: {e}")
        
        # Inicializar nueva conversación
        self.conversations[telegram_id] = {
            'state': ConversationState.INITIAL,
            'lead': new_lead,
            'history': [],
            'inventory_results': []
        }
        logger.info(f"Nueva conversación inicializada para usuario {telegram_id} con nuevo contacto en HubSpot")