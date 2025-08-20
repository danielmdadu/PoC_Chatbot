"""
Gestión del inventario de maquinaria
"""

from typing import List
from models import InventoryItem
from config import logger

class InventoryManager:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.inventory: List[InventoryItem] = []
        self.load_inventory()
    
    def load_inventory(self):
        """Carga el inventario desde el archivo CSV (todas las máquinas se consideran disponibles)"""

        # TODO: Cargar el inventario desde la base de datos
        try:
            self.inventory = [
                InventoryItem(
                    tipo_maquina="Cualquier tipo de maquinaria",
                    modelo="Cualquier modelo de maquinaria",
                    ubicacion="Cualquier ubicación",
                )
            ]
            logger.info(f"Inventario cargado: {len(self.inventory)} items")
        except Exception as e:
            logger.error(f"Error cargando inventario: {e}")
            self.inventory = []
    
    def search_equipment(self) -> List[InventoryItem]:
        """Busca equipos en el inventario basado en la consulta"""
        return self.inventory