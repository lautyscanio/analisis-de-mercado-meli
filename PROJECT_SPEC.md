# Mercadata — Especificación del Proyecto

> Documento de referencia (spec/constitution). Describe qué es el proyecto, por qué existe,
> cómo está construido y cuáles son sus límites reales. Mantenerlo actualizado a medida
> que cambie el alcance o se resuelvan las limitaciones de la API.

---

## 1. Objetivo

Sistema de **inteligencia de mercado** para un vendedor de Mercado Libre Argentina que hoy
opera en el rubro de **materiales eléctricos**, con la intención declarada de expandirlo a
otros rubros (ferretería, plomería, construcción, pinturería) más adelante.

El sistema debe responder tres preguntas de negocio:
1. ¿Qué productos se venden más y a qué precio?
2. ¿Quiénes son los vendedores dominantes de cada producto/categoría (competencia)?
3. ¿Qué está en tendencia de búsqueda, para detectar oportunidades de nuevos productos?

No es una herramienta de gestión de ventas propias (eso lo cubre otro sistema del usuario,
una app de ML distinta orientada a facturación). Este proyecto es **puramente de lectura y
análisis de datos públicos/semi-públicos del marketplace**.

---

## 2. Usuario objetivo

- Vendedor con cuenta ML activa (nickname actual de prueba: **PIME SA**).
- No es técnico, pero entiende conceptos básicos (API, token, permisos).
- Va a usar la app localmente en su PC Windows, sin desplegar a un servidor público.

---

## 3. Arquitectura

```
Browser (Chrome) ──HTTP──> Flask (localhost:5000) ──HTTPS──> api.mercadolibre.com
```

- **Backend**: Python + Flask. Actúa como proxy autenticado hacia la API de ML.
  Nunca se llama a la API de ML directamente desde el navegador (ver sección 5, CORS/PolicyAgent).
- **Frontend**: HTML + CSS + JS vanilla, sin framework ni build step. Un único bundle por archivo,
  servido por Flask desde `/static`. Se eligió esto para no agregar complejidad de tooling
  (webpack/vite/npm) dado que el usuario no es técnico y quiere poder abrir y correr el proyecto
  sin instalar nada más que Python.
- **Gráficos**: Chart.js vía CDN (sin instalar dependencias npm).
- **Persistencia de datos del negocio**: ninguna base de datos. El estado vive en memoria del
  proceso Flask (cache con TTL) y en el navegador (localStorage para el nickname propio).
- **Persistencia de sesión ML**: el token OAuth de usuario se guarda en `.ml_token.json` en la
  raíz del proyecto (no versionar, ver `.gitignore`).

### 3.1. Estructura de archivos

```
productos-+vendidos/
├── app.py                 # Backend Flask: OAuth, proxy API ML, endpoints /api/*
├── requirements.txt        # flask, python-dotenv, requests
├── .env                    # Credenciales reales (NO versionar)
├── .env.example             # Plantilla de credenciales
├── .ml_token.json          # Token OAuth de usuario persistido (NO versionar)
├── start.bat               # Script de arranque para Windows
├── templates/
│   ├── index.html          # Layout principal (sidebar + secciones)
│   └── setup.html           # Página de autorización OAuth manual
└── static/
    ├── style.css            # Design system (tokens, sidebar, secciones, tabla, panel)
    └── app.js               # Estado, fetch a /api/*, render de todas las secciones
```

---

## 4. Autenticación con Mercado Libre

### 4.1. Flujo elegido: Authorization Code (manual, sin redirect URI propio)

ML exige que el Redirect URI de una app sea **HTTPS**, y no acepta `http://localhost`. Como este
proyecto corre 100% local sin certificado propio, se resolvió así:

1. El Redirect URI configurado en el portal ML es `https://httpbin.org/get` (servicio público que
   simplemente devuelve como JSON los parámetros de la URL, incluido el `code`).
2. El usuario hace clic en "Autorizar con ML" desde `/auth/setup`, acepta permisos en ML.
3. ML redirige a httpbin, que muestra el `code` en pantalla.
4. El usuario copia y pega ese código en un formulario de `/auth/setup`.
5. El backend intercambia el código por `access_token` + `refresh_token` y los guarda en
   `.ml_token.json`.
