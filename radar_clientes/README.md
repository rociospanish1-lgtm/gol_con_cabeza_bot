# Radar de clientes: empresas con señales de necesitar un agente IA

No existe ninguna base pública de "empresas que buscan IA". Lo que sí existe son
**señales de que una empresa tiene el problema que tú resuelves**. El radar las
recoge, puntúa cada empresa de 0 a 100 y te dice por qué, con un primer mensaje
ya adaptado a ese motivo.

Viene configurado para **clínicas de estética en Sevilla**, pero sirve para
cualquier sector y ciudad de España (`--sector`, `--ciudad`).

## Señales que detecta

| Señal | Fuente | Puntos | Por qué importa |
|---|---|---|---|
| Publica oferta de recepcionista / atención / gestión de citas | Ofertas de empleo (Adzuna) | +30 | Ya ha decidido pagar un sueldo por atender y agendar |
| Reseñas: "no cogen el teléfono", "imposible contactar" | Google Maps | hasta +30 | El problema es visible para sus pacientes |
| Reseñas: tardan en responder WhatsApp/mensajes | Google Maps | hasta +20 | Pierde consultas fuera de horario |
| Reseñas: citas cambiadas, sin recordatorio | Google Maps | hasta +20 | Ausencias y desorden de agenda |
| Web sin sistema de reserva online | Su web | +20 | Todas las citas pasan por una persona |
| Botón de WhatsApp sin bot | Su web | +10 | Atención manual por WhatsApp |
| Más de 150 reseñas / 50-150 reseñas | Google Maps | +15 / +8 | Volumen de consultas alto |
| Ya tiene chatbot (Tidio, ManyChat, Landbot…) | Su web | −20 | Ya compró una solución |
| Menos de 10 reseñas | Google Maps | −5 | Negocio pequeño, poco presupuesto |

Niveles: **Caliente** ≥ 60 · **Templado** 35-59 · **Frío** < 35.

Software de reservas que reconoce: Koibox, Flowww, Booksy, Treatwell, Fresha,
Doctoralia, Clinic Cloud, BEWE, Calendly y otros (lista en `analisis.py`).
Que una clínica ya use uno no la descarta: puntúa 0 y el motivo te da el
argumento (conectar ese software con WhatsApp y llamadas).

## Instalación (una vez)

```bash
pip install -r radar_clientes/requirements.txt
```

## Claves de API (opcionales, pero sin Google pierdes la mitad del valor)

| Clave | Para qué | Dónde se consigue |
|---|---|---|
| `GOOGLE_PLACES_API_KEY` | Clínicas, valoración y reseñas | Google Cloud Console → activar "Places API (New)" → Credenciales. Tiene uso gratuito mensual; revisa la tabla de precios actual antes de escanear muchas ciudades |
| `ADZUNA_APP_ID` y `ADZUNA_APP_KEY` | Ofertas de empleo en España | developer.adzuna.com (registro gratuito) |

Sin ninguna clave funciona con OpenStreetMap (gratis, pero cubre solo una parte
de las clínicas y no tiene reseñas).

```bash
export GOOGLE_PLACES_API_KEY="tu_clave"
export ADZUNA_APP_ID="tu_id"
export ADZUNA_APP_KEY="tu_clave"
```

En Windows (PowerShell): `$env:GOOGLE_PLACES_API_KEY="tu_clave"`.

## Uso

Ejecuta los comandos desde la carpeta raíz del repositorio:

```bash
python -m radar_clientes demo                 # 5 empresas ficticias para ver cómo funciona
python -m radar_clientes panel                # abre http://127.0.0.1:5000
python -m radar_clientes borrar-demo          # quita las ficticias
python -m radar_clientes escanear             # clínicas estéticas en Sevilla
python -m radar_clientes escanear --ciudad "Dos Hermanas"
python -m radar_clientes exportar leads.csv --minimo 35
```

En el panel puedes lanzar escaneos, filtrar por nivel/estado/zona, marcar cada
empresa (nuevo → contactado → reunión → propuesta → cliente / descartado) y
apuntar notas. Volver a escanear actualiza la puntuación sin borrar tu
seguimiento. Los datos se guardan en `radar_clientes/radar.db`.

## Uso de los datos (léelo antes de contactar)

- **Email en frío:** la LSSI (art. 21) prohíbe enviar comunicaciones comerciales
  por email sin consentimiento previo, también a empresas. Prioriza llamada,
  visita en persona, LinkedIn o mensaje directo en Instagram.
- **Google:** sus condiciones limitan cuánto tiempo puedes guardar los datos de
  Places. Úsalo para prospectar, no para montar o revender una base de datos.
- **RGPD:** el radar solo guarda datos de empresa (nombre, teléfono y web
  públicos). No añadas datos personales de pacientes de las reseñas a tus notas.

## Seguridad

- El panel solo escucha en tu ordenador (`127.0.0.1`) y los formularios llevan token CSRF.
- Al analizar webs bloquea direcciones internas o privadas, limita el tamaño (1,5 MB) y las redirecciones.
- El CSV exportado neutraliza fórmulas para que no se ejecuten al abrirlo en Excel.

## Tests

```bash
python -m pytest radar_clientes/tests
```
