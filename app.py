import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta

# Configuración de la página
st.set_page_config(page_title="Crypto 1H Pattern Detector", page_icon="📈", layout="wide")

st.title("📊 Detector de Patrones de Velas (1H) para Criptomonedas")
st.markdown("Herramienta interactiva conectada a datos en tiempo real de Binance para identificar patrones de giro con filtros de tendencia y volumen.")

# Barra lateral para controles de usuario
st.sidebar.header("⚙️ Configuración")
simbolo = st.sidebar.selectbox(
    "Selecciona el Par", 
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"], 
    index=0
)
limite_velas = st.sidebar.slider("Número de velas de 1H a analizar", min_value=100, max_value=500, value=200, step=50)

# Función con caché para evitar saturar la API del exchange
@st.cache_data(ttl=300) # Actualiza los datos cada 5 minutos
def cargar_datos_y_analizar(symbol, limit):
    exchange = ccxt.binance({'enableRateLimit': True})
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # 1. Indicadores técnicos
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)
    df['vol_sma'] = ta.sma(df['volume'], length=20)
    
    # 2. Patrones de velas
    df['patron_martillo'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="hammer")
    df['patron_engulfing'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="engulfing")
    df['patron_star'] = ta.cdl_pattern(df['open'], df['high'], df['low'], df['close'], name="morningstar")
    
    # 3. Lógica de señales
    df['senal'] = 'NEUTRAL'
    for i in range(1, len(df)):
        precio = df.loc[i, 'close']
        ema = df.loc[i, 'ema_50']
        vol = df.loc[i, 'volume']
        v_sma = df.loc[i, 'vol_sma']
        
        tiene_volumen = vol > (v_sma * 1.2) if pd.notna(v_sma) else False
        alcista_tendencia = precio > ema if pd.notna(ema) else False
        bajista_tendencia = precio < ema if pd.notna(ema) else False
        
        if (df.loc[i, 'patron_martillo'] > 0 or df.loc[i, 'patron_engulfing'] > 0 or df.loc[i, 'patron_star'] > 0):
            if alcista_tendencia and tiene_volumen:
                df.loc[i, 'senal'] = 'COMPRA (LONG)'
        elif (df.loc[i, 'patron_martillo'] < 0 or df.loc[i, 'patron_engulfing'] < 0 or df.loc[i, 'patron_star'] < 0):
            if bajista_tendencia and tiene_volumen:
                df.loc[i, 'senal'] = 'VENTA (SHORT)'
                
    return df

try:
    with st.spinner(f"Analizando datos de {simbolo} en marco temporal de 1H..."):
        df = cargar_datos_y_analizar(simbolo, limite_velas)
        
    # Métricas superiores
    ultimo_precio = df.iloc[-1]['close']
    precio_anterior = df.iloc[-2]['close']
    cambio_pct = ((ultimo_precio - precio_anterior) / precio_anterior) * 100
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio Actual (1H)", f"${ultimo_precio:,.2f}", f"{cambio_pct:.2f}%")
    col2.metric("Tendencia (EMA 50)", "Alcista 🟢" if ultimo_precio > df.iloc[-1]['ema_50'] else "Bajista 🔴")
    
    senales_activas = df[df['senal'] != 'NEUTRAL']
    col3.metric("Señales Detectadas", len(senales_activas))
    
    # Gráfico interactivo nativo
    st.subheader(f"📈 Evolución del Precio y EMA 50 ({simbolo})")
    chart_data = df.set_index('timestamp')[['close', 'ema_50']]
    st.line_chart(chart_data)
    
    # Tabla de señales recientes
    st.subheader("🔍 Historial de Señales Filtradas (Patrón + Volumen + Tendencia)")
    if not senales_activas.empty:
        st.dataframe(
            senales_activas[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'senal']].tail(10), 
            use_container_width=True
        )
    else:
        st.info("No se encontraron señales recientes que cumplan estrictamente con todos los filtros de volumen y tendencia en este rango.")

except Exception as e:
    st.error(f"Ocurrió un error al obtener los datos: {e}")
