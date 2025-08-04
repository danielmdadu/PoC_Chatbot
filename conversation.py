"""
Gestión de conversaciones del chatbot
"""

import os
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
            
            # Guardar conversación completada
            self._save_conversation_to_file(telegram_id, conv)
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
            # Guardar conversación actual antes de reiniciar
            conv = self.conversations[telegram_id]
            if conv['history']:  # Solo guardar si hay historial
                self._save_conversation_to_file(telegram_id, conv)
                logger.info(f"Conversación guardada antes del reset para usuario {telegram_id}")
            
            # Reiniciar conversación
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
📋 COTIZACIÓN

👤 Cliente: {lead.name or 'No especificado'}
🏢 Empresa: {lead.company or 'No especificada'}
📞 Teléfono: {lead.phone or 'No especificado'}
📧 Email: {lead.email or 'No especificado'}
📍 Ubicación: {lead.location or 'No especificada'}

🔧 Equipo de interés: {lead.equipment_interest or 'No especificado'}
📋 Modelo específico: {lead.specific_model or 'No especificado'}
👥 Tipo de cliente: {lead.use_type or 'No especificado'}

💰 PRECIO: $10,000.00 MXN

---
Cotización generada automáticamente
Precio fijo aplicable a todos los equipos
        """
        return quotation.strip()
    
    def _save_conversation_to_file(self, telegram_id: str, conv: Dict):
        """Guarda la conversación en un archivo de texto"""
        try:
            # Crear directorio si no existe
            os.makedirs("conversaciones", exist_ok=True)
            
            # Generar nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversaciones/conversacion_{telegram_id}_{timestamp}.txt"
            
            # Obtener información del lead
            lead = conv['lead']
            
            # Crear contenido del archivo
            content = f"""CONVERSACIÓN DE TELEGRAM
========================

📱 ID de Telegram: {telegram_id}
📅 Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
🔄 Estado: {conv['state'].value}

👤 INFORMACIÓN DEL CLIENTE:
- Nombre: {lead.name or 'No especificado'}
- Empresa: {lead.company or 'No especificada'}
- Teléfono: {lead.phone or 'No especificado'}
- Email: {lead.email or 'No especificado'}
- Ubicación: {lead.location or 'No especificada'}
- Equipo de interés: {lead.equipment_interest or 'No especificado'}
- Modelo específico: {lead.specific_model or 'No especificado'}
- Tipo de cliente: {lead.use_type or 'No especificado'}

💬 HISTORIAL DE CONVERSACIÓN:
"""
            
            # Agregar historial de conversación
            for i, msg in enumerate(conv['history'], 1):
                role = "👤 Usuario" if msg['role'] == 'user' else "🤖 Juan (Bot)"
                content += f"\n{i}. {role}:\n{msg['content']}\n"
            
            # Agregar información de inventario si existe
            if conv.get('inventory_results'):
                content += f"\n🔧 RESULTADOS DE INVENTARIO:\n"
                for item in conv['inventory_results']:
                    content += f"- {item.modelo} ({item.tipo_maquina}) - Ubicación: {item.ubicacion}\n"
            
            # Agregar cotización si existe
            if conv.get('quotation'):
                content += f"\n📋 COTIZACIÓN GENERADA:\n{conv['quotation']}\n"
            
            # Escribir archivo
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Conversación guardada en: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error guardando conversación: {e}")
            return None
    
    def _get_conversation_filename(self, telegram_id: str) -> str:
        """Genera el nombre del archivo para una conversación"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"conversaciones/conversacion_{telegram_id}_{timestamp}.txt"
    
    def get_saved_conversations_stats(self) -> Dict:
        """Obtiene estadísticas de las conversaciones guardadas en archivos"""
        try:
            if not os.path.exists("conversaciones"):
                return {"total_files": 0, "total_size_mb": 0, "files": []}
            
            files = [f for f in os.listdir("conversaciones") if f.endswith('.txt')]
            total_size = sum(os.path.getsize(os.path.join("conversaciones", f)) for f in files)
            
            return {
                "total_files": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": sorted(files, reverse=True)[:10]  # Últimos 10 archivos
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de archivos: {e}")
            return {"total_files": 0, "total_size_mb": 0, "files": []} 