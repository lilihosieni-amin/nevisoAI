# Gemini API - Client Guide

How to send requests to the Gemini API through the dispatcher or directly to Google.

---

## Quick Start

```python
import google.generativeai as genai

# Via Dispatcher (load balanced, rate limit managed)
genai.configure(
    api_key="social",  # Pool name
    transport='rest',  # Important: use REST instead of gRPC
    client_options={"api_endpoint": "http://202.133.89.98:8001"}
)

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Hello!")
print(response.text)
```

---

## Dispatcher vs Direct Google

| Feature | Dispatcher | Direct Google |
|---------|-----------|---------------|
| Endpoint | `http://202.133.89.98:8001` | Default (no config) |
| API Key | Pool name (e.g., `"social"`) | Real API key (`"AIzaSy..."`) |
| Transport | `transport='rest'` (required) | Default (gRPC) |
| Load Balancing | ✅ Automatic | ❌ Manual |
| Rate Limit Handling | ✅ Managed | ❌ Your responsibility |

> **Important:** When using the dispatcher, you must set `transport='rest'` in `genai.configure()`. The dispatcher is a REST proxy and doesn't support gRPC (the SDK's default transport).

---

## Using the Google SDK

### Via Dispatcher

```python
import google.generativeai as genai

genai.configure(
    api_key="social",  # Pool name: "social" or "Legal"
    transport='rest',  # Required for dispatcher
    client_options={"api_endpoint": "http://202.133.89.98:8001"}
)

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("What is 2+2?")
print(response.text)
```

**Using different pools:**

```python
import google.generativeai as genai

# For social media bot - uses "social" pool
genai.configure(
    api_key="social",
    transport='rest',
    client_options={"api_endpoint": "http://202.133.89.98:8001"}
)
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Write a tweet about AI")

# For legal assistant - uses "Legal" pool
genai.configure(
    api_key="Legal",
    transport='rest',
    client_options={"api_endpoint": "http://202.133.89.98:8001"}
)
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Explain contract law")
```

### Direct to Google

```python
import google.generativeai as genai

genai.configure(api_key="AIzaSy...")  # Your real API key

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("What is 2+2?")
print(response.text)
```

---

## Switching Between Endpoints

### Simple Functions

```python
import google.generativeai as genai

def use_dispatcher(pool="social"):
    """Route through dispatcher for load balancing"""
    genai.configure(
        api_key=pool,
        transport='rest',
        client_options={"api_endpoint": "http://202.133.89.98:8001"}
    )

def use_google_direct(api_key):
    """Connect directly to Google"""
    genai.configure(api_key=api_key, client_options={})

# Switch as needed
use_dispatcher("Legal")
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Hello from dispatcher!")

use_google_direct("AIzaSy...")
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Hello from Google!")
```

### Environment Variables (Production)

```python
import os
import google.generativeai as genai

USE_DISPATCHER = os.getenv("USE_DISPATCHER", "true").lower() == "true"

if USE_DISPATCHER:
    genai.configure(
        api_key=os.getenv("DISPATCHER_POOL", "social"),
        transport='rest',
        client_options={"api_endpoint": os.getenv("DISPATCHER_URL", "http://202.133.89.98:8001")}
    )
else:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Your code works the same either way
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Hello!")
```

```bash
# .env for dispatcher
USE_DISPATCHER=true
DISPATCHER_POOL=Legal

# .env for direct Google
USE_DISPATCHER=false
GOOGLE_API_KEY=AIzaSy...
```

---

## SDK Features

All features work with both dispatcher and direct Google:

### Streaming

```python
model = genai.GenerativeModel("gemini-2.5-flash")
for chunk in model.generate_content("Tell me a story", stream=True):
    print(chunk.text, end="")
```

### System Instructions

```python
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    system_instruction="You are a helpful assistant."
)
response = model.generate_content("Hello!")
```

### Chat

```python
model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat()

response = chat.send_message("Hello!")
print(response.text)

response = chat.send_message("What did I say?")
print(response.text)
```

---

## Multimodal Content (Files)

The dispatcher fully supports multimodal content. All file types supported by Gemini work through the dispatcher.

### Supported File Types