6. El `access_token` se refresca automáticamente (dura 6 hs) usando el `refresh_token` sin
   intervención del usuario.

### 4.2. Grant types habilitados en el portal ML

- ✅ Authorization Code
- ✅ Refresh Token
- ❌ Client Credentials (deshabilitado a propósito — no sirve para los endpoints que necesitamos,
  ver sección 5)
- ❌ PKCE (no aplica, es para apps públicas/SPA)

### 4.3. Scopes / permisos activos hoy

- Usuarios → **Lectura**
- Items → **habilitado**
- Negocio: **Mercado Libre** (no VIS)

### 4.4. Pendiente (roadmap inmediato)

- Activar el permiso **"catalog"** (aparece como "Item competition / Catalog suggestions" en el
  checklist de permisos del portal) para desbloquear `/highlights`.

---

## 5. Limitaciones reales de la API de Mercado Libre (verificadas empíricamente)

Esta sección documenta hechos comprobados corriendo requests reales contra la API, no
supuestos. Es la parte más importante del documento porque explica la arquitectura elegida.

### 5.1. Causa raíz de los bloqueos

`GET /applications/{app_id}` devuelve:

```json
"certification_status": "not_certified",
"sandbox_mode": false,
"active": true,
"blocked": false
```

La app está activa y sin bloqueos, pero **no certificada**. Los endpoints de descubrimiento
masivo de publicaciones están reservados a apps certificadas del Developer Partner Program
(requiere USD 1.500.000 de GMV mensual en Argentina — inalcanzable para una herramienta
interna de un solo vendedor).

