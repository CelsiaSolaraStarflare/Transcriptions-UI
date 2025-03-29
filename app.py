import streamlit as st
import whisper
from docx import Document
import os

CACHE_DIR = "transcription_cache"

# 确保缓存目录存在
os.makedirs(CACHE_DIR, exist_ok=True)

# 加载模型
model = whisper.load_model("small")

def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02}:{secs:02}"

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

# 主界面
st.title("语音转录系统")
st.write("上传音频文件生成带时间戳的Word文档")

# 文件上传
uploaded_file = st.file_uploader("选择音频文件", type=["mp3", "wav"])

if uploaded_file:
    task_id = str(len(os.listdir(CACHE_DIR)) + 1)
    cache_subdir = os.path.join(CACHE_DIR, task_id)
    os.makedirs(cache_subdir, exist_ok=True)

    # 保存音频
    audio_path = os.path.join(cache_subdir, uploaded_file.name)
    with open(audio_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    
    # 转录
    doc_path, preview = transcribe(audio_path, cache_subdir)
    
    # 显示结果
    st.download_button(
        "下载DOCX",
        open(doc_path, "rb").read(),
        key="download",
        file_name="transcript.docx"
    )
    st.text_area("转录预览", value=preview, height=300)

# 历史记录
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
                
                # 显示历史转录文本
                doc = Document(doc_path)
                transcript_text = "\n".join([para.text for para in doc.paragraphs])
                st.text_area("历史转录预览", value=transcript_text, height=300)
