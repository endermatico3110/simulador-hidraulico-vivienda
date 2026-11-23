import math
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import hidraulica as h

st.set_page_config(page_title='Simulador hidráulico | Ingeniería', page_icon='💧', layout='wide')

st.markdown('''
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root{--navy:#102a43;--blue:#0787c8;--cyan:#35b9e8;--muted:#627d98;--line:#d9e5ef;--bg:#f3f7fb;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:linear-gradient(180deg,#eef5fa 0%,#f8fbfd 35%,#fff 100%);}
.block-container{max-width:1540px;padding-top:1.7rem;padding-bottom:3rem;}
h1,h2,h3{font-family:'Manrope',sans-serif;color:var(--navy);letter-spacing:-.035em;}
[data-testid="stSidebar"]{background:#f0f5f9;border-right:1px solid #dce7ef;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:0 5px 18px #16324f08;}
[data-testid="stMetricLabel"]{color:var(--muted);font-weight:600;}
[data-testid="stMetricValue"]{color:var(--navy);font-family:'Manrope',sans-serif;}
.stTabs [data-baseweb="tab-list"]{gap:7px;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{background:#eaf1f6;border-radius:10px 10px 0 0;padding:10px 15px;font-weight:600;}
.stTabs [aria-selected="true"]{background:#dff3fc!important;color:#056d9f!important;}
div[data-testid="stAlert"]{border-radius:14px;}
div.stButton>button,div.stDownloadButton>button{border-radius:11px;font-weight:700;}
.small-note{color:#627d98;font-size:.88rem;}
.section-kicker{color:#0787c8;font-size:.76rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase;}
.hero{background:linear-gradient(115deg,#0e2a43,#145477 65%,#0787c8);padding:25px 28px;border-radius:22px;color:white;margin-bottom:20px;box-shadow:0 12px 32px #0e2a4320;}
.hero h1{color:white!important;margin:0;font-size:2rem;}.hero p{color:#d7edf8;margin:.45rem 0 0;}
.pill{display:inline-block;border:1px solid #d8e8f2;background:#f5fbff;border-radius:999px;padding:5px 10px;font-size:.78rem;color:#25617f;font-weight:700;}
</style>
''', unsafe_allow_html=True)

st.markdown('''<div class="hero"><div class="section-kicker" style="color:#9be4ff">LABORATORIO VIRTUAL · INSTALACIONES SANITARIAS</div><h1>💧 Simulador hidráulico</h1><p>Vivienda de cuatro niveles · Cisterna → bomba → tanque elevado → regaderas</p></div>''', unsafe_allow_html=True)
base = h.Datos()

