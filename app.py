import streamlit as st
import ccxt
import pandas as pd
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Crypto 1H Pattern Detector", page_icon="📈", layout="wide")

st.title("📊 Detector de Patrones de Velas (1H) para Criptomonedas")
st.markdown("Herramienta interactiva conectada a datos en tiempo real de Binance para identificar patrones de giro con filtros de tendencia y volumen.")

# Barra lateral
st.sidebar.header("⚙️ Configuración")
simbolo = st.sidebar.selectbox(
    "Selecciona el Par", 
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"], 
    index=0
)
limite_velas = st.sidebar.slider("Número de velas de 1H a analizar", min_value=100, max_value=500, value=200, step=50)

# Funciones nativas para detectar patrones de velas japonesas
def detectar_patrones(df):
    o = df['open']
    h = df['high']
    l = df['low']
    c = df['close']
    
    cuerpo = (c - o).abs()
    rango_total = h - l
    mecha_superior = h - np.maximum(o, c)
    mecha_inferior = np.minimum(o, c) - l
    
    # 1. Martillo (Hammer) / Estrella Fugaz (Shooting Star)
    # Cuerpo pequeño en un extremo y mecha al menos 2 veces el tamaño del cuerpo
    martillo_alcista = (mecha_inferior >= 2 * cuerpo) & (mecha_superior <= cuerpo * 0.5) & (cuerpo > 0)
    martillo_bajista = (mecha_superior >= 2 * cuerpo) & (mecha_inferior <= cuerpo * 0.5) & (cuerpo > 0)
    
    # 2. Envolvente (Engulfing)
    # Vela anterior contraria y cuerpo actual envuelve completamente al anterior
    prev_o = o.shift(1)
    prev_c = c.shift(1)
    
    engulfing_alcista = (prev_c < prev_o) & (c > o) & (o <= prev_c) & (c >= prev_o)
    engulfing_bajista = (prev_c > prev_o) & (c < o) & (o >= prev_c) & (c <= prev_o)
    
    # 3. Estrella de la Mañana / Tarde (Morning / Evening Star - simplificado de 3 velas)
    o2, c2 = o.shift(2), c.shift(2)
    cuerpo1 = (prev_c - prev_o).abs()
    cuerpo2 = (c2 - o2).abs()
    
    morning_star = (c2 < o2) & (cuerpo1 < cuerpo2 * 0.5) & (c > o) & (c > (o2 + c2) / 2)
    evening_star = (c2 > o2) & (cuerpo1 < cuerpo2 * 0.5) & (c < o) & (c < (o2 + c2) / 2)
    
    df['patron_alcista'] = martillo_alcista | engulfing_alcista | morning_star
    df['patron_bajista'] = martillo_bajista | engulfing_bajista | evening_star
    
    # Guardar el nombre del patrón detectado
    condiciones = [
        engulfing_alcista, morning_star, martillo_alcista,
        engulfing_bajista, evening_star, martillo_bajista
    ]
    nombres = [
        'Envolvente Alcista', 'Estrella de la Mañana', 'Martillo Alcista',
        'Envolvente Bajista', 'Estrella de la Tarde', 'Estrella Fugaz / Colgado'
    ]
    df['nombre_patron'] = np.select(condiciones, nombres, default='Ninguno')
    return df

@st.cache_data(ttl=300)
def cargar_datos_y_analizar(symbol, limit):
    # Nota: Si Binance bloquea la IP del servidor de Streamlit (EE.UU.), puedes cambiar ccxt.binance() por ccxt.kraken() o ccxt.bybit()
    exchange = ccxt.binance({'enableRateLimit': True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Indicadores técnicos nativos en Pandas
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['vol_sma'] = df['volume'].rolling(window=20).mean()
    
    # Detectar patrones
    df = detectar_patrones(df)
    
    # Lógica de señales
    df['senal'] = 'NEUTRAL'
    for i in range(2, len(df)):
        precio = df.loc[i, 'close']
        ema = df.loc[i, 'ema_50']
        vol = df.loc[i, 'volume']
        v_sma = df.loc[i, 'vol_sma']
        
        tiene_volumen = vol > (v_sma * 1.2) if pd.notna(v_sma) else False
        alcista_tendencia = precio > ema if pd.notna(ema) else False
        bajista_tendencia = precio < ema if pd.notna(ema) else False
        
        if df.loc[i, 'patron_alcista'] and alcista_tendencia and tiene_volumen:
            df.loc[i, 'senal'] = 'COMPRA (LONG)'
        elif df.loc[i, 'patron_bajista'] and bajista_tendencia and tiene_volumen:
            df.loc[i, 'senal'] = 'VENTA (SHORT)'
            
    return df

try:
    with st.spinner(f"Analizando datos de {simbolo} en marco temporal de 1H..."):
        df = cargar_datos_y_analizar(simbolo, limite_velas)
        
    ultimo_precio = df.iloc[-1]['close']
    precio_anterior = df.iloc[-2]['close']
    cambio_pct = ((ultimo_precio - precio_anterior) / precio_anterior) * 100
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio Actual (1H)", f"${ultimo_precio:,.2f}", f"{cambio_pct:.2f}%")
    col2.metric("Tendencia (EMA 50)", "Alcista 🟢" if ultimo_precio > df.iloc[-1]['ema_50'] else "Bajista 🔴")
    
    senales_activas = df[df['senal'] != 'NEUTRAL']
    col3.metric("Señales Detectadas", len(senales_activas))
    
    st.subheader(f"📈 Evolución del Precio y EMA 50 ({simbolo})")
    chart_data = df.set_index('timestamp')[['close', 'ema_50']]
    st.line_chart(chart_data)
    
    st.subheader("🔍 Historial de Señales Filtradas (Patrón + Volumen + Tendencia)")
    if not senales_activas.empty:
        st.dataframe(
            senales_activas[['timestamp', 'nombre_patron', 'close', 'volume', 'senal']].tail(10), 
            use_container_width=True
        )
    else:
        st.info("No se encontraron señales recientes que cumplan estrictamente con todos los filtros de volumen y tendencia en este rango.")

except Exception as e:
    st.error(f"Ocurrió un error al obtener los datos: {e}")
    st.info("💡 Consejo: Si el error menciona restricción geográfica de Binance (Error 451), cambia 'ccxt.binance()' por 'ccxt.kraken()' o 'ccxt.okx()' en el código.")
