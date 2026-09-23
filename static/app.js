/**
 * Mercadata — Frontend
 *
 * Modelo de datos: se trabaja sobre el CATALOGO de ML (/products). Cada producto de
 * catalogo agrupa a todos los vendedores que lo ofrecen, lo que permite comparar precios
 * de forma exacta y agregar por marca sin heuristicas de matcheo por titulo.
 *
 * Escalabilidad: agregar un rubro nuevo = agregar una entrada en CATEGORIES con su
 * `mlCategory` (id de categoria de ML, para tendencias) y sus subcategorias.
 */

'use strict';

// ═══════════════════════════════════════════════════════════
// CATALOGO DE RUBROS
// `mlCategory` alimenta /trends para que las tendencias sean del rubro y no genericas.
// ═══════════════════════════════════════════════════════════
const CATEGORIES = [
  {
    id: 'electrico',
    label: 'Materiales Eléctricos',
    active: true,
    mlCategory: 'MLA2467',
    icon: '<path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>',
    // Calibrado con requests reales el 2026-09-16 (ver PROJECT_SPEC.md 5.6):
    // - `domain` (tipo de producto de ML) es el filtro principal: con category sola
    //   se colaban medidores, libros, paneles de puerta de auto, etc.
    // - `q` se eligio midiendo cuantos de los primeros 20-30 productos tienen
    //   vendedores activos hoy, probando sinonimos y las tendencias reales de cada
    //   categoria. El vocabulario argentino rinde mucho mas que el "de catalogo":
    //   "termica" 27/30 vs "disyuntor" 0/30; "pinza amperometrica" 20/30 vs
    //   "amperimetrica" 2/30; "modulo toma" 17/30 vs "tomacorriente" 0/30.
    //   Se descartaron terminos con marca (ej. "contactor sica") aunque rindan mas,
    //   porque sesgan las marcas del analisis.
    // - `cat` solo alimenta las tendencias de busqueda de esa subcategoria.
    // - Se quitaron "Motores" y "Transformadores": el catalogo de ML Argentina casi no
    //   los tiene (0-3 de 30 con vendedores, el resto transformadores de audio y
    //   motores de auto) — se venden como publicaciones sueltas, fuera del catalogo.
    subcats: [
      { group: 'Protección y maniobra', q: 'termica',                label: 'Térmicas',                   cat: 'MLA30208',  domain: 'MLA-CIRCUIT_BREAKERS' },
      { group: 'Protección y maniobra', q: 'disyuntor diferencial',  label: 'Disyuntores diferenciales',  cat: 'MLA30208',  domain: 'MLA-CIRCUIT_BREAKERS' },
      { group: 'Protección y maniobra', q: 'protector de tension',   label: 'Protectores de tensión',     cat: 'MLA1719',   domain: 'MLA-STABILIZERS_AND_UPS' },
      { group: 'Protección y maniobra', q: 'contactor tripolar',     label: 'Contactores',                cat: 'MLA411420', domain: 'MLA-HOME_APPLIANCE_CONTACTORS_AND_RELAYS' },
      { group: 'Protección y maniobra', q: 'guardamotor trifasico',  label: 'Guardamotores',              cat: 'MLA433701', domain: 'MLA-MOTOR_STARTERS' },
      { group: 'Protección y maniobra', q: 'fusible tabaquera',      label: 'Fusibles',                   cat: 'MLA381284', domain: 'MLA-INDUSTRIAL_FUSES' },
      { group: 'Protección y maniobra', q: 'temporizador riel din',  label: 'Temporizadores',             cat: 'MLA388861', domain: 'MLA-ELECTRICAL_TIMERS' },
      { group: 'Protección y maniobra', q: 'fotocontrol',            label: 'Fotocontroles',              cat: 'MLA434732', domain: 'MLA-PHOTOCONTROLS' },
      { group: 'Protección y maniobra', q: 'variador de frecuencia', label: 'Variadores de frecuencia',   cat: 'MLA381282', domain: 'MLA-VARIABLE_FREQUENCY_DRIVES' },

      { group: 'Instalación', q: 'cable unipolar',        label: 'Cable unipolar',             cat: 'MLA455454', domain: 'MLA-ELECTRICAL_CABLES' },
      { group: 'Instalación', q: 'cable tipo taller',     label: 'Cable taller / subterráneo', cat: 'MLA455454', domain: 'MLA-ELECTRICAL_CABLES' },
      { group: 'Instalación', q: 'corrugado ignifugo',    label: 'Caños corrugados',           cat: 'MLA411424', domain: 'MLA-CORRUGATED_PIPES' },
      { group: 'Instalación', q: 'gabinete estanco',      label: 'Cajas y gabinetes estancos', cat: 'MLA416561', domain: 'MLA-CABINETS_AND_JUNCTION_BOXES' },
      { group: 'Instalación', q: 'tablero automatico',    label: 'Tableros',                   cat: 'MLA411423', domain: 'MLA-TRANSFER_SWITCHES' },
      { group: 'Instalación', q: 'medidor monofasico',    label: 'Medidores de energía',       cat: 'MLA411422', domain: 'MLA-ELECTRICITY_METERS' },
      { group: 'Instalación', q: 'llave de luz',          label: 'Llaves de luz',              cat: 'MLA388863', domain: 'MLA-WALL_LIGHT_SWITCHES' },
      { group: 'Instalación', q: 'modulo toma',           label: 'Tomacorrientes',             cat: 'MLA435481', domain: 'MLA-ELECTRICAL_OUTLETS' },
      { group: 'Instalación', q: 'ficha macho',           label: 'Fichas',                     cat: 'MLA435484', domain: 'MLA-ELECTRIC_PLUGS' },
      { group: 'Instalación', q: 'alargue prolongador',   label: 'Zapatillas y alargues',      cat: 'MLA411421', domain: 'MLA-POWER_STRIPS' },
      { group: 'Instalación', q: 'portalampara e27',      label: 'Portalámparas',              cat: 'MLA388858', domain: 'MLA-LAMP_HOLDERS' },
      { group: 'Instalación', q: 'cinta aisladora',       label: 'Cintas aisladoras',          cat: 'MLA422401', domain: 'MLA-ADHESIVE_TAPES' },

      { group: 'Iluminación', q: 'lampara led 9w',             label: 'Lámparas LED',          cat: 'MLA377395', domain: 'MLA-LIGHT_BULBS' },
      { group: 'Iluminación', q: 'dicroica led',               label: 'Dicroicas LED',         cat: 'MLA377395', domain: 'MLA-LIGHT_BULBS' },
      { group: 'Iluminación', q: 'tira led 5050',              label: 'Tiras de LED',          cat: 'MLA388926', domain: 'MLA-LED_STRIPS' },
      { group: 'Iluminación', q: 'reflectores led exterior',   label: 'Reflectores',           cat: 'MLA373504', domain: 'MLA-FLOOD_LIGHTS' },
      { group: 'Iluminación', q: 'luz de techo',               label: 'Plafones y apliques',   cat: 'MLA1588',   domain: 'MLA-FLOOR_CEILING_AND_WALL_LIGHTS' },
      { group: 'Iluminación', q: 'luz de emergencia',          label: 'Luces de emergencia',   cat: 'MLA125102', domain: 'MLA-EMERGENCY_LIGHTS' },

      { group: 'Medición', q: 'pinza amperometrica', label: 'Pinzas amperométricas', cat: 'MLA30763',  domain: 'MLA-CLAMP_METERS' },
      { group: 'Medición', q: 'tester',              label: 'Testers / multímetros', cat: 'MLA30810',  domain: 'MLA-MULTIMETERS' },
      { group: 'Medición', q: 'buscapolo',           label: 'Buscapolos',            cat: 'MLA435490', domain: 'MLA-VOLTAGE_DETECTORS' },

      { group: 'Energía', q: 'grupo electrogeno', label: 'Grupos electrógenos', cat: 'MLA30823',  domain: 'MLA-PORTABLE_GENERATORS' },
      { group: 'Energía', q: 'inversor solar',    label: 'Inversores',          cat: 'MLA435616', domain: 'MLA-POWER_INVERTERS' },
      { group: 'Energía', q: 'regulador solar',   label: 'Reguladores solares', cat: 'MLA435615', domain: 'MLA-VOLTAGE_REGULATORS' },
      { group: 'Energía', q: 'panel solar',       label: 'Paneles solares',     cat: 'MLA388630', domain: 'MLA-SOLAR_PANELS' },

      { group: 'Herramientas', q: 'taladro percutor', label: 'Taladros', cat: 'MLA455276', domain: 'MLA-ELECTRIC_DRILLS' },
    ],
  },
  { id: 'ferreteria',   label: 'Ferretería',   active: false, icon: '<circle cx="12" cy="12" r="9"/>' },
  { id: 'plomeria',     label: 'Plomería',     active: false, icon: '<path d="M4 12h16M12 4v16"/>' },
  { id: 'construccion', label: 'Construcción', active: false, icon: '<rect x="4" y="4" width="16" height="16" rx="2"/>' },
  { id: 'pinturas',     label: 'Pinturería',   active: false, icon: '<circle cx="12" cy="12" r="9"/>' },
];

const CFG = {
  // Cuántos productos (de los que tienen vendedores activos) se muestran en la
  // tabla, una vez escaneado el máximo alcanzable por búsqueda (200, ver
  // fetchProductsWithOffers). Se muestran los más disputados primero.
  PAGE_SIZE   : 100,
  MY_NICK     : (window.__MY_NICKNAME__ || '').toUpperCase(),
};

const PALETTE = ['#5b4fe0','#3ecf8e','#e8ac3e','#4f96ec','#e8863f','#e8586c','#9c8cf2','#38b2a8','#4fb8d9','#d9924f','#e07a9e','#8a8fa3'];

// ═══════════════════════════════════════════════════════════
// ESTADO
// ═══════════════════════════════════════════════════════════
const State = {
  products    : [],
  offersById  : {},
  total       : 0,
  analysis    : null,
  loading     : false,
  query       : '',
  sortBy      : 'sellers',
  view        : 'dashboard',
  myBizLoaded : false,
  myBizRequestSeq: 0,
  activeCat   : CATEGORIES.find(c => c.active),
  activeSub   : null,
  panelProduct: null,
  lookup      : null,
  overview    : null,
  overviewSort: { key: 'avg_sellers', dir: 1 },
  compare     : [],
  brandFilter : null,
  undercutSeq : 0,
};
State.activeSub = State.activeCat.subcats[0];

