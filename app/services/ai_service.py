import google.generativeai as genai
import time
import json
import mimetypes
import os
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.services.exceptions import (
    QuotaExceededError,
    InvalidFormatError,
    NetworkError,
    ProcessingTimeoutError,
    FileTooLargeError,
    ContentGenerationError,
    UnknownAIError
)

# Configure Gemini with direct API key (for file upload support)
genai.configure(api_key=settings.GEMINI_API_KEY)

# Add additional MIME types that may not be in the standard library
mimetypes.add_type('audio/x-m4a', '.m4a')
mimetypes.add_type('audio/mp4', '.m4a')
mimetypes.add_type('audio/aac', '.aac')
mimetypes.add_type('audio/ogg', '.ogg')
mimetypes.add_type('audio/opus', '.opus')
mimetypes.add_type('audio/webm', '.weba')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/quicktime', '.mov')


def get_mime_type(file_path: str) -> str:
    """
    Get MIME type for a file, with fallbacks for common audio/video formats

    Args:
        file_path: Path to the file

    Returns:
        MIME type string
    """
    # Try to get from mimetypes library
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type:
        return mime_type

    # Fallback based on extension
    ext = os.path.splitext(file_path)[1].lower()

    mime_map = {
        # Audio formats
        '.m4a': 'audio/mp4',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.opus': 'audio/opus',
        '.aac': 'audio/aac',
        '.flac': 'audio/flac',
        '.wma': 'audio/x-ms-wma',
        '.weba': 'audio/webm',
        # Video formats
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.wmv': 'video/x-ms-wmv',
        '.flv': 'video/x-flv',
        # Image formats
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        # Document formats
        '.pdf': 'application/pdf',
    }

    return mime_map.get(ext, 'application/octet-stream')


