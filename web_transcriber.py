import streamlit as st
import vosk
import json
import wave
import os
import tempfile
from datetime import datetime
import ffmpeg
from docx import Document
import shutil
import urllib.request
import zipfile

# Configura la pagina Streamlit
st.set_page_config(
    page_title="Video Transcriber",
    page_icon="🎥",
    layout="wide"
)

@st.cache_resource
def download_model():
    """Scarica e prepara il modello Vosk"""
    model_path = "models/model-it"
    if not os.path.exists(model_path):
        os.makedirs("models", exist_ok=True)
        # URL del modello italiano
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip"
        zip_path = "model.zip"
        
        # Scarica il modello
        urllib.request.urlretrieve(model_url, zip_path)
        
        # Estrai il modello
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("models")
        
        # Rinomina la cartella
        os.rename("models/vosk-model-small-it-0.22", model_path)
        
        # Pulizia
        os.remove(zip_path)
    
    return model_path

def ensure_dirs():
    """Assicura che le directory necessarie esistano"""
    dirs = ['temp', 'output']
    for dir in dirs:
        if not os.path.exists(dir):
            os.makedirs(dir, exist_ok=True)

def extract_audio(video_path, output_path):
    """Estrae l'audio dal video usando ffmpeg"""
    try:
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, output_path, 
                             acodec='pcm_s16le', 
                             ac=1, 
                             ar='16k',
                             loglevel='quiet')
        ffmpeg.run(stream, overwrite_output=True)
        return True
    except ffmpeg.Error as e:
        st.error(f"Errore nell'estrazione dell'audio: {str(e)}")
        return False

def create_transcriber_app():
    ensure_dirs()
    
    st.title("🎥 Video Speech-to-Text")
    st.write("Converti facilmente l'audio dei tuoi video in testo")

    with st.sidebar:
        st.header("Informazioni")
        st.write("""
        ### Come usare:
        1. Seleziona il file video
        2. Attendi il caricamento
        3. Clicca su 'Inizia Trascrizione'
        4. Scarica il documento Word
        
        ### Formati supportati:
        - MP4
        - AVI
        - MKV
        
        ### Note:
        - Supporta video lunghi
        - Non chiudere la finestra durante la trascrizione
        - La trascrizione potrebbe richiedere alcuni minuti
        """)

    uploaded_file = st.file_uploader("Seleziona un video", type=['mp4', 'avi', 'mkv'])
    
    if uploaded_file is not None:
        file_details = {
            "Nome File": uploaded_file.name,
            "Tipo File": uploaded_file.type,
            "Dimensione": f"{uploaded_file.size / (1024*1024):.2f} MB"
        }
        st.write("### Dettagli del file:")
        for key, value in file_details.items():
            st.write(f"**{key}:** {value}")

        if st.button("🎯 Inizia Trascrizione", use_container_width=True):
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Crea cartella temporanea
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Salva il file video
                    temp_video = os.path.join(temp_dir, "input_video.mp4")
                    with open(temp_video, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                    
                    status_text.text("⏳ Estraendo l'audio dal video...")
                    
                    # Estrai audio
                    temp_audio = os.path.join(temp_dir, "audio.wav")
                    if not extract_audio(temp_video, temp_audio):
                        st.error("Errore nell'estrazione dell'audio")
                        return
                    
                    # Prepara documento
                    doc = Document()
                    doc.add_heading('Trascrizione Video', 0)
                    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
                    doc.add_paragraph(f'File originale: {uploaded_file.name}')
                    doc.add_paragraph('')
                    
                    # Carica modello Vosk
                    model_path = download_model()
                    model = vosk.Model(model_path)
                    rec = vosk.KaldiRecognizer(model, 16000)
                    
                    # Trascrivi audio
                    status_text.text("🎯 Trascrizione in corso...")
                    
                    with wave.open(temp_audio, "rb") as wf:
                        total_frames = wf.getnframes()
                        frames_processed = 0
                        
                        while True:
                            data = wf.readframes(4000)
                            if len(data) == 0:
                                break
                            
                            if rec.AcceptWaveform(data):
                                result = json.loads(rec.Result())
                                if result["text"]:
                                    doc.add_paragraph(result["text"])
                            
                            # Aggiorna progresso
                            frames_processed += 4000
                            progress = min(frames_processed / total_frames, 1.0)
                            progress_bar.progress(progress)
                    
                    # Aggiungi risultato finale
                    final_result = json.loads(rec.FinalResult())
                    if final_result["text"]:
                        doc.add_paragraph(final_result["text"])
                    
                    # Salva documento
                    output_file = os.path.join("output", f'trascrizione_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx')
                    doc.save(output_file)
                    
                    # Offri download
                    with open(output_file, 'rb') as f:
                        st.download_button(
                            label="📥 Scarica Trascrizione",
                            data=f,
                            file_name=os.path.basename(output_file),
                            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        )
                    
                    status_text.text("✅ Trascrizione completata!")
                    
                    # Pulisci il file di output dopo il download
                    if os.path.exists(output_file):
                        os.remove(output_file)
                
            except Exception as e:
                st.error(f"❌ Errore durante l'elaborazione: {str(e)}")

if __name__ == "__main__":
    create_transcriber_app()