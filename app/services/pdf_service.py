# app/services/pdf_service.py - کد اصلاح شده

from weasyprint import HTML
from io import BytesIO
from typing import List, Dict

def generate_note_pdf(note_title: str, note_content: str, session_date: str = None) -> BytesIO:
    """
    Generate PDF for a single note

    Args:
        note_title: Title of the note
        note_content: HTML content of the note as a single string.
        session_date: Optional session date

    Returns:
        BytesIO object containing PDF data
    """
    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="fa">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2.5cm 2cm 3cm 2cm;
                @bottom-right {{
                    content: "نویسو";
                    font-size: 15px;
                    color: #666;
                }}
                @bottom-center {{
                    content: counter(page);
                    font-size: 10px;
                    color: #666;
                }}
            }}
            body {{
                font-family: 'Vazir', 'Tahoma', 'Arial', sans-serif;
                line-height: 1.9;
                color: #000;
                direction: rtl;
                font-size: 14px;
            }}
            .main-title {{
                color: #000;
                border-bottom: 2px solid #000;
                padding-bottom: 12px;
                margin-bottom: 25px;
                font-size: 24px;
                font-weight: bold;
            }}
            .meta {{
                color: #666;
                font-size: 12px;
                margin-bottom: 25px;
                padding: 8px 12px;
                background-color: #f5f5f5;
                border-right: 3px solid #000;
            }}
            .content {{
                color: #000;
            }}
            .content h1 {{
                color: #000;
                margin-top: 25px;
                margin-bottom: 12px;
                font-size: 20px;
                font-weight: bold;
                border-right: 4px solid #000;
                padding-right: 10px;
            }}
            .content h2 {{
                color: #000;
                margin-top: 20px;
                margin-bottom: 10px;
                font-size: 18px;
                font-weight: bold;
                border-right: 3px solid #000;
                padding-right: 8px;
            }}
            .content h3 {{
                color: #000;
                margin-top: 18px;
                margin-bottom: 8px;
                font-size: 16px;
                font-weight: bold;
            }}
            .content h4 {{
                color: #000;
                margin-top: 15px;
                margin-bottom: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            .content p {{
                margin-bottom: 12px;
                text-align: justify;
            }}
            .content ul, .content ol {{
                margin-bottom: 12px;
                padding-right: 25px;
            }}
            .content li {{
                margin-bottom: 6px;
            }}
            .content strong {{
                font-weight: bold;
                color: #000;
            }}
            .content em {{
                font-style: italic;
            }}
            .content code {{
                background-color: #f5f5f5;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
            }}
            .content pre {{
                background-color: #f5f5f5;
                padding: 12px;
                border-right: 3px solid #000;
                margin: 15px 0;
                overflow-x: auto;
            }}
            .content blockquote {{
                border-right: 4px solid #000;
                padding-right: 15px;
                margin: 15px 0;
                color: #333;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="main-title">{note_title}</div>
    """

    if session_date:
        html_content += f'<div class="meta">تاریخ جلسه: {session_date}</div>'

    # محتوای HTML داخل یک div با کلاس content قرار می‌گیرد
    html_content += f'<div class="content">{note_content}</div>'

    html_content += """
    </body>
    </html>
    """

    # Generate PDF
    pdf_buffer = BytesIO()
    HTML(string=html_content).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# تابع generate_notebook_pdf بدون تغییر باقی می‌ماند
def generate_notebook_pdf(notebook_title: str, notes: List[Dict]) -> BytesIO:
    # ... (کد این تابع نیازی به تغییر ندارد)
    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="fa">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2.5cm 2cm 3cm 2cm;
                @bottom-right {{
                    content: "نویسو";
                    font-size: 15px;
                    color: #666;
                }}
                @bottom-center {{
                    content: counter(page);
                    font-size: 10px;
                    color: #666;
                }}
            }}
            body {{
                font-family: 'Vazir', 'Tahoma', 'Arial', sans-serif;
                line-height: 1.9;
                color: #000;
                direction: rtl;
                font-size: 14px;
            }}
            .notebook-title {{
                color: #000;
                border-bottom: 2px solid #000;
                padding-bottom: 12px;
                margin-bottom: 30px;
                font-size: 26px;
                font-weight: bold;
                text-align: center;
            }}
            .note-title {{
                color: #000;
                margin-top: 40px;
                margin-bottom: 15px;
                font-size: 22px;
                font-weight: bold;
                page-break-before: always;
                border-bottom: 1px solid #000;
                padding-bottom: 8px;
            }}
            .meta {{
                color: #666;
                font-size: 12px;
                margin-bottom: 25px;
                padding: 8px 12px;
                background-color: #f5f5f5;
                border-right: 3px solid #000;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .content {{
                color: #000;
            }}
            .content h1 {{
                color: #000;
                margin-top: 25px;
                margin-bottom: 12px;
                font-size: 20px;
                font-weight: bold;
                border-right: 4px solid #000;
                padding-right: 10px;
            }}
            .content h2 {{
                color: #000;
                margin-top: 20px;
                margin-bottom: 10px;
                font-size: 18px;
                font-weight: bold;
                border-right: 3px solid #000;
                padding-right: 8px;
            }}
            .content h3 {{
                color: #000;
                margin-top: 18px;
                margin-bottom: 8px;
                font-size: 16px;
                font-weight: bold;
            }}
            .content h4 {{
                color: #000;
                margin-top: 15px;
                margin-bottom: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            .content p {{
                margin-bottom: 12px;
                text-align: justify;
            }}
            .content ul, .content ol {{
                margin-bottom: 12px;
                padding-right: 25px;
            }}
            .content li {{
                margin-bottom: 6px;
            }}
            .content strong {{
                font-weight: bold;
                color: #000;
            }}
            .content em {{
                font-style: italic;
            }}
            .content code {{
                background-color: #f5f5f5;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
            }}
            .content pre {{
                background-color: #f5f5f5;
                padding: 12px;
                border-right: 3px solid #000;
                margin: 15px 0;
                overflow-x: auto;
            }}
            .content blockquote {{
                border-right: 4px solid #000;
                padding-right: 15px;
                margin: 15px 0;
                color: #333;
                font-style: italic;
            }}
        </style>
    </head>
    <body>
        <div class="notebook-title">{notebook_title}</div>
    """

    # Add each note
    for note in notes:
        html_content += f'<div class="note-title">{note.get("title", "جزوه بدون عنوان")}</div>'

        if note.get("session_date"):
            html_content += f'<div class="meta">تاریخ جلسه: {note["session_date"]}</div>'

        # Add sections
        content = note.get("content", [])
        if isinstance(content, list):
            for section in content:
                html_content += f"""
                <div class="section">
                    <div class="content">{section.get('content', '')}</div>
                </div>
                """
        else:
            html_content += f'<div class="content">{content}</div>'

    html_content += """
    </body>
    </html>
    """

    # Generate PDF
    pdf_buffer = BytesIO()
    HTML(string=html_content).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer