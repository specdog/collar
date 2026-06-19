"""
Tests for output-stripper.py — regex-based filler removal.
"""
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).parent.parent / "skills" / "intelligence-engine" / "scripts"
STRIPPER = str(SCRIPTS / "output-stripper.py")


def run_stripper(text: str) -> str:
    r = subprocess.run(
        ["python3", STRIPPER], input=text,
        capture_output=True, text=True, timeout=5
    )
    return r.stdout.strip()


class TestSelfTalk:
    def test_i_should_stripped(self):
        result = run_stripper("I should check the config first.\n\nThe actual content.")
        assert "I should" not in result
        assert "actual content" in result

    def test_let_me_stripped(self):
        result = run_stripper("Let me verify this.\n\nReal content here.")
        assert "Let me" not in result
        assert "Real content" in result

    def test_i_notice_stripped(self):
        result = run_stripper("I notice the pattern.\n\nThe data shows otherwise.")
        assert "I notice" not in result
        assert "data shows" in result

    def test_i_think_stripped(self):
        result = run_stripper("I think this works.\n\nHere is the result.")
        assert "I think" not in result
        assert "result" in result

    def test_instructional_first_preserved(self):
        """'First, ...' is instructional, not filler — must survive."""
        result = run_stripper("First, install the package with pip.\n\nThen configure the API key.")
        assert "First, install" in result
        assert "Then configure" in result

    def test_content_after_filler_preserved(self):
        """Lines after filler lines must survive."""
        result = run_stripper("I should check.\n\nThe memory system stores facts.\nI notice the recall is simple.\n\nKey insight: it works.")
        assert "memory system stores facts" in result
        assert "Key insight: it works" in result
        assert "I should" not in result
        assert "I notice" not in result

    def test_midword_period_not_stripped(self):
        """Periods in words like .dag must not trigger stripping."""
        result = run_stripper("I should check the .dag files.\n\nThe actual output.")
        assert "I should" not in result
        assert "actual output" in result


class TestPoliteness:
    def test_certainly_stripped(self):
        result = run_stripper("Certainly!\n\nHere is the data.")
        assert "Certainly" not in result
        assert "data" in result

    def test_of_course_stripped(self):
        result = run_stripper("Of course!\n\nThe answer is 42.")
        assert "Of course" not in result
        assert "42" in result

    def test_polite_with_content_kept(self):
        """'Certainly! Let me help.' has content — keep it."""
        result = run_stripper("Certainly! Let me help with the task.\n\nData follows.")
        assert "Let me help" in result  # "Let me" here is NOT standalone
        assert "Data follows" in result


class TestMarkdown:
    def test_bold_stripped(self):
        result = run_stripper("This is **important** content.")
        assert "**" not in result
        assert "important" in result

    def test_italic_stripped(self):
        result = run_stripper("This is *emphasized* text.")
        assert "*" not in result
        assert "emphasized" in result

    def test_header_stripped(self):
        result = run_stripper("## Section\n\nContent here.")
        assert "##" not in result
        assert "Section" in result
        assert "Content" in result

    def test_bold_content_preserved(self):
        """The text inside markdown must survive."""
        result = run_stripper("**critical path** must be preserved.")
        assert "critical path" in result


class TestWhitespace:
    def test_excessive_newlines_collapsed(self):
        result = run_stripper("Line one\n\n\n\nLine two")
        assert "\n\n\n" not in result

    def test_leading_trailing_stripped(self):
        result = run_stripper("\n\n  Content  \n\n")
        assert result == "Content"


class TestSavings:
    def test_typical_reply(self):
        text = (
            "I should verify the pipeline first.\n\n"
            "Certainly!\n\n"
            "The output stripper is active and working correctly.\n"
            "It removes filler text before history storage.\n\n"
            "I notice that savings are significant.\n\n"
            "This means **fewer tokens** per turn.\n"
        )
        result = run_stripper(text)
        assert len(result) < len(text)
        assert "output stripper" in result
        assert "**" not in result  # markdown stripped
        # "fewer tokens" was in a "This means..." line → correctly stripped

    def test_no_false_positive(self):
        """Text without filler should pass through unchanged (except markdown)."""
        text = "The memory system stores facts in JSON format.\nIt uses keyword matching."
        result = run_stripper(text)
        assert "memory system" in result
        assert "keyword matching" in result
        assert len(result) <= len(text)

    def test_code_blocks_preserved(self):
        """Content inside ``` code blocks must never be stripped."""
        text = (
            "Here is the fix:\n\n"
            "I should check something outside.\n\n"
            "```python\n"
            "I should not strip this line inside code.\n"
            "def check():\n"
            "    return True\n"
            "```\n\n"
            "Apply this patch."
        )
        result = run_stripper(text)
        assert "I should not strip this line inside code" in result
        assert "def check():" in result
        assert "Apply this patch" in result
        assert "I should check something outside" not in result

    def test_tilde_code_blocks_preserved(self):
        """Content inside ~~~ code blocks must never be stripped."""
        text = (
            "I should check this first.\n\n"
            "~~~python\n"
            "I should not strip inside tilde blocks.\n"
            "print('hello')\n"
            "~~~\n\n"
            "Back to normal."
        )
        result = run_stripper(text)
        assert "I should not strip inside tilde blocks" in result
        assert "print('hello')" in result
        assert "Back to normal" in result
        assert "I should check this first" not in result

    def test_urls_paths_preserved(self):
        """URLs and file paths must survive stripping."""
        text = (
            "I should verify the path.\n\n"
            "The file is at /Users/dico/collar/agent/prompt_builder.py\n"
            "See https://github.com/specdog/collar/pull/75\n"
        )
        result = run_stripper(text)
        assert "/Users/dico" in result
        assert "github.com" in result
        assert "I should" not in result
        assert len(result) <= len(text)
