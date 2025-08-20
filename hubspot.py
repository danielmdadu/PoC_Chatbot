"""
Integración con HubSpot CRM
"""

import httpx
import requests
import os
from typing import Dict, Optional, Callable, Any
from models import Lead
from config import logger


class HubSpotManager:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        # Para refresh token
        self.refresh_token = os.getenv("HUBSPOT_REFRESH_TOKEN")
        self.client_id = os.getenv("HUBSPOT_CLIENT_ID")
        self.client_secret = os.getenv("HUBSPOT_CLIENT_SECRET")

    async def _refresh_access_token(self) -> bool:
        """Obtiene un nuevo access token usando el refresh token y actualiza self.access_token y self.headers"""
        url = "https://api.hubapi.com/oauth/v1/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            response = requests.post(url, data=data, headers=headers)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                logger.info("Nuevo access token de HubSpot obtenido correctamente.")
                return True
            else:
                logger.error(f"Error al refrescar token de HubSpot: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Excepción al refrescar token de HubSpot: {e}")
            return False

    async def _with_token_refresh(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Ejecuta una función que hace request a HubSpot. Si falla por token, refresca y reintenta una vez."""
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Token de HubSpot expirado. Intentando refrescar...")
                refreshed = await self._refresh_access_token()
                if refreshed:
                    # Reintentar la función con el nuevo token
                    return await func(*args, **kwargs)
            raise
        except Exception as e:
            # Si la función interna ya maneja el error, solo lo relanzamos
            raise
    
    async def create_or_update_contact(self, lead: Lead) -> Optional[str]:
        """Crea o actualiza un contacto en HubSpot, refrescando el token si es necesario"""
        async def _core():
            # Preparar propiedades del contacto
            properties = {
                "telegram_id": lead.telegram_id,
                "telegram_lead": "true",
                "lifecyclestage": "lead"
            }
            if lead.name:
                properties["firstname"] = lead.name
            if lead.company:
                properties["empresa_asociada"] = lead.company
            if lead.phone:
                properties["phone"] = lead.phone
            if lead.email:
                properties["email"] = lead.email
            if lead.location:
                properties["city"] = lead.location
            if lead.equipment_interest:
                properties["equipo_interesado"] = lead.equipment_interest
            if lead.use_type:
                properties["tipo_lead"] = lead.use_type
            logger.info(f"Preparando contacto para HubSpot - Telegram ID: {lead.telegram_id}")
            logger.info(f"Propiedades a enviar: {properties}")
            # Intentar actualizar contacto existente primero
            if lead.hubspot_contact_id:
                result = await self._update_contact(lead.hubspot_contact_id, properties)
                if result:
                    return result
            # Buscar contacto existente por telegram_id
            existing_contact = await self._find_contact_by_telegram_id(lead.telegram_id)
            if existing_contact:
                result = await self._update_contact(existing_contact, properties)
                if result:
                    return result
            # Crear nuevo contacto
            logger.info("Creando nuevo contacto en HubSpot")
            return await self._create_contact(properties)
        try:
            return await self._with_token_refresh(_core)
        except Exception as e:
            logger.error(f"Error en HubSpot: {e}")
            return None
    
    async def create_new_contact(self, lead: Lead) -> Optional[str]:
        """Crea un nuevo contacto en HubSpot sin verificar si existe uno previo"""
        async def _core():
            # Preparar propiedades del contacto
            properties = {
                "telegram_id": lead.telegram_id,
                "telegram_lead": "true",
                "lifecyclestage": "lead"
            }
            if lead.name:
                properties["firstname"] = lead.name
            if lead.company:
                properties["empresa_asociada"] = lead.company
            if lead.phone:
                properties["phone"] = lead.phone
            if lead.email:
                properties["email"] = lead.email
            if lead.location:
                properties["city"] = lead.location
            if lead.equipment_interest:
                properties["equipo_interesado"] = lead.equipment_interest
            if lead.use_type:
                properties["tipo_lead"] = lead.use_type
            
            logger.info(f"Creando nuevo contacto en HubSpot para reset - Telegram ID: {lead.telegram_id}")
            logger.info(f"Propiedades a enviar: {properties}")
            
            return await self._create_contact(properties)
        
        try:
            return await self._with_token_refresh(_core)
        except Exception as e:
            logger.error(f"Error creando nuevo contacto en HubSpot: {e}")
            return None
    
    async def _create_contact(self, properties: Dict) -> Optional[str]:
        """Crea un nuevo contacto"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self.headers,
                json={"properties": properties}
            )
            if response.status_code == 201:
                data = response.json()
                logger.info(f"Contacto creado exitosamente: {data['id']}")
                logger.info(f"Propiedades del contacto creado: {properties}")
                return data['id']
            elif response.status_code == 401:
                # Token expirado, lanzar para que _with_token_refresh lo maneje
                raise httpx.HTTPStatusError("Token expirado", request=response.request, response=response)
            else:
                logger.error(f"Error creando contacto: {response.status_code}")
                logger.error(f"Respuesta de HubSpot: {response.text}")
                logger.error(f"Propiedades que se intentaron enviar: {properties}")
                return None
    
    async def _update_contact(self, contact_id: str, properties: Dict) -> Optional[str]:
        """Actualiza un contacto existente"""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                headers=self.headers,
                json={"properties": properties}
            )
            if response.status_code == 200:
                logger.info(f"Contacto actualizado exitosamente: {contact_id}")
                logger.info(f"Propiedades actualizadas: {properties}")
                return contact_id
            elif response.status_code == 401:
                # Token expirado, lanzar para que _with_token_refresh lo maneje
                raise httpx.HTTPStatusError("Token expirado", request=response.request, response=response)
            else:
                logger.error(f"Error actualizando contacto {contact_id}: {response.status_code}")
                logger.error(f"Respuesta de HubSpot: {response.text}")
                logger.error(f"Propiedades que se intentaron actualizar: {properties}")
                return None
    
    async def _find_contact_by_telegram_id(self, telegram_id: str) -> Optional[str]:
        """Busca un contacto por telegram_id"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "telegram_id",
                            "operator": "EQ",
                            "value": telegram_id
                        }]
                    }]
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    return data['results'][0]['id']
                return None
            elif response.status_code == 401:
                # Token expirado, lanzar para que _with_token_refresh lo maneje
                raise httpx.HTTPStatusError("Token expirado", request=response.request, response=response)
            return None