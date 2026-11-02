# Explorador de Transacciones Multifuente

Sistema en Python que **normaliza** transacciones de 3 fuentes con estructuras distintas, las **valida**,
calcula **métricas** y las expone en una **interfaz web interactiva (Flask)** con filtros.

---

## 1. Requisitos
- Python 3.10 o superior (`python --version`)
- pip

## 2. Instalación y ejecución

```bash
# 1) Entrar a la carpeta del proyecto
cd transaction_explorer

# 2) (Recomendado) crear y activar un entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac / Linux

# 3) Instalar dependencias
pip install -r requirements.txt

# 4) Levantar la aplicación
python app.py
```

Abrir en el navegador: **http://127.0.0.1:5000**
(Para detenerla: `Ctrl + C` en la terminal.)

> En Windows, si `python` no funciona, probar `py` en su lugar.

---

## 3. Cómo probarlo

### 3.1 Pruebas automáticas (30 segundos)
```bash
python -m unittest discover tests -v
```
Debe terminar con `Ran 7 tests ... OK`. Cubren: las 3 fuentes normalizan al mismo valor, archivo limpio sin
inválidos, archivo con inconsistencias, métricas consistentes, redondeo auditado, límite de 3 decimales y
monedas con 0 y 3 decimales (JPY, KWD).

### 3.2 Prueba manual en la interfaz
En el selector **Dataset** (arriba a la derecha) hay dos archivos:

**A) `transactions_valid.json` (datos limpios)** — resultado esperado:

| Total | Válidas | Inválidas | Requieren revisión | SUCCESS / FAILED / PENDING |
|---|---|---|---|---|
| 11 | 11 | 0 | 0 | 5 / 3 / 3 |

**B) `transactions_mixed.json` (con inconsistencias)** — resultado esperado:

| Total | Válidas | Inválidas | Requieren revisión | SUCCESS / FAILED / PENDING |
|---|---|---|---|---|
| 30 | 13 | 17 | 1 | 7 / 3 / 3 |

Totales por moneda esperados (solo válidas): USD 1,511.51 (5) · EUR 375.98 (3) · GBP 56.25 (2) ·
MXN 1,200.00 (1) · JPY 1,500 (1) · KWD 12.345 (1).

### 3.3 Lista de verificación (qué hacer y qué debes ver)

| # | Acción | Resultado esperado |
|---|---|---|
| 1 | Dataset `transactions_mixed.json` → pestaña **Válidas** | 13 filas; `204` aparece con monto `100.50 USD` (venía como `10050`) |
| 2 | Buscar ID `A-77` | `99.99 EUR`, `2025-03-10T14:22:00Z` (venía como `"€99,99"`) |
| 3 | Filtro **Estado = SUCCESS** | 7 filas, todas con badge verde |
| 4 | Filtro **Moneda = KWD** | `207` con `12.345` (3 decimales) |
| 5 | Filtro **Moneda = JPY** | `tx_004` con `1,500` (0 decimales) |
| 6 | **Monto mín.** `100` + **Moneda** USD | Solo USD con monto ≥ 100 |
| 7 | **Desde / Hasta** `2025-03-11` | Solo transacciones de ese día (UTC) |
| 8 | **Ordenar** Monto ↓ | De mayor a menor |
| 9 | Filtro **Revisión → Solo REQUIERE_REVISION** | `tx_016`: monto `10.51`, original `10.505` |
| 10 | Pestaña **Inválidas** (17) | Cada fila muestra su motivo y el registro original |
| 11 | Inválidas → Motivo `DUPLICATE` | 2 filas (`tx_001` y `302`) |
| 12 | Inválidas → Fuente `desconocida` | 2 filas (`{"foo":"bar"}` y el texto suelto) |
| 13 | Pestaña **Auditoría** | 1 entrada: `ROUNDING`, `10.505 → 10.51`, `ROUND_HALF_UP a 2 decimales` |
| 14 | Botón **Exportar JSON** | JSON normalizado, respeta los filtros activos |

### 3.4 Motivos de invalidez que debes ver en `transactions_mixed.json`

