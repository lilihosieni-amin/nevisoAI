"""
HTML Processing Service
Processes Gemini AI output to fix formatting issues
"""
import re
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """
    Process and fix HTML output from Gemini AI
    """

    @staticmethod
    def add_inline_styles_to_code_blocks(html: str) -> str:
        """
        Add inline styles to <pre> and <code> tags to prevent horizontal scroll

        Args:
            html: Raw HTML string from Gemini

        Returns:
            Processed HTML with inline styles
        """
        try:
            if not html:
                return html

            soup = BeautifulSoup(html, 'html.parser')

            # Style for <pre> tags
            pre_style = (
                "white-space: pre-wrap !important; "
                "word-wrap: break-word !important; "
                "overflow-x: auto !important; "
                "max-width: 100% !important; "
                "padding: 1rem; "
                "background-color: #f5f5f5; "
                "border-radius: 4px; "
                "direction: ltr; "
                "font-family: 'Courier New', monospace; "
                "font-size: 0.9em; "
                "line-height: 1.5; "
                "margin: 1rem 0;"
            )

            # Style for <code> tags
            code_style = (
                "white-space: pre-wrap !important; "
                "word-wrap: break-word !important; "
                "max-width: 100%; "
                "display: inline-block; "
                "font-family: 'Courier New', monospace; "
                "font-size: 0.9em;"
            )

            # Style for <code> inside <pre>
            code_in_pre_style = (
                "white-space: pre-wrap !important; "
                "word-wrap: break-word !important; "
                "display: block; "
                "overflow-x: auto; "
                "font-family: 'Courier New', monospace;"
            )

            # Apply styles to all <pre> tags
            for pre in soup.find_all('pre'):
                existing_style = pre.get('style', '')
                pre['style'] = existing_style + pre_style

                # Apply styles to <code> inside <pre>
                for code in pre.find_all('code'):
                    existing_code_style = code.get('style', '')
                    code['style'] = existing_code_style + code_in_pre_style

            # Apply styles to standalone <code> tags (not inside <pre>)
            for code in soup.find_all('code'):
                if not code.find_parent('pre'):
                    existing_style = code.get('style', '')
                    code['style'] = existing_style + code_style

            return str(soup)

        except Exception as e:
            logger.error(f"Error processing HTML: {str(e)}", exc_info=True)
            # Return original HTML if processing fails
            return html

    @staticmethod
    def add_container_wrapper(html: str) -> str:
        """
        Wrap HTML content in a container div with proper styling

        Args:
            html: HTML content

        Returns:
            Wrapped HTML
        """
        try:
            if not html:
                return html

            container_style = (
                "max-width: 100%; "
                "overflow-x: hidden; "
                "word-wrap: break-word; "
                "padding: 1rem; "
                "box-sizing: border-box;"
            )

            wrapper = f'<div style="{container_style}">{html}</div>'
            return wrapper

        except Exception as e:
            logger.error(f"Error wrapping HTML: {str(e)}", exc_info=True)
            return html

    @staticmethod
    def fix_table_overflow(html: str) -> str:
        """
        Fix table overflow issues by making them scrollable

        Args:
            html: HTML content

        Returns:
            HTML with fixed tables
        """
        try:
            if not html:
                return html

            soup = BeautifulSoup(html, 'html.parser')

            table_wrapper_style = (
                "overflow-x: auto; "
                "max-width: 100%; "
                "margin: 1rem 0; "
                "display: block;"
            )

            table_style = (
                "max-width: 100%; "
                "border-collapse: collapse; "
                "width: 100%;"
            )

            # Wrap each table in a scrollable div
            for table in soup.find_all('table'):
                # Add style to table
                existing_table_style = table.get('style', '')
                table['style'] = existing_table_style + table_style

                # Create wrapper div
                wrapper = soup.new_tag('div', style=table_wrapper_style)
                table.wrap(wrapper)

            return str(soup)

        except Exception as e:
            logger.error(f"Error fixing table overflow: {str(e)}", exc_info=True)
            return html

    @staticmethod
    def add_responsive_styles(html: str) -> str:
        """
        Add responsive styles to prevent horizontal scroll on mobile

        Args:
            html: HTML content

        Returns:
            HTML with responsive styles
        """
        try:
            if not html:
                return html

            soup = BeautifulSoup(html, 'html.parser')

            # Style for images
            img_style = (
                "max-width: 100% !important; "
                "height: auto !important; "
                "display: block; "
                "margin: 1rem 0;"
            )

            for img in soup.find_all('img'):
                existing_style = img.get('style', '')
                img['style'] = existing_style + img_style

            # Style for iframes (videos, etc.)
            iframe_wrapper_style = (
                "position: relative; "
                "padding-bottom: 56.25%; "  # 16:9 aspect ratio
                "height: 0; "
                "overflow: hidden; "
                "max-width: 100%; "
                "margin: 1rem 0;"
            )

            iframe_style = (
                "position: absolute; "
                "top: 0; "
                "left: 0; "
                "width: 100%; "
                "height: 100%;"
            )

            for iframe in soup.find_all('iframe'):
                existing_style = iframe.get('style', '')
                iframe['style'] = existing_style + iframe_style

                # Wrap in responsive container
                wrapper = soup.new_tag('div', style=iframe_wrapper_style)
                iframe.wrap(wrapper)

            return str(soup)

        except Exception as e:
            logger.error(f"Error adding responsive styles: {str(e)}", exc_info=True)
            return html

    @staticmethod
    def process_gemini_output(html: str) -> str:
        """
        Complete processing pipeline for Gemini AI output

        Args:
            html: Raw HTML from Gemini

        Returns:
            Fully processed HTML ready for display
        """
        try:
            if not html:
                return html

            # Apply all processing steps
            html = HTMLProcessor.add_inline_styles_to_code_blocks(html)
            html = HTMLProcessor.fix_table_overflow(html)
            html = HTMLProcessor.add_responsive_styles(html)
            html = HTMLProcessor.add_container_wrapper(html)

            logger.info("Successfully processed Gemini HTML output")
            return html

        except Exception as e:
            logger.error(f"Error in HTML processing pipeline: {str(e)}", exc_info=True)
            # Return original HTML if processing fails
            return html

    @staticmethod
    def strip_dangerous_tags(html: str) -> str:
        """
        Remove potentially dangerous HTML tags for security

        Args:
            html: HTML content

        Returns:
            Sanitized HTML
        """
        try:
            if not html:
                return html

            soup = BeautifulSoup(html, 'html.parser')

            # Remove dangerous tags
            dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed']
            for tag_name in dangerous_tags:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Remove event handlers
            for tag in soup.find_all():
                # Remove all attributes starting with 'on' (onclick, onload, etc.)
                attrs_to_remove = [
                    attr for attr in tag.attrs
                    if attr.startswith('on')
                ]
                for attr in attrs_to_remove:
                    del tag[attr]

            return str(soup)

        except Exception as e:
            logger.error(f"Error sanitizing HTML: {str(e)}", exc_info=True)
            return html


# Singleton instance
html_processor = HTMLProcessor()
