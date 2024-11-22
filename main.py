from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.background import BackgroundTasks
from pydub import AudioSegment
from dotenv import load_dotenv
import os
import requests
from google.oauth2 import service_account
from google.cloud import texttospeech
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from notion_client import Client
from openai import OpenAI
import re
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion_client = Client(auth=NOTION_TOKEN)

progress = {}

# Helper Functions
def update_progress(task_id, message):
    progress[task_id] = message


def extract_article_content(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string if soup.title else "No Title Found"
    body = "\n".join(p.get_text() for p in soup.find_all("p"))
    return title.strip(), body.strip()

def calculate_word_count(text):
    """
    Calculate the word count of the given text.
    """
    return len(text.split())

def split_text(text, max_bytes=5000):
    """
    Splits text into chunks that are less than max_bytes in size.
    """
    chunks = []
    current_chunk = ""

    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if len(current_chunk.encode("utf-8")) + len(paragraph.encode("utf-8")) < max_bytes:
            current_chunk += paragraph + "\n"
        else:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def query_openai(prompt, model="gpt-4o-mini"):
    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def authenticate_google_drive():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=credentials)


def create_mp3_with_google_tts(title, body, task_id):
    """
    Create an MP3 file using Google Cloud Text-to-Speech API.
    Handles the 5000-byte limit by splitting text into smaller chunks.
    """
    # Initialize Google Text-to-Speech client
    client = texttospeech.TextToSpeechClient.from_service_account_file(SERVICE_ACCOUNT_FILE)

    # Combine title and body into one string
    text = f"Title: {title}\n\n{body}"

    # Split the text into chunks
    text_chunks = split_text(text)
    print(f"Total chunks to synthesize: {len(text_chunks)}")

    # Sanitize the title for the output file
    sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title)
    output_file = f"{sanitized_title}.mp3"

    # Synthesize each chunk and save as temporary files
    temp_files = []
    for i, chunk in enumerate(text_chunks):
        synthesis_input = texttospeech.SynthesisInput(text=chunk)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-GB",  # British English
            #name="en-GB-Neural2-A"  # Specific voice name
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        temp_file = f"temp_chunk_{i}.mp3"
        with open(temp_file, "wb") as out:
            out.write(response.audio_content)
        temp_files.append(temp_file)

    # Combine all the temporary MP3 files into a single MP3
    combined_audio = AudioSegment.empty()
    for temp_file in temp_files:
        combined_audio += AudioSegment.from_file(temp_file)
        os.remove(temp_file)  # Delete the temporary file after combining

    combined_audio.export(output_file, format="mp3")

    update_progress(task_id, "Generated MP3 file")
    return output_file


def upload_to_google_drive(file_path, drive_service, folder_id, task_id):
    file_metadata = {"name": os.path.basename(file_path), "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="audio/mpeg")
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    update_progress(task_id, "Uploaded MP3 file to Google Drive")
    return uploaded_file["id"]

def add_to_notion(title, summary, cefr_level, word_count, questions, tags, url):
    """
    Add the article details to a Notion database.
    """
    notion_client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Title": {"title": [{"text": {"content": title}}]},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "CEFR Level": {"rich_text": [{"text": {"content": cefr_level}}]},
            "Word Count": {"number": word_count},
            "Comprehension Questions": {"rich_text": [{"text": {"content": questions}}]},
            "Tags": {"multi_select": [{"name": tag} for tag in tags.split(",")]},
            "URL": {"url": url},
        },
    )
    print(f"Article '{title}' added to Notion database.")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    return JSONResponse({"status": progress.get(task_id, "Not started")})


@app.post("/process/")
async def process_article(request: Request, background_tasks: BackgroundTasks, url: str = Form(...), generate_mp3: bool = Form(False)):
    task_id = str(hash(url))
    progress[task_id] = "Starting process"
    
    def background_task():
        try:
            update_progress(task_id, "Extracting article content")
            title, body = extract_article_content(url)
            
            if not body:
                update_progress(task_id, "No content found in the article")
                return

            word_count = calculate_word_count(body)

            update_progress(task_id, "Summarising article")
            summary = query_openai(f"Summarise this article in approximately 100 words.:\n\n{body}")
            
            update_progress(task_id, "Determining CEFR level")
            cefr_level = query_openai(f"Determine the CEFR level (A1, A2, B1, B2, C1, or C2) of the following article. Respond with the level only, nothing else:\n\n{body}")

            update_progress(task_id, "Generating comprehension questions")
            questions = query_openai(f"Create three comprehension questions to check understanding of the following article. Ensure the questions are clear and relevant:\n\n{body}")

            update_progress(task_id, "Generating Tags")
            tags = query_openai(f"Create one to three generalised tags to describe the following article. Use broad categories like Health, Politics, Technology, etc. Respond with tags separated by commas:\n\n{body}")
 
            if generate_mp3:
                update_progress(task_id, "Generating MP3 file")
                mp3_file = create_mp3_with_google_tts(title, body, task_id)
                drive_service = authenticate_google_drive()
                upload_to_google_drive(mp3_file, drive_service, GOOGLE_DRIVE_FOLDER_ID, task_id)

            # Notion integration
            add_to_notion(title, summary, cefr_level, word_count, questions, tags, url)

            update_progress(task_id, "Processing complete")
        except Exception as e:
            update_progress(task_id, f"Error: {str(e)}")

    background_tasks.add_task(background_task)
    return {"task_id": task_id, "message": "Processing started"}