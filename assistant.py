import asyncio
import websockets
import json
import base64
import shutil
import os
import subprocess
from openai import AsyncOpenAI
import socket
import threading

print("Starting whisper subprocess")
args = './stream -m ./models/ggml-tiny.en.bin -t 6 --step 0 --length 5000 -vth 0.6'.split(' ')
whisper_proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Define API keys and voice ID
OPENAI_API_KEY = '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'
ELEVENLABS_API_KEY = 'a1c47b5b440c613cd300c1509fa7d88c'
VOICE_ID = '7nDZZfx8upeW4iy5X91D'

# Set OpenAI API key
aclient = AsyncOpenAI(api_key=OPENAI_API_KEY)

def is_installed(lib_name):
    return shutil.which(lib_name) is not None


global_chunks = []
history = [
    {
        "role": "system", 
        "content": "You are a chatbot assistant embedded into a car. The driver is being monitored through an embedded system containing a gyroscope and accelerometer.\
        It appears that the driver is swerving and not driving carefully. It is possible they are sleepy, drowsy, drunk, or otherwise distracted.\
        It is your job to converse with the driver and ensure everything is ok. It is very important that you are concise."
     }
]

async def text_chunker(chunks):
    """Split text into chunks, ensuring to not break sentences."""
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""

    async for text in chunks:
        if text is None or text == "":
            continue
        global_chunks.append(text)

        if buffer.endswith(splitters):
            yield buffer + " "
            buffer = text
        elif text.startswith(splitters):
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text

    if buffer:
        print(f'{buffer}\n', flush=True)
        yield buffer + " "


async def stream(audio_stream):
    """Stream audio data using mpv player."""
    if not is_installed("mpv"):
        raise ValueError(
            "mpv not found, necessary to stream audio. "
            "Install instructions: https://mpv.io/installation/"
        )

    mpv_process = subprocess.Popen(
        ["mpv", "--no-cache", "--no-terminal", "--", "fd://0"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    print("Started streaming audio")
    async for chunk in audio_stream:
        if chunk:
            mpv_process.stdin.write(chunk)
            mpv_process.stdin.flush()

    if mpv_process.stdin:
        mpv_process.stdin.close()
    mpv_process.wait()


async def text_to_speech_input_streaming(voice_id, text_iterator):
    """Send text to ElevenLabs API and stream the returned audio."""
    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id=eleven_monolingual_v1"

    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({
            "text": " ",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
            "xi_api_key": ELEVENLABS_API_KEY,
        }))

        async def listen():
            """Listen to the websocket for audio data and stream it."""
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    if data.get("audio"):
                        yield base64.b64decode(data["audio"])
                    elif data.get('isFinal'):
                        break
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break

        listen_task = asyncio.create_task(stream(listen()))

        async for text in text_chunker(text_iterator):
            await websocket.send(json.dumps({"text": text, "try_trigger_generation": True}))

        await websocket.send(json.dumps({"text": ""}))

        await listen_task


async def chat_completion(query, first=False):
    """Retrieve text from OpenAI and pass it to the text-to-speech function."""
    if first:
        response = await aclient.chat.completions.create(model='gpt-3.5-turbo', messages= history,
        temperature=1, stream=True)
    else:
        response = await aclient.chat.completions.create(model='gpt-3.5-turbo', messages= history + [
            {'role': 'user', 'content': query}
        ],
        temperature=1, stream=True)

    async def text_iterator():
        async for chunk in response:
            delta = chunk.choices[0].delta
            yield delta.content

    await text_to_speech_input_streaming(VOICE_ID, text_iterator())


def start_listening():
    whisper_proc.stdin.write("START\n")
    whisper_proc.stdin.flush()

def get_user_input():
    print("Getting input from whisper")
    res = whisper_proc.stdout.readline()
    print("Got his message:", res)
    return res

def socket_function():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost",3001))

    while True:
        print(s.recv(1024).decode("utf-8"))

if __name__ == "__main__":
    socket_thread = threading.Thread(target=socket_function)
    socket_thread.start()

    user_query = ""
    first_message = True
    while True:
        asyncio.run(chat_completion(user_query, first_message))
        
        ai_response = "".join(global_chunks)
        global_chunks = []
        if first_message:
            history += [
                {"role": "assistant", "content": ai_response}
            ]
            first_message = False
        else:
            history += [
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": ai_response}
            ]
            
        start_listening()
        user_query = get_user_input()

whisper_proc.terminate()