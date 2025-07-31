"""
Gestión del inventario de maquinaria
"""

import pandas as pd
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
        try:
            df = pd.read_csv(self.csv_path)
            self.inventory = [
                InventoryItem(
                    tipo_maquina=row['tipo_maquina'],
                    modelo=row['modelo'],
                    ubicacion=row['ubicacion'],
                )
                for _, row in df.iterrows()
            ]
            logger.info(f"Inventario cargado: {len(self.inventory)} items")
        except Exception as e:
            logger.error(f"Error cargando inventario: {e}")
            self.inventory = []
    
    def search_equipment(self, query: str) -> List[InventoryItem]:
        """Busca equipos en el inventario basado en la consulta"""
        query_lower = query.lower()
        matches = []
        for item in self.inventory:
            if (query_lower in item.tipo_maquina.lower() or 
                query_lower in item.modelo.lower()):
                matches.append(item)
        return matches
    
    def get_items_by_type(self, tipo_maquina: str) -> List[InventoryItem]:
        """Obtiene items por tipo de máquina"""
        tipo_lower = tipo_maquina.lower()
        return [
            item for item in self.inventory 
            if tipo_lower in item.tipo_maquina.lower()
        ]