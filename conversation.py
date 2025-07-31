"""
Gestión de conversaciones del chatbot
"""

from datetime import datetime
from typing import Dict, List
from models import Lead, ConversationState
from inventory import InventoryManager, InventoryItem
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
            # Extraer información del equipo
            equipment_info = await self.llm.extract_field(message, "equipment")
            logger.info(f"Información de equipo extraída: {equipment_info}")
            
            if equipment_info:
                lead.equipment_interest = equipment_info
                
                # Realizar búsqueda en inventario
                inventory_results = self.inventory.search_equipment(message)
                conv['inventory_results'] = inventory_results
                
                # Si no hay resultados, intentar búsqueda más amplia
                if not inventory_results:
                    # Buscar por tipo de máquina
                    type_results = self.inventory.get_items_by_type(equipment_info)
                    if type_results:
                        conv['inventory_results'] = type_results
                        logger.info(f"Búsqueda por tipo encontrada: {len(type_results)} resultados")
                    else:
                        # Buscar por marca
                        brand_results = self.inventory.get_items_by_brand(equipment_info)
                        if brand_results:
                            conv['inventory_results'] = brand_results
                            logger.info(f"Búsqueda por marca encontrada: {len(brand_results)} resultados")
                
                logger.info(f"Resultados de inventario: {len(conv['inventory_results'])} items")
                conv['state'] = ConversationState.WAITING_COMPANY
                await self._sync_to_hubspot(lead)

        elif current_state == ConversationState.WAITING_COMPANY:
            lead.company = await self.llm.extract_field(message, "company")
            logger.info(f"Empresa extraída: {lead.company}")
            if lead.company:
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
                conv['state'] = ConversationState.COMPLETED
                await self._sync_to_hubspot(lead)

        # Generar respuesta con LLM
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
    
    async def handle_inventory_query(self, telegram_id: str, message: str) -> str:
        """Maneja consultas específicas sobre el inventario"""
        conv = self.get_conversation(telegram_id)
        
        # Agregar mensaje del usuario al historial
        conv['history'].append({"role": "user", "content": message})
        
        # Realizar búsqueda en inventario
        inventory_results = self.inventory.search_equipment(message)
        conv['inventory_results'] = inventory_results
        
        # Si no hay resultados, intentar búsquedas más específicas
        if not inventory_results:
            # Buscar por tipo de máquina
            type_results = self.inventory.get_items_by_type(message)
            if type_results:
                conv['inventory_results'] = type_results
                logger.info(f"Búsqueda por tipo encontrada: {len(type_results)} resultados")
            else:
                # Buscar por marca
                brand_results = self.inventory.get_items_by_brand(message)
                if brand_results:
                    conv['inventory_results'] = brand_results
                    logger.info(f"Búsqueda por marca encontrada: {len(brand_results)} resultados")
                else:
                    # Buscar por ubicación
                    location_results = self.inventory.get_items_by_location(message)
                    if location_results:
                        conv['inventory_results'] = location_results
                        logger.info(f"Búsqueda por ubicación encontrada: {len(location_results)} resultados")
        
        # Cambiar estado temporalmente para la consulta
        original_state = conv['state']
        conv['state'] = ConversationState.INVENTORY_QUERY
        
        # Generar respuesta con información del inventario
        response = await self.llm.generate_response(
            conv['history'], 
            conv['state'], 
            conv.get('inventory_results')
        )
        
        # Agregar respuesta al historial
        conv['history'].append({"role": "assistant", "content": response})
        
        # Restaurar estado original
        conv['state'] = original_state
        
        return response
    
    def get_inventory_summary(self) -> Dict:
        """Obtiene un resumen del inventario"""
        return self.inventory.get_inventory_summary()
    
    def search_inventory_by_criteria(self, criteria: Dict) -> List[InventoryItem]:
        """Busca en el inventario por criterios específicos"""
        results = []
        
        if 'tipo' in criteria:
            results = self.inventory.get_items_by_type(criteria['tipo'])
        elif 'marca' in criteria:
            results = self.inventory.get_items_by_brand(criteria['marca'])
        elif 'ubicacion' in criteria:
            results = self.inventory.get_items_by_location(criteria['ubicacion'])
        elif 'query' in criteria:
            results = self.inventory.search_equipment(criteria['query'])
        
        return results
    
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