// ═══════════════════════════════════════════════════════════
// API
// ═══════════════════════════════════════════════════════════
const API = {
  async products(q, offset = 0, category = '', domain = '', limit = CFG.PAGE_SIZE) {
    const params = { q, limit, offset };
    if (category) params.category = category;
    if (domain) params.domain = domain;
    const r = await fetch(`/api/products?${new URLSearchParams(params)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async offers(productId, light = false) {
    const r = await fetch(`/api/products/${productId}/offers${light ? '?light=1' : ''}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async related(productId) {
    const r = await fetch(`/api/products/${encodeURIComponent(productId)}/related`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async overview(subcats) {
    const r = await fetch('/api/overview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subcats }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async timeseries(productId) {
    const r = await fetch(`/api/reports/product-timeseries?${new URLSearchParams({ product_id: productId })}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async trends(category = '') {
    const r = await fetch(`/api/trends${category ? `?category=${encodeURIComponent(category)}` : ''}`);
    return r.json();
  },
  async lookup(input, days = 30) {
    const r = await fetch(`/api/lookup?${new URLSearchParams({ input, days })}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async analysis(q, category = '', domain = '') {
    const params = { q };
    if (category) params.category = category;
    if (domain) params.domain = domain;
    const r = await fetch(`/api/analysis?${new URLSearchParams(params)}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async myBusiness(days) {
    const r = await fetch(`/api/my-business?days=${days}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async priceAlerts(q) {
    const r = await fetch(`/api/reports/price-alerts?${new URLSearchParams({ q })}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async sellerTimeseries(nickname) {
    const r = await fetch(`/api/reports/seller-timeseries?${new URLSearchParams({ nickname })}`);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
  async undercutAlerts() {
    const r = await fetch('/api/reports/undercut-alerts');
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || `Error HTTP ${r.status}`);
    return d;
  },
};

// ═══════════════════════════════════════════════════════════
// FORMATTERS
// ═══════════════════════════════════════════════════════════
const Fmt = {
  _ars: new Intl.NumberFormat('es-AR', { style:'currency', currency:'ARS', minimumFractionDigits:0, maximumFractionDigits:0 }),
  _num: new Intl.NumberFormat('es-AR'),
  price : (v) => (v == null || !isFinite(v)) ? '—' : Fmt._ars.format(v),
  number: (v) => v != null ? Fmt._num.format(v) : '—',
  esc   : (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'),

  rep(levelId) {
    const map = {
      '5_green'       : { cls: 'rep-5', label: 'Platinum' },
      '4_light_green' : { cls: 'rep-4', label: 'Oro'      },
      '3_yellow'      : { cls: 'rep-3', label: 'Plata'    },
      '2_orange'      : { cls: 'rep-2', label: 'Bronce'   },
      '1_red'         : { cls: 'rep-1', label: 'Bajo'     },
    };
    return map[levelId] || { cls: '', label: 'Sin datos' };
  },

  repDots(levelId) {
    const { cls, label } = Fmt.rep(levelId);
    return `<div class="rep-dots ${cls}">${'<span class="rep-dot"></span>'.repeat(5)}</div><div class="rep-label">${Fmt.esc(label)}</div>`;
  },

  threat(sellerSales, levelId) {
    let s = 0;
    s += { '5_green': 40, '4_light_green': 28, '3_yellow': 14, '2_orange': 5 }[levelId] || 0;
    if      (sellerSales > 50000) s += 45;
    else if (sellerSales > 10000) s += 35;
    else if (sellerSales > 2000)  s += 25;
    else if (sellerSales > 300)   s += 12;
    if (s >= 55) return { cls: 'threat-high', label: 'Competencia alta'  };
    if (s >= 28) return { cls: 'threat-mid',  label: 'Competencia media' };
    return           { cls: 'threat-low',  label: 'Oportunidad'      };
  },
};

// ═══════════════════════════════════════════════════════════
// DOM
// ═══════════════════════════════════════════════════════════
const $ = (id) => document.getElementById(id);
const html = (el, c) => { if (el) el.innerHTML = c; };

function showBanner(msg) { const el = $('errorBanner'); if (el) { $('errorText').textContent = msg; el.style.display = 'flex'; } }
function hideBanner()    { const el = $('errorBanner'); if (el) el.style.display = 'none'; }

function setProgress(label) {
  const pill = $('progressPill');
  if (!pill) return;
  if (!label) { pill.style.display = 'none'; return; }
  pill.style.display = 'flex';
  html($('progressLabel'), Fmt.esc(label));
}

function setSearchLoading(on) {
  const btn = $('btnSearch');
  if (!btn) return;
  btn.disabled = on;
  btn.textContent = on ? 'Analizando…' : 'Buscar';
}

function toast(msg) {
  const host = $('toastHost');
  if (!host) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ═══════════════════════════════════════════════════════════
// ROUTER DE VISTAS
// ═══════════════════════════════════════════════════════════
const VIEW_META = {
  dashboard: { sub: 'Panel general · Argentina',  showSort: true  },
  charts:    { sub: 'Gráficos del rubro · Argentina', showSort: false },
  overview:  { sub: 'Comparativa de subcategorías · Argentina', showSort: false },
  mybiz:     { sub: 'Datos reales de tu cuenta · Argentina', showSort: false },
  lookup:    { sub: 'Comparar una publicación puntual · Argentina', showSort: false },
};

function switchView(view) {
  State.view = view;
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('is-active', v.id === `view-${view}`));
  document.querySelectorAll('.nav-item[data-view]').forEach(el => el.classList.toggle('is-active', el.dataset.view === view));

  const meta = VIEW_META[view] || VIEW_META.dashboard;
  html($('topbarSub'), Fmt.esc(meta.sub));
  const sortWrap = $('sortWrap');
  if (sortWrap) sortWrap.style.display = meta.showSort ? '' : 'none';

  if (view === 'mybiz' && !State.myBizLoaded) App.loadMyBusiness();

  // Chart.js necesita recalcular tamaños cuando el contenedor pasa de display:none a visible
  if (view === 'charts' || view === 'mybiz' || view === 'lookup') setTimeout(() => Object.values(charts).forEach(c => c?.resize()), 60);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.switchView = switchView;

// ═══════════════════════════════════════════════════════════
// SIDEBAR
// ═══════════════════════════════════════════════════════════
function renderRubrosNav() {
  const nav = $('rubrosNav');
  if (!nav) return;
  nav.innerHTML = CATEGORIES.map(cat => {
    const cls = cat.active
      ? (cat.id === State.activeCat.id ? 'nav-item is-active' : 'nav-item')
      : 'nav-item is-disabled';
    return `<div class="${cls}" data-cat="${cat.id}">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${cat.icon}</svg>
      ${Fmt.esc(cat.label)}${cat.active ? '' : '<span class="nav-badge">Pronto</span>'}</div>`;
  }).join('');

  nav.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const cat = CATEGORIES.find(c => c.id === el.dataset.cat);
      if (!cat.active) { toast(`"${cat.label}" está planificado para una próxima etapa.`); return; }
      State.activeCat = cat;
      State.activeSub = cat.subcats[0];
      renderRubrosNav();
      populateCategorySelect();
      html($('topbarTitle'), Fmt.esc(cat.label));
      loadTrends();
    });
  });
}

function populateCategorySelect() {
  const sel = $('selCat');
  if (!sel) return;
  const groups = [];
  State.activeCat.subcats.forEach((s, i) => {
    let g = groups.find(x => x.name === (s.group || ''));
    if (!g) groups.push(g = { name: s.group || '', items: [] });
    g.items.push(`<option value="${i}">${Fmt.esc(s.label)}</option>`);
  });
  sel.innerHTML = groups.map(g => g.name
    ? `<optgroup label="${Fmt.esc(g.name)}">${g.items.join('')}</optgroup>`
    : g.items.join('')).join('');
}

// ═══════════════════════════════════════════════════════════
// TENDENCIAS — filtradas por la categoría de ML del rubro
// ═══════════════════════════════════════════════════════════
async function loadTrends() {
  const sub    = State.activeSub;
  const catId  = sub?.cat || State.activeCat.mlCategory || '';
  const label  = sub?.label || State.activeCat.label;

  html($('trendsSubtitle'), `Búsquedas reales en “${Fmt.esc(label)}”`);
  html($('trendsBody'), `<div class="empty-state"><div class="empty-title">Cargando tendencias…</div></div>`);

  try {
    let data  = await API.trends(catId);
    let items = data.items || [];

    // Algunas subcategorías muy específicas no tienen tendencias propias: se cae al rubro.
    if (!items.length && catId !== State.activeCat.mlCategory) {
      data  = await API.trends(State.activeCat.mlCategory);
      items = data.items || [];
      html($('trendsSubtitle'), `Búsquedas reales en “${Fmt.esc(State.activeCat.label)}”`);
    }

    if (!items.length) {
      html($('trendsBody'), `<div class="empty-state"><div class="empty-title">Sin tendencias para esta categoría</div></div>`);
      return;
    }

    html($('trendsBody'), `<div class="trend-list">${items.slice(0, 14).map((it, i) => `
      <div class="trend-row">
        <div class="trend-rank ${i < 3 ? 'tier-1' : i < 6 ? 'tier-2' : ''}">${i + 1}</div>
        <div class="trend-kw">${Fmt.esc(it.keyword)}</div>
        <button class="trend-link trend-analyze" data-kw="${Fmt.esc(it.keyword)}" title="Analizar este término dentro de la subcategoría">Analizar</button>
        <a class="trend-link" href="${Fmt.esc(it.url)}" target="_blank" rel="noopener noreferrer">Ver en ML
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7,7 17,7 17,17"/></svg>
        </a>
      </div>`).join('')}</div>`);
    $('trendsBody').querySelectorAll('.trend-analyze').forEach(btn => btn.addEventListener('click', () => {
      const inp = $('inputQ');
      if (inp) inp.value = btn.dataset.kw;
      App.search();
    }));
  } catch (e) {
    html($('trendsBody'), `<div class="empty-state"><div class="empty-title">No se pudieron cargar las tendencias</div><div class="empty-sub">${Fmt.esc(e.message)}</div></div>`);
  }
}

// ═══════════════════════════════════════════════════════════
// MARCAS (panel general) — se alimenta del mismo análisis que los gráficos
// ═══════════════════════════════════════════════════════════

/** Texto honesto sobre cuanto del catalogo se analizo: 100% real o el techo que impone la API de ML. */
function coverageNote(a) {
  const n = a.catalog_sample || a.analyzed || 0;
  if (a.full_coverage) return `Se analizó el 100% del catálogo (${Fmt.number(n)} productos)`;
  return `Se analizaron ${Fmt.number(n)} de ${Fmt.number(a.total_catalog)} — Mercado Libre no permite recuperar más de eso por búsqueda`;
}

/**
 * Aviso honesto sobre el sesgo de muestreo de marcas: verificado 2026-09-16 que
 * NINGUNA búsqueda de texto da una muestra representativa de marcas — el ranking
 * de relevancia de ML mezcla marcas totalmente distinto segun la palabra exacta
 * usada (ej. en Lámparas LED: "led" trae 127 marcas distintas y 0 productos Sica,
 * "dicroica led" trae 5 Sica, la búsqueda curada de la subcategoría trae 11 Sica
 * — pero Sica tiene 231 productos reales en ese dominio). No hay forma de
 * arreglar esto sin fragmentar en docenas de búsquedas por dominio, algo
 * descartado a propósito (ver PROJECT_SPEC.md 7.5). Por eso el grafico se
 * etiqueta como "muestra" y no como "presencia real en el catálogo".
 */
function brandSampleCaveat(a) {
  const n = a.catalog_sample || a.analyzed || 0;
  return `Estos números son de una <strong>muestra de ${Fmt.number(n)} productos</strong> para la búsqueda de esta
    subcategoría, no de todo el catálogo. Mercado Libre no deja traer una muestra pareja de marcas: una marca
    puede tener muchos más productos reales de los que aparecen acá si sus títulos no coinciden bien con esta
    búsqueda puntual — no la descartes solo por este número.`;
}

function renderBrandBars(a) {
  const brands = (a.brands || []).slice(0, 10);
  if (!brands.length) {
    html($('marcasBody'), `<div class="empty-state"><div class="empty-title">Sin datos de marcas</div></div>`);
    return;
  }
  const max = brands[0].products || 1;
  html($('marcasBody'), `
    <div class="brand-bars">${brands.map(b => `
      <div class="brand-bar-row${State.brandFilter === b.brand ? ' is-active' : ''}" data-brand="${Fmt.esc(b.brand)}" onclick="App.filterByBrand('${Fmt.esc(b.brand)}')" title="Filtrar la tabla de abajo por ${Fmt.esc(b.brand)}">
        <div class="brand-bar-label" title="${Fmt.esc(b.brand)}">${Fmt.esc(b.brand)}</div>
        <div class="brand-bar-track"><div class="brand-bar-fill" style="width:${(b.products / max) * 100}%"></div></div>
        <div class="brand-bar-val">${b.products}</div>
      </div>`).join('')}</div>
    <div class="insight" style="margin:0 18px 14px">
      <div class="insight-icon i-warn">!</div>
      <div class="insight-text">${brandSampleCaveat(a)}</div>
    </div>
    <div style="padding:0 18px 16px;font-size:11.5px;color:var(--text-3)">
      ${coverageNote(a)} · hacé clic en una marca para filtrar la tabla ·
      <a href="#" onclick="switchView('charts');return false;" style="color:var(--accent-2)">Ver gráficos completos →</a>
    </div>`);
}

// ═══════════════════════════════════════════════════════════
// GRAFICOS
// ═══════════════════════════════════════════════════════════
const charts = {};

const CHART_BASE = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#8b8d98', font: { size: 11, family: 'Sansation' }, boxWidth: 10, padding: 10 } },
    tooltip: {
      backgroundColor: '#1e1e26', borderColor: '#2a2a34', borderWidth: 1,
      titleColor: '#f3f4f6', bodyColor: '#8b8d98', padding: 10, cornerRadius: 8,
      titleFont: { size: 12, family: 'Sansation' }, bodyFont: { size: 11.5, family: 'Sansation' },
    },
  },
};

const AXES_DARK = {
  x: { ticks: { color: '#4b4d57', font: { size: 10.5, family: 'Sansation' } }, grid: { color: '#1f1f27' }, border: { display: false } },
  y: { ticks: { color: '#4b4d57', font: { size: 10.5, family: 'Sansation' } }, grid: { color: '#1f1f27' }, border: { display: false } },
};

function drawChart(canvasId, config) {
  const el = $(canvasId);
  if (!el || typeof Chart === 'undefined') return;
  if (charts[canvasId]) {
    // Si new Chart() de una corrida anterior tiro una excepcion a mitad de camino,
    // charts[canvasId] quedaba apuntando a una instancia ya destruida (Chart.js
    // pone this.canvas = null al final de destroy()); volver a llamar .destroy()
    // sobre eso tira "Cannot read properties of null (reading 'style')". Se limpia
    // la entrada ANTES de intentar destruir, para que un fallo no dañe la proxima corrida.
    const stale = charts[canvasId];
    delete charts[canvasId];
    try { stale.destroy(); } catch { /* ya estaba destruido/roto, ignorar */ }
  }
  try {
    charts[canvasId] = new Chart(el, config);
  } catch (e) {
    console.error('[Mercadata] drawChart', canvasId, e);
  }
}

function renderCharts(a) {
  $('chartsEmpty').style.display   = 'none';
  $('chartsContent').style.display = '';

  // KPIs propios de la vista
  const uniqueSellers = new Set();
  (a.sellers || []).forEach(s => uniqueSellers.add(s.nickname));
  const setKpi = (id, val, sub) => {
    const el = $(id);
    if (!el) return;
    el.querySelector('.metric-value').textContent = val;
    if (sub) el.querySelector('.metric-sub').textContent = sub;
  };
  setKpi('cProducts', Fmt.number(a.catalog_sample || a.analyzed), coverageNote(a));
  setKpi('cBrands',   Fmt.number((a.brands || []).length));
  setKpi('cSellers',  Fmt.number(uniqueSellers.size), 'Top vendedores del rubro');
  setKpi('cAvgPrice', Fmt.price(a.price_stats?.avg));

  const brands = (a.brands || []).slice(0, 9);

  // 0. Mapa de oportunidad: cada producto como un punto (vendedores x precio),
  // tamaño = dispersion de precio. Coloreado por marca para detectar patrones.
  const oppProducts = (a.products || []).filter(p => p.sellers > 0 && p.min_price > 0);
  const brandIndex = new Map((a.brands || []).map((b, i) => [b.brand, i]));
  const colorFor = (brand) => PALETTE[(brandIndex.get(brand) ?? 0) % PALETTE.length];
  drawChart('chartOpportunity', {
    type: 'bubble',
    data: {
      datasets: [{
        label: 'Productos',
        data: oppProducts.map(p => ({ x: p.sellers, y: p.min_price, r: Math.min(16, 5 + (p.spread_pct || 0) / 12), _p: p })),
        backgroundColor: oppProducts.map(p => colorFor(p.brand) + 'b3'),
        borderColor: oppProducts.map(p => colorFor(p.brand)),
        borderWidth: 1.5,
      }],
    },
    options: {
      ...CHART_BASE, scales: {
        x: { ...AXES_DARK.x, title: { display: true, text: 'Vendedores compitiendo', color: '#4b4d57', font: { size: 11 } } },
        y: { ...AXES_DARK.y, title: { display: true, text: 'Precio mínimo', color: '#4b4d57', font: { size: 11 } } },
      },
      plugins: {
        ...CHART_BASE.plugins, legend: { display: false },
        tooltip: {
          ...CHART_BASE.plugins.tooltip,
          callbacks: {
            title: (c) => c[0].raw._p.name.slice(0, 60),
            label: (c) => { const p = c.raw._p; return `${p.brand || 'Sin marca'} · ${p.sellers} vendedores · ${Fmt.price(p.min_price)} · dispersión ${p.spread_pct}%`; },
          },
        },
      },
      onClick: (evt, elements, chart) => {
        if (!elements.length) return;
        const p = chart.data.datasets[elements[0].datasetIndex].data[elements[0].index]._p;
        App.openPanel({ id: p.id, name: p.name, brand: p.brand });
      },
      onHover: (evt, elements) => { evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
    },
  });

  // 1. Participación de marcas
  drawChart('chartBrandShare', {
    type: 'doughnut',
    data: {
      labels: brands.map(b => b.brand),
      datasets: [{ data: brands.map(b => b.products), backgroundColor: PALETTE, borderColor: '#121217', borderWidth: 2 }],
    },
    options: { ...CHART_BASE, cutout: '58%', plugins: { ...CHART_BASE.plugins, legend: { ...CHART_BASE.plugins.legend, position: 'right' } } },
  });

  // 2. Demanda por marca
  const byDemand = [...(a.brands || [])].sort((x, y) => y.avg_sellers - x.avg_sellers).slice(0, 8);
  drawChart('chartBrandDemand', {
    type: 'bar',
    data: {
      labels: byDemand.map(b => b.brand),
      datasets: [{ label: 'Vendedores por producto', data: byDemand.map(b => b.avg_sellers), backgroundColor: '#3ecf8e', borderRadius: 5 }],
    },
    options: { ...CHART_BASE, scales: AXES_DARK, plugins: { ...CHART_BASE.plugins, legend: { display: false } } },
  });

  // 3. Posicionamiento de precios
  const byPrice = [...(a.brands || [])].filter(b => b.avg_price > 0).sort((x, y) => y.avg_price - x.avg_price).slice(0, 8);
  drawChart('chartBrandPrice', {
    type: 'bar',
    data: {
      labels: byPrice.map(b => b.brand),
      datasets: [{ label: 'Precio promedio', data: byPrice.map(b => b.avg_price), backgroundColor: '#e8ac3e', borderRadius: 5 }],
    },
    options: {
      ...CHART_BASE, indexAxis: 'y', scales: AXES_DARK,
      plugins: { ...CHART_BASE.plugins, legend: { display: false },
        tooltip: { ...CHART_BASE.plugins.tooltip, callbacks: { label: (c) => Fmt.price(c.raw) } } },
    },
  });

  // 4. Productos más disputados
  const topProd = (a.products || []).slice(0, 8);
  drawChart('chartTopProducts', {
    type: 'bar',
    data: {
      labels: topProd.map(p => (p.name || '').split(' ').slice(0, 4).join(' ')),
      datasets: [{ label: 'Vendedores', data: topProd.map(p => p.sellers), backgroundColor: '#5b4fe0', borderRadius: 5 }],
    },
    options: {
      ...CHART_BASE, indexAxis: 'y', scales: AXES_DARK,
      plugins: { ...CHART_BASE.plugins, legend: { display: false },
        tooltip: { ...CHART_BASE.plugins.tooltip, callbacks: { title: (c) => topProd[c[0].dataIndex].name } } },
    },
  });

  // 5. Mayor dispersión de precios
  const bySpread = [...(a.products || [])].filter(p => p.spread_pct > 0).sort((x, y) => y.spread_pct - x.spread_pct).slice(0, 8);
  drawChart('chartSpread', {
    type: 'bar',
    data: {
      labels: bySpread.map(p => (p.name || '').split(' ').slice(0, 4).join(' ')),
      datasets: [{ label: 'Dispersión %', data: bySpread.map(p => p.spread_pct), backgroundColor: '#e8863f', borderRadius: 5 }],
    },
    options: {
      ...CHART_BASE, indexAxis: 'y', scales: AXES_DARK,
      plugins: { ...CHART_BASE.plugins, legend: { display: false },
        tooltip: { ...CHART_BASE.plugins.tooltip, callbacks: {
          title: (c) => bySpread[c[0].dataIndex].name,
          label: (c) => `+${c.raw}% entre el más barato y el más caro`,
        } } },
    },
  });

  // 6. Vendedores con más presencia
  const sellers = (a.sellers || []).slice(0, 10);
  drawChart('chartTopSellers', {
    type: 'bar',
    data: {
      labels: sellers.map(s => s.nickname),
      datasets: [
        { label: 'Productos donde compite', data: sellers.map(s => s.appearances), backgroundColor: '#4f96ec', borderRadius: 5 },
        { label: 'Veces con mejor precio',  data: sellers.map(s => s.wins),        backgroundColor: '#3ecf8e', borderRadius: 5 },
      ],
    },
    options: { ...CHART_BASE, indexAxis: 'y', scales: AXES_DARK },
  });

  // 7. Reputación
  const repLabels = { '5_green': 'Platinum', '4_light_green': 'Oro', '3_yellow': 'Plata', '2_orange': 'Bronce', '1_red': 'Bajo', 'sin_datos': 'Sin datos' };
  const repColors = { '5_green': '#3ecf8e', '4_light_green': '#7fe0bb', '3_yellow': '#e8ac3e', '2_orange': '#e8863f', '1_red': '#e8586c' };
  const repEntries = Object.entries(a.reputation || {}).sort((x, y) => y[1] - x[1]);
  drawChart('chartReputation', {
    type: 'pie',
    data: {
      labels: repEntries.map(([k]) => repLabels[k] || k),
      datasets: [{
        data: repEntries.map(([, v]) => v),
        backgroundColor: repEntries.map(([k]) => repColors[k] || '#4b4d57'),
        borderColor: '#121217', borderWidth: 2,
      }],
    },
    options: { ...CHART_BASE, plugins: { ...CHART_BASE.plugins, legend: { ...CHART_BASE.plugins.legend, position: 'right' } } },
  });

  // 8. Política de envíos
  const free = a.logistics?.free || 0, paid = a.logistics?.paid || 0;
  drawChart('chartShipping', {
    type: 'doughnut',
    data: {
      labels: ['Con envío gratis', 'Sin envío gratis'],
      datasets: [{ data: [free, paid], backgroundColor: ['#3ecf8e', '#4b4d57'], borderColor: '#121217', borderWidth: 2 }],
    },
    options: { ...CHART_BASE, cutout: '58%', plugins: { ...CHART_BASE.plugins, legend: { ...CHART_BASE.plugins.legend, position: 'right' } } },
  });
}

// ═══════════════════════════════════════════════════════════
// INSIGHTS — reglas deterministas sobre los datos ya cargados
// ═══════════════════════════════════════════════════════════
function renderInsights(a) {
  const out = [];
  const brands  = a.brands || [];
  const sellers = a.sellers || [];
  const prods   = a.products || [];

  if (brands.length) {
    const top = brands[0];
    out.push({ t: 'info', html: `<strong>${Fmt.esc(top.brand)}</strong> es la marca con más presencia en esta muestra: ${top.products} productos distintos de los analizados para esta búsqueda (no necesariamente el total real de la marca, ver nota en "Marcas del rubro").` });

    const demand = [...brands].sort((x, y) => y.avg_sellers - x.avg_sellers)[0];
    if (demand && demand.avg_sellers >= 3) {
      out.push({ t: 'info', html: `<strong>${Fmt.esc(demand.brand)}</strong> es la marca más disputada: un promedio de <strong>${demand.avg_sellers} vendedores</strong> por producto. Alta demanda, pero competencia dura.` });
    }

    const cheap = [...brands].filter(b => b.avg_price > 0).sort((x, y) => x.avg_price - y.avg_price)[0];
    const pricey = [...brands].filter(b => b.avg_price > 0).sort((x, y) => y.avg_price - x.avg_price)[0];
    if (cheap && pricey && cheap.brand !== pricey.brand) {
      out.push({ t: 'info', html: `Rango de posicionamiento: <strong>${Fmt.esc(cheap.brand)}</strong> juega en la gama económica (${Fmt.price(cheap.avg_price)} promedio) y <strong>${Fmt.esc(pricey.brand)}</strong> en la premium (${Fmt.price(pricey.avg_price)}).` });
    }
  }

  const lowComp = prods.filter(p => p.sellers > 0 && p.sellers <= 2);
  if (lowComp.length) {
    out.push({ t: 'op', html: `<strong>${lowComp.length} productos</strong> tienen 2 o menos vendedores. Poca competencia directa: puede ser una puerta de entrada, aunque conviene validar que tengan demanda real.` });
  }

  const wide = [...prods].sort((x, y) => y.spread_pct - x.spread_pct)[0];
  if (wide && wide.spread_pct > 40) {
    out.push({ t: 'op', html: `En <strong>${Fmt.esc((wide.name || '').split(' ').slice(0, 6).join(' '))}</strong> hay una diferencia del <strong>${wide.spread_pct}%</strong> entre el precio más bajo y el más alto. Dispersión así de amplia suele significar margen para posicionarse.` });
  }

  if (sellers.length) {
    const dom = sellers[0];
    out.push({ t: 'warn', html: `<strong>${Fmt.esc(dom.nickname)}</strong> aparece en ${dom.appearances} de los productos analizados y gana en precio ${dom.wins} ${dom.wins === 1 ? 'vez' : 'veces'}. Es el competidor a vigilar en este rubro.` });
  }

  const free = a.logistics?.free || 0, paid = a.logistics?.paid || 0;
  if (free + paid > 0) {
    const pct = Math.round((free / (free + paid)) * 100);
    out.push({ t: pct >= 70 ? 'warn' : 'info', html: `El <strong>${pct}%</strong> de las publicaciones ofrece envío gratis. ${pct >= 70 ? 'Es prácticamente un requisito para competir en este rubro.' : 'Todavía hay espacio para diferenciarse con logística.'}` });
  }

  const icons = { op: '↗', warn: '!', info: 'i' };
  html($('insightsBody'), `<div class="insight-list">${out.map(i => `
    <div class="insight">
      <div class="insight-icon i-${i.t}">${icons[i.t]}</div>
      <div class="insight-text">${i.html}</div>
    </div>`).join('')}</div>`);

  $('seccion-insights').style.display = out.length ? '' : 'none';
}

// ═══════════════════════════════════════════════════════════
// ALERTAS DE PRECIO — compara la corrida actual contra la anterior guardada.
// Recien muestra algo util despues de haber analizado el mismo rubro 2+ veces.
// ═══════════════════════════════════════════════════════════
async function loadPriceAlerts(q) {
  const section = $('seccion-alertas');
  try {
    const data = await API.priceAlerts(q);
    const alerts = data.alerts || [];
    if (!alerts.length) { section.style.display = 'none'; return; }

    html($('alertsBody'), `<div class="insight-list">${alerts.slice(0, 8).map(a => {
      const down = a.pct_change < 0;
      return `<div class="insight">
        <div class="insight-icon ${down ? 'i-op' : 'i-warn'}">${down ? '↓' : '↑'}</div>
        <div class="insight-text">
          <strong>${Fmt.esc((a.name || '').split(' ').slice(0, 7).join(' '))}</strong>
          ${down ? 'bajó' : 'subió'} de <strong>${Fmt.price(a.old_price)}</strong> a
          <strong>${Fmt.price(a.new_price)}</strong> (${down ? '' : '+'}${a.pct_change}%)
          ${a.brand ? ` · ${Fmt.esc(a.brand)}` : ''}
        </div>
      </div>`;
    }).join('')}</div>`);
    section.style.display = '';
  } catch {
    section.style.display = 'none';
  }
}

// ═══════════════════════════════════════════════════════════
// ALERTAS DE UNDERCUT — tus publicaciones donde, ahora mismo, algun otro
// vendedor del mismo producto de catalogo tiene un precio mas bajo que el tuyo.
// A diferencia de "Movimientos de precio" (loadPriceAlerts), esto es especifico
// a tu cuenta y no depende de haber corrido un analisis del rubro antes.
// ═══════════════════════════════════════════════════════════
async function loadUndercutAlerts() {
  const seq = ++State.undercutSeq;
  const body = $('undercutBody');
  if (!body) return;
  html(body, `<div class="panel-loading"><div class="panel-spinner"></div><span>Comparando tus precios contra la competencia…</span></div>`);
  try {
    const data = await API.undercutAlerts();
    if (seq !== State.undercutSeq) return;
    renderUndercutAlerts(data);
  } catch (e) {
    if (seq !== State.undercutSeq) return;
    html(body, `<div class="empty-state"><div class="empty-sub">${Fmt.esc(e.message)}</div></div>`);
  }
}

function renderUndercutAlerts(data) {
  const alerts = data.alerts || [];
  const subParts = [`${Fmt.number(data.checked)} publicaciones con producto de catálogo revisadas`];
  if (data.no_catalog) subParts.push(`${Fmt.number(data.no_catalog)} sin match de catálogo (no se pueden comparar)`);
  html($('undercutSub'), subParts.join(' · '));

  if (!alerts.length) {
    html($('undercutBody'), `<div class="empty-state">
      <div class="empty-title">Nadie te está ganando por precio</div>
      <div class="empty-sub">${data.checked ? 'Tenés el precio más bajo en todas tus publicaciones catalogadas.' : 'No encontramos publicaciones propias agrupadas en el catálogo de ML todavía.'}</div>
    </div>`);
    return;
  }

  html($('undercutBody'), `<div class="insight-list">${alerts.map(a => `
    <div class="comp-card">
      <div class="comp-top">
        <div class="comp-left"><div class="comp-nick-wrap">
          <span class="comp-nick">${Fmt.esc((a.title || '').split(' ').slice(0, 8).join(' '))}</span>
        </div></div>
        <div>
          <div class="comp-price">${Fmt.price(a.best_price)}</div>
          <div class="comp-price-range" style="color:var(--red)">-${a.diff_pct}% vs. tu precio</div>
        </div>
      </div>
      <div class="comp-stats">
        <div class="comp-stat-item"><span class="comp-stat-val">${Fmt.price(a.my_price)}</span><span class="comp-stat-label">Tu precio</span></div>
        <div class="comp-stat-item"><span class="comp-stat-val">${Fmt.esc(a.competitor_nickname || '—')}</span><span class="comp-stat-label">Te está ganando</span></div>
        <div class="comp-stat-item" style="margin-left:auto"><span class="threat-badge threat-high">${a.competitors_below} por debajo</span></div>
      </div>
      <div class="comp-links">
        ${a.permalink ? `<a class="comp-link" href="${Fmt.esc(a.permalink)}" target="_blank" rel="noopener noreferrer">Tu publicación ↗</a>` : ''}
        ${a.competitor_permalink ? `<a class="comp-link comp-link-action" href="${Fmt.esc(a.competitor_permalink)}" target="_blank" rel="noopener noreferrer">Ver competidor ↗</a>` : ''}
      </div>
    </div>`).join('')}</div>`);
}

// ═══════════════════════════════════════════════════════════
// VENDEDOR A VIGILAR — tendencia de presencia/victorias en el tiempo. Proxy honesto
// de fortaleza de un competidor (ML no expone ventas de terceros por API, ver spec).
// ═══════════════════════════════════════════════════════════
async function loadSellerTrend(nickname) {
  const section = $('seccion-vendedor-trend');
  if (!nickname) { section.style.display = 'none'; return; }
  try {
    const data = await API.sellerTimeseries(nickname);
    const history = data.history || [];
    if (history.length < 2) { section.style.display = 'none'; return; }

    html($('sellerTrendSubtitle'), `<strong>${Fmt.esc(nickname)}</strong> — en cuántos productos aparece y cuántas veces gana por precio, en el tiempo`);
    drawChart('chartSellerTrend', {
      type: 'line',
      data: {
        labels: history.map(h => new Date(h.ts_utc).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })),
        datasets: [
          { label: 'Aparece en', data: history.map(h => h.appearances), borderColor: '#4f96ec', tension: 0.3, pointRadius: 2 },
          { label: 'Gana por precio', data: history.map(h => h.wins), borderColor: '#3ecf8e', tension: 0.3, pointRadius: 2 },
        ],
      },
      options: { ...CHART_BASE, scales: AXES_DARK, plugins: { ...CHART_BASE.plugins, legend: { display: true } } },
    });
    section.style.display = '';
  } catch {
    section.style.display = 'none';
  }
}

// ═══════════════════════════════════════════════════════════
// TABLA DE PRODUCTOS
// ═══════════════════════════════════════════════════════════
function renderSkeletons(n = 10) {
  html($('tbody'), Array.from({ length: n }, () => `
    <tr>
      <td><div class="sk" style="width:22px;height:22px;border-radius:5px"></div></td>
      <td><div class="sk" style="width:44px;height:44px;border-radius:6px"></div></td>
      <td><div class="sk" style="width:230px;height:13px;margin-bottom:5px"></div><div class="sk" style="width:90px;height:10px"></div></td>
      <td><div class="sk" style="width:70px;height:13px"></div></td>
      <td><div class="sk" style="width:80px;height:13px"></div></td>
      <td><div class="sk" style="width:50px;height:13px"></div></td>
      <td><div class="sk" style="width:120px;height:13px"></div></td>
      <td><div class="sk" style="width:70px;height:20px"></div></td>
    </tr>`).join(''));
}

const RANK_EXPLAIN = {
  sellers:    'Ordenado por cantidad de vendedores compitiendo',
  price_asc:  'Ordenado por precio más bajo primero',
  price_desc: 'Ordenado por precio más alto primero',
};

function sortedProducts() {
  let arr = State.brandFilter ? State.products.filter(p => p.brand === State.brandFilter) : [...State.products];
  const g = (p) => State.offersById[p.id];
  if (State.sortBy === 'price_asc')       arr.sort((a, b) => (g(a)?.minPrice ?? Infinity) - (g(b)?.minPrice ?? Infinity));
  else if (State.sortBy === 'price_desc') arr.sort((a, b) => (g(b)?.minPrice ?? -1) - (g(a)?.minPrice ?? -1));
  else                                    arr.sort((a, b) => (g(b)?.total ?? -1) - (g(a)?.total ?? -1));
  return arr;
}

function renderProducts() {
  const tbody = $('tbody');
  if (!tbody) return;
  const list = sortedProducts();

  html($('rankExplain'), RANK_EXPLAIN[State.sortBy] || RANK_EXPLAIN.sellers);

  const filterBar = $('brandFilterBar');
  if (filterBar) {
    if (State.brandFilter) {
      html($('brandFilterName'), Fmt.esc(State.brandFilter));
      filterBar.style.display = 'flex';
    } else {
      filterBar.style.display = 'none';
    }
  }

  if (!list.length) {
    html(tbody, `<tr class="empty-row"><td colspan="8"><div class="empty-state">
      <div class="empty-title">Sin resultados para "${Fmt.esc(State.query)}"</div>
      <div class="empty-sub">${State.brandFilter ? `No hay productos de ${Fmt.esc(State.brandFilter)} en esta lista` : 'Probá con otra categoría'}</div></div></td></tr>`);
    return;
  }

  const maxSellers = Math.max(...list.map(p => State.offersById[p.id]?.total || 0), 1);

  tbody.innerHTML = list.map((p, idx) => {
    const o    = State.offersById[p.id];
    const rank = idx + 1;
    const rk   = rank === 1 ? 'top-1' : rank === 2 ? 'top-2' : rank === 3 ? 'top-3' : '';

    const thumb = p.thumbnail
      ? `<img class="product-thumb" src="${Fmt.esc(p.thumbnail)}" alt="" loading="lazy" onerror="this.style.display='none'">`
      : `<div class="product-thumb-ph"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="5"/></svg></div>`;

    const priceCell = o
      ? (o.minPrice != null
          ? `<span class="price-val">${Fmt.price(o.minPrice)}</span>${o.maxPrice > o.minPrice ? `<div style="font-size:10.5px;color:var(--text-3);font-family:var(--font-mono)">hasta ${Fmt.price(o.maxPrice)}</div>` : ''}`
          : `<span style="color:var(--text-3)">Sin ofertas</span>`)
      : `<div class="sk" style="width:70px;height:13px"></div>`;

    const sellersCell = o
      ? `<span class="sold-val">${o.total}</span><div class="sold-bar"><div class="sold-bar-fill" style="width:${(o.total / maxSellers) * 100}%"></div></div>`
      : `<div class="sk" style="width:50px;height:13px"></div>`;

    const leader = o?.offers?.[0];
    const isMine = leader && CFG.MY_NICK && (leader.nickname || '').toUpperCase() === CFG.MY_NICK;

    const leaderCell = o
      ? (leader ? `<span class="seller-nick" title="${Fmt.esc(leader.nickname)}">${Fmt.esc(leader.nickname || '—')}${isMine ? '<span class="my-badge">VOS</span>' : ''}</span>` : '<span style="color:var(--text-3)">—</span>')
      : `<div class="sk" style="width:120px;height:13px"></div>`;

    const repCell = o ? (leader ? Fmt.repDots(leader.reputation) : '') : `<div class="sk" style="width:70px;height:20px"></div>`;

    const isComparing = State.compare.includes(p.id);
    return `<tr data-pid="${p.id}" class="${isMine ? 'row-mine' : ''}${isComparing ? ' is-comparing' : ''}" style="--row-i:${Math.min(idx, 16)}">
      <td class="rank-cell">
        <label class="cmp-check" title="Sumar a comparación" onclick="event.stopPropagation()">
          <input type="checkbox" ${isComparing ? 'checked' : ''} onchange="App.toggleCompare('${p.id}')">
          <span class="cmp-box"></span>
        </label>
        <div class="rank-num ${rk}">${rank}</div>
      </td>
      <td>${thumb}</td>
      <td>
        <span class="product-name" title="${Fmt.esc(p.name)}">${Fmt.esc(p.name)}</span>
        <span class="product-id">${Fmt.esc(p.id)}</span>
      </td>
      <td><span class="pubs-val">${Fmt.esc(p.brand || '—')}</span></td>
      <td>${priceCell}</td>
      <td>${sellersCell}</td>
      <td>${leaderCell}</td>
      <td>${repCell}</td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('tr[data-pid]').forEach(tr => {
    tr.addEventListener('click', () => {
      const p = State.products.find(x => x.id === tr.dataset.pid);
      if (p) App.openPanel(p);
    });
  });
}

function renderMetrics() {
  const withOffers = State.products.filter(p => State.offersById[p.id]?.minPrice != null);

  const mTotal = $('mTotal');
  if (mTotal) {
    mTotal.querySelector('.metric-value').textContent = Fmt.number(State.total);
    mTotal.querySelector('.metric-sub').textContent   = `${State.products.length} productos en pantalla`;
  }

  const prices = withOffers.map(p => State.offersById[p.id].minPrice);
  const mRange = $('mRange');
  if (mRange) {
    mRange.querySelector('.metric-value').textContent = prices.length ? `${Fmt.price(Math.min(...prices))} – ${Fmt.price(Math.max(...prices))}` : '—';
    mRange.querySelector('.metric-sub').textContent = 'Precio más bajo por producto';
  }

  const leaderCount = {};
  withOffers.forEach(p => {
    const n = State.offersById[p.id]?.offers?.[0]?.nickname;
    if (n) leaderCount[n] = (leaderCount[n] || 0) + 1;
  });
  const topLeader = Object.entries(leaderCount).sort((a, b) => b[1] - a[1])[0];
  const mLeader = $('mLeader');
  if (mLeader) {
    mLeader.querySelector('.metric-value').textContent = topLeader ? topLeader[0] : '—';
    mLeader.querySelector('.metric-sub').textContent   = topLeader ? `Mejor precio en ${topLeader[1]} de ${withOffers.length} productos` : 'Calculando…';
  }

  const disputed = [...State.products].filter(p => State.offersById[p.id]).sort((a, b) => State.offersById[b.id].total - State.offersById[a.id].total)[0];
  const mTop = $('mTop');
  if (mTop && disputed) {
    mTop.querySelector('.metric-value').textContent = (disputed.name || '').split(' ').slice(0, 6).join(' ');
    mTop.querySelector('.metric-sub').textContent   = `${State.offersById[disputed.id].total} vendedores compitiendo`;
  }

  const rc = $('resultsCount');
  if (rc) rc.textContent = `${State.products.length} de ${Fmt.number(State.total)} productos del catálogo`;
}

// ═══════════════════════════════════════════════════════════
// PANEL DE COMPETENCIA
// ═══════════════════════════════════════════════════════════

/** Tendencia propia (guardada localmente cada vez que se corrio un analisis de rubro).
 *  Solo tiene sentido con 2+ fotos; si hay una sola todavia no hay tendencia que mostrar. */
async function renderPanelTrend(productId) {
  let history = [];
  try {
    const d = await API.timeseries(productId);
    history = d.history || [];
  } catch { return; }
  if (history.length < 2) return;

  const body = document.getElementById('panelBody');
  if (!body) return;
  body.insertAdjacentHTML('afterbegin', `
    <div class="panel-section" style="margin-bottom:0">Tendencia de precio (histórico propio)</div>
    <div class="chart-box" style="padding:10px 18px 18px;height:140px"><canvas id="panelTrendChart"></canvas></div>`);

  drawChart('panelTrendChart', {
    type: 'line',
    data: {
      labels: history.map(h => new Date(h.ts_utc).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })),
      datasets: [
        { label: 'Mínimo', data: history.map(h => h.min_price), borderColor: '#3ecf8e', tension: 0.3, pointRadius: 2 },
        { label: 'Promedio', data: history.map(h => h.avg_price), borderColor: '#5b4fe0', tension: 0.3, pointRadius: 2 },
      ],
    },
    options: { ...CHART_BASE, scales: AXES_DARK, plugins: { ...CHART_BASE.plugins, legend: { display: true } } },
  });
}

function renderPanel(product, data, targetId = 'panelBody', pinnedItemId = null) {
  const offers = data.offers || [];
  if (!offers.length) {
    html($(targetId), `<div style="padding:50px 20px;text-align:center;color:var(--text-3)"><div style="font-size:13px">Ningún vendedor está ofreciendo este producto actualmente</div></div>`);
    return;
  }

  const prices = offers.map(o => o.price).filter(p => p != null);
  const min = Math.min(...prices), max = Math.max(...prices);
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;

  const summary = `<div class="panel-summary">
    <div class="panel-stat"><div class="panel-stat-val" style="color:var(--accent-2)">${data.total}</div><div class="panel-stat-label">Vendedores</div></div>
    <div class="panel-stat"><div class="panel-stat-val" style="color:var(--green)">${Fmt.price(min)}</div><div class="panel-stat-label">Precio mínimo</div></div>
    <div class="panel-stat"><div class="panel-stat-val" style="color:var(--yellow)">${Fmt.price(avg)}</div><div class="panel-stat-label">Precio promedio</div></div>
  </div>`;

  const buyBoxNote = data.buy_box_winner_item
    ? `<div class="insight" style="margin-bottom:16px"><div class="insight-icon i-info">★</div><div class="insight-text">El algoritmo de Mercado Libre eligió un <strong>ganador oficial de la página</strong> (no siempre es el precio más bajo: también pesan reputación y envío). Se marca con ★ abajo.</div></div>`
    : '';

  let rangeViz = '';
  if (max > min) {
    const marks = offers.slice(0, 15).map(o => {
      const pct  = ((o.price - min) / (max - min)) * 100;
      const mine = CFG.MY_NICK && (o.nickname || '').toUpperCase() === CFG.MY_NICK;
      return `<div style="position:absolute;left:${pct}%;top:-4px;width:2px;height:12px;border-radius:1px;background:${mine ? 'var(--green)' : 'var(--text-2)'};transform:translateX(-50%)"></div>`;
    }).join('');
    rangeViz = `<div class="price-range-viz">
      <div class="price-range-label">Dispersión de precios entre vendedores</div>
      <div class="price-range-track">${marks}</div>
      <div class="price-range-ticks"><span>${Fmt.price(min)}</span><span>${Fmt.price(max)}</span></div>
    </div>`;
  }

  const rankCls = ['top-1', 'top-2', 'top-3'];
  const cards = offers.map((o, idx) => {
    const mine    = CFG.MY_NICK && (o.nickname || '').toUpperCase() === CFG.MY_NICK;
    const pinned  = pinnedItemId && o.item_id === pinnedItemId;
    const threat = Fmt.threat(o.seller_sales, o.reputation);
    const diff   = min > 0 ? ((o.price - min) / min) * 100 : 0;
    const badges = [
      o.buy_box_winner ? '<span class="comp-link" style="cursor:default;color:var(--yellow);border-color:rgba(242,184,75,.3)">★ Ganador oficial ML</span>' : '',
      o.free_shipping  ? '<span class="comp-link" style="cursor:default">Envío gratis</span>' : '',
      o.official_store ? '<span class="comp-link" style="cursor:default">Tienda oficial</span>' : '',
      o.city           ? `<span class="comp-link" style="cursor:default">${Fmt.esc(o.city)}</span>` : '',
      o.permalink      ? `<a class="comp-link comp-link-action" href="${Fmt.esc(o.permalink)}" target="_blank" rel="noopener noreferrer">Ver publicación ↗</a>` : '',
    ].filter(Boolean).join('');

    return `<div class="comp-card${mine ? ' comp-mine' : ''}"${pinned ? ' style="outline:2px solid var(--accent-2)"' : ''}>
      <div class="comp-top">
        <div class="comp-left">
          <div class="comp-rank-num ${rankCls[idx] || ''}">${idx + 1}</div>
          <div class="comp-nick-wrap">
            <span class="comp-nick">${Fmt.esc(o.nickname || '—')}${mine ? '<span class="tag-mine">Mi cuenta</span>' : ''}${pinned ? '<span class="tag-mine" style="background:var(--accent-2)">Publicación analizada</span>' : ''}</span>
            ${Fmt.repDots(o.reputation)}
          </div>
        </div>
        <div>
          <div class="comp-price">${Fmt.price(o.price)}</div>
          ${idx > 0 && diff > 0 ? `<div class="comp-price-range">+${diff.toFixed(1)}% vs. mínimo</div>` : ''}
        </div>
      </div>
      <div class="comp-stats">
        <div class="comp-stat-item"><span class="comp-stat-val">${Fmt.number(o.seller_sales)}</span><span class="comp-stat-label">Ventas del vendedor</span></div>
        <div class="comp-stat-item" style="margin-left:auto"><span class="threat-badge ${threat.cls}">${threat.label}</span></div>
      </div>
      <div class="comp-links">${badges}</div>
    </div>`;
  }).join('');

  html($(targetId), `${summary}${buyBoxNote}${rangeViz}<div class="panel-section">${offers.length} vendedores compitiendo</div>${cards}`);
}

// ═══════════════════════════════════════════════════════════
// ANALIZAR PUBLICACIÓN
// ═══════════════════════════════════════════════════════════
function renderLookupResult(data) {
  const it     = data.item;
  const isMine = CFG.MY_NICK && (it.seller_nickname || '').toUpperCase() === CFG.MY_NICK;
  const thumb  = it.thumbnail
    ? `<img class="panel-thumb" src="${Fmt.esc(it.thumbnail)}" alt="" onerror="this.style.display='none'">`
    : `<div class="panel-thumb-ph"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="5"/></svg></div>`;

  const blockedNote = it.blocked
    ? `<div class="insight" style="margin-top:14px"><div class="insight-icon i-warn">!</div><div class="insight-text">Mercado Libre no permite ver precio ni vendedor de publicaciones ajenas por API (restricción de apps no certificadas). Identificamos el producto por el título que trae el link.</div></div>`
    : '';
  const groupNote = data.mode === 'catalog'
    ? (data.match === 'exact'
        ? `<div class="insight" style="margin-top:14px"><div class="insight-icon i-op">✓</div><div class="insight-text">Encontramos esta publicación exacta entre los vendedores del producto de catálogo <strong>${Fmt.esc(data.product?.name || '')}</strong> — la comparación es contra el 100% de los vendedores reales.</div></div>`
        : `<div class="insight" style="margin-top:14px"><div class="insight-icon i-op">✓</div><div class="insight-text">Agrupada en el producto de catálogo <strong>${Fmt.esc(data.product?.name || '')}</strong>: la comparación de abajo es contra el 100% de los vendedores reales de ese producto.</div></div>`)
    : `<div class="insight" style="margin-top:14px"><div class="insight-icon i-warn">!</div><div class="insight-text">Esta publicación no figura dentro de un producto de catálogo. Abajo están los productos de catálogo más parecidos${data.confident ? ' — el primero coincide con alta seguridad y ya lo cargamos' : ': elegí cuál es el mismo producto'}.</div></div>`;

  html($('lookupHeaderCard'), `
    <div class="panel-header" style="padding:18px">
      <div class="panel-product" style="display:flex;gap:14px;align-items:center">
        ${thumb}
        <div class="panel-product-info">
          <div class="panel-product-name">${Fmt.esc(it.title)}${isMine ? '<span class="tag-mine">Mi cuenta</span>' : ''}</div>
          <div class="panel-product-price">${it.price != null ? Fmt.price(it.price) : '—'}</div>
          <div class="panel-product-id">${Fmt.esc(it.id)}${it.blocked ? '' : ` · Vendido por ${Fmt.esc(it.seller_nickname || '—')} ${Fmt.repDots(it.seller_reputation)}`}</div>
        </div>
      </div>
      ${it.permalink ? `<a class="comp-link" href="${Fmt.esc(it.permalink)}" target="_blank" rel="noopener noreferrer">Ver en ML ↗</a>` : ''}
    </div>
    ${blockedNote}${groupNote}`);

  if (data.business) {
    renderLookupBusiness(data.business, it);
    $('lookupBusiness').style.display = '';
  } else {
    $('lookupBusiness').style.display = 'none';
  }

  $('lookupRelated').style.display = 'none';

  if (data.mode === 'catalog') {
    $('lookupCandidates').style.display = 'none';
    renderLookupComparison(data.product, data, it.id);
    loadRelated(data.product.id, 'lookupRelated', data.item?.price);
    return;
  }

  // mode === 'manual_match': candidatos a confirmar
  $('lookupComparison').style.display = 'none';
  const candidates = data.candidates || [];
  const autoPick = data.confident && candidates[0]?.sellers > 0 ? candidates[0] : null;
  if (!candidates.length) {
    html($('lookupCandidates'), `<div class="empty-state"><div class="empty-title">No encontramos productos de catálogo parecidos</div><div class="empty-sub">Esta publicación parece ser única o de un rubro no soportado todavía.</div></div>`);
  } else {
    html($('lookupCandidates'), `
      <div class="section-head">
        <div class="section-head-left">
          <div class="section-title-wrap">
            <div class="section-title">${autoPick ? '¿No es este producto? Otros candidatos' : '¿Cuál de estos es el mismo producto?'}</div>
            <div class="section-sub">Ordenados por coincidencia con el título (tipo de producto, marca, medidas y modelo). Los que no tienen vendedores hoy aparecen más abajo.</div>
          </div>
        </div>
      </div>
      <div class="rel-grid">${candidates.map(c => candidateCard(c, autoPick && c.id === autoPick.id)).join('')}</div>`);
  }
  $('lookupCandidates').style.display = '';
  if (autoPick) App.selectCandidate(autoPick.id);
}

function matchLevel(score) {
  if (score >= 0.75) return { cls: 'threat-low', label: 'Coincidencia alta' };
  if (score >= 0.5)  return { cls: 'threat-mid', label: 'Coincidencia media' };
  return { cls: '', label: 'Coincidencia baja' };
}

function candidateCard(c, selected) {
  const lvl = matchLevel(c.score || 0);
  return `<div class="rel-card${selected ? ' is-selected' : ''}" data-pid="${Fmt.esc(c.id)}" onclick="App.selectCandidate('${Fmt.esc(c.id)}')">
    <div class="rel-top">
      ${c.thumbnail ? `<img class="rel-thumb" src="${Fmt.esc(c.thumbnail)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : '<div class="rel-thumb"></div>'}
      <div class="rel-info">
        <div class="rel-name" title="${Fmt.esc(c.name)}">${Fmt.esc(c.name)}</div>
        <div class="rel-brand">${Fmt.esc(c.brand || 'Sin marca')}</div>
      </div>
    </div>
    <div class="rel-stats">
      <span class="threat-badge ${lvl.cls}">${lvl.label}</span>
      <span class="rel-stat">${c.sellers ? `${c.sellers} vend. · desde ${Fmt.price(c.min_price)}` : 'Sin vendedores hoy'}</span>
    </div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════
// MAPA DEL RUBRO — comparativa entre subcategorías
// ═══════════════════════════════════════════════════════════
function competitionLevel(avg) {
  if (avg >= 12) return { cls: 'threat-high', label: 'Alta' };
  if (avg >= 5)  return { cls: 'threat-mid',  label: 'Media' };
  return { cls: 'threat-low', label: 'Baja' };
}

function renderOverview() {
  const rows = [...(State.overview?.rows || [])];
  const { key, dir } = State.overviewSort;
  rows.sort((a, b) => {
    // Sin datos o con muestra chica (<8 productos con vendedores) van al final: sus promedios no son confiables
    const rank = (r) => !r.with_sellers ? 2 : r.with_sellers < 8 ? 1 : 0;
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    const va = a[key], vb = b[key];
    if (typeof va === 'string' || typeof vb === 'string') return dir * String(va ?? '').localeCompare(String(vb ?? ''));
    return dir * ((va ?? -Infinity) - (vb ?? -Infinity));
  });
  document.querySelectorAll('.overview-table th[data-sort]').forEach(th => {
    th.classList.toggle('is-sorted', th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? 'asc' : 'desc') : '';
  });

  html($('overviewBody'), rows.map(r => {
    const lvl = r.with_sellers ? competitionLevel(r.avg_sellers) : null;
    const thin = r.with_sellers < 8;
    return `<tr data-label="${Fmt.esc(r.label)}" title="Analizar ${Fmt.esc(r.label)}">
      <td><span class="product-name">${Fmt.esc(r.label)}</span><span class="product-id">${Fmt.esc(r.group || '')}</span></td>
      <td>${lvl ? `<span class="threat-badge ${lvl.cls}">${lvl.label}</span> <span class="sold-val">${r.avg_sellers}</span>` : '<span style="color:var(--text-3)">—</span>'}
        <div class="product-id" style="${thin ? 'color:var(--orange)' : ''}">${r.with_sellers}/${r.sampled} con vendedores${thin ? ' · muestra chica' : ''}</div></td>
      <td><span class="sold-val">${r.low_competition_products}</span></td>
      <td><span class="price-val">${Fmt.price(r.median_price)}</span></td>
      <td>${r.free_shipping_pct != null ? `${r.free_shipping_pct}%` : '—'}</td>
      <td>${r.official_store_pct != null ? `${r.official_store_pct}%` : '—'}</td>
      <td>${Fmt.esc(r.top_brand || '—')}</td>
      <td><span class="product-id">${Fmt.number(r.catalog_total)}</span></td>
    </tr>`;
  }).join('') || `<tr class="empty-row"><td colspan="8"><div class="empty-state"><div class="empty-title">Sin datos</div></div></td></tr>`);

  $('overviewBody').querySelectorAll('tr[data-label]').forEach(tr => tr.addEventListener('click', () => {
    const idx = State.activeCat.subcats.findIndex(s => s.label === tr.dataset.label);
    if (idx < 0) return;
    State.activeSub = State.activeCat.subcats[idx];
    const sel = $('selCat'); if (sel) sel.value = String(idx);
    const inp = $('inputQ'); if (inp) { inp.value = ''; inp.placeholder = `Buscar dentro de “${State.activeSub.label}”…`; }
    loadTrends();
    switchView('dashboard');
    App.search();
  }));
}

// ═══════════════════════════════════════════════════════════
// PRODUCTOS EQUIVALENTES — otras marcas con las mismas especificaciones técnicas
// ═══════════════════════════════════════════════════════════
const _relatedSeq = {};

async function loadRelated(productId, targetId, referencePrice = null) {
  const seq = (_relatedSeq[targetId] = (_relatedSeq[targetId] || 0) + 1);
  const host = $(targetId);
  if (!host) return;
  const isPanel = targetId === 'panelBody';
  const box = isPanel ? document.createElement('div') : host;
  if (isPanel) { box.id = 'panelRelated'; $('panelRelated')?.remove(); host.appendChild(box); }
  box.style.display = '';
  html(box, `${isPanel ? '' : relatedHead('Buscando productos equivalentes…', '')}<div class="panel-loading"><div class="panel-spinner"></div><span>Buscando equivalentes de otras marcas…</span></div>`);

  let data;
  try {
    data = await API.related(productId);
  } catch (e) {
    if (seq !== _relatedSeq[targetId]) return;
    html(box, `${isPanel ? '' : relatedHead('Productos equivalentes', '')}<div class="empty-state"><div class="empty-sub">${Fmt.esc(e.message)}</div></div>`);
    return;
  }
  if (seq !== _relatedSeq[targetId]) return;
  if (isPanel && State.panelProduct?.id !== productId) return;
  html(box, renderRelated(data, referencePrice, isPanel));
}

function relatedHead(title, sub) {
  return `<div class="section-head"><div class="section-head-left">
    <div class="section-icon" style="background:var(--blue-dim);color:var(--blue)">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
    </div>
    <div class="section-title-wrap"><div class="section-title">${title}</div><div class="section-sub">${sub}</div></div>
  </div></div>`;
}

function renderRelated(data, referencePrice, compact) {
  const related = data.related || [];
  const specs   = (data.specs || []).slice(0, 6);
  const specChips = specs.length
    ? `<div class="rel-specs">${specs.map(s => `<span class="comp-link" style="cursor:default">${Fmt.esc(s.name)}: <strong>${Fmt.esc(s.value)}</strong></span>`).join('')}</div>`
    : '';
  const head = compact
    ? `<div class="panel-section" style="margin-top:22px">Equivalentes de otras marcas</div>`
    : relatedHead('Productos equivalentes y alternativas', 'Mismo tipo de producto, comparado por especificaciones técnicas del catálogo de ML. Solo productos con vendedores activos hoy.');

  if (!related.length) {
    return `${head}${specChips}<div class="empty-state" style="padding:22px"><div class="empty-sub">No encontramos productos equivalentes con vendedores activos.</div></div>`;
  }

  const ref = referencePrice || data.source?.min_price;
  const st  = data.same_spec_stats || {};
  let insight = '';
  if (st.count && st.median) {
    const diff = ref ? ((ref - st.median) / st.median) * 100 : null;
    const pos = diff == null ? ''
      : Math.abs(diff) < 3 ? ` Este precio (${Fmt.price(ref)}) está <strong>en línea con la mediana</strong>.`
      : ` Este precio (${Fmt.price(ref)}) está <strong>${Math.abs(diff).toFixed(0)}% ${diff > 0 ? 'por encima' : 'por debajo'}</strong> de la mediana.`;
    insight = `<div class="insight" style="margin:${compact ? '0 0 12px' : '14px 18px 0'}"><div class="insight-icon i-info">≈</div><div class="insight-text">
      <strong>${st.count} producto${st.count === 1 ? '' : 's'} de otras marcas/modelos con las mismas especificaciones.</strong>
      Precio mínimo entre ellos ${Fmt.price(st.min)}, mediana ${Fmt.price(st.median)}.${pos}</div></div>`;
  }

  const cards = related.map(r => {
    const diff = ref && r.min_price ? ((r.min_price - ref) / ref) * 100 : null;
    const badge = r.same_specs
      ? '<span class="threat-badge threat-low">Mismas specs</span>'
      : r.score >= 0.5 ? '<span class="threat-badge threat-mid">Similar</span>' : '<span class="threat-badge">Alternativa</span>';
    const diffs = (r.diff_specs || []).map(d => `${Fmt.esc(d.name)}: ${Fmt.esc(d.value)}`).join(' · ');
    return `<div class="rel-card" data-related="1" data-pid="${Fmt.esc(r.id)}" data-name="${Fmt.esc(r.name)}" data-brand="${Fmt.esc(r.brand || '')}" data-thumb="${Fmt.esc(r.thumbnail || '')}" title="Ver todos los vendedores de este producto">
      <div class="rel-top">
        ${r.thumbnail ? `<img class="rel-thumb" src="${Fmt.esc(r.thumbnail)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : '<div class="rel-thumb"></div>'}
        <div class="rel-info">
          <div class="rel-name" title="${Fmt.esc(r.name)}">${Fmt.esc(r.name)}</div>
          <div class="rel-brand">${Fmt.esc(r.brand || 'Sin marca')}</div>
        </div>
      </div>
      <div class="rel-stats">
        ${badge}
        <span class="rel-stat">${r.sellers} vend.</span>
        <span class="rel-price">${Fmt.price(r.min_price)}${diff != null ? ` <em class="${diff < 0 ? 'down' : 'up'}">${diff > 0 ? '+' : ''}${diff.toFixed(0)}%</em>` : ''}</span>
      </div>
      ${diffs ? `<div class="rel-diff">Difiere en ${diffs}</div>` : ''}
    </div>`;
  }).join('');

  return `${head}${compact ? '' : specChips}${insight}<div class="rel-grid${compact ? ' compact' : ''}">${cards}</div>`;
}

/** Desglose de "boosts" del price_to_win: que palanca puntual mejora las chances de ganar el catalogo. */
function renderBoosts(boosts) {
  if (!boosts || !boosts.length) return '';
  const statusMeta = {
    boosted:     { cls: 'threat-low',  label: 'Activo' },
    opportunity: { cls: 'threat-high', label: 'Oportunidad' },
    not_boosted: { cls: 'threat-mid',  label: 'No aplica ahora' },
    not_apply:   { cls: '',            label: 'No aplica' },
  };
  return `<div class="panel-section" style="margin-top:10px;margin-bottom:0">Qué mejorar para ganar el catálogo</div>
    <div class="comp-links" style="padding:8px 0 0;flex-wrap:wrap">
      ${boosts.map(b => {
        const st = statusMeta[b.status] || { cls: '', label: b.status || '' };
        return `<span class="comp-link" style="cursor:default"><span class="threat-badge ${st.cls}" style="margin-right:6px">${st.label}</span>${Fmt.esc(b.description || b.id)}</span>`;
      }).join('')}
    </div>`;
}

function renderLookupBusiness(b, it) {
  const setKpi = (id, val, sub) => {
    const el = $(id);
    if (!el) return;
    el.querySelector('.metric-value').textContent = val;
    if (sub != null) el.querySelector('.metric-sub').textContent = sub;
  };

  setKpi('lbVisits', Fmt.number(b.visits_total), `Últimos ${b.period_days} días`);
  setKpi('lbOrders', Fmt.number(b.orders_count), it.sold_quantity != null ? `${Fmt.number(it.sold_quantity)} vendidas (histórico total)` : 'Unidades en el período');
  setKpi('lbRevenue', b.revenue ? Fmt.price(b.revenue) : '—', `Sobre ${b.orders_count} venta${b.orders_count === 1 ? '' : 's'}`);
  setKpi('lbConversion', b.conversion_pct != null ? `${b.conversion_pct}%` : '—', 'Ventas sobre visitas del período');

  drawChart('chartLookupVisits', {
    type: 'line',
    data: {
      labels: (b.visits_series || []).map(p => new Date(p.date).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })),
      datasets: [{
        label: 'Visitas', data: (b.visits_series || []).map(p => p.total),
        borderColor: '#5b4fe0', backgroundColor: 'rgba(91,79,224,0.12)', fill: true, tension: 0.35, pointRadius: 2,
      }],
    },
    options: { ...CHART_BASE, scales: AXES_DARK, plugins: { ...CHART_BASE.plugins, legend: { display: false } } },
  });

  const ptwLabels = {
    winning:              { cls: 'threat-low',  label: 'Estás ganando' },
    competing:            { cls: 'threat-mid',  label: 'En competencia' },
    sharing_first_place:  { cls: 'threat-mid',  label: 'Empatás el primer lugar' },
    losing:               { cls: 'threat-high', label: 'Estás perdiendo' },
    not_listed:           { cls: '',            label: 'Sin datos de competencia' },
  };
  const reasonLabels = { item_not_opted_in: 'Esta publicación no está sumada al programa de precio competitivo de ML.' };

  const p = b.price_to_win;
  if (!p) {
    html($('lookupPtwBody'), '');
  } else {
    const st = ptwLabels[(p.status || '').toLowerCase()] || { cls: '', label: p.status || 'Sin datos' };
    const reason = p.reason ? (reasonLabels[p.reason] || p.reason) : '';
    html($('lookupPtwBody'), `<div class="comp-card">
      <div class="comp-top">
        <div class="comp-left"><div class="comp-nick-wrap"><span class="comp-nick">Precio para ganar (ML)</span></div></div>
        <div><span class="threat-badge ${st.cls}">${st.label}</span></div>
      </div>
      ${p.price_to_win != null ? `<div class="comp-stats">
        <div class="comp-stat-item"><span class="comp-stat-val">${Fmt.price(p.current_price)}</span><span class="comp-stat-label">Tu precio actual</span></div>
        <div class="comp-stat-item"><span class="comp-stat-val" style="color:var(--green)">${Fmt.price(p.price_to_win)}</span><span class="comp-stat-label">Precio para ganar</span></div>
        ${p.competitors_sharing_first_place != null ? `<div class="comp-stat-item"><span class="comp-stat-val">${p.competitors_sharing_first_place}</span><span class="comp-stat-label">Compiten por el 1er lugar</span></div>` : ''}
      </div>${renderBoosts(p.boosts)}` : (reason ? `<div class="insight-text" style="padding-top:4px">${Fmt.esc(reason)}</div>` : '')}
    </div>`);
  }
}

function renderLookupComparison(product, offersData, pinnedItemId) {
  const offers = offersData.offers || [];
  let posNote = '';
  if (pinnedItemId) {
    const idx = offers.findIndex(o => o.item_id === pinnedItemId);
    if (idx >= 0) {
      const prices = offers.map(o => o.price).filter(p => p != null);
      const minP   = Math.min(...prices);
      const myP    = offers[idx].price;
      const diff   = minP > 0 ? ((myP - minP) / minP) * 100 : 0;
      const mine = !!State.lookup?.item?.is_mine;
      posNote = idx === 0
        ? `<div class="insight"><div class="insight-icon i-op">★</div><div class="insight-text"><strong>${mine ? 'Tenés' : 'Esta publicación tiene'} el precio más bajo</strong> entre los ${offers.length} vendedores de este producto.</div></div>`
        : `<div class="insight"><div class="insight-icon i-warn">!</div><div class="insight-text">${mine ? 'Tu' : 'Esta'} publicación ocupa la <strong>posición ${idx + 1} de ${offers.length}</strong> por precio — ${mine ? 'estás' : 'está'} <strong>${diff.toFixed(1)}% por encima</strong> del más bajo (${Fmt.price(minP)}).</div></div>`;
    }
  }
  $('lookupComparison').style.display = '';
  renderPanel(product, offersData, 'lookupBody', pinnedItemId);
  if (posNote) document.getElementById('lookupBody').insertAdjacentHTML('afterbegin', posNote);
}

// ═══════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════
function exportCSV() {
  if (!State.products.length) return;
  const header = ['Rank','Producto ID','Nombre','Marca','Precio min','Precio max','Vendedores','Mejor precio (vendedor)'];
  const rows = sortedProducts().map((p, i) => {
    const o = State.offersById[p.id] || {};
    return [i + 1, p.id, `"${(p.name || '').replace(/"/g, '""')}"`, `"${(p.brand || '').replace(/"/g, '""')}"`,
            o.minPrice ?? '', o.maxPrice ?? '', o.total ?? '', `"${(o.offers?.[0]?.nickname || '').replace(/"/g, '""')}"`];
  });
  const blob = new Blob(['\ufeff' + [header, ...rows].map(r => r.join(',')).join('\n')], { type: 'text/csv;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `mercadata-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

// ═══════════════════════════════════════════════════════════
// APP
// ═══════════════════════════════════════════════════════════
const MAX_COMPARE = 4;

function renderCompareBar() {
  const bar = $('cmpBar');
  if (!bar) return;
  const n = State.compare.length;
  if (!n) { bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  html($('cmpCount'), String(n));
  html($('cmpNames'), State.compare.map(id => {
    const p = State.products.find(x => x.id === id);
    return `<span class="cmp-chip">${Fmt.esc((p?.name || id).slice(0, 26))}<button onclick="App.toggleCompare('${id}')" title="Quitar">✕</button></span>`;
  }).join(''));
  const btn = $('btnOpenCompare');
  if (btn) btn.disabled = n < 2;
}

function renderCompareModal() {
  const cols = State.compare.map(id => State.products.find(p => p.id === id)).filter(Boolean);
  const rows = [
    { label: 'Marca', get: (p) => p.brand || '—' },
    { label: 'Precio desde', get: (p) => Fmt.price(State.offersById[p.id]?.minPrice) },
    { label: 'Precio hasta', get: (p) => Fmt.price(State.offersById[p.id]?.maxPrice) },
    { label: 'Vendedores', get: (p) => State.offersById[p.id]?.total ?? '—' },
    { label: 'Mejor precio (vendedor)', get: (p) => Fmt.esc(State.offersById[p.id]?.offers?.[0]?.nickname || '—') },
  ];
  const prices = cols.map(p => State.offersById[p.id]?.minPrice).filter(v => v != null);
  const bestPrice = prices.length ? Math.min(...prices) : null;
  const sellersArr = cols.map(p => State.offersById[p.id]?.total).filter(v => v != null);
  const fewestSellers = sellersArr.length ? Math.min(...sellersArr) : null;

  html($('cmpModalBody'), `
    <div class="cmp-cols" style="grid-template-columns:160px repeat(${cols.length},1fr)">
      <div class="cmp-col cmp-col-label"></div>
      ${cols.map(p => `
        <div class="cmp-col cmp-col-head">
          ${p.thumbnail ? `<img src="${Fmt.esc(p.thumbnail)}" alt="" class="cmp-col-thumb">` : '<div class="cmp-col-thumb"></div>'}
          <div class="cmp-col-name" title="${Fmt.esc(p.name)}">${Fmt.esc(p.name)}</div>
          <button class="btn-ghost" onclick="App.closeCompare();App.openPanel(State.products.find(x=>x.id==='${p.id}'))">Ver detalle</button>
        </div>`).join('')}
      ${rows.map(r => `
        <div class="cmp-col cmp-col-label">${r.label}</div>
        ${cols.map(p => {
          const val = r.get(p);
          const isBestPrice   = r.label === 'Precio desde' && bestPrice != null && State.offersById[p.id]?.minPrice === bestPrice;
          const isFewestSellers = r.label === 'Vendedores' && fewestSellers != null && State.offersById[p.id]?.total === fewestSellers;
          return `<div class="cmp-col cmp-col-val${(isBestPrice || isFewestSellers) ? ' is-best' : ''}">${val}${isBestPrice ? ' <span class="cmp-best-tag">mejor</span>' : ''}${isFewestSellers ? ' <span class="cmp-best-tag">menos disputado</span>' : ''}</div>`;
        }).join('')}`).join('')}
    </div>`);
}

const App = {
  toggleCompare(productId) {
    const i = State.compare.indexOf(productId);
    if (i >= 0) {
      State.compare.splice(i, 1);
    } else {
      if (State.compare.length >= MAX_COMPARE) { toast(`Máximo ${MAX_COMPARE} productos para comparar`); return; }
      State.compare.push(productId);
    }
    document.querySelectorAll('tbody tr[data-pid]').forEach(tr => {
      tr.classList.toggle('is-comparing', State.compare.includes(tr.dataset.pid));
      const cb = tr.querySelector('.cmp-check input');
      if (cb) cb.checked = State.compare.includes(tr.dataset.pid);
    });
    renderCompareBar();
  },

  clearCompare() {
    State.compare = [];
    document.querySelectorAll('tbody tr.is-comparing').forEach(tr => {
      tr.classList.remove('is-comparing');
      const cb = tr.querySelector('.cmp-check input');
      if (cb) cb.checked = false;
    });
    renderCompareBar();
  },

  openCompare() {
    if (State.compare.length < 2) return;
    renderCompareModal();
    $('cmpScrim').style.display = 'block';
    $('cmpModal').style.display = 'flex';
    $('cmpModal').setAttribute('aria-hidden', 'false');
  },

  closeCompare() {
    $('cmpScrim').style.display = 'none';
    $('cmpModal').style.display = 'none';
    $('cmpModal').setAttribute('aria-hidden', 'true');
  },

  filterByBrand(brand) {
    State.brandFilter = State.brandFilter === brand ? null : brand;
    document.querySelectorAll('.brand-bar-row').forEach(el => el.classList.toggle('is-active', el.dataset.brand === State.brandFilter));
    renderProducts();
  },

  async search() {
    if (State.loading) return;
    const sub    = State.activeSub || State.activeCat.subcats[0];
    const custom = $('inputQ')?.value.trim() || '';
    const q      = custom || sub.q;
    // Con domain (tipo de producto) no se manda category: el domain es mas preciso y
    // la category puede dejar afuera productos del mismo tipo clasificados en otra rama.
    let domId = sub?.domain || '';
    let catId = domId ? '' : (sub?.cat || State.activeCat.mlCategory || '');

    State.loading = true;
    State.query = q;
    State.products = [];
    State.offersById = {};
    State.total = 0;
    State.compare = [];
    State.brandFilter = null;
    renderCompareBar();

    hideBanner();
    setSearchLoading(true);
    setProgress('Buscando en el catálogo…');
    renderSkeletons(10);
    ['mTotal','mRange','mLeader','mTop'].forEach(id => {
      const el = $(id);
      if (el) { el.querySelector('.metric-value').textContent = '—'; el.querySelector('.metric-sub').textContent = 'Calculando…'; }
    });

    try {
      let { products, totalCatalog } = await fetchProductsWithOffers(q, catId, domId);
      // Texto libre que no pertenece al tipo de producto de la subcategoria (ej. se
      // escribio "reflector" estando en Térmicas): se reintenta sobre todo el catalogo.
      if (custom && domId && !products.length) {
        toast(`"${custom}" no está en ${sub.label}: buscando en todo el catálogo`);
        domId = ''; catId = '';
        ({ products, totalCatalog } = await fetchProductsWithOffers(q, catId, domId));
      }
      // Se escaneó el máximo alcanzable (200); de lo que tiene vendedores activos,
      // se muestran los CFG.PAGE_SIZE más disputados (más vendedores compitiendo).
      products.sort((a, b) => (State.offersById[b.id]?.total ?? 0) - (State.offersById[a.id]?.total ?? 0));
      State.total    = totalCatalog;
      State.products = products.slice(0, CFG.PAGE_SIZE);
      renderProducts();
      renderMetrics();

      if (!State.products.length) { $('btnExport').style.display = 'none'; setProgress(null); return; }
      $('btnExport').style.display = 'flex';

      // Análisis agregado: alimenta gráficos, marcas e insights
      setProgress('Generando análisis…');
      const analysis = await API.analysis(q, catId, domId);
      State.analysis = analysis;
      renderCharts(analysis);
      renderBrandBars(analysis);
      renderInsights(analysis);
      loadPriceAlerts(analysis.query);
      loadSellerTrend(analysis.sellers?.[0]?.nickname);

      setProgress(null);
    } catch (e) {
      console.error('[Mercadata]', e);
      setProgress(null);
      showBanner(e.message || 'Error al conectar con la API');
      html($('tbody'), `<tr class="empty-row"><td colspan="8"><div class="empty-state">
        <div class="empty-title">Error al cargar el catálogo</div>
        <div class="empty-sub">${Fmt.esc(e.message)}</div></div></td></tr>`);
    } finally {
      State.loading = false;
      setSearchLoading(false);
    }
  },

  async openPanel(product) {
    State.panelProduct = product;
    document.querySelectorAll('tbody tr').forEach(tr => tr.classList.remove('row-selected'));
    document.querySelector(`tbody tr[data-pid="${product.id}"]`)?.classList.add('row-selected');

    $('panelScrim').classList.add('open');
    $('compPanel').classList.add('open');
    $('compPanel').setAttribute('aria-hidden', 'false');

    const thumb = product.thumbnail
      ? `<img class="panel-thumb" src="${Fmt.esc(product.thumbnail)}" alt="" onerror="this.style.display='none'">`
      : `<div class="panel-thumb-ph"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="5"/></svg></div>`;

    const o = State.offersById[product.id];
    html($('panelProductInfo'), `${thumb}
      <div class="panel-product-info">
        <div class="panel-product-name">${Fmt.esc(product.name)}</div>
        <div class="panel-product-price">${o?.minPrice != null ? Fmt.price(o.minPrice) : '—'}</div>
        <div class="panel-product-id">${Fmt.esc(product.id)}${product.brand ? ' · ' + Fmt.esc(product.brand) : ''}</div>
      </div>`);

    html($('panelBody'), `<div class="panel-loading"><div class="panel-spinner"></div><span>Analizando competencia…</span></div>`);

    try {
      // Siempre se pide el detalle completo (con reputacion de vendedores y buy_box),
      // aunque ya tengamos datos "light" cacheados de la carga de la tabla.
      const data = await API.offers(product.id);
      State.offersById[product.id] = {
        ...(State.offersById[product.id] || {}),
        total: data.total || 0, offers: data.offers || [],
      };
      renderPanel(product, data);
      renderPanelTrend(product.id); // no bloquea el panel si falla o no hay historial todavia
      const prices = (data.offers || []).map(o => o.price).filter(v => v != null);
      loadRelated(product.id, 'panelBody', prices.length ? Math.min(...prices) : null);
    } catch (e) {
      html($('panelBody'), `<div style="padding:30px 20px;color:var(--red);font-size:13px">${Fmt.esc(e.message)}</div>`);
    }
  },

  closePanel() {
    $('panelScrim').classList.remove('open');
    $('compPanel').classList.remove('open');
    $('compPanel').setAttribute('aria-hidden', 'true');
    document.querySelectorAll('tbody tr').forEach(tr => tr.classList.remove('row-selected'));
    State.panelProduct = null;
  },

  setSort(v) { State.sortBy = v; renderProducts(); },
  export: exportCSV,

  async loadMyBusiness() {
    const days = Number($('selBizDays')?.value || 30);
    const requestId = ++State.myBizRequestSeq;   // descarta respuestas de requests anteriores
    setProgress('Cargando datos de tu cuenta…');
    loadUndercutAlerts(); // en paralelo, no bloquea el resto — maneja sus propios errores
    try {
      const data = await API.myBusiness(days);
      if (requestId !== State.myBizRequestSeq) return;   // llegó una carga más nueva primero
      State.myBizLoaded = true;
      renderMyBusiness(data);
    } catch (e) {
      if (requestId === State.myBizRequestSeq) showBanner(e.message || 'Error al cargar Mi Negocio');
    } finally {
      if (requestId === State.myBizRequestSeq) setProgress(null);
    }
  },

  async loadOverview() {
    const btn = $('btnOverview');
    if (btn?.disabled) return;
    if (btn) { btn.disabled = true; btn.textContent = 'Generando…'; }
    hideBanner();
    setProgress(`Comparando ${State.activeCat.subcats.length} subcategorías… (puede tardar un minuto)`);
    try {
      const subcats = State.activeCat.subcats.map(s => ({ q: s.q, domain: s.domain || '', cat: s.cat || '', label: s.label, group: s.group || '' }));
      State.overview = await API.overview(subcats);
      const ts = State.overview.generated_at ? new Date(State.overview.generated_at).toLocaleString('es-AR') : '';
      html($('overviewSub'), `${State.overview.rows.length} subcategorías · ${Fmt.esc(ts)} · hacé clic en una columna para ordenar`);
      renderOverview();
    } catch (e) {
      showBanner(e.message || 'No se pudo generar el mapa del rubro');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Actualizar mapa'; }
      setProgress(null);
    }
  },

  async analyzeListing() {
    const raw = $('inputLookup')?.value.trim();
    if (!raw) { toast('Pegá un link o un código de publicación primero.'); return; }
    if (State.loading) return;

    State.loading = true;
    const btn = $('btnLookup');
    if (btn) { btn.disabled = true; btn.textContent = 'Analizando…'; }
    hideBanner();
    $('lookupEmpty').style.display   = 'none';
    $('lookupContent').style.display = 'none';
    setProgress('Buscando la publicación en Mercado Libre…');

    const days = Number($('selLookupDays')?.value || 30);
    try {
      const data = await API.lookup(raw, days);
      State.lookup = data;
      renderLookupResult(data);
      $('lookupContent').style.display = '';
    } catch (e) {
      console.error('[Mercadata]', e);
      $('lookupEmpty').style.display = '';
      showBanner(e.message || 'No se pudo analizar la publicación');
    } finally {
      State.loading = false;
      if (btn) { btn.disabled = false; btn.textContent = 'Analizar'; }
      setProgress(null);
    }
  },

  async selectCandidate(productId) {
    if (!State.lookup) return;
    setProgress('Cargando comparación…');
    try {
      const offersData = await API.offers(productId);
      const candidate = (State.lookup.candidates || []).find(c => c.id === productId);
      const pinnedId  = State.lookup.item_id || State.lookup.item?.id || null;
      renderLookupComparison({ id: productId, name: candidate?.name }, offersData, pinnedId);
      // Los candidatos quedan visibles (marcado el elegido) para poder corregir la elección
      document.querySelectorAll('#lookupCandidates .rel-card').forEach(el => el.classList.toggle('is-selected', el.dataset.pid === productId));
      loadRelated(productId, 'lookupRelated', State.lookup.item?.price);
    } catch (e) {
      $('lookupComparison').style.display = '';
      html($('lookupBody'), `<div style="padding:30px 20px;text-align:center;color:var(--text-3)"><div style="font-size:13px">Este producto de catálogo no tiene vendedores activos en este momento. Probá con otro candidato de la lista.</div></div>`);
    } finally {
      setProgress(null);
    }
  },
};

/**
 * Trae el máximo de productos de catálogo alcanzable en UNA búsqueda y descarta
 * los que no tienen ningún vendedor activo hoy (la API real devuelve muchas
 * entradas de catálogo "huérfanas", sin ofertas vigentes).
 *
 * Techo real verificado el 2026-09-16 contra la API en vivo: Mercado Libre
 * rechaza (400 "The maximum allowed value for 'offset' is 100") cualquier
 * pedido a /products/search con offset > 100, sin importar cuán grande sea
 * paging.total ni cuánto se espere la respuesta — no es una cuestión de
 * tiempo, es una validación dura del lado del servidor. 'limit' tiene el
 * mismo techo (100). Con los dos al máximo, 200 productos de catálogo por
 * búsqueda es el techo honesto: no hay forma de traer más en una sola
 * búsqueda sin fragmentarla en sub-búsquedas, algo descartado a propósito
 * (ver PROJECT_SPEC.md 7.5). Antes se asumía un techo de ~1000 (medido
 * 2026-09-15); ML lo bajó, y el código viejo fallaba en silencio pasada la
 * 3ra página, mostrando muchos menos productos de los que hoy son alcanzables.
 *
 * Escanea siempre el máximo (200), sin cortar antes: la cantidad de productos
 * con vendedores activos varía mucho según el rubro (a veces 10%, a veces 90%
 * del catálogo), así que juntar todo lo que haya y ordenar después es más
 * confiable que parar en un número fijo.
 */
async function fetchProductsWithOffers(q, category = '', domain = '') {
  const PAGE_SIZE   = 100;
  const MAX_OFFSET  = 100;
  const REACHABLE   = MAX_OFFSET + PAGE_SIZE; // 200: techo real de ML para esta búsqueda
  let offset = 0, totalCatalog = 0;
  const collected = [];

  while (offset <= MAX_OFFSET) {
    const data = await API.products(q, offset, category, domain, PAGE_SIZE);
    if (offset === 0) totalCatalog = data.total || 0;
    const batch = data.results || [];
    if (!batch.length) break;

    await loadOffersForBatch(batch, (done) => {
      collected.push(...done.filter(p => (State.offersById[p.id]?.total || 0) > 0));
      const scanned = Math.min(offset + done.length, Math.min(totalCatalog, REACHABLE));
      setProgress(`Analizando el catálogo… ${collected.length} con vendedores encontrados (${scanned} de ${Math.min(totalCatalog, REACHABLE)} revisados)`);
      return false; // nunca cortar antes de tiempo: se quiere el máximo alcanzable
    });

    offset += PAGE_SIZE;
    if (offset >= totalCatalog) break;
  }

  return { products: collected, totalCatalog };
}

/**
 * Pide /api/products/{id}/offers (modo liviano) para una lista de productos, de a tandas.
 * `onChunk(chunk)` se llama despues de cada tanda; si devuelve true se corta (ya alcanza).
 */
async function loadOffersForBatch(list, onChunk = null) {
  const BATCH = 12;
  for (let i = 0; i < list.length; i += BATCH) {
    const chunk = list.slice(i, i + BATCH);
    await Promise.all(chunk.map(async p => {
      try {
        const data   = await API.offers(p.id, true);
        const prices = (data.offers || []).map(o => o.price).filter(v => v != null);
        State.offersById[p.id] = {
          total: data.total || 0, offers: data.offers || [],
          minPrice: prices.length ? Math.min(...prices) : null,
          maxPrice: prices.length ? Math.max(...prices) : null,
        };
      } catch {
        State.offersById[p.id] = { total: 0, offers: [], minPrice: null, maxPrice: null };
      }
    }));
    if (onChunk && onChunk(chunk)) return;
  }
}

// ═══════════════════════════════════════════════════════════
// MI NEGOCIO — datos reales y propios: ventas por período, visitas,
// conversión y precio recomendado para ganar (price_to_win)
// ═══════════════════════════════════════════════════════════
function renderMyBusiness(d) {
  const setKpi = (id, val, sub) => {
    const el = $(id);
    if (!el) return;
    el.querySelector('.metric-value').textContent = val;
    if (sub != null) el.querySelector('.metric-sub').textContent = sub;
  };

  setKpi('bTotalListings', Fmt.number(d.total_listings));
  setKpi('bVisits', Fmt.number(d.visits_total), `Últimos ${d.period_days} días`);
  setKpi('bOrders', Fmt.number(d.orders_count), d.revenue ? `${Fmt.price(d.revenue)} facturados` : 'Sin ventas en el período');
  setKpi('bConversion', d.conversion_pct != null ? `${d.conversion_pct}%` : '—', 'Ventas sobre visitas totales');

  // Serie de visitas
  drawChart('chartVisitsSeries', {
    type: 'line',
    data: {
      labels: (d.visits_series || []).map(p => new Date(p.date).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })),
      datasets: [{
        label: 'Visitas', data: (d.visits_series || []).map(p => p.total),
        borderColor: '#5b4fe0', backgroundColor: 'rgba(91,79,224,0.12)', fill: true, tension: 0.35, pointRadius: 2,
      }],
    },
    options: { ...CHART_BASE, scales: AXES_DARK, plugins: { ...CHART_BASE.plugins, legend: { display: false } } },
  });

  // Top productos propios por ventas históricas
  const top = (d.items || []).slice(0, 8);
  drawChart('chartMyTopItems', {
    type: 'bar',
    data: {
      labels: top.map(it => (it.title || '').split(' ').slice(0, 5).join(' ')),
      datasets: [{ label: 'Vendidos (histórico)', data: top.map(it => it.sold_quantity || 0), backgroundColor: '#3ecf8e', borderRadius: 5 }],
    },
    options: {
      ...CHART_BASE, indexAxis: 'y', scales: AXES_DARK,
      plugins: { ...CHART_BASE.plugins, legend: { display: false },
        tooltip: { ...CHART_BASE.plugins.tooltip, callbacks: { title: (c) => top[c[0].dataIndex].title } } },
    },
  });

  // Precio para ganar
  const ptwLabels = {
    winning:              { cls: 'threat-low',  label: 'Estás ganando' },
    competing:            { cls: 'threat-mid',  label: 'En competencia' },
    sharing_first_place:  { cls: 'threat-mid',  label: 'Empatás el primer lugar' },
    losing:               { cls: 'threat-high', label: 'Estás perdiendo' },
    not_listed:           { cls: '',            label: 'Sin datos de competencia' },
  };
  const reasonLabels = { item_not_opted_in: 'Esta publicación no está sumada al programa de precio competitivo de ML.' };

  if (!d.price_to_win?.length) {
    html($('priceToWinBody'), `<div class="empty-state"><div class="empty-title">Sin datos disponibles</div><div class="empty-sub">Ninguna de tus publicaciones principales tiene precio de referencia calculado por ML todavía.</div></div>`);
  } else {
    html($('priceToWinBody'), d.price_to_win.map(p => {
      const st = ptwLabels[(p.status || '').toLowerCase()] || { cls: '', label: p.status || 'Sin datos' };
      const reason = p.reason ? (reasonLabels[p.reason] || p.reason) : '';
      return `<div class="comp-card">
        <div class="comp-top">
          <div class="comp-left"><div class="comp-nick-wrap"><span class="comp-nick">${Fmt.esc(p.title)}</span></div></div>
          <div><span class="threat-badge ${st.cls}">${st.label}</span></div>
        </div>
        ${p.price_to_win != null ? `<div class="comp-stats">
          <div class="comp-stat-item"><span class="comp-stat-val">${Fmt.price(p.current_price)}</span><span class="comp-stat-label">Tu precio actual</span></div>
          <div class="comp-stat-item"><span class="comp-stat-val" style="color:var(--green)">${Fmt.price(p.price_to_win)}</span><span class="comp-stat-label">Precio para ganar</span></div>
          ${p.competitors_sharing_first_place != null ? `<div class="comp-stat-item"><span class="comp-stat-val">${p.competitors_sharing_first_place}</span><span class="comp-stat-label">Compiten por el 1er lugar</span></div>` : ''}
        </div>${renderBoosts(p.boosts)}` : (reason ? `<div class="insight-text" style="padding-top:4px">${Fmt.esc(reason)}</div>` : '')}
      </div>`;
    }).join(''));
  }

  // Tabla de publicaciones
  html($('bizItemsSub'), `${d.total_listings} publicaciones totales · muestra analizada: ${d.items_sample_size || d.items.length} · ${Fmt.number(d.total_sold_sample)} unidades vendidas (histórico, sobre la muestra)`);
  html($('bizItemsBody'), (d.items || []).map(it => {
    const thumb = it.thumbnail
      ? `<img class="product-thumb" src="${Fmt.esc(it.thumbnail)}" alt="" loading="lazy" onerror="this.style.display='none'">`
      : `<div class="product-thumb-ph"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="5"/></svg></div>`;
    return `<tr>
      <td>${thumb}</td>
      <td><span class="product-name" title="${Fmt.esc(it.title)}">${Fmt.esc(it.title)}</span><span class="product-id">${Fmt.esc(it.id)}</span></td>
      <td><span class="price-val">${Fmt.price(it.price)}</span></td>
      <td><span class="sold-val">${Fmt.number(it.sold_quantity)}</span></td>
      <td><span class="pubs-val">${Fmt.number(it.available_quantity)}</span></td>
      <td><a class="link-btn" href="${Fmt.esc(it.permalink)}" target="_blank" rel="noopener noreferrer">Ver
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7,7 17,7 17,17"/></svg>
      </a></td>
    </tr>`;
  }).join('') || `<tr class="empty-row"><td colspan="6"><div class="empty-state"><div class="empty-title">Sin publicaciones activas</div></div></td></tr>`);
}

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════
(function init() {
  renderRubrosNav();
  populateCategorySelect();
  loadTrends();
  switchView('dashboard');

  document.querySelectorAll('.nav-item[data-view]').forEach(el => {
    el.addEventListener('click', () => switchView(el.dataset.view));
  });

  $('inputQ')?.addEventListener('keydown', e => { if (e.key === 'Enter') App.search(); });
  $('inputLookup')?.addEventListener('keydown', e => { if (e.key === 'Enter') App.analyzeListing(); });

  const nickInput = $('inputMyNick');
  if (nickInput) {
    nickInput.value = window.__MY_NICKNAME__ || '';
    nickInput.addEventListener('change', function () {
      localStorage.setItem('ml_my_nick', this.value.trim());
      CFG.MY_NICK = this.value.trim().toUpperCase();
      renderProducts();
    });
  }

  $('selSort')?.addEventListener('change', function () { App.setSort(this.value); });
  $('selBizDays')?.addEventListener('change', () => App.loadMyBusiness());

  $('selCat')?.addEventListener('change', function () {
    State.activeSub = State.activeCat.subcats[Number(this.value)] || State.activeCat.subcats[0];
    const inp = $('inputQ');
    if (inp) { inp.value = ''; inp.placeholder = `Buscar dentro de “${State.activeSub.label}”…`; }
    loadTrends();
  });

  document.addEventListener('keydown', e => { if (e.key === 'Escape' && State.panelProduct) App.closePanel(); });

  document.querySelectorAll('.overview-table th[data-sort]').forEach(th => th.addEventListener('click', () => {
    const key = th.dataset.sort;
    State.overviewSort = State.overviewSort.key === key
      ? { key, dir: -State.overviewSort.dir }
      : { key, dir: ['label', 'top_brand', 'avg_sellers', 'median_price', 'official_store_pct'].includes(key) ? 1 : -1 };
    if (State.overview) renderOverview();
  }));

  document.addEventListener('click', e => {
    const card = e.target.closest('.rel-card[data-related]');
    if (!card) return;
    const d = card.dataset;
    App.openPanel({ id: d.pid, name: d.name, brand: d.brand || null, thumbnail: d.thumb || null });
  });
})();
