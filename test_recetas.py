#!/usr/bin/env python3
"""
Script de prueba del módulo de RECETAS
Ejecuta pruebas básicas para validar que todo funciona correctamente.

Uso:
    python test_recetas.py

Requisitos:
    - El servidor FastAPI debe estar ejecutándose en http://localhost:8000
    - Haber insertado datos de prueba (productos, insumos, configuracion)
"""

import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8000"

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.END}")

# ============================
# TEST 1: Crear una receta
# ============================
def test_crear_receta():
    print_test("Crear una receta válida")
    
    payload = {
        "id_producto": 1,  # Asegúrate de que este producto existe
        "nombre": "Café Americano",
        "descripcion": "Espresso diluido en agua caliente",
        "activo": True,
        "insumos": [
            {"id_insumo": 1, "cantidad": 18.0},  # Asegúrate de que existen
            {"id_insumo": 2, "cantidad": 150.0}
        ]
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/recetas/",
            json=payload,
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            print_success("Receta creada correctamente")
            print(f"ID Receta: {data.get('id_receta')}")
            print(f"Costo Total: ${data.get('costo_total'):.2f}")
            print(f"Precio Venta: ${data.get('precio_venta_producto'):.2f}")
            
            print_info("Detalles de insumos:")
            for insumo in data.get('insumos', []):
                print(f"  - {insumo['nombre_insumo']}: "
                      f"{insumo['cantidad']} x ${insumo['costo_unitario']:.4f} "
                      f"= ${insumo['subtotal']:.2f}")
            
            return data.get('id_receta')
        else:
            print_error(f"Error: {response.json()}")
            return None
            
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return None


# ============================
# TEST 2: Obtener una receta
# ============================
def test_obtener_receta(id_receta):
    print_test(f"Obtener receta ID: {id_receta}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/recetas/{id_receta}",
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Receta obtenida correctamente")
            print(f"Nombre: {data.get('nombre')}")
            print(f"Descripcion: {data.get('descripcion')}")
            print(f"Costo Total: ${data.get('costo_total'):.2f}")
            print(f"Precio Venta: ${data.get('precio_venta_producto'):.2f}")
            return True
        else:
            print_error(f"Error: {response.json()}")
            return False
            
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return False


# ============================
# TEST 3: Listar recetas
# ============================
def test_listar_recetas():
    print_test("Listar todas las recetas")
    
    try:
        response = requests.get(
            f"{BASE_URL}/recetas/",
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Se encontraron {len(data)} recetas")
            
            for receta in data:
                print(f"\n  ID: {receta['id_receta']}")
                print(f"  Nombre: {receta['nombre']}")
                print(f"  Costo: ${receta['costo_total']:.2f}")
                print(f"  Precio: ${receta['precio_venta_producto']:.2f}")
            
            return True
        else:
            print_error(f"Error: {response.json()}")
            return False
            
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return False


# ============================
# TEST 4: Actualizar una receta
# ============================
def test_actualizar_receta(id_receta):
    print_test(f"Actualizar receta ID: {id_receta}")
    
    payload = {
        "nombre": "Café Americano XL",
        "insumos": [
            {"id_insumo": 1, "cantidad": 25.0},  # Aumenta cantidad
            {"id_insumo": 2, "cantidad": 200.0}
        ]
    }
    
    try:
        response = requests.put(
            f"{BASE_URL}/recetas/{id_receta}",
            json=payload,
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Receta actualizada correctamente")
            print(f"Nuevo nombre: {data.get('nombre')}")
            print(f"Nuevo costo: ${data.get('costo_total'):.2f}")
            print(f"Nuevo precio: ${data.get('precio_venta_producto'):.2f}")
            return True
        else:
            print_error(f"Error: {response.json()}")
            return False
            
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return False


# ============================
# TEST 5: Errores (validación)
# ============================
def test_errores():
    print_test("Validación de errores")
    
    # Error 1: Producto no existe
    print("\n1. Intentar crear con producto inexistente:")
    try:
        response = requests.post(
            f"{BASE_URL}/recetas/",
            json={
                "id_producto": 99999,
                "nombre": "Test",
                "insumos": [{"id_insumo": 1, "cantidad": 10}]
            },
            timeout=5
        )
        if response.status_code == 404:
            print_success(f"Validación correcta: {response.json()['detail']}")
        else:
            print_error(f"Error inesperado: {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # Error 2: Cantidad <= 0
    print("\n2. Intentar crear con cantidad inválida:")
    try:
        response = requests.post(
            f"{BASE_URL}/recetas/",
            json={
                "id_producto": 1,
                "nombre": "Test",
                "insumos": [{"id_insumo": 1, "cantidad": 0}]
            },
            timeout=5
        )
        if response.status_code == 400:
            print_success(f"Validación correcta: {response.json()['detail']}")
        else:
            print_error(f"Error inesperado: {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # Error 3: Insumo no existe
    print("\n3. Intentar crear con insumo inexistente:")
    try:
        response = requests.post(
            f"{BASE_URL}/recetas/",
            json={
                "id_producto": 1,
                "nombre": "Test",
                "insumos": [{"id_insumo": 99999, "cantidad": 10}]
            },
            timeout=5
        )
        if response.status_code == 404:
            print_success(f"Validación correcta: {response.json()['detail']}")
        else:
            print_error(f"Error inesperado: {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")


# ============================
# TEST 6: Eliminar una receta
# ============================
def test_eliminar_receta(id_receta):
    print_test(f"Eliminar receta ID: {id_receta}")
    
    try:
        response = requests.delete(
            f"{BASE_URL}/recetas/{id_receta}",
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 204:
            print_success("Receta eliminada correctamente")
            return True
        else:
            print_error(f"Error: {response.json() if response.text else 'Sin respuesta'}")
            return False
            
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return False


# ============================
# MAIN
# ============================
def main():
    print(f"{Colors.BLUE}\n{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}PRUEBAS DEL MÓDULO DE RECETAS{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    print_info("Asegúrate de que:")
    print("  1. El servidor FastAPI está ejecutándose (localhost:8000)")
    print("  2. Existen datos en las tablas: productos, insumo, configuracion")
    print("  3. Productos y insumos tienen IDs: 1, 2, etc.")
    
    # Test 1: Crear
    id_receta = test_crear_receta()
    
    if id_receta:
        # Test 2: Obtener
        test_obtener_receta(id_receta)
        
        # Test 3: Listar
        test_listar_recetas()
        
        # Test 4: Actualizar
        test_actualizar_receta(id_receta)
    
    # Test 5: Errores
    test_errores()
    
    # Test 6: Eliminar
    if id_receta:
        test_eliminar_receta(id_receta)
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.GREEN}PRUEBAS COMPLETADAS{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")


if __name__ == "__main__":
    main()
