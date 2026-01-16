import os
import json
import argparse
import requests
import time
from typing import List, Dict, Any
import google.auth
from google.auth.transport.requests import Request
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.settings import config

def load_proposal(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_authenticated_session():
    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    credentials.refresh(Request())
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    })
    return session

def wait_for_operation(session, operation_name):
    """
    Espera a que una Long Running Operation (LRO) termine.
    Documentación LRO: https://cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.operations/get
    """
    print(f"      ⏳ Esperando finalización de operación: {operation_name}...")
    base_op_url = f"https://dataplex.googleapis.com/v1/{operation_name}"
    
    while True:
        resp = session.get(base_op_url)
        if resp.status_code != 200:
            print(f"      ❌ Error consultando operación: {resp.status_code} - {resp.text}")
            return False
            
        op_data = resp.json()
        if op_data.get("done"):
            if "error" in op_data:
                print(f"      ❌ La operación falló: {op_data['error']}")
                return False
            print("      ✅ Operación completada.")
            return True
        
        time.sleep(2) # Esperar antes de reintentar

def publish_data_products(proposal_data: Dict[str, Any], dry_run: bool = False):
    """
    Publica los data products usando la API REST de Dataplex (Preview).
    """
    project_id = config.PROJECT_ID
    # Usamos la ubicación específica de Dataplex (debe coincidir con la de los assets, ej 'us')
    location = config.DATAPLEX_LOCATION
    
    # Endpoint base para Data Products (Universal Catalog)
    base_url = f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}/dataProducts"
    
    session = get_authenticated_session() if not dry_run else None

    data_products = proposal_data.get("data_products", [])
    print(f"📦 Procesando {len(data_products)} Productos de Datos (Dataplex API - Location: {location})...")

    for dp in data_products:
        name = dp.get("name")
        description = dp.get("description")
        domain = dp.get("domain")
        owner_role = dp.get("owner")
        tables = dp.get("tables", [])

        # ID seguro
        data_product_id = name.lower().replace(" ", "-").replace("&", "and").replace("_", "-")
        data_product_id = "".join([c for c in data_product_id if c.isalnum() or c == "-"])

        print(f"\n🔹 Producto: {name}")
        print(f"   ID: {data_product_id}")
        print(f"   Dominio: {domain} | Owner Role: {owner_role}")

        default_owner_email = "carlos.monteverde@sngular.com" 
        
        # Sanitización de labels
        safe_domain_label = "".join([c if c.isalnum() else "_" for c in domain.lower()])
        while "__" in safe_domain_label:
            safe_domain_label = safe_domain_label.replace("__", "_")

        payload = {
            "displayName": name,
            "description": f"{description}\n\nDomain: {domain}",
            "labels": {
                "domain": safe_domain_label,
                "generated_by": "ai-agent"
            },
            "ownerEmails": [default_owner_email] 
        }

        if dry_run:
            print(f"   [DRY RUN] POST/PATCH {base_url}?dataProductId={data_product_id}")
            print(f"   [DRY RUN] Payload: {json.dumps(payload, indent=2)}")
            for table_ref in tables:
                print(f"   [DRY RUN]   + Adding Asset: {table_ref}")
            continue

        try:
            # 1. Crear/Verificar Data Product
            get_url = f"{base_url}/{data_product_id}"
            resp = session.get(get_url)
            
            product_created = False
            
            if resp.status_code == 200:
                print(f"   ⚠️ El Data Product '{data_product_id}' ya existe. Actualizando (Overwrite)...")
                update_mask = "displayName,description,labels,ownerEmails"
                patch_url = f"{base_url}/{data_product_id}?updateMask={update_mask}"
                
                patch_resp = session.patch(patch_url, json=payload)
                
                if patch_resp.status_code in [200, 201, 202]:
                     resp_json = patch_resp.json()
                     # Si devuelve operación, esperar
                     if "name" in resp_json and "operations" in resp_json["name"]:
                         if wait_for_operation(session, resp_json["name"]):
                             product_created = True
                     else:
                         # Operación síncrona o ya terminada (raro en update, pero posible)
                         print(f"   ✅ Data Product actualizado exitosamente (Sync).")
                         product_created = True
                else:
                     print(f"   ❌ Error actualizando Data Product: {patch_resp.status_code} - {patch_resp.text}")

            elif resp.status_code == 404:
                # Create
                create_url = f"{base_url}?dataProductId={data_product_id}"
                create_resp = session.post(create_url, json=payload)
                
                if create_resp.status_code in [200, 201, 202]:
                    resp_json = create_resp.json()
                    print(f"   🚀 Solicitud de creación enviada.")
                    # Si devuelve operación, esperar
                    if "name" in resp_json and "operations" in resp_json["name"]:
                         if wait_for_operation(session, resp_json["name"]):
                             product_created = True
                    else:
                         print(f"   ✅ Data Product creado exitosamente (Sync): {resp_json.get('name')}")
                         product_created = True
                else:
                    print(f"   ❌ Error creando Data Product: {create_resp.status_code} - {create_resp.text}")
            else:
                 print(f"   ❌ Error verificando existencia: {resp.status_code} - {resp.text}")

            # 2. Agregar Assets (Tablas)
            if product_created and tables:
                print(f"      🔗 Asociando {len(tables)} tablas como assets...")
                assets_url = f"{base_url}/{data_product_id}/dataAssets"
                
                for table_ref in tables:
                    # table_ref viene como "dataset.table" del JSON
                    # Necesitamos el Full Resource Name para Dataplex:
                    # //bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}
                    
                    if "." not in table_ref:
                         print(f"      ⚠️ Formato de tabla incorrecto (se espera dataset.table): {table_ref}")
                         continue
                         
                    dataset_id, table_id = table_ref.split(".", 1)
                    resource_name = f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}"
                    
                    asset_id = f"{dataset_id}-{table_id}".replace("_", "-").lower() # ID safe para el asset
                    
                    asset_payload = {
                        "displayName": table_id,
                        "resourceSpec": {
                            "type": "BIGQUERY_TABLE", # Opcional/Inferido, pero resource name manda
                            "name": resource_name
                        }
                        # "resource": resource_name  <-- A veces es "resource" en top level o dentro de spec, a verificar.
                        # Según doc search result 3: "resource" field.
                        # Vamos a probar con "resource" campo top-level o el shape correcto.
                        # Si falla, ajustamos. La API de Dataplex a veces usa "resource" directo.
                    }
                    
                    # Ajuste payload: El error "Starting an object on a scalar field" indica que 'resource' debe ser string.
                    # El error "Unknown name displayName" indica que no es válido en este nivel o versión.
                    # Probamos payload minimalista válido.
                    real_asset_payload = {
                        "resource": {
                             "name": resource_name,
                             "type": "BIGQUERY_TABLE"
                         }
                    }
                    # Wait, error says "Starting an object on a scalar field" at 'data_asset' (resource).
                    # This implies 'resource' IS the scalar field? Or the API wrapper expects it differently.
                    # Let's look at the error closely: "Invalid value at 'data_asset' (resource)". 
                    # Actually, standard Google APIs often take "resource": "full/path".
                    
                    real_asset_payload = {
                        "resource": resource_name,  # String directo
                        # "displayName": table_id # Si falla, lo quitamos. La API puede inferirlo.
                    }

                    # Intentamos crear el asset
                    asset_create_url = f"{assets_url}?dataAssetId={asset_id}"
                    
                    # Verificamos si existe primero (idiempotencia básica)
                    asset_check = session.get(f"{assets_url}/{asset_id}")
                    if asset_check.status_code == 200:
                         print(f"      Example: Asset {asset_id} ya existe.")
                    else:
                         asset_resp = session.post(asset_create_url, json=real_asset_payload)
                         if asset_resp.status_code in [200, 201, 202]:
                             print(f"      ✅ Asset agregado: {table_id}")
                         else:
                             print(f"      ❌ Error agregando asset {table_id}: {asset_resp.status_code} - {asset_resp.text}")


        except Exception as e:
            print(f"   ❌ Error de conexión/sesión: {e}")

def main():
    parser = argparse.ArgumentParser(description="Publicar Data Products en Dataplex (REST API)")
    parser.add_argument("--file", required=True, help="Ruta al archivo JSON de propuesta")
    parser.add_argument("--dry-run", action="store_true", help="Simular ejecución sin cambios")
    
    args = parser.parse_args()
    
    try:
        data = load_proposal(args.file)
        publish_data_products(data, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    main()
