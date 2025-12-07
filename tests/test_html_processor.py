"""
Test Cases for HTML Processor
"""
import pytest
from app.services.html_processor import html_processor


class TestHTMLProcessor:
    """Test HTML processing for preventing horizontal scroll"""

    def test_add_styles_to_pre_tags(self):
        """Test adding styles to <pre> tags"""
        html = "<pre><code>public class A { }</code></pre>"

        result = html_processor.add_inline_styles_to_code_blocks(html)

        assert 'white-space: pre-wrap' in result
        assert 'word-wrap: break-word' in result
        assert 'overflow-x: auto' in result

    def test_add_styles_to_code_tags(self):
        """Test adding styles to standalone <code> tags"""
        html = "<p>This is <code>inline code</code> example</p>"

        result = html_processor.add_inline_styles_to_code_blocks(html)

        assert 'white-space: pre-wrap' in result
        assert 'word-wrap: break-word' in result

    def test_long_code_without_spaces(self):
        """Test handling of long code without spaces"""
        long_code = "a" * 200  # Very long line
        html = f"<pre><code>{long_code}</code></pre>"

        result = html_processor.add_inline_styles_to_code_blocks(html)

        # Check that wrap styles are applied
        assert 'white-space: pre-wrap' in result
        assert 'word-wrap: break-word' in result
        # Original content should be preserved
        assert long_code in result

    def test_fix_table_overflow(self):
        """Test table overflow fix"""
        html = """
        <table>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </table>
        """

        result = html_processor.fix_table_overflow(html)

        # Should wrap table in div with overflow-x
        assert 'overflow-x: auto' in result
        assert '<div' in result
        assert '<table' in result

    def test_responsive_images(self):
        """Test adding responsive styles to images"""
        html = '<img src="test.jpg">'

        result = html_processor.add_responsive_styles(html)

        assert 'max-width: 100%' in result
        assert 'height: auto' in result

    def test_complete_processing_pipeline(self):
        """Test complete processing pipeline"""
        html = """
        <h1>Test</h1>
        <pre><code>public class VeryLongClassNameThatWouldCauseHorizontalScrollIfNotWrapped {
    public static void main(String[] args) {
        System.out.println("This is a very long line of code that should wrap");
    }
}</code></pre>
        <table>
            <tr><td>Data</td></tr>
        </table>
        <img src="test.jpg">
        """

        result = html_processor.process_gemini_output(html)

        # Check all fixes are applied
        assert 'white-space: pre-wrap' in result  # Code blocks fixed
        assert 'overflow-x: auto' in result  # Tables fixed
        assert 'max-width: 100%' in result  # Images fixed
        assert '<div' in result  # Container wrapper added

    def test_empty_html(self):
        """Test handling of empty HTML"""
        html = ""

        result = html_processor.process_gemini_output(html)

        assert result == ""

    def test_none_html(self):
        """Test handling of None"""
        html = None

        result = html_processor.process_gemini_output(html)

        assert result is None

    def test_persian_text_in_code(self):
        """Test handling of Persian text in code blocks"""
        html = """
        <pre><code>// این یک کامنت فارسی است
public class A {
    // متن فارسی در کد
}</code></pre>
        """

        result = html_processor.add_inline_styles_to_code_blocks(html)

        # Persian text should be preserved
        assert 'این یک کامنت فارسی است' in result
        assert 'متن فارسی در کد' in result
        # Styles should be applied
        assert 'white-space: pre-wrap' in result

    def test_nested_code_blocks(self):
        """Test handling of nested code structures"""
        html = """
        <div>
            <pre><code>outer code</code></pre>
            <p>text <code>inline</code></p>
        </div>
        """

        result = html_processor.add_inline_styles_to_code_blocks(html)

        # Both code blocks should have styles
        assert result.count('white-space: pre-wrap') >= 2

    def test_malformed_html(self):
        """Test handling of malformed HTML"""
        html = "<pre><code>test</pre>"  # Missing closing tag

        # Should not crash
        result = html_processor.process_gemini_output(html)

        assert result is not None
        assert 'test' in result

    def test_strip_dangerous_tags(self):
        """Test removal of dangerous tags"""
        html = """
        <p>Safe content</p>
        <script>alert('xss')</script>
        <p onclick="dangerous()">Click me</p>
        """

        result = html_processor.strip_dangerous_tags(html)

        # Script should be removed
        assert '<script>' not in result
        assert "alert('xss')" not in result
        # onclick should be removed
        assert 'onclick' not in result
        # Safe content should remain
        assert 'Safe content' in result
        assert 'Click me' in result

    def test_real_world_example(self):
        """Test with real-world example from user"""
        html = """
        <pre><code>public class A {    public A() {        System.out.println("Hi");    }}</code></pre>
        """

        result = html_processor.process_gemini_output(html)

        # Should have wrap styles
        assert 'white-space: pre-wrap' in result
        assert 'word-wrap: break-word' in result
        # Content preserved
        assert 'public class A' in result
        assert 'System.out.println' in result
