from typing import Optional
from vertexai.generative_models import GenerativeModel

class DataProductGenerator:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Generador de Recomendaciones de Productos de Datos (Data Products) para Dataplex
        """
        self.model = GenerativeModel(model_name)

    def _build_prompt(self, technical_context: str) -> str:
        return f"""
        Eres un Data Product Manager experto en Google Cloud Dataplex y Data Mesh.
        
        TU TAREA:
        Analiza los siguientes METADATOS TÉCNICOS de BigQuery y sugiere una lista de PRODUCTOS DE DATOS lógicos.
        
        CONTEXTO TÉCNICO (Tablas y Columnas):
        -------------------------------------
        {technical_context}
        -------------------------------------

        DEFINICIÓN DE PRODUCTO DE DATOS:
        Un Data Product es un contenedor lógico que agrupa tablas relacionadas que sirven a un propósito de negocio específico (ej. "Visión 360 del Cliente", "Análisis de Ventas", "Inventario Farmacéutico").

        REQUISITOS:
        1. Agrupa las tablas en productos de datos coherentes.
        2. Asigna un nombre de negocio claro y una descripción detallada.
        3. Identifica un posible "domain" (ej. Marketing, Finance, Supply Chain).
        4. Sugiere un "owner" (rol funcional, ej. "Sales Director", "Data Steward - Pharma").
        
        SALIDA ESPERADA (JSON ÚNICAMENTE):
        Una lista de productos bajo la clave "data_products".
        
        {{
            "data_products": [
                {{
                    "name": "Customer 360",
                    "description": "Consolidated view of patient and customer demographics.",
                    "domain": "Sales & CRM",
                    "owner": "CRM Product Owner",
                    "tables": [
                        "dataset.patients_table",
                        "dataset.contact_info_table"
                    ]
                }},
                {{
                    "name": "Pharmaceutical Inventory",
                    "description": "Tracking of drug stock, batches, and expiration dates.",
                    "domain": "Supply Chain",
                    "owner": "Logistics Manager",
                    "tables": [
                        "dataset.drugs_inventory",
                        "dataset.shipments"
                    ]
                }}
            ]
        }}
        
        REGLAS:
        - Responde SOLO EL JSON VÁLIDO.
        - Si una tabla no encaja claramente, intenta agruparla en un producto "General" o similar, pero prioriza agrupaciones de negocio fuertes.
        """

    def suggest_data_products(self, technical_context: str) -> Optional[str]:
        """
        Genera sugerencias de productos de datos basadas en el contexto técnico.
        """
        prompt = self._build_prompt(technical_context)
        print("🧠 Gemini analizando contexto para sugerir Productos de Datos...")
        
        try:
            response = self.model.generate_content(prompt)
            if response.text:
                return response.text.replace("```json", "").replace("```", "").strip()
        except Exception as e:
            print(f"❌ Error generando productos de datos: {e}")
        
        return None
