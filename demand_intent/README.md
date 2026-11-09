# Demand Intent · Clínicas de estética (Sevilla)

Una versión propia de la lógica de **Demandbase Intent**, adaptada a clínicas de estética.
Detecta qué clínicas tienen **ahora** el dolor que resuelve un agente IA (atención al cliente,
agenda y citas), las ordena por prioridad y te da el **primer mensaje** para cada una.

## Qué hace y qué no hace

Demandbase detecta intención con datos B2B que compra a terceros (IPs, consumo de contenido, bidstream).
Eso no existe para clínicas de barrio. Aquí la intención se saca de señales públicas que **sí**
predicen la compra en este sector:

| Señal | De dónde sale | Por qué importa |
|---|---|---|
| Sin reserva online (Treatwell, Booksy, Fresha, Doctoralia, Flowww, Koibox…) | HTML de su web | Las citas entran a mano |
| "Pide tu cita llamando" / formulario | Texto de la web | Dependen de una persona libre |
| Sin chat ni bot (Tidio, ManyChat, Intercom, Landbot…) | HTML de su web | Nadie responde fuera de horario |
| WhatsApp sin bot | Enlaces wa.me | Lo atiende alguien entre cabina y cabina |
| "Trabaja con nosotros" / buscan recepcionista | Web | Crecen o están saturadas |
| Reseñas tipo "no cogen el teléfono", "tardan días", "me cambiaron la cita" | Google Maps | Dolor confesado por sus clientas |
| Tratamientos de ticket alto, nº de reseñas, varias sedes | Web + Maps | Más dinero perdido por cita perdida |

**Puntuación:** FIT (0-40, ¿se parece a mi cliente ideal?) + INTENT (0-60, ¿tiene ahora el dolor?) = 0-100.
- **CALIENTE** ≥ 65 → contactar esta semana
- **TEMPLADA** 45-64 → contactar con contenido / caso de uso
- **FRÍA** < 45 → nutrir, no vender

Cada vez que lo ejecutas guarda el histórico. Si una clínica sube **+10 puntos** entre dos ejecuciones
(nuevas quejas, empiezan a contratar…), sale marcada como **SUBIDA DE INTENCIÓN**: es el equivalente
al "intent surge" de Demandbase.

## Uso

Requisitos: Python 3.10 o superior. No hay que instalar nada más.

```bash
# 1) (Opcional) Sacar clínicas de Google Maps con sus reseñas
export GOOGLE_PLACES_API_KEY="tu_clave"
python -m demand_intent buscar "clínica medicina estética Sevilla" -o cuentas.csv
python -m demand_intent buscar "centro de estética Nervión Sevilla" -o cuentas_nervion.csv

# 2) Puntuar el listado (visita las webs y analiza reseñas)
python -m demand_intent analizar cuentas.csv -o resultados

# 3) Analizar una sola clínica al momento (antes de una llamada)
python -m demand_intent clinica https://www.clinica-ejemplo.es --nombre "Clínica Ejemplo"
```

Resultados en `resultados/`:
- `ranking.csv` → ábrelo en Excel o Google Sheets (separador `;`)
- `informe.html` → fichas con ángulo de entrada, mensaje sugerido y citas literales de reseñas
- `historico.json` → puntuaciones anteriores para detectar subidas

### Sin clave de Google

Rellena el CSV a mano (ver `ejemplo_clinicas.csv`). Columnas:
`nombre;web;telefono;direccion;categoria;valoracion;num_resenas;instagram;notas;resenas`.
En `web` escribe la URL, `NO` si la clínica no tiene web, o déjalo vacío si aún no lo has mirado.
En `resenas` pega las reseñas negativas de Google Maps separadas por `||`. Con 3-5 reseñas
de 1-3 estrellas por clínica basta.

## Coste y límites

- Google Places API (New): el campo de reseñas se factura en el nivel Enterprise + Atmosphere y
  Google devuelve **máximo 5 reseñas** por clínica. Google da crédito gratuito mensual; para
  100-200 clínicas al mes lo normal es no pasar de ese crédito, pero revisa los precios actuales
  en la consola de Google Cloud antes de lanzar búsquedas grandes.
- Webs hechas 100 % con JavaScript (algunas de Wix) pueden no mostrar el widget de reservas en el HTML:
  revisa a mano las que salgan "sin reserva online" antes de usarlo como argumento.
- Las señales son indicios, no certezas. El mensaje de apertura hace una pregunta, no afirma.

## Ajustar el modelo

Todo está en `config.py`: pesos, umbrales, ciudades, herramientas y frases de dolor.
Cuando tengas 10-15 conversaciones cerradas (ganadas y perdidas), compara qué señales tenían
y sube el peso de las que más se repiten en las ganadas.

## Tests

```bash
python -m unittest discover -s demand_intent/tests -t .
```
