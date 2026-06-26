import os
import sys
from supabase import create_client, Client

# Este script facilita la migración de datos entre tu base de datos antigua (personal)
# y la nueva base de datos de Supabase (empresa).

# Puedes configurar estas variables de entorno en tu terminal o hardcodearlas temporalmente aquí.
OLD_SUPABASE_URL = os.environ.get("OLD_SUPABASE_URL", "")
OLD_SUPABASE_SERVICE_KEY = os.environ.get("OLD_SUPABASE_SERVICE_KEY", "")

NEW_SUPABASE_URL = os.environ.get("NEW_SUPABASE_URL", "")
NEW_SUPABASE_SERVICE_KEY = os.environ.get("NEW_SUPABASE_SERVICE_KEY", "")

# ORDEN DE MIGRACIÓN (para respetar las claves foráneas)
TABLES_ORDER = [
    "administradores",
    "consorcios",
    "vecinos",
    "unidades_funcionales",
    "proveedores",
    "gastos",
    "cobros"
]

def migrate():
    if not all([OLD_SUPABASE_URL, OLD_SUPABASE_SERVICE_KEY, NEW_SUPABASE_URL, NEW_SUPABASE_SERVICE_KEY]):
        print("ERROR: Debes configurar las variables de entorno de Supabase de origen (OLD) y destino (NEW).")
        print("Ejemplo en terminal:")
        print("  export OLD_SUPABASE_URL='https://tu-vieja-db.supabase.co'")
        print("  export OLD_SUPABASE_SERVICE_KEY='tu-service-role-key-vieja'")
        print("  export NEW_SUPABASE_URL='https://tu-nueva-db.supabase.co'")
        print("  export NEW_SUPABASE_SERVICE_KEY='tu-service-role-key-nueva'")
        print("\nO puedes editar directamente este archivo 'migrate_db.py' con los strings correspondientes.")
        sys.exit(1)

    print("Conectando con Supabase de origen...")
    old_client: Client = create_client(OLD_SUPABASE_URL, OLD_SUPABASE_SERVICE_KEY)
    
    print("Conectando con Supabase de destino...")
    new_client: Client = create_client(NEW_SUPABASE_URL, NEW_SUPABASE_SERVICE_KEY)

    print("\n--- INICIANDO MIGRACIÓN DE DATOS ---")
    
    for table in TABLES_ORDER:
        print(f"\nMigrando tabla: {table}...")
        
        # 1. Obtener datos de la base de datos antigua con paginación
        all_data = []
        limit = 1000
        start = 0
        while True:
            try:
                res = old_client.table(table).select("*").range(start, start + limit - 1).execute()
                data = res.data
                if not data:
                    break
                all_data.extend(data)
                if len(data) < limit:
                    break
                start += limit
            except Exception as e:
                print(f"  Error al leer de {table}: {e}")
                sys.exit(1)
        
        print(f"  Se encontraron {len(all_data)} registros en la DB de origen.")
        
        if not all_data:
            continue
            
        # 2. Insertar en la nueva base de datos
        # Insertamos en bloques para evitar exceder límites de payload
        chunk_size = 200
        inserted_count = 0
        for i in range(0, len(all_data), chunk_size):
            chunk = all_data[i:i+chunk_size]
            try:
                # Usamos insert ya que la base de datos nueva debería estar vacía.
                new_client.table(table).insert(chunk).execute()
                inserted_count += len(chunk)
                print(f"  Insertados {inserted_count}/{len(all_data)} registros...")
            except Exception as e:
                print(f"  Error al escribir en la tabla {table}: {e}")
                print("  Intenta asegurarte de haber corrido los esquemas SQL en la base de datos nueva antes de migrar.")
                sys.exit(1)
                
        print(f"  ¡Tabla {table} migrada con éxito!")
        
    print("\n🎉 ¡La migración de datos ha finalizado correctamente!")

if __name__ == "__main__":
    migrate()
