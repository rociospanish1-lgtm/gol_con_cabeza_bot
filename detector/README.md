# Detector de clínicas de estética en Sevilla (captación para Agencia de Agentes IA)

Fecha del análisis: 31/10/2026 · Fuente: Google Maps + reseñas de Google (vía OpenSEO).

## Qué hace

1. **Saca de Google Maps** las 50 clínicas de estética con más reseñas en un radio de 8 km de Sevilla centro (incluye Mairena, Tomares y Camas).
2. **Descarta** las que no son tu cliente: cadenas (Dorsia, Meye, Clínica Londres, Doctor Life), clínicas sobre todo dentales, fisio o nutrición, y negocios abandonados. Quedan 30 independientes.
3. **Lee las 10 peores reseñas** de cada una y detecta quejas que un agente IA resuelve: teléfono que no se coge, WhatsApp o Instagram sin respuesta, citas perdidas, esperas sin aviso, "ya te llamamos" que nunca llega. Hecho en 16 de las 30.
4. **Puntúa de 0 a 100** y ordena: A = contactar ya, B = segunda ronda, C = baja prioridad o reseñas pendientes de revisar.

Puntuación:

| Criterio | Puntos |
|---|---|
| Volumen (nº de reseñas = nº de citas que gestionan) | 5-20 |
| Sin web propia (solo Instagram/Facebook) | 12 |
| Valoración por debajo de 4,6 | 8 |
| Quejas en reseñas que un agente resuelve | hasta 50 |
| Deja críticas sin responder | 5 |

## Resultado

- **8 clínicas en prioridad A**, cada una con una reseña concreta que sirve de prueba (columna "Prueba" del Excel).
- 2 en B, 18 sin revisar todavía (C), 19 descartadas.
- Archivo: `leads_clinicas_sevilla.xlsx` (también en `.csv`).

| # | Clínica | Zona | Teléfono | Nota / reseñas | Dolor principal visto en reseñas |
|---|---|---|---|---|---|
| 1 | Clínica Cuve | Sevilla (Nervión) | 955 540 515 | 4,9 / 350 | WhatsApp y llamadas sin respuesta; perdieron un tratamiento capilar por no hacer seguimiento (feb 2026, sin responder) |
| 2 | Clínica Rocío Vázquez | Sevilla | 954 980 055 | 4,3 / 298 | Mandan WhatsApp a mano sin mirar la agenda (a pacientes ya citados o que ya habían venido); 1 h 30 min de espera sin aviso |
| 3 | Clínica Mallén | Sevilla | 954 642 729 | 4,5 / 313 | Gestionan las citas a mano por mensajes de Instagram; una cita sin confirmar acabó en reseña de 1 estrella (jul 2026) |
| 4 | NaturBeauty Lab | Mairena | 954 180 840 | 4,9 / 404 | Mensajes de postratamiento sin respuesta durante semanas; sin canal el fin de semana |
| 5 | AnaBoss | Tomares | 665 153 515 | 5,0 / 450 | La dueña admite por escrito que no coge el teléfono mientras atiende pacientes |
| 6 | Clínicas Dr. Román | Sevilla + Los Palacios | 954 035 676 | 4,5 / 82 | La doctora va 1 día a la semana; citas que caducan; "me dejaron en visto" |
| 7 | Revitaliza | Camas | 657 040 965 | 4,3 / 77 | Las ofertas de Instagram traen leads, pero las citas no se apuntan |
| 8 | Clínica Vene | Sevilla | 631 267 515 | 4,8 / 1.746 | Captan con anuncios de Instagram; esperas de 1-3 h sin avisar; "se pondrá en contacto contigo" incumplido |

## Antes de contactar: haz la prueba del paciente misterioso

Antes de llamar a ninguna de las 8, escríbeles como si fueras una paciente:

1. **Martes a las 21:00:** WhatsApp preguntando precio y disponibilidad de un tratamiento (por ejemplo, bótox en el tercio superior).
2. **Miércoles a las 14:30:** llamada en la franja de comida.
3. **El mismo día:** mensaje por Instagram.

Apunta cuánto tardan en responder por cada canal. Con eso vas a la primera conversación con un dato suyo, de esta semana, y no con una opinión tuya. Las reseñas demuestran que el problema existió; la prueba demuestra que sigue existiendo hoy.

## Primer contacto

**Canal:** llamada a la clínica pidiendo hablar con la gerencia, o visita en persona. No envíes emails comerciales en frío: la LSSI exige consentimiento previo para comunicaciones comerciales por email. El WhatsApp, solo después de un primer contacto.

**Guion base de 30 segundos** (cambia lo que va entre corchetes por el dato de cada clínica):

> Hola, soy Rocío Pineda, de Agencia de Agentes IA, aquí en Sevilla. Seré breve. El martes os escribí por WhatsApp a las 21:00 preguntando por [tratamiento] y la respuesta llegó [X horas] después. En vuestras reseñas de Google hay [dato concreto: "dos pacientes este año que cuentan que llamaron y nadie les devolvió la llamada"]. Monto un asistente que responde WhatsApp e Instagram al momento, a cualquier hora, con vuestros precios reales, y deja la cita apuntada en vuestra agenda. ¿Os puedo enseñar en 15 minutos cómo habría contestado a ese mensaje?

**Dato concreto para cada clínica** (sale de sus propias reseñas):

- **Cuve:** "Una paciente se hizo unas analíticas para un tratamiento capilar, las mandó por WhatsApp y nadie le contestó."
- **Rocío Vázquez:** "Una paciente cuenta que le escribisteis por WhatsApp preguntando si quería información cuando ya estaba citada, y otro diciendo 'aquí le esperamos' cuando ya había ido."
- **Mallén:** "Vosotros mismos decís en Google que gestionáis a diario muchas citas por Instagram, y esa misma gestión os costó una reseña de 1 estrella en julio."
- **NaturBeauty Lab:** "Una paciente no tenía a quién escribir un sábado después de un tratamiento porque la clínica estaba cerrada."
- **AnaBoss:** "Respondisteis a una reseña explicando que no cogéis llamadas mientras atendéis pacientes. Tiene todo el sentido. El asistente es justo para esos ratos."
- **Dr. Román:** "Si la doctora pasa consulta un día a la semana, cada hueco que se queda libre es una semana perdida."
- **Revitaliza:** "Una paciente llamó, le contestasteis por WhatsApp y al llegar su cita no estaba apuntada."
- **Vene:** "Captáis pacientes con promociones en Instagram. ¿Cuántos de esos leads se enfrían antes de que alguien los llame?"

## Cómo ampliarlo

- **Las 18 clínicas en "C - revisar reseñas":** cuesta 2 créditos de OpenSEO por clínica (10 reseñas). Analizarlas todas sale por unos 36 créditos de los 431 que quedan.
- **Otros barrios o municipios** (Dos Hermanas, Alcalá, Sevilla Este): una búsqueda nueva de 50 clínicas cuesta 35 créditos. Se guarda en `data/maps_busqueda_<fecha>.json`.
- Al añadir hallazgos a `data/hallazgos_resenas.json`, ejecuta `python3 detector.py` para regenerar el Excel.

## Limitaciones

- Desde este entorno no se pueden abrir las webs de las clínicas. Por eso no está comprobado si tienen ya chat o reserva online.
- Las reseñas negativas muestran problemas que existieron, no que sigan ocurriendo. La prueba del paciente misterioso sirve para confirmarlo.
- Algunas reseñas pueden ser falsas o de la competencia. Usa siempre el patrón (2 o más quejas parecidas), nunca una sola reseña aislada.