# --------- Sidebar: system data ---------
with st.sidebar:
    st.markdown('### ⚙️ Configuración del sistema')
    with st.expander('🏠 Geometría de la vivienda', expanded=True):
        altura_piso = st.number_input('Altura de cada piso (m)', 2.0, 5.0, float(base.altura_piso), .1)
        altura_regadera = st.number_input('Altura de regadera sobre el piso (m)', 1.0, 3.0, float(base.altura_regadera), .1)
        base_tanque = st.number_input('Cota de la base del tanque (m)', 5.0, 25.0, float(base.base_tanque), .5)
        prof_agua_max = st.number_input('Altura útil máxima del agua (m)', .2, 3.0, float(base.prof_agua_max), .1)
        nivel_cisterna = st.number_input('Cota del agua en cisterna (m)', -10.0, 5.0, float(base.nivel_cisterna), .1)
    with st.expander('🛢️ Geometría del tanque', expanded=True):
        tipo_tanque = st.radio('Forma del tanque elevado', ['Rectangular', 'Cilíndrico vertical'], horizontal=True)
        if tipo_tanque == 'Rectangular':
            ancho = st.number_input('Ancho interior (m)', .3, 10., 1.20, .05)
            largo = st.number_input('Largo interior (m)', .3, 10., 1.50, .05)
            area_tanque = ancho * largo
            dims_tanque = f'{ancho:.2f} × {largo:.2f} m'
        else:
            diam = st.number_input('Diámetro interior (m)', .3, 5., 1.10, .05)
            area_tanque = math.pi * diam**2 / 4
            dims_tanque = f'Ø {diam:.2f} m'
        d_equiv = math.sqrt(4 * area_tanque / math.pi)
        st.caption(f'Área en planta: **{area_tanque:.2f} m²** · Capacidad útil: **{area_tanque*prof_agua_max:.2f} m³**')
    with st.expander('🔧 Tuberías y accesorios', expanded=False):
        d_montante = st.selectbox('Diámetro de montante', list(h.DIAM), index=list(h.DIAM).index(base.d_montante))
        d_ramal = st.selectbox('Diámetro de ramal', list(h.DIAM), index=list(h.DIAM).index(base.d_ramal))
        L_bajada = st.number_input('Longitud bajada principal (m)', .1, 100., float(base.L_bajada), .5)
        L_horizontal = st.number_input('Longitud tramo horizontal (m)', .1, 100., float(base.L_horizontal), .5)
        L_ramal = st.number_input('Longitud ramal (m)', .1, 100., float(base.L_ramal), .5)
        L_impulsion = st.number_input('Longitud impulsión (m)', .1, 100., float(base.L_impulsion), .5)
        L_succion = st.number_input('Longitud succión (m)', .1, 100., float(base.L_succion), .5)
    with st.expander('📐 Criterios de operación', expanded=True):
        demanda = st.slider('Factor de demanda', .25, 1.5, float(base.demanda), .05)
        p_min = st.number_input('Presión mínima requerida (m c.a.)', .5, 10., float(base.p_min), .1)
        modo_label = st.selectbox('Modelo de cálculo', ['Según informe', 'Equilibrio de caudales'])
        modo = 'informe' if modo_label == 'Según informe' else 'equilibrio'
        fuente_label = st.selectbox('Caudal de la bomba', ['Curva provisional de bomba', 'Caudal de referencia del informe'])
        fuente_q = 'curva' if fuente_label.startswith('Curva') else 'referencia'