| Type | Formats | Max Size |
|------|---------|----------|
| Images | JPEG, PNG, GIF, WebP | 20MB |
| Audio | MP3, WAV, AIFF, AAC, OGG, FLAC | 25MB |
| Video | MP4, MPEG, MOV, AVI, FLV, MKV, WebM | 2GB |
| Documents | PDF, TXT, HTML, CSS, JS, Python, etc. | 100MB |

### Images

```python
import base64
from pathlib import Path

model = genai.GenerativeModel("gemini-2.5-flash")

# Load image as base64
image_path = Path("photo.jpg")
with open(image_path, "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

# Send with text prompt
response = model.generate_content([
    {"mime_type": "image/jpeg", "data": image_data},
    "Describe this image in detail."
])
print(response.text)
```

**Using PIL/Pillow:**

```python
from PIL import Image

model = genai.GenerativeModel("gemini-2.5-flash")
image = Image.open("photo.jpg")

response = model.generate_content([image, "What's in this image?"])
print(response.text)
```

### Audio

```python
import base64

model = genai.GenerativeModel("gemini-2.5-flash")

with open("audio.mp3", "rb") as f:
    audio_data = base64.b64encode(f.read()).decode("utf-8")

response = model.generate_content([
    {"mime_type": "audio/mp3", "data": audio_data},
    "Transcribe this audio and summarize it."
])
print(response.text)
```

### Video

```python
import base64

model = genai.GenerativeModel("gemini-2.5-flash")

with open("video.mp4", "rb") as f:
    video_data = base64.b64encode(f.read()).decode("utf-8")

response = model.generate_content([
    {"mime_type": "video/mp4", "data": video_data},
    "Describe what happens in this video."
])
print(response.text)
```

### PDF Documents

```python
import base64

model = genai.GenerativeModel("gemini-2.5-flash")

with open("document.pdf", "rb") as f:
    pdf_data = base64.b64encode(f.read()).decode("utf-8")

response = model.generate_content([
    {"mime_type": "application/pdf", "data": pdf_data},
    "Summarize this document."
])
print(response.text)
```

### HTTP Request with Image

```bash
# Encode image to base64
IMAGE_BASE64=$(base64 -w0 photo.jpg)

# Send via dispatcher
curl -X POST "http://202.133.89.98:8001/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: social" \
  -d '{
    "contents": [{
      "parts": [
        {"inline_data": {"mime_type": "image/jpeg", "data": "'$IMAGE_BASE64'"}},
        {"text": "Describe this image."}
      ]
    }]
  }'
```

### Multiple Files

```python
model = genai.GenerativeModel("gemini-2.5-flash")

# Multiple images
response = model.generate_content([
    {"mime_type": "image/jpeg", "data": image1_b64},
    {"mime_type": "image/jpeg", "data": image2_b64},
    "Compare these two images."
])

# Mixed content (image + audio)
response = model.generate_content([
    {"mime_type": "image/jpeg", "data": image_b64},
    {"mime_type": "audio/mp3", "data": audio_b64},
    "Does the audio describe this image?"
])
```

---

## Available Pools (Dispatcher)

| Pool | Description |
|------|-------------|
| `social` | Social media applications |
| `Legal` | Legal AI assistant |

---

## Supported Models

| Model | Description |
|-------|-------------|
| `gemini-2.5-pro` | Most capable |
| `gemini-2.5-flash` | Fast and efficient |
| `gemini-2.5-flash-lite` | Lightweight |
| `gemini-2.0-flash` | Previous generation |
| `gemini-2.0-flash-lite` | Previous generation lite |

---

## Alternative: HTTP Requests

If not using the SDK:

```bash
# Via Dispatcher
curl -X POST "http://202.133.89.98:8001/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: social" \
  -d '{"contents": [{"parts": [{"text": "Hello"}]}]}'

# Direct to Google
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: AIzaSy..." \
  -d '{"contents": [{"parts": [{"text": "Hello"}]}]}'
```

---

## Docker Clients

If your app runs in Docker, connect to the dispatcher network:

```bash
docker network connect gemini-dispatcher_default your-container
```

Then use internal URL:
```python
genai.configure(
    api_key="your-pool",
    transport='rest',
    client_options={"api_endpoint": "http://gemini-dispatcher:8000"}
)
```

---

**Dispatcher URL:** `http://202.133.89.98:8001`