def compress_audio_file(file_path: str, target_bitrate: str = "48k") -> Tuple[str, bool]:
    """
    Compress an audio file using ffmpeg to reduce size before upload.

    Uses opus codec with low bitrate optimized for speech recognition.
    Only compresses audio files; returns original path for non-audio files.

    Args:
        file_path: Path to the original file
        target_bitrate: Target bitrate for compression (default: 48k for speech)

    Returns:
        Tuple of (path_to_use, is_temporary) - if is_temporary=True, caller should delete after use
    """
    mime_type = get_mime_type(file_path)

    # Only compress audio files, not video or images
    if not mime_type.startswith('audio/'):
        print(f"[COMPRESS] Skipping non-audio file: {file_path} (type: {mime_type})")
        return file_path, False

    # Get original file size
    original_size = os.path.getsize(file_path)
    original_size_mb = original_size / (1024 * 1024)
    print(f"[COMPRESS] Original audio file: {file_path}")
    print(f"[COMPRESS] Original size: {original_size_mb:.2f} MB")

    # Skip compression for small files (< 1 MB)
    if original_size < 1 * 1024 * 1024:
        print(f"[COMPRESS] File is small ({original_size_mb:.2f} MB), skipping compression")
        return file_path, False

    try:
        # Create temporary file for compressed output
        # Use .ogg extension for opus codec
        temp_fd, temp_path = tempfile.mkstemp(suffix='.ogg')
        os.close(temp_fd)

        # ffmpeg command for audio compression
        # -y: overwrite output
        # -i: input file
        # -vn: no video (strip video if present)
        # -ac 1: mono channel (good for speech, half the data)
        # -ar 16000: 16kHz sample rate (good for speech recognition)
        # -c:a libopus: use opus codec (best quality/size ratio)
        # -b:a: target bitrate
        cmd = [
            'ffmpeg',
            '-y',
            '-i', file_path,
            '-vn',
            '-ac', '1',
            '-ar', '16000',
            '-c:a', 'libopus',
            '-b:a', target_bitrate,
            temp_path
        ]

        print(f"[COMPRESS] Running ffmpeg compression...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            print(f"[COMPRESS] ffmpeg failed: {result.stderr}")
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return file_path, False

        # Check compressed size
        compressed_size = os.path.getsize(temp_path)
        compressed_size_mb = compressed_size / (1024 * 1024)
        reduction = (1 - compressed_size / original_size) * 100

        print(f"[COMPRESS] Compressed size: {compressed_size_mb:.2f} MB")
        print(f"[COMPRESS] Size reduction: {reduction:.1f}%")

        # Only use compressed file if it's actually smaller
        if compressed_size >= original_size:
            print(f"[COMPRESS] Compressed file not smaller, using original")
            os.remove(temp_path)
            return file_path, False

        print(f"[COMPRESS] ✓ Using compressed file: {temp_path}")
        return temp_path, True

    except subprocess.TimeoutExpired:
        print(f"[COMPRESS] ffmpeg timed out, using original file")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return file_path, False
    except Exception as e:
        print(f"[COMPRESS] Compression error: {str(e)}, using original file")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        return file_path, False


SYSTEM_INSTRUCTION = """You are a helpful assistant for students. Transcribe the given audio/video/image files into a comprehensive structured note.

### Goal
Create ONE cohesive lecture note from **ALL provided files** (audio of the lecturer, videos, images of slides/boards).  
The note must:

- Preserve the **original language** of the lecturer (e.g., Farsi, English, etc.).  
- Include **all** content said by the lecturer relevant to the lecture’s subject.  
- The final note must be complete, coherent, and written in the same language as the lecturer.  

### Input
You will receive zero or more of the following:
- Audio/video files (lectures, class recordings)  
- Image files (photos of board/slides)  
- Optional transcripts/recognized text from OCR/ASR if available  

### Instructions

#### 1. Transcribe & Extract
- If audio/video is provided, accurately **transcribe** the lecturer’s speech (keep the same language).  
- If images are provided, extract text and important formulas/diagrams as text summaries (don’t embed images; describe them).  
- Merge all extracted information into **one logically structured note**.

#### 2. Combine & Organize
- Use semantic HTML structure:
  - `<h1>` → main topic  
  - `<h2>` → major sections  
  - `<h3>` → subtopics  
  - `<p>` → paragraph text  
  - `<ul>/<ol>/<li>` → lists  
  - `<pre><code>` → formulas or code blocks  

#### 3. Faithfulness & Completeness
- Include all lecturer explanations and examples.  
- Deduplicate overlapping content but keep all unique information.  
- If conflicts exist between files, prioritize **spoken content**.  

#### 4. Title Generation
- Infer a short, meaningful session title based on **all files** (topic + focus).  
- The **language of the title must match the lecturer’s language** (e.g., Persian if the lecture is in Persian, English if in English).  
- Example:  
  > “ساختمان داده‌ها — درخت‌ها (جلسه پنجم)”  
  or  
  > “Data Structures — Trees (Lecture 5)”

### Output Format

Output **must be ONLY** a valid JSON object in the following structure:

```json
{
  "title": "Title of the lecture/session (based on all files, in same language as lecturer)",
  "note": "<h1>Main Topic</h1><p>Combined content from all files...</p><h2>Subsection</h2><p>More details...</p>"
}
```

### CRITICAL JSON FORMATTING RULES

- The `note` field must contain **valid HTML** with UTF-8 characters.  
- Escape rules:
  - All double quotes `"` inside HTML → `\"`
  - All backslashes `\` → `\\\\`
  - Never use single quotes `'`; use `&apos;` instead  
- Output must contain **only** the JSON, no text before or after.  

### Quality Checklist (Must be true before final output)
- [ ] Output is a **single JSON object**  
- [ ] `title` is concise, in the same language as the lecturer  
- [ ] `note` is valid HTML with proper tags  
- [ ] All escape rules applied  
- [ ] Note language = lecturer’s language  



### Final Output Example

```json
{
  "title": "Introduction to Algorithms — Lecture 1",
  "note": "<h1>Algorithm Basics</h1><p>Algorithms are step-by-step instructions...</p><h2>Examples</h2><ul><li>Sorting</li><li>Searching</li></ul>"
}
```

### Now use the provided files to produce the JSON.

"""


async def process_files_with_gemini(file_paths: List[str]) -> Dict[str, str]:
    """
    Process multiple files with Gemini AI and return structured JSON content

    Requires google-generativeai >= 0.8.0 for proper multimodal file upload support

    Args:
        file_paths: List of paths to local files to process

    Returns:
        Dictionary with 'title' and 'note' keys (and optionally other fields)

    Raises:
        Exception: If processing fails
    """
    try:
        print("=" * 80)
        print(f"[GEMINI] Starting processing of {len(file_paths)} file(s)")
        for i, path in enumerate(file_paths, 1):
            print(f"[GEMINI] File {i}: {path}")
        print("=" * 80)

        print("[GEMINI] Step 1/5: Compressing audio files...")

        # Compress audio files before upload to reduce size and upload time
        files_to_upload = []  # List of (path, is_temporary) tuples
        temp_files_to_cleanup = []  # Track temp files for cleanup

        for i, file_path in enumerate(file_paths, 1):
            print(f"[GEMINI]   Processing file {i}/{len(file_paths)} for compression: {file_path}")
            compressed_path, is_temp = compress_audio_file(file_path)
            files_to_upload.append((compressed_path, is_temp))
            if is_temp:
                temp_files_to_cleanup.append(compressed_path)

        print(f"[GEMINI] Step 2/5: Uploading {len(files_to_upload)} file(s) to Gemini...")

        # Upload files to Gemini File API
        uploaded_files = []
        try:
            for i, (file_path_to_upload, is_temp) in enumerate(files_to_upload, 1):
                original_path = file_paths[i-1]
                print(f"[GEMINI]   Uploading file {i}/{len(files_to_upload)}: {file_path_to_upload}")
                if is_temp:
                    print(f"[GEMINI]   (compressed from: {original_path})")
                try:
                    # Get MIME type for the file
                    mime_type = get_mime_type(file_path_to_upload)
                    print(f"[GEMINI]   Detected MIME type: {mime_type}")

                    uploaded_file = genai.upload_file(path=file_path_to_upload, mime_type=mime_type)
                    uploaded_files.append(uploaded_file)
                    print(f"[GEMINI]   ✓ File {i} uploaded: {uploaded_file.name}")
                except Exception as upload_error:
                    error_str = str(upload_error).lower()
                    print(f"[GEMINI]   ✗ Failed to upload file {i}: {str(upload_error)}")

                    # Classify the error
                    if "quota" in error_str or "limit" in error_str or "exceeded" in error_str:
                        raise QuotaExceededError()
                    elif "invalid" in error_str or "format" in error_str or "unsupported" in error_str:
                        raise InvalidFormatError()
                    elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
                        raise NetworkError()
                    elif "too large" in error_str or "size" in error_str:
                        raise FileTooLargeError()
                    else:
                        raise UnknownAIError(f"خطا در آپلود فایل: {str(upload_error)}")
        finally:
            # Cleanup temporary compressed files after upload (success or failure)
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"[GEMINI]   Cleaned up temp file: {temp_file}")
                except Exception as cleanup_error:
                    print(f"[GEMINI]   Warning: Failed to cleanup temp file {temp_file}: {cleanup_error}")

        print(f"[GEMINI] Step 3/5: Waiting for file processing (max 30s)...")

        # Wait for files to be processed
        max_wait = 30  # seconds
        start_time = time.time()

        for i, uploaded_file in enumerate(uploaded_files, 1):
            while uploaded_file.state.name == "PROCESSING":
                if time.time() - start_time > max_wait:
                    print(f"[GEMINI]   ⚠ Warning: File {i} still processing after {max_wait}s, continuing anyway...")
                    break
                print(f"[GEMINI]   Waiting for file {i} to be processed...")
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                print(f"[GEMINI]   ✗ File {i} processing failed")
                raise ContentGenerationError("پردازش فایل در سرور Gemini با خطا مواجه شد")

            print(f"[GEMINI]   ✓ File {i} ready: {uploaded_file.state.name}")

        print("[GEMINI] Step 4/5: Initializing Gemini model...")

        # Initialize model with system instruction
        try:
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_TRANSCRIPTION_MODEL,
                system_instruction=SYSTEM_INSTRUCTION
            )
            print(f"[GEMINI]   ✓ Model initialized ({settings.GEMINI_TRANSCRIPTION_MODEL})")
        except Exception as model_error:
            print(f"[GEMINI]   ✗ Failed to initialize model: {str(model_error)}")
            raise

        # Create prompt with uploaded files
        if len(file_paths) > 1:
            prompt = f"I'm providing you with {len(file_paths)} files. Please analyze all of them and create ONE comprehensive note combining information from all sources."
        else:
            prompt = "Please analyze this file and create a structured note."

        print(f"[GEMINI] Step 5/5: Generating content from {len(uploaded_files)} file(s)...")
        print(f"[GEMINI]   Using prompt: {prompt[:100]}...")

        try:
            # Send files and prompt to model with increased output limit
            content_parts = [prompt] + uploaded_files

            # Configure generation with higher token limit and timeout
            generation_config = {
                "max_output_tokens": 100000,
                "temperature": 0.4,
                "top_p": 0.95,
            }

            # Set request timeout to 15 minutes for long files
            request_options = {
                "timeout": 900  # 15 minutes in seconds
            }

            response = model.generate_content(
                content_parts,
                generation_config=generation_config,
                request_options=request_options
            )

            print("[GEMINI]   ✓ Content generation completed")
        except Exception as gen_error:
            error_str = str(gen_error).lower()
            error_type = type(gen_error).__name__
            print(f"[GEMINI]   ✗ Content generation failed: {str(gen_error)}")
            print(f"[GEMINI]   Error details: {error_type}")

            # Classify generation errors - check type first, then message
            if "DeadlineExceeded" in error_type or "deadline" in error_str or "timeout" in error_str:
                raise ProcessingTimeoutError()
            elif "quota" in error_str or ("limit" in error_str and "rate" in error_str):
                raise QuotaExceededError()
            elif "network" in error_str or "connection" in error_str:
                raise NetworkError()
            else:
                raise ContentGenerationError(f"خطا در تولید محتوا: {str(gen_error)}")

        # Parse the response
        print("[GEMINI] Parsing Gemini response...")

        # Check for finish reason to detect truncation
        try:
            finish_reason = response.candidates[0].finish_reason
            print(f"[GEMINI]   Finish reason: {finish_reason}")
            if finish_reason == 1:  # STOP - normal completion
                print("[GEMINI]   ✓ Response completed normally")
            elif finish_reason == 2:  # MAX_TOKENS - truncated
                print("[GEMINI]   ⚠ WARNING: Response truncated due to MAX_TOKENS limit!")
            elif finish_reason == 3:  # SAFETY - blocked by safety
                print("[GEMINI]   ⚠ WARNING: Response blocked by safety filters")
            else:
                print(f"[GEMINI]   ⚠ WARNING: Unexpected finish reason: {finish_reason}")
        except Exception as e:
            print(f"[GEMINI]   Could not check finish reason: {e}")

        try:
            processed_text = response.text.strip()
        except:
            # Fallback to candidates
            try:
                processed_text = response.candidates[0].content.parts[0].text.strip()
            except:
                print("[GEMINI]   ✗ Could not extract text from response")
                raise Exception("Could not extract text from Gemini response")

        print(f"[GEMINI]   Raw response length: {len(processed_text)} characters")
        print(f"[GEMINI]   First 200 chars: {processed_text[:200]}...")
        print(f"[GEMINI]   Last 200 chars: ...{processed_text[-200:]}")

        # Check if response seems truncated
        if not processed_text.endswith('}') and not processed_text.endswith('```'):
            print("[GEMINI]   ⚠ WARNING: Response might be truncated (doesn't end with } or ```)")
            print("[GEMINI]   ⚠ This might cause JSON parsing errors")

        # Remove markdown code blocks if present
        if processed_text.startswith("```json"):
            processed_text = processed_text[7:]
            print("[GEMINI]   Removed ```json prefix")
        if processed_text.startswith("```"):
            processed_text = processed_text[3:]
            print("[GEMINI]   Removed ``` prefix")
        if processed_text.endswith("```"):
            processed_text = processed_text[:-3]
            print("[GEMINI]   Removed ``` suffix")
        processed_text = processed_text.strip()

        # Parse JSON
        print("[GEMINI] Attempting to parse JSON...")
        print(f"[GEMINI] Text to parse (first 500 chars): {processed_text[:500]}...")

        try:
            # Try standard JSON parsing first
            result = json.loads(processed_text)
            print("[GEMINI]   ✓ JSON parsed successfully")
            print(f"[GEMINI]   Keys in result: {list(result.keys())}")

            # Validate structure
            if not isinstance(result, dict):
                print(f"[GEMINI]   ✗ Result is not a dict, it's: {type(result)}")
                raise ValueError("Result is not a dictionary")

            # Ensure required fields exist
            if 'title' not in result:
                print("[GEMINI]   ⚠ Warning: 'title' field missing, using default")
                result['title'] = "Untitled Note"
            if 'note' not in result:
                print("[GEMINI]   ⚠ Warning: 'note' field missing, using raw text")
                result['note'] = f"<p>{processed_text}</p>"

            print(f"[GEMINI]   Title: {result['title'][:100]}...")
            print(f"[GEMINI]   Note length: {len(result.get('note', ''))} characters")
            print(f"[GEMINI]   Note preview (first 200 chars): {result.get('note', '')[:200]}...")
            print("=" * 80)
            print("[GEMINI] ✓ Processing completed successfully")
            print("=" * 80)
            return result

        except json.JSONDecodeError as e:
            print(f"[GEMINI]   ✗ Standard JSON parsing failed: {str(e)}")
            print(f"[GEMINI]   Error at line {e.lineno}, column {e.colno}")

            # Try to fix common JSON issues
            print("[GEMINI]   Attempting to fix JSON formatting issues...")

            # Strategy: Use regex to extract title and note separately
            import re

            try:
                # Extract title using regex
                title_match = re.search(r'"title"\s*:\s*"([^"]+)"', processed_text)
                if not title_match:
                    print("[GEMINI]   ✗ Could not extract title")
                    title = "Transcription"
                else:
                    title = title_match.group(1)
                    print(f"[GEMINI]   ✓ Extracted title: {title[:100]}...")

                # Extract note - find "note": " and extract until the last "
                # Strategy: Find the pattern "note": " and then find matching closing quote

                # Find where "note" field starts
                note_field_match = re.search(r'"note"\s*:\s*"', processed_text)
                if not note_field_match:
                    print("[GEMINI]   ✗ Could not find 'note' field")
                    return {
                        "title": title,
                        "note": f"<p>{processed_text}</p>"
                    }

                # The content starts right after "note": "
                note_content_start = note_field_match.end()

                # Now find the closing quote. We need to be careful because there might be escaped quotes
                # Look for the pattern ",\n  "summary" or just }\n to find the end
                # Try to find either the next field or the closing brace

                # Method: Find the last quote before either "summary" or the final }
                summary_match = re.search(r'",?\s*"summary"', processed_text[note_content_start:])
                closing_brace_match = re.search(r'"\s*}', processed_text[note_content_start:])

                if summary_match:
                    # Note ends just before ",  "summary"
                    note_content_end = note_content_start + summary_match.start()
                elif closing_brace_match:
                    # Note ends just before "  }
                    note_content_end = note_content_start + closing_brace_match.start()
                else:
                    # Fallback: use the last quote in the document
                    note_content_end = processed_text.rfind('"')

                note_html = processed_text[note_content_start:note_content_end]

                # Unescape any escaped characters
                note_html = note_html.replace('\\"', '"')
                note_html = note_html.replace('\\n', '\n')
                note_html = note_html.replace('\\t', '\t')
                note_html = note_html.replace('\\\\', '\\')

                print(f"[GEMINI]   ✓ Extracted note (length: {len(note_html)} chars)")
                print(f"[GEMINI]   Note preview: {note_html[:200]}...")

                return {
                    "title": title,
                    "note": note_html
                }

            except Exception as fix_error:
                print(f"[GEMINI]   ✗ Failed to fix JSON: {str(fix_error)}")
                print(f"[GEMINI]   Returning raw text as fallback")
                return {
                    "title": "Transcription",
                    "note": f"<p>{processed_text}</p>"
                }

    except Exception as e:
        print("=" * 80)
        print(f"[GEMINI] ✗ ERROR: {str(e)}")
        print(f"[GEMINI] Exception type: {type(e).__name__}")
        import traceback
        print(f"[GEMINI] Traceback:\n{traceback.format_exc()}")
        print("=" * 80)
        raise


async def process_file_with_gemini(file_path: str) -> Dict[str, str]:
    """
    Process a single file with Gemini AI (wrapper for backward compatibility)

    Args:
        file_path: Path to the local file to process

    Returns:
        Dictionary with 'title' and 'note' keys (and optionally other fields)

    Raises:
        Exception: If processing fails
    """
    return await process_files_with_gemini([file_path])


def test_gemini_connection() -> bool:
    """Test if Gemini API is configured correctly"""
    try:
        model = genai.GenerativeModel(settings.GEMINI_TRANSCRIPTION_MODEL)
        response = model.generate_content("Hello")
        return True
    except Exception as e:
        print(f"Gemini connection test failed: {str(e)}")
        return False
