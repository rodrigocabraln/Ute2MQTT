# Consumo medido cada 15 minutos

Extensión de [Ute2MQTT](https://github.com/rodrigocabraln/Ute2MQTT).
El cliente original sigue consultando consumo del período, gastos y deuda.
`history_main.py` consulta por separado la curva del portal de autoservicio UTE
con agrupación `QH` y magnitud `IMPORT_ACTIVE_ENERGY`.

## Ejecución

Requiere Python 3.11 o superior. Ejecutar desde la raíz del repositorio:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Completar `.env` y ejecutar el setup original para guardar las credenciales
cifradas. El historial usa `UTE_SERVICE_ID`, `UTE_SERVICE_POINT_ID`,
`ENCRYPTION_KEY`, `CREDENTIALS_PATH` y la configuración MQTT del mismo setup.
Configurar `MQTT_DISCOVERY_PREFIX=homeassistant` para el discovery estándar.
Preparar los directorios persistentes con permisos de escritura para UID 1000:

```sh
mkdir -p credentials data
# En Linux, si es necesario: sudo chown -R 1000:1000 credentials data
docker compose run --rm ute2mqtt python setup.py
docker compose run --rm ute-history python history_main.py --once --start 2026-09-01 --end 2026-10-03
docker compose up -d
```

Para ejecutar sin Docker, exportar las variables del entorno antes de usar
`.venv/bin/python history_main.py --once`. El script no carga `.env` por sí solo.

`UTE_HISTORY_LOOKBACK_DAYS=30` vuelve a consultar una ventana móvil para
capturar datos demorados y correcciones. `UTE_HISTORY_POLL_HOURS=6` controla
la frecuencia de descarga. El historial se conserva sin límite en
`UTE_HISTORY_DB=./data/history.sqlite3`; hacer respaldo de ese archivo con
el proceso detenido. Un backfill manual permite revisar fechas más antiguas.

## Contrato MQTT

Con prefijo `UTE` y servicio `SERVICE`:

- `UTE/SERVICE/history/days/YYYY-MM-DD`: JSON con `schema_version`, `timezone`,
  `interval_minutes` e `intervals` (timestamp ISO UTC → kWh medidos).
- `UTE/SERVICE/history/index`: lista ordenada de días disponibles.
- `UTE/SERVICE/history/state`: último intervalo, kWh y fecha de descarga.
- Discovery del sensor «Consumo último intervalo de 15 minutos», dentro del
  mismo dispositivo UTE. Es una medición de un intervalo; no un contador acumulado.

Los bloques diarios se particionan en UTC; la visualización debe convertirlos
a `America/Montevideo`. Todos los mensajes son retenidos con QoS 1 y se espera
confirmación del broker antes de desconectar. Se republica el historial guardado
para permitir recuperación de un broker vacío, con costo proporcional al historial.
El consumidor debe fusionar por timestamp y reemplazar valores corregidos.

## Datos y límites

Se preservan ceros reales, se omiten valores nulos y períodos todavía abiertos,
y se rechazan negativos, valores no finitos, timestamps desalineados y duplicados
contradictorios. No se interpolan lecturas. La base separa los puntos de servicio
y actualiza cada intervalo sin duplicarlo. Una descarga fallida no altera la base;
un fallo MQTT deja los datos guardados para el siguiente intento. Un nulo posterior
no elimina una lectura existente: solo un nuevo valor medido la reemplaza.

La resolución es de 15 minutos, pero UTE puede publicar con demora. No proporciona
consumo instantáneo ni por minuto. El acceso web no tiene un contrato de API estable;
cambios de formato pueden requerir actualizar el cliente.

MQTT no permite cargar automáticamente estadísticas pasadas en el recorder de
Home Assistant. Para el panel Energía y las gráficas históricas hay que mantener
una integración que importe estadísticas históricas, o implementar un consumidor
con esa función. Esta extensión entrega el historial para ese consumidor y un sensor
del último intervalo; no reproduce lecturas viejas como si ocurrieran ahora.

## Organización y pruebas

`ute/history/portal.py` maneja HTTP; `normalize.py`, la validación;
`store.py`, persistencia; `publish.py`, MQTT. `history_main.py` coordina estos
módulos y permite una descarga única o un servicio periódico con apagado por señales.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Pruebas sin credenciales reales: fechas y zona horaria, ausencias y ceros,
rechazo de datos inválidos, persistencia y correcciones, separación de servicios,
login, lotes de treinta días y confirmación de publicaciones MQTT.

Las pruebas usan HTTP y MQTT simulados y no verifican acceso a servicios reales.
Para ejecutar consultas reales, usar el contenedor Python 3.11 incluido o
Python 3.11+ con OpenSSL.