| Código | Registros | Ejemplo |
|---|---|---|
| `MISSING_FIELD` | 4 | sin `status`, `id` nulo, `ref` vacío, monto sin moneda |
| `BAD_AMOUNT` | 3 | `"abc"`, `10.5051` (4 decimales), `total: 10.5` (no entero) |
| `DUPLICATE` | 2 | `tx_001` repetido y `transaction_id: 302` repetido |
| `BAD_DATE` | 2 | `2025-13-45 99:99:99` y `03/25/2025` (mes 25) |
| `UNKNOWN_SOURCE` | 2 | objeto sin campo identificador y texto que no es objeto |
| `AMOUNT_OUT_OF_RANGE` | 1 | `-20.00` |
| `UNSUPPORTED_CURRENCY` | 1 | `ZZZ` |
| `BAD_STATUS` | 1 | `weird_state` |
| `FUTURE_DATE` | 1 | año 2099 |

### 3.5 Probar la API directamente
```
http://127.0.0.1:5000/api/transactions?dataset=transactions_mixed.json&currency=EUR
http://127.0.0.1:5000/api/metrics?dataset=transactions_mixed.json
http://127.0.0.1:5000/api/audit?dataset=transactions_mixed.json
```

### 3.6 Probar con tus propios datos
Copia un `.json` (lista de objetos) a la carpeta `data/` y recarga: aparece en el selector.
Si el archivo está mal formado, la interfaz muestra un mensaje de error en lugar de caerse.

### 3.7 Probar que las reglas realmente mandan
Abre `config/rules.json`, cambia algo y recarga la página (no hace falta reiniciar):
- `validation.max_amount` → `100` : muchos registros pasan a inválidos (`AMOUNT_OUT_OF_RANGE`).
- Agrega `"rechazado"` a `status_mapping.FAILED` y un registro con ese estado pasa a válido.
- Quita `"MXN"` de `supported_currencies` : `206` pasa a inválido.

---

## 4. Estructura del proyecto (separación de responsabilidades)

| Archivo | Responsabilidad |
|---|---|
| `config/rules.json` | **Reglas**: monedas y decimales, símbolos, mapeo de estados, formatos de fecha, criterios de validez, redondeo |
| `txnexplorer/models.py` | Esquema normalizado (`Transaction`), cuarentena (`InvalidRecord`), auditoría (`AuditEntry`) |
| `txnexplorer/loader.py` | Lectura del JSON de entrada |
| `txnexplorer/normalizer.py` | Detección de fuente + conversión de monto, moneda, estado y fecha |
| `txnexplorer/validator.py` | Criterios de validez (rango, moneda soportada, fecha futura, duplicados) |
| `txnexplorer/pipeline.py` | Orquesta: detectar → normalizar → validar → separar |
| `txnexplorer/metrics.py` | Total, válidas/inválidas, conteo por estado, totales por moneda |
| `txnexplorer/filters.py` | Filtros y ordenamiento de la interfaz |
| `txnexplorer/audit.py` | Registro de auditoría (`logs/audit_<dataset>.json`) |
| `app.py` + `templates/index.html` | Interfaz Flask |
| `data/` | Datos de prueba (limpios e inconsistentes) |
| `tests/` | Pruebas automáticas |

## 5. Esquema normalizado
```json
{
  "id": "string",
  "amount": 99.99,
  "currency": "USD",
  "timestamp": "2025-03-10T14:22:00Z",
  "status": "SUCCESS | FAILED | PENDING",
  "source": "gateway_a | gateway_b | gateway_c",
  "original_amount": null,
  "flags": []
}
```
`original_amount` y `flags` solo se llenan cuando se aplicó un redondeo (`["REQUIERE_REVISION"]`).

## 6. Reglas principales (detalle en `config/rules.json` y `NOTA_TECNICA.md`)
- **Fuentes:** `gateway_a` (`id`), `gateway_b` (`transaction_id`, monto en unidades menores, fecha día/mes/año), `gateway_c` (`ref`, monto con símbolo y moneda inferida).
- **Fechas:** salida ISO-8601 UTC; fechas sin zona horaria se asumen UTC.
- **Inválidos:** no se descartan; van a cuarentena con su motivo.
- **Redondeo:** más decimales que la moneda (hasta 3) → `ROUND_HALF_UP` + `REQUIERE_REVISION` + auditoría; más de 3 → inválido.
- **Duplicados:** se conserva la primera aparición.

## 7. Problemas comunes
| Síntoma | Solución |
|---|---|
| `ModuleNotFoundError: flask` | Activar el entorno virtual y correr `pip install -r requirements.txt` |
| `Address already in use` | Otro programa usa el puerto 5000: cerrarlo o cambiar a `app.run(port=5001)` |
| Los números no coinciden con la tabla | Se modificó `rules.json` o los datos; restaurar los originales |
| Error de ruta al correr tests | Ejecutar siempre desde la carpeta raíz del proyecto |