try:
    d = h.copiar(base, altura_piso=altura_piso, altura_regadera=altura_regadera,
        base_tanque=base_tanque, prof_agua_max=prof_agua_max, d_tanque=d_equiv,
        nivel_cisterna=nivel_cisterna, d_montante=d_montante, d_ramal=d_ramal,
        L_bajada=L_bajada, L_horizontal=L_horizontal, L_ramal=L_ramal,
        L_impulsion=L_impulsion, L_succion=L_succion, demanda=demanda, p_min=p_min)
    errores = d.validar()
    if errores:
        for err in errores: st.error(err)
        st.stop()

    # --------- Independent shower valves and pump control ---------
    st.markdown('### 🎛️ Panel de operación')
    left, right = st.columns([1.35, 1])
    with left:
        nivel = st.slider('Nivel inicial del agua en el tanque (m)', float(d.base_tanque), float(d.nivel_max), float(d.nivel_arranque), .01)
        st.markdown('**Regaderas: abre o cierra cada punto de consumo**')
        shower_cols = st.columns(4)
        shower_open = []
        for i, col in enumerate(shower_cols, start=1):
            with col:
                shower_open.append(st.toggle(f'Piso {i}', value=True, key=f'shower_{i}'))
    with right:
        pump_mode = st.radio('Control de la bomba', ['Automático', 'Encendida', 'Apagada'], horizontal=False, help='Automático: arranca en el nivel de arranque y se detiene al alcanzar el nivel máximo.')
        piso = st.selectbox('Piso destacado en resultados', [1, 2, 3, 4], index=3)
        st.caption('El modo automático aplica una lógica de control por nivel alto/bajo; no representa un tablero eléctrico real.')

    # Hydraulic network calculation with independent open/closed floor demand.
    fractions = tuple(1.0 if is_open else 0.0 for is_open in shower_open)
    floor_results = []
    for floor in range(1, 5):
        rr = h.residual_piso(d, nivel, floor, fractions)
        if shower_open[floor-1]:
            factor = min(1.0, math.sqrt(max(rr['P'], 0.0) / d.p_min))
            q_shower = h.q_hunter(1) * d.demanda * factor
            state = 'Suficiente' if rr['P'] >= d.p_min else ('Sin flujo' if factor < .01 else 'Insuficiente')
        else:
            factor, q_shower, state = 0.0, 0.0, 'Cerrada'
        rr.update({'f_abast': factor, 'Q_regadera': q_shower, 'P_jet': max(rr['P'],0),
                   'estado': state, 'v_ramal': rr['tramos'][-1]['v'] if shower_open[floor-1] else 0.0})
        floor_results.append(rr)
    selected = floor_results[piso-1]
    total_demand = sum(x['Q_regadera'] for x in floor_results)

    op = h.punto_operacion(d, d.dz_bombeo)
    q_pump = d.q_llenado_ref if fuente_q == 'referencia' else op['Q_Lmin']/60
    pump_h = h.bomba_estatica(d, q_pump, d.dz_bombeo)

    # Time-domain tank balance using the actual selected tank area and shower demand.
    def tank_simulation(initial_level, area, max_level, start_level, base_level, qin_lps, qout_lps, control, minutes=30, dt=2):
        level = min(max(initial_level, base_level), max_level)
        pump_running = (level <= start_level) if control == 'Automático' else (control == 'Encendida')
        ts, levels, states, inflows = [0.0], [level], [pump_running], [qin_lps if pump_running else 0.0]
        for step in range(int(minutes*60/dt)):
            if control == 'Automático':
                if level >= max_level - 1e-6: pump_running = False
                elif level <= start_level + 1e-6: pump_running = True
            elif control == 'Apagada': pump_running = False
            else: pump_running = level < max_level - 1e-6
            qin = qin_lps if pump_running else 0.0
            qout = qout_lps if level > base_level + 1e-9 else min(qout_lps, qin)
            level = min(max(level + ((qin-qout)/1000/area)*dt, base_level), max_level)
            if control == 'Automático':
                if level >= max_level - 1e-6: pump_running = False
                elif level <= start_level + 1e-6: pump_running = True
            ts.append((step+1)*dt/60); levels.append(level); states.append(pump_running); inflows.append(qin_lps if pump_running else 0.0)
        return {'t':np.array(ts),'nivel':np.array(levels),'bomba':np.array(states),'qin':np.array(inflows)}

    bal = tank_simulation(nivel, area_tanque, d.nivel_max, d.nivel_arranque, d.base_tanque,
                          q_pump, total_demand, pump_mode)
    pump_running_now = bool(bal['bomba'][0])
    state_colors = {'Suficiente':'#159b70','Insuficiente':'#d97706','Sin flujo':'#dc4545','Cerrada':'#8295a7'}

    # --------- Animated system diagram ---------
    st.markdown('### 🏢 Vista general del sistema')
    st.caption('Animación conceptual del recorrido del agua. No es un análisis CFD ni una representación a escala.')
    frac_level = min(1., max(0., (nivel-d.base_tanque)/max(d.prof_agua_max,.001)))
    water_h = 72*frac_level
    final_level = float(bal['nivel'][-1])
    final_frac = min(1., max(0., (final_level-d.base_tanque)/max(d.prof_agua_max,.001)))
    water_h_end = 72*final_frac
    pump_active = pump_running_now
    pipe_class = 'flow' if pump_active else 'still'
    branches=[]
    for i, rr in enumerate(floor_results, start=1):
        y = 230 + (i-1)*82
        active = shower_open[i-1] and rr['Q_regadera'] > .005
        cls = 'flow' if active else 'still'
        color = '#18a6d8' if active else '#a8b8c5'
        shower = (f'<path d="M818 {y-8} h24 v9 h-12" class="pipeThin"/><path d="M830 {y+1} q-11 12 0 23 q11-11 0-23" class="drop {"dropOn" if active else ""}"/>')
        branches.append(f'<path d="M650 {y} H805" class="water {cls}" style="stroke:{color}"/><text x="855" y="{y+2}" class="lbl">Piso {i}</text><text x="855" y="{y+23}" class="sm">{rr["estado"]} · {rr["Q_regadera"]:.2f} L/s</text>{shower}')
    branch_svg=''.join(branches)
    if tipo_tanque == 'Rectangular':
        tank_outline='<rect x="510" y="40" width="190" height="105" rx="8" class="tank"/>'
        tank_water=f'<clipPath id="tankClip"><rect x="515" y="45" width="180" height="95" rx="4"/></clipPath><rect x="515" y="{140-water_h:.1f}" width="180" height="{water_h:.1f}" class="tankWater" clip-path="url(#tankClip)"><animate attributeName="y" values="{140-water_h:.1f};{140-water_h_end:.1f};{140-water_h:.1f}" dur="8s" repeatCount="indefinite"/><animate attributeName="height" values="{water_h:.1f};{water_h_end:.1f};{water_h:.1f}" dur="8s" repeatCount="indefinite"/></rect>'
    else:
        tank_outline='<path d="M540 55 Q540 39 605 39 Q670 39 670 55 L670 130 Q670 146 605 146 Q540 146 540 130 Z" class="tank"/><ellipse cx="605" cy="55" rx="65" ry="16" class="tank"/><ellipse cx="605" cy="130" rx="65" ry="16" class="tankBottom"/>'
        tank_water=f'<clipPath id="tankClip"><path d="M544 55 Q544 43 605 43 Q666 43 666 55 L666 130 Q666 142 605 142 Q544 142 544 130 Z"/></clipPath><rect x="544" y="{130-water_h:.1f}" width="122" height="{water_h:.1f}" class="tankWater" clip-path="url(#tankClip)"><animate attributeName="y" values="{130-water_h:.1f};{130-water_h_end:.1f};{130-water_h:.1f}" dur="8s" repeatCount="indefinite"/><animate attributeName="height" values="{water_h:.1f};{water_h_end:.1f};{water_h:.1f}" dur="8s" repeatCount="indefinite"/></rect>'
    svg = f'''<!doctype html><html><head><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f4f8fc;font-family:Arial,sans-serif;color:#102a43}}
    .wrap{{border:1px solid #dbe7f0;border-radius:20px;background:linear-gradient(145deg,#fff,#eef6fb);padding:8px;box-shadow:0 8px 25px #16324f0c}}
    svg{{width:100%;height:auto;display:block}}.building{{fill:#fff;stroke:#8ba2b5;stroke-width:3}}.slab{{stroke:#c4d2dd;stroke-width:5}}
    .pipe{{fill:none;stroke:#607d91;stroke-width:13;stroke-linecap:round;stroke-linejoin:round}}.pipeThin{{fill:none;stroke:#607d91;stroke-width:7;stroke-linecap:round}}
    .water{{fill:none;stroke:#18a6d8;stroke-width:6;stroke-linecap:round;stroke-dasharray:12 15}}.flow{{animation:dash 1s linear infinite}}.still{{opacity:.18;stroke-dasharray:4 10;animation:none}}@keyframes dash{{to{{stroke-dashoffset:-54}}}}
    .tank{{fill:#fafdff;stroke:#46677f;stroke-width:4}}.tankBottom{{fill:#fafdff;stroke:#46677f;stroke-width:3}}.tankWater{{fill:#35b9e8;opacity:.8}}
    .lbl{{font-size:17px;font-weight:bold;fill:#173b56}}.sm{{font-size:13px;fill:#627d98}}.drop{{fill:#9bdff5;opacity:.2}}.dropOn{{opacity:1;animation:fall .75s ease-in-out infinite alternate}}@keyframes fall{{to{{transform:translateY(7px)}}}}
    .pump{{fill:#fff;stroke:#46677f;stroke-width:4}}.pumpActive{{fill:#d8f4ff;stroke:#0787c8}}.status{{font-size:14px;font-weight:bold;fill:{'#0787c8' if pump_active else '#627d98'}}}
    </style></head><body><div class="wrap"><svg viewBox="0 0 1050 650" role="img" aria-label="Diagrama del sistema hidráulico de cuatro pisos">
    <rect x="315" y="175" width="510" height="390" rx="8" class="building"/><path d="M315 257 H825 M315 339 H825 M315 421 H825 M315 503 H825" class="slab"/>
    <text x="338" y="205" class="lbl">EDIFICACIÓN · 4 NIVELES</text>
    {tank_outline}{tank_water}<text x="515" y="25" class="lbl">Tanque {tipo_tanque.lower()}</text><text x="515" y="165" class="sm">Nivel inicial: {nivel:.2f} m · {frac_level*100:.0f}% útil</text>
    <path d="M605 146 V230 M605 230 V503" class="pipe"/><path d="M605 146 V230 M605 230 V503" class="water flow"/>{branch_svg}
    <rect x="45" y="490" width="190" height="115" rx="12" class="tank"/><rect x="50" y="545" width="180" height="55" rx="6" class="tankWater"/><text x="70" y="480" class="lbl">Cisterna</text>
    <path d="M235 550 H285" class="pipe"/><path d="M235 550 H285" class="water {pipe_class}"/><rect x="285" y="515" width="95" height="72" rx="12" class="pump {'pumpActive' if pump_active else ''}"/><circle cx="332" cy="551" r="20" fill="none" stroke="#46677f" stroke-width="4"/><path d="M324 539 L344 551 L324 563 Z" fill="#0787c8"/>
    <text x="278" y="612" class="sm">Bomba: {'ENCENDIDA' if pump_active else 'APAGADA'}</text><path d="M380 550 H435 V92 H510" class="pipe"/><path d="M380 550 H435 V92 H510" class="water {pipe_class}"/>
    <text x="451" y="335" class="sm" transform="rotate(-90 451 335)">Impulsión</text><text x="730" y="75" class="status">{'LLENANDO' if pump_active else 'SIN LLENADO'}</text>
    <text x="45" y="635" class="sm">Esquema ilustrativo · distribución conceptual · no está a escala</text></svg></div></body></html>'''
    components.html(svg, height=665, scrolling=False)

    # --------- Compact interpretation ---------
    st.markdown('### 📊 Estado del sistema')
    m1,m2,m3,m4 = st.columns(4)
    m1.metric('Presión · piso '+str(piso), f"{selected['P']:.2f} m c.a.", f"{selected['P']*9.80665:.1f} kPa")
    m2.metric('Caudal de esa regadera', f"{selected['Q_regadera']:.3f} L/s")
    m3.metric('Demanda total abierta', f"{total_demand:.3f} L/s")
    m4.metric('Volumen útil del tanque', f"{area_tanque*prof_agua_max:.2f} m³", dims_tanque)

    state = selected['estado']
    if state == 'Suficiente': st.success(f'Piso {piso}: presión suficiente. La presión residual supera el mínimo de {d.p_min:.1f} m c.a.')
    elif state == 'Insuficiente': st.warning(f'Piso {piso}: presión insuficiente. El caudal estimado se reduce frente al valor de diseño.')
    elif state == 'Sin flujo': st.error(f'Piso {piso}: no hay presión disponible para mantener el flujo.')
    else: st.info(f'Piso {piso}: regadera cerrada; no existe consumo en ese punto.')
    with st.expander('Entender este resultado en 20 segundos'):
        a,b,c = st.columns(3)
        a.metric('Altura disponible', f"{selected['h_est']:.2f} m")
        b.metric('Pérdidas calculadas', f"{selected['hL']:.2f} m")
        c.metric('Presión mínima', f"{d.p_min:.2f} m c.a.")
        st.write(f"La superficie del agua está {selected['h_est']:.2f} m por encima de la regadera. El recorrido pierde {selected['hL']:.2f} m de carga por fricción y accesorios; quedan {selected['P']:.2f} m c.a. de presión residual.")
    st.info('Principio físico: a igual diferencia vertical entre la superficie del agua y la regadera, la presión hidrostática es la misma para un tanque rectangular o cilíndrico. La forma modifica el área, la capacidad y la rapidez con que cambia el nivel; no aumenta por sí sola la presión.')

    # --------- Tabs ---------
    tab1,tab2,tab3,tab4,tab5 = st.tabs(['Presión y regaderas','Tanque y geometría','Bomba automática','Red de tuberías','Comparar tanques'])
    with tab1:
        dfp = pd.DataFrame([{'Punto':f'Piso {r["piso"]}','Válvula':('Abierta' if shower_open[r['piso']-1] else 'Cerrada'),'Presión residual (m c.a.)':r['P'],'Caudal (L/s)':r['Q_regadera'],'Estado':r['estado']} for r in floor_results])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dfp['Punto'],y=dfp['Presión residual (m c.a.)'],name='Presión residual',marker_color=['#159b70' if x>=d.p_min else '#e39a35' if x>0 else '#d7e0e8' for x in dfp['Presión residual (m c.a.)']]))
        fig.add_hline(y=d.p_min,line_dash='dash',line_color='#d94b4b',annotation_text=f'Mínimo {d.p_min:.1f} m c.a.')
        fig.update_layout(title='Presión disponible en cada regadera',yaxis_title='Presión (m c.a.)',height=370,template='plotly_white',margin=dict(l=20,r=20,t=55,b=20))
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(dfp,use_container_width=True,hide_index=True)
    with tab2:
        level_df = pd.DataFrame({'Tiempo (min)':bal['t'],'Nivel de agua (m)':bal['nivel']})
        figt = go.Figure(go.Scatter(x=level_df['Tiempo (min)'],y=level_df['Nivel de agua (m)'],mode='lines',fill='tozeroy',name='Nivel',line=dict(width=3,color='#159bd7')))
        figt.add_hline(y=d.nivel_arranque,line_dash='dash',annotation_text='Arranque')
        figt.add_hline(y=d.nivel_max,line_dash='dot',annotation_text='Nivel máximo')
        figt.add_hline(y=d.nivel_min,line_dash='dash',annotation_text='Nivel mínimo operativo')
        figt.update_layout(title='Evolución estimada del nivel del tanque',xaxis_title='Tiempo (min)',yaxis_title='Cota (m)',height=370,template='plotly_white',margin=dict(l=20,r=20,t=55,b=20))
        st.plotly_chart(figt,use_container_width=True)
        vol_actual = area_tanque * max(0,nivel-d.base_tanque)
        va,vb,vc = st.columns(3)
        va.metric('Volumen inicial',f'{vol_actual:.2f} m³')
        vb.metric('Volumen útil máximo',f'{area_tanque*prof_agua_max:.2f} m³')
        vc.metric('Área en planta',f'{area_tanque:.2f} m²')
        st.caption(f'Geometría: {tipo_tanque} · Dimensiones interiores: {dims_tanque}. El cálculo del balance usa el área horizontal del tanque.')
    with tab3:
        c1,c2,c3 = st.columns(3)
        c1.metric('Altura requerida por el modelo',f"{pump_h['HB']:.2f} m")
        c2.metric('Caudal adoptado',f"{q_pump*60:.1f} L/min")
        c3.metric('Potencia hidráulica',f"{pump_h['Ph']:.1f} W")
        st.markdown(f"**Control seleccionado:** {pump_mode} · **Estado al inicio:** {'Bomba encendida' if pump_running_now else 'Bomba apagada'}")
        curve = sorted(d.curva); qvals = np.linspace(0,max(x for x,y in curve),150)
        hvals = [h.curva_H(d,q) for q in qvals]
        sysvals = [h.bomba_estatica(d,q/60,d.dz_bombeo)['HB'] for q in qvals]
        figb = go.Figure()
        figb.add_trace(go.Scatter(x=qvals,y=hvals,mode='lines',name='Curva de bomba H-Q',line=dict(width=3)))
        figb.add_trace(go.Scatter(x=qvals,y=sysvals,mode='lines',name='Curva del sistema',line=dict(width=3)))
        figb.add_trace(go.Scatter(x=[op['Q_Lmin']],y=[op['H']],mode='markers',name='Punto de operación',marker=dict(size=12)))
        figb.update_layout(title='Curva de la bomba y curva del sistema',xaxis_title='Caudal (L/min)',yaxis_title='Altura (m)',height=370,template='plotly_white')
        st.plotly_chart(figb,use_container_width=True)
        st.warning('La curva de bomba del archivo original es provisional. Sustitúyela por la curva exacta del equipo antes de usar los resultados para dimensionamiento definitivo.')
    with tab4:
        details=[]
        for rr in floor_results:
            for tramo in rr['tramos']:
                details.append({'Piso evaluado':rr['piso'],'Tramo':tramo['nombre'],'Caudal (L/s)':tramo['Q'],'Diámetro (m)':tramo['D'],'Velocidad (m/s)':tramo['v'],'Reynolds':tramo['Re'],'Pérdida total (m)':tramo['hL']})
        st.dataframe(pd.DataFrame(details),use_container_width=True,hide_index=True)
        st.caption('Los tramos se recalculan para la combinación de regaderas abiertas. Los caudales de Hunter siguen siendo una aproximación probabilística del modelo base.')
    with tab5:
        st.markdown('**Comparación a igual altura de agua**')
        st.write('Si ambas geometrías tienen la misma altura de agua y la misma cota de base, la presión hidrostática en una misma regadera es igual. La capacidad y la variación del nivel sí dependen del área en planta.')
        comp1,comp2 = st.columns(2)
        with comp1:
            st.markdown('**Tanque rectangular alternativo**')
            ca = st.number_input('Ancho (m)',.3,10.,1.2,.05,key='cmp_w')
            cl = st.number_input('Largo (m)',.3,10.,1.5,.05,key='cmp_l')
            area_rect=ca*cl
        with comp2:
            st.markdown('**Tanque cilíndrico alternativo**')
            cd = st.number_input('Diámetro (m)',.3,5.,1.1,.05,key='cmp_d')
            area_cyl=math.pi*cd**2/4
        comp_df=pd.DataFrame([
            {'Geometría':'Rectangular','Área (m²)':area_rect,'Volumen a altura útil (m³)':area_rect*prof_agua_max,'Presión a igual altura (m c.a.)':'Igual'},
            {'Geometría':'Cilíndrico vertical','Área (m²)':area_cyl,'Volumen a altura útil (m³)':area_cyl*prof_agua_max,'Presión a igual altura (m c.a.)':'Igual'}])
        st.dataframe(comp_df,use_container_width=True,hide_index=True)
        st.caption('Para comparar presiones distintas, modifica la altura de la columna de agua o la cota de instalación; cambiar solo la forma no cambia la presión a igual altura.')

    st.divider()
    st.markdown('### 📤 Exportar resultados')
    export_rows=[]
    for rr in floor_results:
        export_rows.append({'Piso':rr['piso'],'Regadera':('Abierta' if shower_open[rr['piso']-1] else 'Cerrada'),'Presión residual (m c.a.)':rr['P'],'Caudal (L/s)':rr['Q_regadera'],'Velocidad ramal (m/s)':rr['v_ramal'],'Estado':rr['estado']})
    csv=pd.DataFrame(export_rows).to_csv(index=False).encode('utf-8-sig')
    st.download_button('⬇️ Descargar resultados por piso (CSV)',data=csv,file_name='resultados_simulador_hidraulico.csv',mime='text/csv')
    st.caption('Herramienta académica. Verifica supuestos, coeficientes, normativa aplicable y curva real de la bomba antes de utilizar los resultados para diseño o instalación.')
except Exception as exc:
    st.error('Se produjo un problema al calcular el escenario.')
    st.exception(exc)
