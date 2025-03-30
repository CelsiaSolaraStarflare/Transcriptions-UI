import streamlit as st
import whisper
from docx import Document
import os
import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent  # Imported for silence detection

CACHE_DIR = "transcription_cache"

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Load the Whisper model (no device argument, so it will auto-detect)
model = whisper.load_model("base")  # Use the default device (CPU or GPU)

def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02}:{secs:02}"

def split_audio(audio_path, num_chunks=10):
    """Split the audio file into `num_chunks` parts."""
    audio = AudioSegment.from_file(audio_path)
    chunk_length = len(audio) // num_chunks  # Duration of each chunk in milliseconds
    
    chunks = []
    for i in range(num_chunks):
        start_time = i * chunk_length
        end_time = (i + 1) * chunk_length if i != num_chunks - 1 else len(audio)
        chunk = audio[start_time:end_time]
        chunk_path = audio_path.replace(".mp3", f"_{i+1}.mp3").replace(".wav", f"_{i+1}.wav")
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)
    
    return chunks

def split_audio_on_silence(audio_path, min_silence_len=500, silence_thresh=-40, padding=200):
    """
    Split the audio file into chunks based on silence detection.
    This function detects non-silent parts of the audio and uses them as split boundaries,
    adding optional padding to each segment. The resulting chunks are exported as separate audio files.

    Parameters:
      audio_path (str): Path to the audio file.
      min_silence_len (int, optional): Minimum length (in ms) that a silence must have to be considered a split point (default: 500 ms).
      silence_thresh (int, optional): Silence threshold in dBFS; audio below this is considered silent (default: -40 dBFS).
      padding (int, optional): Extra milliseconds to add before and after each non-silent segment (default: 200 ms).

    Returns:
      chunks (list): List of file paths for each exported audio segment.
    """
    audio = AudioSegment.from_file(audio_path)
    nonsilent_ranges = detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    chunks = []
    
    for idx, (start_ms, end_ms) in enumerate(nonsilent_ranges):
        # Add padding to avoid clipping the start or end of speech
        padded_start = max(0, start_ms - padding)
        padded_end = min(len(audio), end_ms + padding)
        chunk = audio[padded_start:padded_end]
        chunk_path = audio_path.replace(".mp3", f"_chunk{idx+1}.mp3").replace(".wav", f"_chunk{idx+1}.wav")
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)
    
    return chunks

def transcribe(audio_path, cache_subdir):
    audio = whisper.load_audio(audio_path)
    result = model.transcribe(audio)
    segments = result["segments"]

    doc = Document()
    doc.add_heading("语音转录结果", level=1)
    transcript = []

    for segment in segments:
        start = segment['start']
        end = segment['end']
        text = segment['text'].strip()
        timestamp = f"[{format_time(start)} - {format_time(end)}]"
        line = f"{timestamp} {text}"
        doc.add_paragraph(line)
        transcript.append(line)
    
    output_path = os.path.join(cache_subdir, "transcript.docx")
    doc.save(output_path)
    return output_path, "\n".join(transcript)

# Main interface
st.title("语音转录系统")
st.write("上传音频文件生成带时间戳的Word文档")

# File upload
uploaded_file = st.file_uploader("选择音频文件", type=["mp3", "wav"])

if uploaded_file:
    task_id = str(len(os.listdir(CACHE_DIR)) + 1)
    cache_subdir = os.path.join(CACHE_DIR, task_id)
    os.makedirs(cache_subdir, exist_ok=True)

    # Save the uploaded audio file
    audio_path = os.path.join(cache_subdir, uploaded_file.name)
    with open(audio_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    # Use silence-based chunking to split the audio
    chunks = split_audio_on_silence(audio_path, min_silence_len=500, silence_thresh=-40, padding=200)
    
    all_transcripts = []
    for chunk in chunks:
        doc_path, preview = transcribe(chunk, cache_subdir)
        all_transcripts.append(preview)
    
    # Combine all transcriptions into a single transcript
    full_transcript = "\n".join(all_transcripts)
    
    # Save the combined transcript document
    full_doc_path = os.path.join(cache_subdir, "full_transcript.docx")
    doc = Document()
    doc.add_heading("完整语音转录结果", level=1)
    doc.add_paragraph(full_transcript)
    doc.save(full_doc_path)
    
    # Display results
    st.download_button(
        "下载完整DOCX",
        open(full_doc_path, "rb").read(),
        key="download",
        file_name="full_transcript.docx"
    )
    st.text_area("转录预览", value=full_transcript, height=300)

# History records
st.sidebar.subheader("历史记录")
dirs = os.listdir(CACHE_DIR)
history_tasks = sorted(dirs, key=lambda x: int(x))
for task in history_tasks:
    task_dir = os.path.join(CACHE_DIR, task)
    if os.path.isdir(task_dir):
        if st.sidebar.button(f"任务 {task}"):
            files = os.listdir(task_dir)
            audio_files = [f for f in files if f.endswith((".mp3", ".wav"))]
            doc_files = [f for f in files if f.endswith(".docx")]
            
            if audio_files:
                st.audio(os.path.join(task_dir, audio_files[0]))
            if doc_files:
                doc_path = os.path.join(task_dir, doc_files[0])
                with open(doc_path, "rb") as f:
                    doc_content = f.read()
                st.download_button("下载历史文件", doc_content, file_name=doc_files[0])
                
                # Display historical transcription text
                doc = Document(doc_path)
                transcript_text = "\n".join([para.text for para in doc.paragraphs])
                st.text_area("历史转录预览", value=transcript_text, height=300)
