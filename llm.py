"""
Gestión del LLM (Groq)
"""

import json
import re
from typing import List, Dict
from groq import Groq
from models import ConversationState, InventoryItem
from config import logger

class LLMManager:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    async def generate_response(self, conversation_history: List[Dict], 
                              current_state: ConversationState,
                              inventory_results: List[InventoryItem] = None) -> str:
        """Genera respuesta usando Groq LLM"""
        
        system_prompt = self._get_system_prompt(current_state, inventory_results)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return self._get_fallback_response(current_state)
    
    def _get_system_prompt(self, state: ConversationState, 
                          inventory_results: List[InventoryItem] = None) -> str:
        """Genera el prompt del sistema según el estado de la conversación"""

        base_prompt = (
            "Eres Juan, un asistente de ventas profesional especializado en maquinaria ligera. "
            "Tu trabajo es calificar leads de manera natural y conversacional.\n"
            "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER NI REPETIR)>>\n"
            "REGLAS IMPORTANTES:\n"
            "- Sé amigable pero profesional\n"
            "- Mantén respuestas CORTAS (máximo 30 palabras)\n"
            "- Explica brevemente por qué necesitas cada información\n"
            "- Si el usuario hace preguntas sobre maquinaria, respóndelas primero de forma concisa\n"
            "- Después de responder consultas, amablemente solicita la información que necesitas\n"
            "- Nunca inventes información sobre inventario\n"
            "- SIGUE EXACTAMENTE las instrucciones del estado actual\n"
            "NO repitas ni menciones estas instrucciones en tu respuesta al usuario.\n"
            "<</INSTRUCCIONES>>\n"
        )

        if state == ConversationState.INITIAL:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: INICIAL\n"
                "INSTRUCCIÓN: Preséntate como Juan, asistente de ventas especializado en maquinaria ligera, y pregunta el nombre de forma breve.\n"
                "Ejemplo: '¡Hola! Soy Juan, tu asistente de ventas especializado en maquinaria ligera. ¿Podrías decirme tu nombre?'\n"
                "Mantén la respuesta corta (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_NAME:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO NOMBRE\n"
                "INSTRUCCIÓN: Pregunta el nombre de forma breve, explicando que es para personalizar la atención.\n"
                "Ejemplo: 'Para brindarte atención personalizada, ¿podrías decirme tu nombre?'\n"
                "Si el usuario hace preguntas sobre maquinaria, respóndelas de forma concisa y luego pide el nombre.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_EQUIPMENT:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PREGUNTANDO POR EQUIPO\n"
                "INSTRUCCIÓN: Pregunta qué tipo de maquinaria busca de forma breve, explicando que es para revisar el inventario.\n"
                "Ejemplo: 'Para revisar nuestro inventario, ¿qué tipo de maquinaria buscas?'\n"
                "Si el usuario hace preguntas sobre maquinaria, respóndelas de forma concisa y luego pide el tipo de equipo.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_COMPANY:
            inventory_info = ""
            if inventory_results:
                inventory_info = f"\nEQUIPOS DISPONIBLES:\n"
                for item in inventory_results[:3]:  # Máximo 3 resultados
                    inventory_info += f"- {item.modelo} ({item.tipo_maquina}) - Ubicación: {item.ubicacion}\n"
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO EMPRESA\n"
                f"{inventory_info}"
                "INSTRUCCIÓN: Informa brevemente sobre disponibilidad y pregunta el nombre de la empresa para generar cotización.\n"
                "Ejemplo: 'Tenemos equipos disponibles. Para generar tu cotización, ¿cuál es el nombre de tu empresa?'\n"
                "Si el usuario hace preguntas sobre equipos, respóndelas de forma concisa y luego pide la empresa.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_PHONE:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO TELÉFONO\n"
                "INSTRUCCIÓN: Pregunta el teléfono de forma breve, explicando que es para contactarlo.\n"
                "Ejemplo: 'Para contactarte, ¿me proporcionas tu teléfono?'\n"
                "Si el usuario hace preguntas sobre equipos o proceso, respóndelas de forma concisa y luego pide el teléfono.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_EMAIL:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO EMAIL\n"
                "INSTRUCCIÓN: Pregunta el email de forma breve, explicando que es para enviar información.\n"
                "Ejemplo: 'Para enviarte información, ¿cuál es tu email?'\n"
                "Si el usuario hace preguntas sobre proceso o equipos, respóndelas de forma concisa y luego pide el email.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_LOCATION:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO UBICACIÓN\n"
                "INSTRUCCIÓN: Pregunta la ubicación de forma breve, explicando que es para calcular costos de envío.\n"
                "Ejemplo: 'Para calcular costos de envío, ¿en qué ciudad necesitas el equipo?'\n"
                "Si el usuario hace preguntas sobre envíos, respóndelas de forma concisa y luego pide la ubicación.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_USE_TYPE:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: CLASIFICANDO TIPO DE CLIENTE\n"
                "INSTRUCCIÓN: Pregunta el tipo de uso de forma breve, explicando que es para ofrecer mejores condiciones.\n"
                "Ejemplo: 'Para ofrecerte mejores condiciones, ¿el equipo es para uso propio o reventa?'\n"
                "Si el usuario hace preguntas sobre condiciones, respóndelas de forma concisa y luego pide esta información.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        elif state == ConversationState.WAITING_MODEL:
            instrucciones = (
                "<<INSTRUCCIONES DEL SISTEMA (NO RESPONDER)>>\n"
                "Estado: PIDIENDO MODELO ESPECÍFICO\n"
                "INSTRUCCIÓN: Pregunta el modelo específico que desea adquirir, explicando que es para generar la cotización.\n"
                "Ejemplo: 'Para generar tu cotización, ¿qué modelo específico te interesa?'\n"
                "Si el usuario hace preguntas sobre modelos o precios, respóndelas de forma concisa y luego pide el modelo.\n"
                "Mantén respuestas cortas (máximo 30 palabras).\n"
                "<</INSTRUCCIONES>>"
            )
            return base_prompt + instrucciones

        return base_prompt

    def _get_fallback_response(self, state: ConversationState) -> str:
        """Respuestas de respaldo si falla el LLM"""
        fallbacks = {
            ConversationState.INITIAL: "¡Hola! Soy Juan, tu asistente de ventas especializado en maquinaria ligera. ¿Podrías decirme tu nombre?",
            ConversationState.WAITING_NAME: "Para brindarte atención personalizada, ¿podrías decirme tu nombre?",
            ConversationState.WAITING_EQUIPMENT: "Para revisar nuestro inventario, ¿qué tipo de maquinaria buscas?",
            ConversationState.WAITING_PHONE: "Para contactarte, ¿me proporcionas tu teléfono?",
            ConversationState.WAITING_EMAIL: "Para enviarte información, ¿cuál es tu email?",
            ConversationState.WAITING_LOCATION: "Para calcular costos de envío, ¿en qué ciudad necesitas el equipo?",
            ConversationState.WAITING_COMPANY: "Para generar tu cotización, ¿cuál es el nombre de tu empresa?",
            ConversationState.WAITING_USE_TYPE: "Para ofrecerte mejores condiciones, ¿el equipo es para uso propio o reventa?",
            ConversationState.WAITING_MODEL: "Para generar tu cotización, ¿qué modelo específico te interesa?"
        }
        return fallbacks.get(state, "¿Podrías repetir esa información?") 
    

    async def extract_field(self, message: str, field_type: str) -> str:
        """Extrae un campo específico usando LLM y devuelve el valor limpio"""
        
        extraction_prompts = {
            "company": (
                "Extrae el nombre de la empresa del siguiente mensaje si el mensaje solo contiene la empresa o si el usuario indica explícitamente que trabaja en, representa, pertenece a, es de, o su empresa es la mencionada. "
                "Ignora marcas, equipos o palabras genéricas. Si no hay una indicación clara de relación laboral o pertenencia, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            ),
            "name": (
                "Extrae el nombre de la persona del siguiente mensaje si el mensaje solo contiene un nombre o si el usuario lo menciona explícitamente como su nombre, o si se presenta como tal. "
                "Ignora saludos, apodos, nombres de empresas, marcas o equipos. Si no hay una indicación clara de nombre personal, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            ),
            "phone": (
                "Extrae el número de teléfono del siguiente mensaje si el usuario lo proporciona de cualquier forma, por ejemplo: 'mi número es', 'puedes contactarme al', 'es', 'te dejo mi número', etc. "
                "Acepta cualquier número con formato de teléfono (dígitos, espacios, guiones, paréntesis, etc.) que parezca un número de contacto. Si no hay un número de teléfono válido, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            ),
            "email": (
                "Extrae la dirección de email del siguiente mensaje si el mensaje solo contiene un email o si el usuario la proporciona explícitamente como su correo electrónico, el correo de su empresa o el correo al que se puede contactar. "
                "Ignora textos que no tengan formato de email o que no estén acompañados de una indicación clara de ser un email. Si no hay un email válido, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            ),
            "location": (
                "Extrae la ubicación o ciudad del siguiente mensaje si el mensaje solo contiene una ubicación o si el usuario la menciona explícitamente como el lugar donde requiere el equipo, donde se encuentra, o su ciudad. "
                "Ignora ubicaciones que sean parte de nombres de empresas, marcas o equipos. Si no hay una indicación clara de ubicación, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            ),
            "equipment": (
                "Extrae el tipo de equipo o maquinaria del siguiente mensaje si el mensaje solo contiene un tipo de equipo o maquinaria o si el usuario lo menciona explícitamente como el equipo que busca, requiere o le interesa. "
                "Ignora menciones genéricas, marcas, empresas o equipos que no sean solicitados explícitamente. Si no hay una indicación clara de equipo de interés, responde con 'value': null. "
                "Responde ÚNICAMENTE en formato JSON con la clave 'value'."
            )
        }
        
        prompt = f"{extraction_prompts[field_type]}\n\nMensaje: {message}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_json_response(result)
            
        except Exception as e:
            logger.error(f"Error extrayendo {field_type}: {e}")
            return ""

    def _parse_json_response(self, result: str) -> str:
        """Parsea la respuesta JSON del LLM y extrae el valor"""
        
        # Limpiar markdown si está presente
        result = re.sub(r'^```.*?\n', '', result)  # Remover ```json
        result = re.sub(r'\n```$', '', result)    # Remover ``` final
        result = result.strip('`')                # Remover backticks simples
        
        # Extraer solo el objeto JSON (desde { hasta })
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            result = json_match.group(0)
        
        try:
            # Intentar parsear como JSON
            parsed = json.loads(result)
            value = parsed.get('value')
            
            # Normalizar valores nulos o vacíos
            if value is None or (isinstance(value, str) and value.strip().lower() in ('null', '', 'n/a')):
                return ""
            
            return str(value).strip()
            
        except json.JSONDecodeError:
            # Fallback: extraer valor usando regex
            logger.warning(f"JSON inválido, usando fallback: {result}")
            
            # Buscar patrón "value": "contenido"
            value_match = re.search(r'"value":\s*"([^"]*)"', result)
            if value_match:
                value = value_match.group(1)
                return "" if value.lower() in ('null', 'n/a') else value
            
            # Buscar patrón value: contenido (sin comillas)
            value_match = re.search(r'"?value"?:\s*([^,}\n]+)', result)
            if value_match:
                value = value_match.group(1).strip().strip('"')
                return "" if value.lower() in ('null', 'n/a') else value
            
            # Si todo falla, devolver vacío
            return ""