**Requisitos reales del programa (verificado en la doc oficial, actualizada 19/02/2026):**
1. Cumplir las buenas prácticas de la plataforma.
2. Postularse con [este formulario](https://docs.google.com/forms/d/e/1FAIpQLSftLvUCWc3GMwag-dbArKgeliAKNqTWB2LgTOS1mrAKQF8AvA/viewform).
3. GMV: **vendedores de ML usando tu solución** con facturación mensual combinada de
   USD 1.500.000 en Argentina (usuarios activos, últimos 3 meses).
4. Aprobar una Evaluación de Seguridad con 65% o más.
5. Cumplir las iniciativas de desarrollo asignadas por un Integration Expert.

**Checklist de buenas prácticas (punto 1), verificado contra el código el 2026-09-16:**

| Práctica exigida | Estado | Por qué |
|---|---|---|
| No enviar mensajes automatizados/plantillas | ✅ | La app no tiene ningún endpoint que escriba a `/messages`; es de solo lectura. |
| No modificar la plantilla de etiquetas de envío | ✅ | No hay integración con envíos/etiquetas en absoluto. |
| No clonar publicaciones ni imágenes | ✅ | La app no crea ni edita publicaciones propias (eso lo cubre otra app del usuario, ver §1). |
| Catalogar en catálogo cuando corresponda / repuestos con compatibilidad / moda con tabla de talles | ✅ (no aplica) | Estas reglas son para quien publica; esta app no publica nada. |
| No hacer rastreo web (scraping) | ✅ | Línea roja explícita desde antes, ver §7. Todo pasa por la API oficial. |
| Limitar las IPs que pueden usar el token de la app | ✅ | `app.run(host="127.0.0.1", ...)`: el servidor Flask solo escucha localhost, ningún otro dispositivo de la red puede llegar al proceso que tiene el token. |
| Manejar el 429 (rate limit) con backoff | ✅ | `ml_get()` reintenta con backoff exponencial + jitter y respeta `Retry-After` (ver §5.4). |

Todas las prácticas de la lista ya se cumplían o se ajustaron para cumplirse (host binding
explícito). Lo único fuera de nuestro control es el punto 3 (GMV): es el filtro real que
excluye a esta app, no el checklist de buenas prácticas.

El punto 3 es la razón de fondo por la que esto no aplica a este proyecto: el programa está
pensado para **plataformas que sirven a muchos vendedores** (tipo Nubimetrics, Real Trends,
Tiendanube), no para una herramienta interna de un único vendedor analizando su propio
rubro. No hay forma de alcanzar ese GMV combinado con un solo usuario, sin importar cuánto
factures vos mismo. Por eso la certificación queda fuera de alcance salvo que este proyecto
se transforme en un producto que venda a terceros vendedores.

**No es un problema de scopes**: se activó el permiso "catalog" en el portal, se reautorizó
con un token nuevo, y el 403 se mantuvo idéntico.

### 5.2. Endpoints VERIFICADOS — funcionan (200 OK)

| Endpoint | Qué aporta |
|---|---|
| `/products/{id}/items` (item_id por vendedor) | Permite reconocer una publicación de un tercero por su `item_id` (ver 5.7) |
| `/products/search?status=active&site_id=MLA&q=...` | Buscador del catálogo oficial. **Reemplaza a `/sites/MLA/search`.** Acepta `category` (categoría de ML) y, opcionalmente, `domain_id` (dominio de producto, ej. `MLA-CIRCUIT_BREAKERS`) — más preciso que `category` sola, ver 5.5. |
| `/sites/MLA/domain_discovery/search?q=...` | Sugiere el `domain_id` más probable para un texto de búsqueda. Útil para curar `domain_id` por subcategoría, pero su top resultado no siempre es el semánticamente correcto (ver 5.5) — no usar a ciegas en runtime, verificar manualmente cada caso. |
| `/products/{catalog_product_id}` | Detalle del producto de catálogo |
| `/products/{id}/items` | **Núcleo del análisis**: todos los vendedores que ofrecen ese producto, con `price`, `seller_id`, `listing_type_id`, `shipping`, `seller_address`, `official_store_id`, `original_price` |
| `/users/{seller_id}` | `nickname`, `seller_reputation.level_id`, `transactions.total` |
| `/users/{user_id}/items/search` | Publicaciones propias |
| `/sites/MLA/categories`, `/categories/{id}` | Árbol de categorías |
| `/trends/MLA`, `/trends/MLA/{category_id}` | Tendencias de búsqueda semanales |
| `/items/{id}/visits/time_window` | Visitas por ventana temporal |

### 5.3. Endpoints BLOQUEADOS (403)

| Endpoint | Error |
|---|---|
| `/sites/MLA/search` | `forbidden` (incluso filtrando por `catalog_product_id`) |
| `/highlights/...` | `PA_UNAUTHORIZED_RESULT_FROM_POLICIES` |
| `/items/{id}` (item ajeno individual) | `access_denied` |
| `/marketplace/benchmarks/user/{id}/items` | `Invalid caller.id` |

### 5.4. Otras restricciones

- **`sold_quantity` por publicación**: no disponible. Proxy en uso:
  `seller_reputation.transactions.total` (ventas históricas del **vendedor**, no del producto).
- **Offset y limit máximos de `/products/search`: 100 cada uno** (ver §5.8 — bajó desde el
  ~1000 medido el 2026-09-15; no confundir con la cifra vieja).
- **Rate limiting**: la documentación oficial no publica una cifra fija; recomienda backoff
  exponencial con jitter. Cualquier número específico visto en informes de terceros
  (ej. "1500 req/min") debe tratarse como no verificado.
- **Reseñas/opiniones**: no hay endpoint público oficial. Fuera de alcance.

### 5.5. `category` sola no alcanza para eliminar ruido — se suma `domain_id`

Verificado empíricamente (2026-09-15): varias categorías de ML son más anchas de lo que
sugiere su nombre y agrupan dominios de producto sin relación entre sí. Ejemplos reales
encontrados analizando la sección "Materiales Eléctricos":

- Categoría `MLA411423` ("Tableros") + texto "tablero electrico" → sin filtro de dominio,
  el 100% de la primera página eran filtros/rejillas de ventilación para gabinetes
  (`domain_id: MLA-FANS`), no gabinetes/tableros en sí.
- Categoría `MLA377395` ("Focos") + texto "lampara led" → traía lámparas LED para
  vehículos (`MLA-VEHICLE_LED_BULBS`) y hasta un juguete para pájaros con luz LED
  (`MLA-BIRD_TOYS`) mezclados con las bombitas LED reales.

Sumar `domain_id` (ej. `MLA-TRANSFER_SWITCHES` para el primer caso, `MLA-LIGHT_BULBS` para
el segundo) filtra por el tipo de producto que ML ya clasificó internamente, no por texto,
y elimina ese cruce. El `domain_id` correcto se identificó **verificando cada subcategoría
a mano** contra `/categories/{id}` y `/sites/MLA/domain_discovery/search` — este último
sugiere candidatos pero su primer resultado no siempre es el semánticamente correcto para
el rubro (ej. para "motor electrico" sugiere motores de aeromodelismo antes que motores
eléctricos genéricos), así que no se usa a ciegas en runtime, solo como ayuda de curación
manual. El mapeo final vive en `CATEGORIES` en `static/app.js` (campos `cat` y `domain`
opcional por subcategoría).

También se corrigieron 2 IDs de categoría directamente mal mapeados (no un problema de
`domain_id`, sino de haber apuntado a la categoría equivocada desde el inicio):
"Disyuntores y Protección" apuntaba a `MLA435347` (categoría padre "Tableros y Medidores",
mezclaba multímetros/testers con disyuntores reales) en vez de `MLA30208`
("Interruptores Automáticos"); y "Tableros y Medidores" reusaba por error el mismo ID que
"Disyuntores y Protección" en vez de `MLA411423` ("Tableros").

### 5.6. Calibración de búsquedas por subcategoría (verificado 2026-09-16)

Medido con requests reales (cuántos de los primeros 20-30 productos de cada búsqueda tienen
vendedores activos hoy, vía `/products/{id}/items`):

- **El catálogo de ML Argentina está lleno de fichas importadas** (Brasil, México, Chile) que nadie
  vende acá. En varias subcategorías 0 de 15 productos tenían vendedores. Por eso antes aparecían
  "pocos productos".
- **El vocabulario argentino rinde muchísimo más** que el término "de catálogo", incluso dentro del
  mismo `domain_id`: "termica" 27/30 vs "disyuntor" 0/30; "pinza amperometrica" 20/30 vs
  "amperimetrica" 2/30; "modulo toma" 17/30 vs "tomacorriente" 0/30; "llave de luz" 23/30 vs
  "interruptor" 0/30; "grupo electrogeno" 20/30 vs "generador" 1/20.
- Se usaron las **tendencias reales de cada categoría** (`/trends/MLA/{cat}`) como candidatos de
  palabra clave y se eligió el de mejor rendimiento. Se descartaron términos con marca
  ("contactor sica" rinde 15/20 pero sesga las marcas del análisis).
- **Predictores de "tiene vendedores"** en el resultado de `/products/search`: con `parent_id`,
  64% tiene vendedores (vs 8% sin); `authority_types` con COMMUNITY, 34% (vs 3%). `/api/products`
  ordena cada página por eso (`_offer_likelihood`), sin descartar nada.
- `/products/search` **exige** `q` (o identificadores/atributos): no se puede listar un dominio
  entero sin texto. No acepta varios `domain_id` separados por coma. `sort` se ignora.
- Con `domain_id` no se manda `category`: el dominio es más preciso y la categoría deja afuera
  productos del mismo tipo clasificados en otra rama.
- **Quitados por falta de cobertura de catálogo**: "Motores" (37% eran paneles de puerta de auto,
  0/30 con vendedores con cualquier término) y "Transformadores" (transformadores de audio y
  libros, 0-3/30). En ML Argentina se venden como publicaciones sueltas, fuera del catálogo.
  "Todo el rubro" (`q=electricidad`) se reemplazó por la vista **Mapa del rubro**: traía 85%
  medidores y 14% libros.

### 5.7. Identificar una publicación de un competidor sin `/items/{id}`

`/items/{id}`, `/items?ids=` y `/user-products/{id}` dan 403 para terceros. Pero
`/products/{id}/items` sí lista el `item_id`, precio, vendedor y reputación de **cada** publicación
del producto. Entonces, con el texto del link:

1. `/sites/MLA/domain_discovery/search` sugiere el tipo de producto y la marca.
2. Se busca en los 2 dominios más probables + búsqueda libre, y se rankea por cobertura del
   título, marca, medidas ("2x25"), números ("30ma") y códigos de modelo.
3. Si el `item_id` pegado aparece entre los vendedores de un candidato → **match exacto**, con
   precio y vendedor reales. Verificado 4/4 con links reales de terceros.

Si no aparece (publicación fuera de catálogo), se muestran candidatos y solo se autoselecciona
el primero si la coincidencia es alta y clara.

### 5.8. El techo real de `/products/search` bajó a 200 resultados por búsqueda (verificado 2026-09-16)

**Corrige lo documentado el 2026-09-15** (§5.4 e informes previos hablaban de un offset máximo
de ~1000). Probado hoy contra la API real, con el mismo endpoint y las mismas credenciales:

```
GET /products/search?q=termica&domain_id=MLA-CIRCUIT_BREAKERS&limit=50&offset=100 → 200 OK
GET /products/search?q=termica&domain_id=MLA-CIRCUIT_BREAKERS&limit=50&offset=150 → 400
  {"error":"bad_request","details":["external_search_products.offset: The maximum allowed value for 'offset' is 100"]}
```

Confirmado también sin `domain_id` (solo `q`) y con `category` en vez de `domain_id`: el límite
es el mismo en los tres casos, así que es una validación del endpoint, no de una combinación de
parámetros puntual. También se confirmó que `limit` tiene el mismo techo (100): pedir `limit=200`
da `400 "The maximum allowed value for 'limit' is 100"`.

**Conclusión práctica**: con `limit=100` y `offset` en 0 y 100, el máximo honesto que se puede
traer en **una sola búsqueda** son **200 productos de catálogo** — sin importar que `paging.total`
diga 730, 10000 o cualquier otro número más grande. Pedir un offset mayor no es más lento, es
directamente rechazado por el servidor. **Esto no cambia la línea roja de la sección 7.5**: seguir
usando una sola búsqueda por subcategoría con el límite honesto (200) no es lo mismo que fragmentar
sistemáticamente en decenas de sub-búsquedas para inflar la cobertura de una categoría completa —
eso sigue fuera de discusión.

**Por qué esto causaba "pocos productos" antes de este fix**: `/api/analysis` y el listado del
dashboard estaban armados asumiendo el techo viejo (`page_size=50, max_offset=1000`). A partir de
la 3ra página (offset=150) cada pedido fallaba con 400, y `ml_get_pages` lo absorbía en silencio
devolviendo una lista vacía para esa página — sin excepción visible, sin aviso en la UI. El
resultado quedaba truncado a los primeros ~150 productos de catálogo (a veces menos, según cuántos
tenían vendedores activos), muy por debajo de lo que hoy es alcanzable. Corregido a
`page_size=100, max_offset=100` en `/api/analysis`, `/api/products` (usado por el dashboard) y
`_subcat_snapshot` (Mapa del rubro).

**Pendiente de verificar**: si el mismo techo de offset aplica a `/products/{id}/items` (las
ofertas de un producto puntual). No se encontró en el rubro actual ningún producto con más de
100 vendedores activos para probarlo en la práctica; si en algún momento un producto muy disputado
muestra menos vendedores de los que `total` indica, revisar esto primero.

**No es un cambio nuestro**: ML bajó este límite del lado del servidor entre el 2026-09-15 y el
2026-09-16. No hay forma de saber si es permanente o una restricción temporal — conviene volver a
verificarlo si en el futuro los números vuelven a sentirse "demasiado chicos" de nuevo.

---

## 5bis. Arquitectura de datos elegida: pivot al catálogo

En vez de buscar publicaciones sueltas (bloqueado), el sistema trabaja sobre el **catálogo
oficial de productos** de ML. El flujo es:

```
/products/search?q="disyuntor diferencial"
        ↓  (devuelve productos normalizados, con marca como atributo estructurado)
/products/{id}/items
        ↓  (devuelve TODOS los vendedores de ese producto con sus precios)
/users/{seller_id}
        ↓  (nickname + reputación + volumen histórico)
   Análisis de competencia completo
```

**Ventajas sobre el enfoque original:**
- Los productos vienen normalizados: no hace falta adivinar qué publicaciones son "el mismo
  producto" con heurísticas de matcheo por título.
- La marca (`BRAND`) es un atributo estructurado → la comparativa de marcas es exacta.
- La cantidad de vendedores por producto es un indicador directo de demanda y presión
  competitiva (ej: *Disyuntor Schneider 4x25* → 38 vendedores compitiendo).

**Lo que se pierde:** ventas por publicación individual (`sold_quantity`).

---

## 6. Estado actual del dashboard, sección por sección

| Sección | Fuente de datos | Estado |
|---|---|---|
| Tendencias de búsqueda | `/api/trends` → `/trends/MLA` | ✅ Datos reales |
| Comparativa de marcas | `/api/analysis` → agrega `/products/search` por atributo `BRAND` | ✅ Datos reales |
| Productos y competencia del rubro | `/api/products` → `/products/search` | ✅ Datos reales |
| Panel de competencia (drawer) | `/api/products/{id}/offers` → `/products/{id}/items` + `/users/{id}` | ✅ Datos reales |
| KPIs (rango de precios, vendedor dominante, producto más disputado) | Derivados de lo anterior | ✅ Datos reales |
| Productos equivalentes (panel y Analizar publicación) | `/api/products/{id}/related` → mismo `domain_id` + atributos técnicos del catálogo | ✅ Datos reales |
| Mapa del rubro | `POST /api/overview` → muestra de 25 productos por subcategoría | ✅ Datos reales (muestra) |
| Tendencias → "Analizar" | Botón por término de tendencia, busca dentro de la subcategoría | ✅ |

### 6.1. Qué muestra cada métrica

- **Vendedores**: cuántos compiten por el mismo producto de catálogo. Proxy de demanda y de
  dificultad para ganar por precio.
- **Precio desde / hasta**: dispersión real entre todos los oferentes del producto.
- **Ventas del vendedor**: transacciones históricas totales de esa cuenta (no del producto).
- **Nivel de competencia** (alta / media / oportunidad): score combinado de reputación del
  vendedor y su volumen histórico.
- **Vendedor dominante**: el que aparece con el mejor precio en más productos del rubro.
- **Productos equivalentes**: otros productos del mismo `domain_id` comparados atributo por
  atributo (polos, corriente, potencia, IP...). "Mismas specs" = todas las especificaciones
  numéricas coinciden (tolerancia ±10% para 220V/230V/240V) y no difieren las medidas escritas en
  el nombre. Muestra precio mínimo y mediana de los equivalentes vs. el producto analizado.
- **Mapa del rubro**: vendedores promedio por producto (Baja <5, Media 5-12, Alta ≥12), productos
  con ≤3 vendedores, precio mediano, % envío gratis y % tiendas oficiales sobre la muestra.
  Subcategorías con menos de 8 productos con vendedores se marcan "muestra chica".

---

## 7. Líneas rojas (decisiones de seguridad tomadas explícitamente)

Estas restricciones se establecieron después de intentos fallidos y una corrección de rumbo
explícita del usuario. No se deben revertir sin que el usuario lo pida de nuevo:

1. **No usar la sesión personal de Chrome del usuario** para automatizar navegación en ML
   (riesgo de que ML marque la cuenta de vendedor real como bot).
2. **No hacer web scraping** del HTML de Mercado Libre con Playwright/browsers headless.
   Se intentó, ML lo detecta (challenge de seguridad), y esto viola los Términos y Condiciones
   de la plataforma.
3. **No usar servicios de terceros de scraping** (DataForSEO, Bright Data, etc.) — son pagos y
   están fuera del alcance actual.
4. Cualquier credencial (Client Secret, tokens) que se comparta accidentalmente en el chat debe
   regenerarse en el portal ML.
5. **No fragmentar busquedas por rangos de precio (u otro truco) para esquivar el techo real de
   `/products/search`** (200 resultados por busqueda desde el 2026-09-16, antes ~1050 — ver §5.8).
   Ese limite es una medida anti-abuso deliberada de ML para apps no certificadas; armar un
   algoritmo para esquivarlo sistematicamente (para "miles de categorias") es exactamente el
   patron de extraccion masiva que ese limite existe para frenar, con riesgo real de suspension
   de la app/cuenta. Se propuso 2 veces en la sesion del 2026-09-15 (via IAs externas) y se
   rechazo las 2 veces. Usar el maximo honesto por busqueda (`limit=100`, hasta `offset=100`) no
   es lo mismo que esto y esta permitido — ver §5.8.
6. **No inferir ventas de terceros via diferencia de `available_quantity` u otro campo**, aunque
   sea matematicamente prolijo: hoy es ademas moot porque `/items/{id}` de terceros da 403 en
   esta app no certificada, pero el rechazo es por principio (no por la limitacion tecnica).

---

## 8. Modelo de escalabilidad (multi-rubro)

El sidebar y el selector de categorías están gobernados por un único array en
`static/app.js`:

```js
const CATEGORIES = [
  { id: 'electrico', label: 'Materiales Eléctricos', active: true, subcats: [...] },
  { id: 'ferreteria', label: 'Ferretería', active: false },
  // ...
];
```

Agregar un rubro nuevo implica:
1. Sumar una entrada a `CATEGORIES` con sus subcategorías de búsqueda
   (`group` + `label` + `q` + `domain` + `cat`).
2. Marcar `active: true`.
3. **Calibrar con datos, no a ojo** (método de 5.6): obtener el `domain_id` con
   `domain_discovery` y el árbol de `/categories/{id}`; para elegir `q`, probar sinónimos
   rioplatenses + las tendencias de `/trends/MLA/{cat}` y quedarse con el término (sin marca) que
   tenga más productos con vendedores entre los primeros 20-30. Si ningún término supera ~3/30,
   el tipo de producto no vive en el catálogo y no conviene sumarlo.
4. Opcionalmente, asignar `mlCategoryId` (ID de categoría oficial de ML) para habilitar
   `/highlights` en ese rubro en cuanto el scope esté activo.

No hace falta tocar `index.html` ni `style.css` — el sidebar y el `<select>` de categoría se
renderizan dinámicamente desde ese array.

---

## 9. Roadmap

1. ✅ **Afinar búsquedas del rubro** (hecho 2026-09-16): 18 → 35 subcategorías calibradas con
   `domain_id` + palabra clave medida (ver 5.6); arreglado bug de paginación del listado (pedía
   páginas de 24 y avanzaba de a 50, salteando productos); orden por probabilidad de tener
   vendedores; "Analizar publicación" con match exacto para links de terceros (5.7); productos
   equivalentes por especificación; vista Mapa del rubro; tendencias clickeables.
2. ✅ **Persistencia histórica** (hecho 2026-09-15): snapshots de precio/vendedores por producto en
   SQLite (`data/mercadata.db`), guardados en cada corrida de `/api/analysis` sin llamadas extra.
   Endpoint `/api/reports/product-timeseries`, grafico de tendencia en el panel de producto.
2bis. ✅ **Corrección de categorías/dominios mal mapeados** (hecho 2026-09-15): 4 de las 18
   subcategorías de "Materiales Eléctricos" apuntaban a un `category` de ML incorrecto o
   demasiado ancho, causando marcas/productos ajenos al rubro real en marcas, productos y
   gráficos ("Disyuntores y Protección", "Tableros y Medidores", "Lámparas LED", "Herramientas
   Eléctricas" — ver 5.5 para el detalle verificado). Se sumó soporte de `domain_id` en
   `/api/products` y `/api/analysis` (opcional, `?domain=`) para los casos donde `category` +
   texto libre no alcanzaba. Se eliminó `/api/brands`, endpoint muerto que ya no llamaba el
   frontend (la comparativa de marcas corre sobre `/api/analysis` desde antes).
3. **Alertas**: avisar cuando un competidor baja de precio por debajo del propio.
4. **Replicar a nuevos rubros**: sumar entradas a `CATEGORIES` en `static/app.js`.
5. Descartado: certificación de la app en ML (requisitos de GMV inalcanzables) y cualquier
   forma de scraping.

---

## 10. Cómo correr el proyecto

```powershell
# 1. Copiar plantilla de credenciales
copy .env.example .env
# completar ML_CLIENT_ID, ML_CLIENT_SECRET, SECRET_KEY

# 2. Arrancar
start.bat
# o directamente:
python app.py

# 3. Autorizar (una sola vez, o cuando el token expire sin refresh_token válido)
# abrir http://localhost:5000/auth/setup
```
