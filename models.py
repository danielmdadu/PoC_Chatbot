"""
Modelos de datos para el chatbot
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime

class ConversationState(Enum):
    INITIAL = "initial"
    WAITING_NAME = "waiting_name"
    WAITING_EQUIPMENT = "waiting_equipment"
    WAITING_COMPANY = "waiting_company"
    WAITING_PHONE = "waiting_phone"
    WAITING_EMAIL = "waiting_email"
    WAITING_LOCATION = "waiting_location"
    WAITING_USE_TYPE = "waiting_use_type"
    WAITING_MODEL = "waiting_model"
    COMPLETED = "completed"

@dataclass
class Lead:
    telegram_id: str
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    equipment_interest: Optional[str] = None
    use_type: Optional[str] = None  # "cliente_final" o "distribuidor"
    specific_model: Optional[str] = None  # modelo específico seleccionado
    hubspot_contact_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class InventoryItem:
    tipo_maquina: str
    modelo: str
    ubicacion: str