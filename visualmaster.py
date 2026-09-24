import streamlit as st
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import base64
import streamlit.components.v1 as components

from pedalboard import (
    Pedalboard,
    Compressor,
    Gain,
    HighShelfFilter,
    LowShelfFilter,
    Limiter,
    Reverb,
    Delay
)

# Configuración de la página web
st.set_page_config(page_title="Masterizador Pro 2026", layout="wide")

st.title("🎛️ Masterizador Pro con Waveform Dinámico en Tiempo Real")
st.write("Sube tu tema, ajusta los faders de efectos y observa cómo la forma de onda y el audio cambian al instante.")

# --------------------------------------------------
# ÁREA PRINCIPAL: CARGA DE ARCHIVO
# --------------------------------------------------
archivo_subido = st.file_uploader("📂 Arrastra o selecciona tu archivo (MP3 o WAV)", type=["mp3", "wav"])

if archivo_subido is not None:
    # Cargar audio desde Streamlit
    audio_datos, samplerate = sf.read(archivo_subido)
    
    if audio_datos.ndim == 1:
        audio_original = np.column_stack((audio_datos, audio_datos))  # Convertir mono a estéreo seguro
    else:
        audio_original = audio_datos

    duracion = len(audio_original) / samplerate

    # Mostrar información general del archivo
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Sample Rate:** {samplerate} Hz")
    with col2:
        st.info(f"**Duración:** {duracion:.2f} segundos")

    # --------------------------------------------------
    # BARRA LATERAL: CONTROLES Y EFECTOS EN VIVO
    # --------------------------------------------------
    st.sidebar.header("⚙️ Controles en Tiempo Real")

    perfil = st.sidebar.selectbox(
        "Elige un Perfil Base",
        ["Acústico / Balada", "Rock / Pop Cañero", "Moderno / Comercial"]
    )

    if perfil == "Acústico / Balada":
        def_graves, def_brillo, def_comp, def_gan, def_lim = -1.0, 0.8, 1.3, 1.2, -1.2
    elif perfil == "Rock / Pop Cañero":
        def_graves, def_brillo, def_comp, def_gan, def_lim = -1.5, 1.5, 2.0, 1.8, -1.0
    else:
        def_graves, def_brillo, def_comp, def_gan, def_lim = -0.8, 2.0, 2.5, 2.2, -0.8

    st.sidebar.subheader("Ecualización y Dinámica")
    graves = st.sidebar.slider("Graves (dB)", -6.0, 6.0, def_graves, 0.1)
    brillo = st.sidebar.slider("Brillo (dB)", -6.0, 6.0, def_brillo, 0.1)
    compresion = st.sidebar.slider("Ratio de Compresión", 1.0, 4.0, def_comp, 0.1)
    ganancia = st.sidebar.slider("Ganancia de Entrada (dB)", 0.0, 6.0, def_gan, 0.1)
    limitador = st.sidebar.slider("Techo del Limitador (dB)", -3.0, 0.0, def_lim, 0.1)

    st.sidebar.subheader("Efectos Creativos (Faders)")
    cantidad_delay = st.sidebar.slider("Cantidad de Delay", 0.0, 1.0, 0.0, 0.05)
    cantidad_reverb = st.sidebar.slider("Cantidad de Reverb", 0.0, 1.0, 0.0, 0.05)
    cantidad_echo = st.sidebar.slider("Cantidad de Echo", 0.0, 1.0, 0.0, 0.05)

    fade = st.sidebar.checkbox("Aplicar Fades (In/Out)", value=True)

    # --------------------------------------------------
    # PROCESAMIENTO EN TIEMPO REAL (STREAMING)
    # --------------------------------------------------
    audio_procesado_fades = audio_original.copy()
    
    # Fades opcionales
    if fade and len(audio_procesado_fades) > int(samplerate * 0.1):
        muestras_fade = int(samplerate * 0.1)
        curva_in = np.linspace(0.0, 1.0, muestras_fade)
        for c in range(audio_procesado_fades.shape[1]):
            audio_procesado_fades[:muestras_fade, c] *= curva_in

    # Construir Cadena de Efectos
    lista_efectos = [
        LowShelfFilter(cutoff_frequency_hz=80, gain_db=graves),
        HighShelfFilter(cutoff_frequency_hz=10000, gain_db=brillo),
    ]

    if cantidad_delay > 0.0:
        lista_efectos.append(Delay(delay_seconds=0.25, feedback=0.3, mix=cantidad_delay))
    
    if cantidad_reverb > 0.0:
        lista_efectos.append(Reverb(room_size=0.25, damping=0.5, wet_level=cantidad_reverb, dry_level=1.0))

    if cantidad_echo > 0.0:
        lista_efectos.append(Delay(delay_seconds=0.5, feedback=0.5, mix=cantidad_echo))

    lista_efectos.extend([
        Compressor(threshold_db=-18, ratio=compresion, attack_ms=20, release_ms=120),
        Gain(gain_db=ganancia),
        Limiter(threshold_db=limitador, release_ms=100)
    ])

    board = Pedalboard(lista_efectos)
    
    # Pedalboard requiere formato (canales, muestras)
    audio_pedalboard_input = audio_procesado_fades.T 
    mastered_pedalboard = board(audio_pedalboard_input, samplerate)
    
    # Regresar a formato estándar (muestras, canales)
    mastered_audio = mastered_pedalboard.T

    # Medición de sonoridad (LUFS)
    meter = pyln.Meter(samplerate)
    lufs_antes = meter.integrated_loudness(audio_original)
    lufs_despues = meter.integrated_loudness(mastered_audio)

    # Guardar archivo temporal actualizado con los nuevos parámetros
    audio_para_guardar = np.ascontiguousarray(mastered_audio)
    nombre_archivo_temp = "temp_master.wav"
    sf.write(nombre_archivo_temp, audio_para_guardar, samplerate, subtype="PCM_24")

    # Métricas visuales
    m1, m2 = st.columns(2)
    m1.metric("LUFS Original", f"{lufs_antes:.2f} LUFS")
    m2.metric("LUFS Masterizado", f"{lufs_despues:.2f} LUFS", delta=f"{lufs_despues - lufs_antes:+.2f} dB")

    st.subheader("🎚️ Reproductor y Waveform Dinámico en Vivo")
    st.write("Cada vez que modifiques un parámetro, la onda se actualizará automáticamente reflejando los cambios de volumen, compresión y ecualización.")

    # Convertir el archivo WAV actualizado a Base64
    with open(nombre_archivo_temp, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()

    # Plantilla HTML con Wavesurfer.js forzando la recarga al cambiar el Base64
    waveform_html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/wavesurfer.js@7"></script>
        <style>
            body {
                background-color: #0e1117;
                color: #ffffff;
                font-family: sans-serif;
                margin: 0;
                padding: 10px;
            }
            #waveform {
                width: 100%;
                background: #0e1117;
                border-radius: 8px;
            }
            .player-container {
                background: #161b22;
                padding: 15px;
                border-radius: 10px;
                border: 1px solid #30363d;
            }
            .controls {
                margin-top: 12px;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            button {
                background: #00ffcc;
                border: none;
                color: #0e1117;
                padding: 8px 18px;
                font-weight: bold;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            }
            button:hover {
                background: #00b38f;
            }
            #time-display {
                font-size: 13px;
                color: #8b949e;
                font-family: monospace;
            }
        </style>
    </head>
    <body>
        <div class="player-container">
            <div id="waveform"></div>
            <div class="controls">
                <button id="playBtn">▶ Play</button>
                <span id="time-display">0:00 / 0:00</span>
            </div>
        </div>

        <script>
            const wavesurfer = WaveSurfer.create({
                container: '#waveform',
                waveColor: '#00ffcc',
                progressColor: '#007acc',
                cursorColor: '#ffffff',
                cursorWidth: 2,
                barWidth: 2,
                barRadius: 2,
                height: 110,
                normalize: true,
            });

            // Cargar el nuevo audio procesado
            wavesurfer.load('data:audio/wav;base64,AUDIO_BASE64_PLACEHOLDER');

            const playBtn = document.getElementById('playBtn');
            const timeDisplay = document.getElementById('time-display');

            playBtn.addEventListener('click', () => {
                wavesurfer.playPause();
            });

            wavesurfer.on('play', () => {
                playBtn.textContent = '⏸ Pausar';
            });

            wavesurfer.on('pause', () => {
                playBtn.textContent = '▶ Play';
            });

            wavesurfer.on('audioprocess', () => {
                updateTime();
            });

            wavesurfer.on('interaction', () => {
                updateTime();
            });

            wavesurfer.on('ready', () => {
                updateTime();
            });

            function updateTime() {
                const current = formatTime(wavesurfer.getCurrentTime());
                const total = formatTime(wavesurfer.getDuration());
                timeDisplay.textContent = current + ' / ' + total;
            }

            function formatTime(seconds) {
                const minutes = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return minutes + ':' + (secs < 10 ? '0' : '') + secs;
            }
        </script>
    </body>
    </html>
    """

    waveform_html = waveform_html_template.replace("AUDIO_BASE64_PLACEHOLDER", audio_base64)

    # Renderizar el componente web en Streamlit (al cambiar audio_base64, Streamlit recrea el componente automáticamente con la nueva forma de onda)
    components.html(waveform_html, height=210)

    # Botón de descarga final del archivo procesado
    with open(nombre_archivo_temp, "rb") as file:
        st.download_button(
            label="📥 Descargar WAV Masterizado Definitivo",
            data=file,
            file_name="audio_MASTER_definitivo.wav",
            mime="audio/wav"
        )
