"""
Gestión del inventario de maquinaria con búsqueda avanzada
"""

import pandas as pd
import re
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from models import InventoryItem
from config import logger

class InventoryManager:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.inventory: List[InventoryItem] = []
        self.search_index: Dict[str, List[int]] = defaultdict(list)
        self.type_index: Dict[str, List[int]] = defaultdict(list)
        self.brand_index: Dict[str, List[int]] = defaultdict(list)
        self.location_index: Dict[str, List[int]] = defaultdict(list)
        self.load_inventory()
        self._build_search_indexes()
    
    def load_inventory(self):
        """Carga el inventario desde el archivo CSV"""
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
    
    def _build_search_indexes(self):
        """Construye índices de búsqueda para optimizar las consultas"""
        for idx, item in enumerate(self.inventory):
            # Índice por tipo de máquina
            tipo_normalized = self._normalize_text(item.tipo_maquina)
            self.type_index[tipo_normalized].append(idx)
            
            # Índice por marca (extraída del modelo)
            brand = self._extract_brand(item.modelo)
            if brand:
                self.brand_index[brand.lower()].append(idx)
            
            # Índice por ubicación
            location_normalized = self._normalize_text(item.ubicacion)
            self.location_index[location_normalized].append(idx)
            
            # Índice de búsqueda general
            search_terms = self._extract_search_terms(item)
            for term in search_terms:
                self.search_index[term].append(idx)
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para búsqueda"""
        return re.sub(r'[^\w\s]', '', text.lower()).strip()
    
    def _extract_brand(self, modelo: str) -> Optional[str]:
        """Extrae la marca del modelo"""
        # Patrones comunes de marcas
        brand_patterns = [
            r'^(CAT|CATERPILLAR)',
            r'^(BOBCAT)',
            r'^(JCB)',
            r'^(JLG)',
            r'^(GENIE)',
            r'^(TOYOTA)',
            r'^(CUMMINS)',
            r'^(ATLAS\s+COPCO)',
            r'^(BOMAG)'
        ]
        
        for pattern in brand_patterns:
            match = re.search(pattern, modelo, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_search_terms(self, item: InventoryItem) -> List[str]:
        """Extrae términos de búsqueda de un item"""
        terms = []
        
        # Términos del tipo de máquina
        tipo_words = self._normalize_text(item.tipo_maquina).split()
        terms.extend(tipo_words)
        
        # Términos del modelo
        modelo_words = self._normalize_text(item.modelo).split()
        terms.extend(modelo_words)
        
        # Términos de ubicación
        location_words = self._normalize_text(item.ubicacion).split()
        terms.extend(location_words)
        
        # Sinónimos y variaciones
        synonyms = self._get_synonyms(item.tipo_maquina)
        terms.extend(synonyms)
        
        return list(set(terms))  # Eliminar duplicados
    
    def _get_synonyms(self, tipo_maquina: str) -> List[str]:
        """Obtiene sinónimos y variaciones del tipo de máquina"""
        synonyms_map = {
            'excavadora': ['excavadora', 'excavador', 'excavación', 'excava'],
            'retroexcavadora': ['retroexcavadora', 'retro', 'backhoe', 'retroexcavador'],
            'cargador': ['cargador', 'carga', 'loader', 'cargador frontal'],
            'minicargador': ['minicargador', 'mini cargador', 'skid steer', 'minicarga'],
            'compactador': ['compactador', 'compactación', 'compactor'],
            'plataforma': ['plataforma', 'elevadora', 'plataforma elevadora', 'aerial'],
            'montacargas': ['montacargas', 'forklift', 'carretilla', 'elevador'],
            'generador': ['generador', 'generación', 'generator', 'gen'],
            'compresor': ['compresor', 'compresión', 'compressor'],
            'rodillo': ['rodillo', 'roller', 'compactación']
        }
        
        tipo_lower = tipo_maquina.lower()
        for key, synonyms in synonyms_map.items():
            if key in tipo_lower:
                return synonyms
        return []
    
    def search_equipment(self, query: str) -> List[InventoryItem]:
        """Búsqueda avanzada de equipos en el inventario"""
        if not query.strip():
            return []
        
        query_normalized = self._normalize_text(query)
        query_words = query_normalized.split()
        
        # Calcular scores para cada item
        item_scores = defaultdict(int)
        
        for word in query_words:
            # Búsqueda exacta en índices
            if word in self.search_index:
                for idx in self.search_index[word]:
                    item_scores[idx] += 2  # Peso alto para coincidencias exactas
            
            # Búsqueda por tipo
            if word in self.type_index:
                for idx in self.type_index[word]:
                    item_scores[idx] += 3  # Peso muy alto para tipo
            
            # Búsqueda por marca
            if word in self.brand_index:
                for idx in self.brand_index[word]:
                    item_scores[idx] += 2  # Peso alto para marca
            
            # Búsqueda por ubicación
            if word in self.location_index:
                for idx in self.location_index[word]:
                    item_scores[idx] += 1  # Peso bajo para ubicación
            
            # Búsqueda parcial (substring)
            for term, indices in self.search_index.items():
                if word in term or term in word:
                    for idx in indices:
                        item_scores[idx] += 1
        
        # Ordenar por score y devolver resultados
        sorted_items = sorted(item_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Devolver máximo 10 resultados con score > 0
        results = []
        for idx, score in sorted_items[:10]:
            if score > 0:
                results.append(self.inventory[idx])
        
        return results
    
    def get_items_by_type(self, tipo_maquina: str) -> List[InventoryItem]:
        """Obtiene items por tipo de máquina usando el índice"""
        tipo_normalized = self._normalize_text(tipo_maquina)
        
        # Búsqueda exacta
        if tipo_normalized in self.type_index:
            return [self.inventory[idx] for idx in self.type_index[tipo_normalized]]
        
        # Búsqueda parcial
        results = []
        for tipo, indices in self.type_index.items():
            if tipo_normalized in tipo or tipo in tipo_normalized:
                results.extend([self.inventory[idx] for idx in indices])
        
        return results
    
    def get_items_by_brand(self, brand: str) -> List[InventoryItem]:
        """Obtiene items por marca"""
        brand_lower = brand.lower()
        if brand_lower in self.brand_index:
            return [self.inventory[idx] for idx in self.brand_index[brand_lower]]
        return []
    
    def get_items_by_location(self, location: str) -> List[InventoryItem]:
        """Obtiene items por ubicación"""
        location_normalized = self._normalize_text(location)
        if location_normalized in self.location_index:
            return [self.inventory[idx] for idx in self.location_index[location_normalized]]
        return []
    
    def get_available_types(self) -> List[str]:
        """Obtiene todos los tipos de máquinas disponibles"""
        return list(self.type_index.keys())
    
    def get_available_brands(self) -> List[str]:
        """Obtiene todas las marcas disponibles"""
        return list(self.brand_index.keys())
    
    def get_available_locations(self) -> List[str]:
        """Obtiene todas las ubicaciones disponibles"""
        return list(self.location_index.keys())
    
    def get_inventory_summary(self) -> Dict:
        """Obtiene un resumen del inventario"""
        return {
            'total_items': len(self.inventory),
            'types': len(self.type_index),
            'brands': len(self.brand_index),
            'locations': len(self.location_index),
            'available_types': self.get_available_types(),
            'available_brands': self.get_available_brands(),
            'available_locations': self.get_available_locations()
        }