"""
NÚCLEO DE CÁLCULO DEL SIMULADOR HIDRÁULICO
Vivienda de cuatro niveles: cisterna -> bomba -> tanque elevado -> regaderas (por gravedad).

Todas las ecuaciones son las del marco teórico del informe. Los números entre
paréntesis, por ejemplo (8), son los de esas ecuaciones.
Este archivo NO depende de Streamlit ni de Plotly: se puede probar solo (prueba_modelo.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

G = 9.81          # gravedad (m/s²)
RHO = 1000.0      # densidad del agua (kg/m³)
NU = 1.0e-6       # viscosidad cinemática del agua a 20 °C (m²/s)

# Diámetros interiores de tubería de PVC clase 10 (m) - catálogo Pavco Wavin (Tabla 2 del informe)
DIAM = {"1/2": 0.0174, "3/4": 0.0229, "1": 0.0294, "1 1/4": 0.0380}
# Norma IS.010: caudal probable de Hunter (UH -> L/s) y velocidades límite (m/s)
HUNTER = {6: 0.25, 12: 0.38, 18: 0.50, 24: 0.61}
VEL_MAX = {"1/2": 1.90, "3/4": 2.20, "1": 2.48, "1 1/4": 2.85}
VEL_MIN = 0.60

# Curva H-Q de la bomba. PROVISIONAL: son los puntos de la CPm 660 (sin "M") de la ficha de Pedrollo.
# La curva exacta de la CPm 660M no está en el informe: reemplácela en la interfaz cuando la tenga.
CURVA_PROVISIONAL = [(0, 48.0), (20, 47.5), (40, 46.0), (60, 44.0), (80, 41.0), (90, 39.5), (100, 37.5), (110, 35.0), (120, 32.0)]


@dataclass
class Datos:
    """Datos de entrada. Los valores por defecto son los de la Tabla 2 del informe."""
    altura_piso: float = 2.80         # m
    altura_regadera: float = 2.00     # m sobre el piso (supuesto del informe)
    base_tanque: float = 12.00        # m, base del tanque respecto al piso del primer nivel
    prof_agua_max: float = 1.00       # m, profundidad del agua con el nivel máximo
    desc_arranque: float = 0.40       # m, la bomba arranca 0,40 m bajo el nivel máximo (mitad de la altura útil)
    desc_minimo: float = 0.80         # m, nivel mínimo extremo bajo el máximo
    d_tanque: float = 1.10            # m
    nivel_cisterna: float = -0.50     # m (supuesto del modelo; con el tanque lleno da Δz = 13,50 m)
    d_montante: str = "3/4"
    d_ramal: str = "1/2"
    L_bajada: float = 12.0            # m
    L_horizontal: float = 3.0         # m
    L_ramal: float = 3.0              # m
    L_impulsion: float = 15.0         # m
    L_succion: float = 2.0            # m
    K_codo90: float = 1.5
    K_te_linea: float = 0.9
    K_te_deriv: float = 2.0
    K_bola: float = 0.05
    K_retencion: float = 2.0
    K_entrada: float = 0.5            # valor usual (supuesto del informe)
    K_succion: float = 3.0            # supuesto del informe
    p_min: float = 2.0                # m c.a., presión mínima de salida (IS.010)
    demanda: float = 1.0              # factor respecto del caudal de diseño de Hunter (1 = 100 %)
    q_llenado_ref: float = 1.164      # L/s, caudal de llenado de referencia (Tabla 5 del informe)
    q_ref_piso1: float = 0.220        # L/s, caudal de referencia de la regadera del piso 1
    q_ref_piso4: float = 0.145        # L/s, caudal de referencia de la regadera del piso 4
    curva: list = field(default_factory=lambda: [tuple(p) for p in CURVA_PROVISIONAL])

    @property
    def techo(self) -> float: return 4 * self.altura_piso
    @property
    def nivel_max(self) -> float: return self.base_tanque + self.prof_agua_max
    @property
    def nivel_arranque(self) -> float: return self.nivel_max - self.desc_arranque
    @property
    def nivel_min(self) -> float: return self.nivel_max - self.desc_minimo
    @property
    def dz_bombeo(self) -> float: return self.nivel_max - self.nivel_cisterna

    def validar(self) -> list[str]:
        """Devuelve la lista de errores; vacía si los datos son válidos."""
        e = []
        for nombre in ("altura_piso", "altura_regadera", "prof_agua_max", "d_tanque", "L_bajada", "L_horizontal", "L_ramal",
                       "L_impulsion", "L_succion", "p_min", "demanda"):
            if getattr(self, nombre) <= 0: e.append(f"{nombre} debe ser mayor que cero.")
        if self.d_montante not in DIAM or self.d_ramal not in DIAM: e.append("Diámetro de tubería no válido.")
        if self.desc_minimo < self.desc_arranque: e.append("El nivel mínimo debe estar por debajo del nivel de arranque.")
        if self.desc_minimo > self.prof_agua_max: e.append("El nivel mínimo no puede quedar bajo la base del tanque.")
        if any(getattr(self, k) < 0 for k in ("K_codo90", "K_te_linea", "K_te_deriv", "K_bola", "K_retencion", "K_entrada", "K_succion")):
            e.append("Los coeficientes K no pueden ser negativos.")
        return e


# ------------------------------------------------------------------------------------ ecuaciones
def presion_hidrostatica(h: float) -> float:
    """Ecuación (1): P = rho·g·h   (h en m -> P en Pa)"""
    return RHO * G * h


def tramo_calc(Q_Ls: float, D: float, L: float, sumK: float) -> dict:
    """Velocidad y pérdidas de un tramo. Q en L/s, D y L en m."""
    if Q_Ls <= 1e-9:
        return dict(Q=0.0, D=D, L=L, K=sumK, v=0.0, Re=0.0, f=0.0, hv=0.0, hf=0.0, hm=0.0, hL=0.0)
    A = math.pi * D ** 2 / 4
    v = (Q_Ls / 1000) / A                     # ecuaciones (4) y (5)
    Re = v * D / NU                           # ecuación (6)
    f = 0.3164 / Re ** 0.25                   # ecuación (7), Blasius
    hv = v ** 2 / (2 * G)
    hf = f * (L / D) * hv                     # ecuación (8), Darcy-Weisbach
    hm = sumK * hv                            # ecuación (9)
    return dict(Q=Q_Ls, D=D, L=L, K=sumK, v=v, Re=Re, f=f, hv=hv, hf=hf, hm=hm, hL=hf + hm)


def q_hunter(n_pisos: int) -> float:
    """Caudal probable de Hunter (L/s) para n pisos (6 UH por piso)."""
    return HUNTER[6 * n_pisos]


def construir_tramos(d: Datos, piso: int, f=(1, 1, 1, 1)) -> list[dict]:
    """Tramos entre el tanque y la regadera del piso. f = fracción de abastecimiento de cada piso (1 = completo)."""
    s = d.demanda
    fac = lambda pisos: sum(f[k - 1] for k in pisos) / len(pisos)
    todos = [1, 2, 3, 4]
    t = [("Bajada principal", q_hunter(4) * s * fac(todos), DIAM["1"], d.L_bajada, d.K_entrada + d.K_bola + 2 * d.K_codo90),
         ("Tramo horizontal", q_hunter(4) * s * fac(todos), DIAM["1"], d.L_horizontal, d.K_codo90)]
    for p in range(2, piso + 1):
        serv = list(range(p, 5))
        t.append((f"Montante, piso {p-1} a {p}", q_hunter(len(serv)) * s * fac(serv), DIAM[d.d_montante], d.altura_piso, d.K_te_linea))
    t.append(("Ramal de piso", q_hunter(1) * s * fac([piso]), DIAM[d.d_ramal], d.L_ramal, 2 * d.K_codo90 + d.K_bola + d.K_te_deriv))
    out = []
    for nombre, Q, D, L, K in t:
        r = tramo_calc(Q, D, L, K); r["nombre"] = nombre; out.append(r)
    return out


def z_regadera(d: Datos, piso: int) -> float:
    return (piso - 1) * d.altura_piso + d.altura_regadera


def residual_piso(d: Datos, nivel: float, piso: int, f=(1, 1, 1, 1)) -> dict:
    """Ecuaciones (10) y (12): P2/(rho·g) = (z1 - z2) - v2²/2g - hL   (todo en m c.a.)"""
    tramos = construir_tramos(d, piso, f)
    hL = sum(t["hL"] for t in tramos)
    cv = tramos[-1]["hv"]
    h = nivel - z_regadera(d, piso)
    return dict(piso=piso, h_est=h, P_est=presion_hidrostatica(h), hL=hL, cv=cv, P=h - cv - hL, tramos=tramos)


def resolver(d: Datos, nivel: float, modo: str = "informe") -> list[dict]:
    """Presión, caudal y estado de abastecimiento de las regaderas de los cuatro pisos.
    modo 'informe'   : caudales de diseño fijos en las tuberías (reproduce las tablas del informe).
    modo 'equilibrio': el caudal de cada piso se ajusta a la presión disponible hasta que el sistema se equilibra.
    El caudal de la regadera se modela como Q = Q_diseño·sqrt(P/P_min) cuando P < P_min (ley de orificio)."""
    f = [1.0] * 4
    if modo == "equilibrio":
        for _ in range(300):
            P = [residual_piso(d, nivel, k, f)["P"] for k in range(1, 5)]
            nuevo = [min(1.0, math.sqrt(max(p, 0.0) / d.p_min)) for p in P]
            f2 = [0.5 * a + 0.5 * b for a, b in zip(f, nuevo)]
            conv = max(abs(a - b) for a, b in zip(f, f2)) < 1e-7
            f = f2
            if conv: break
    res = []
    for k in range(1, 5):
        r = residual_piso(d, nivel, k, f)
        fs = f[k - 1] if modo == "equilibrio" else min(1.0, math.sqrt(max(r["P"], 0.0) / d.p_min))
        r["f_abast"] = fs
        r["Q_regadera"] = q_hunter(1) * d.demanda * fs
        r["P_jet"] = max(r["P"], 0.0)
        r["estado"] = "Suficiente" if r["P"] >= d.p_min else ("Sin flujo" if fs < 0.01 else "Insuficiente")
        r["v_ramal"] = r["tramos"][-1]["v"]
        res.append(r)
    return res


def altura_minima(d: Datos) -> dict:
    """Se despeja de la ecuación (12) el nivel con el que el piso 4 recibe p_min (paso 7 del informe)."""
    P0 = residual_piso(d, 0.0, 4)["P"]
    z_req = d.p_min - P0
    z_max = z_req + d.desc_arranque
    base = z_max - d.prof_agua_max
    return dict(z_arranque=z_req, z_max=z_max, base=base, sobre_techo=base - d.techo)


def bomba_estatica(d: Datos, Q_Ls: float, dz: float) -> dict:
    """Ecuaciones (13) y (14): altura de bombeo y potencia hidráulica."""
    imp = tramo_calc(Q_Ls, DIAM["1"], d.L_impulsion, d.K_retencion + d.K_bola + 4 * d.K_codo90)
    suc = tramo_calc(Q_Ls, DIAM["1 1/4"], d.L_succion, d.K_succion)
    HB = dz + imp["hL"] + suc["hL"]
    return dict(HB=HB, Ph=RHO * G * (Q_Ls / 1000) * HB, h_imp=imp["hL"], h_suc=suc["hL"], v_imp=imp["v"], Q=Q_Ls)


def curva_H(d: Datos, Q_Lmin: float) -> float:
    xs, ys = zip(*sorted(d.curva))
    return float(np.interp(Q_Lmin, xs, ys))


def punto_operacion(d: Datos, dz: float) -> dict:
    """Intersección entre la curva de la bomba y la curva del sistema (Δz + pérdidas de impulsión y succión)."""
    xs = np.array(sorted(p[0] for p in d.curva), dtype=float)
    qmax = float(xs[-1])
    qs = np.linspace(1.0, qmax, 600)
    dif = np.array([curva_H(d, q) - bomba_estatica(d, q / 60, dz)["HB"] for q in qs])
    idx = np.where(dif <= 0)[0]
    if len(idx) == 0:
        return dict(Q_Lmin=qmax, H=curva_H(d, qmax), fuera_de_rango=True)
    i = idx[0]
    if i == 0: return dict(Q_Lmin=float(qs[0]), H=curva_H(d, qs[0]), fuera_de_rango=False)
    q = qs[i - 1] - dif[i - 1] * (qs[i] - qs[i - 1]) / (dif[i] - dif[i - 1])
    return dict(Q_Lmin=float(q), H=curva_H(d, q), fuera_de_rango=False)


def balance_tanque(d: Datos, nivel0: float, bomba_on: bool, q_bomba_Ls: float, t_max_min: float = 30.0, dt: float = 2.0) -> dict:
    """Balance de masa del tanque: A·dh/dt = Q_entrada - Q_demanda. La bomba arranca en el nivel de arranque
    y se detiene en el nivel máximo (control de la IS.010). Sin bomba, el tanque solo se vacía."""
    A = math.pi * d.d_tanque ** 2 / 4
    dem = d.demanda * q_hunter(4)                  # L/s
    nivel = min(max(nivel0, d.base_tanque), d.nivel_max)
    encendida = bomba_on and nivel <= d.nivel_arranque
    t_l, n_l, b_l = [0.0], [nivel], [encendida]
    for k in range(int(t_max_min * 60 / dt)):
        qin = q_bomba_Ls if (bomba_on and encendida) else 0.0
        qout = dem if nivel > d.base_tanque + 1e-9 else min(dem, qin)
        nivel = min(max(nivel + (qin - qout) / 1000 / A * dt, d.base_tanque), d.nivel_max)
        if bomba_on:
            if nivel >= d.nivel_max - 1e-9: encendida = False
            elif nivel <= d.nivel_arranque: encendida = True
        t_l.append((k + 1) * dt / 60); n_l.append(nivel); b_l.append(encendida)
    return dict(t=np.array(t_l), nivel=np.array(n_l), bomba=np.array(b_l), demanda_Ls=dem)


def perdidas_un_punto(d: Datos, piso: int, Q_Ls: float) -> tuple[float, float]:
    """Pérdidas hasta una regadera con UN solo punto abierto (el mismo caudal en todo el recorrido)."""
    h = 0.0
    for t in construir_tramos(d, piso):
        h += tramo_calc(Q_Ls, t["D"], t["L"], t["K"])["hL"]
    r = tramo_calc(Q_Ls, DIAM[d.d_ramal], d.L_ramal, 0.0)
    return h, r["hv"]


def calibrar_regadera(d: Datos, nivel: float | None = None) -> dict:
    """Paso 9: con el caudal del piso 1 se despeja K_r de la ecuación (10); luego se calcula el caudal del piso 4."""
    nivel = d.nivel_arranque if nivel is None else nivel
    hL1, hv1 = perdidas_un_punto(d, 1, d.q_ref_piso1)
    Kr = ((nivel - z_regadera(d, 1)) - hL1 - hv1) / hv1
    dz4 = nivel - z_regadera(d, 4)
    lo, hi = 0.001, 2.0
    for _ in range(80):
        Q = (lo + hi) / 2
        hL, hv = perdidas_un_punto(d, 4, Q)
        lo, hi = (Q, hi) if dz4 - (hL + hv + Kr * hv) > 0 else (lo, Q)
    return dict(Kr=Kr, Q4=Q, error=error_relativo(Q, d.q_ref_piso4))


def error_relativo(x_sim: float, x_ref: float) -> float:
    """Ecuación (15): e (%) = |X_sim - X_ref| / X_ref · 100"""
    return abs(x_sim - x_ref) / abs(x_ref) * 100 if x_ref != 0 else float("nan")


# ------------------------------------------------------------------------------------ evaluación completa
def evaluar(d: Datos, nivel: float, piso: int, modo: str, bomba_on: bool, fuente_q: str = "curva") -> dict:
    """Calcula todo lo que necesitan la interfaz, los escenarios y el reporte."""
    errores = d.validar()
    if errores: raise ValueError(" ".join(errores))
    res = resolver(d, nivel, modo)
    dz = d.dz_bombeo
    op = punto_operacion(d, dz)
    if fuente_q == "referencia":
        q_bomba = d.q_llenado_ref; aviso_q = "caudal de llenado de referencia del informe"
    else:
        q_bomba = op["Q_Lmin"] / 60
        aviso_q = "curva de la bomba (provisional)" + (" - punto de operación fuera del rango de la curva" if op["fuera_de_rango"] else "")
    bomba = bomba_estatica(d, q_bomba, dz); bomba["fuente"] = aviso_q; bomba["op"] = op
    bal = balance_tanque(d, nivel, bomba_on, q_bomba)
    return dict(datos=d, nivel=nivel, piso=piso, modo=modo, bomba_on=bomba_on, res=res, sel=res[piso - 1],
                minima=altura_minima(d), bomba=bomba, balance=bal, calibracion=calibrar_regadera(d),
                demanda_Ls=d.demanda * q_hunter(4))


def explicar(r: dict) -> str:
    """Explicación automática (3 a 5 líneas) con los valores reales de la simulación."""
    d, s, p = r["datos"], r["sel"], r["piso"]
    estado_txt = {"Suficiente": "suficiente, porque la presión residual supera el mínimo de la norma",
                  "Insuficiente": "insuficiente, porque la presión residual queda por debajo del mínimo de la norma y el caudal se reduce",
                  "Sin flujo": "nulo: la presión disponible no alcanza para que salga agua"}[s["estado"]]
    l1 = (f"Con el nivel del agua en {r['nivel']:.2f} m y una demanda de {r['demanda_Ls']:.2f} L/s, la presión estática en la regadera del piso {p} "
          f"es de {s['h_est']:.2f} m c.a. ({s['P_est']/1000:.1f} kPa), porque el agua está {s['h_est']:.2f} m por encima de ella.")
    l2 = (f"Al circular por las tuberías, el agua pierde {s['hL']:.2f} m de carga por fricción y accesorios, y la presión residual queda en {s['P']:.2f} m c.a. "
          f"(mínimo de la norma: {d.p_min:.1f} m c.a.).")
    l3 = (f"El caudal que llega a la regadera es de {s['Q_regadera']:.3f} L/s y la velocidad en su ramal es de {s['v_ramal']:.2f} m/s; "
          f"el abastecimiento es {estado_txt}.")
    if r["bomba_on"]:
        b = r["bomba"]
        l4 = (f"La bomba está activada: para llenar el tanque debe entregar {b['HB']:.2f} m de altura con {b['Q']*1000:.0f} mL/s ({b['Q']*60:.0f} L/min), "
              f"es decir, {b['Ph']:.0f} W de potencia hidráulica; mientras funciona, el nivel del tanque se mantiene.")
    else:
        bal = r["balance"]; i = np.where(bal["nivel"] <= d.nivel_min + 1e-9)[0]
        cuando = f"llega al nivel mínimo ({d.nivel_min:.2f} m) a los {bal['t'][i[0]]:.1f} min" if len(i) else f"baja de {bal['nivel'][0]:.2f} a {bal['nivel'][-1]:.2f} m en {bal['t'][-1]:.0f} min"
        l4 = f"La bomba está desactivada: el tanque no se recarga, su nivel baja con la demanda y {cuando}, con lo que la presión disminuye."
    return " ".join([l1, l2, l3, l4])


def copiar(d: Datos, **cambios) -> Datos:
    return replace(d, **cambios)
