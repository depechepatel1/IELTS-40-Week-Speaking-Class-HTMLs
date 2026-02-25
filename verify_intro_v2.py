
from playwright.sync_api import sync_playwright
import os

def verify_intro_packet():
    cwd = os.getcwd()
    file_path = f"file://{cwd}/intro_packet.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Navigating to {file_path}")
        page.goto(file_path)

        # Verify title
        title = page.title()
        print(f"Page title: {title}")
        assert "IELTS Speaking Mastery" in title

        # Verify content presence
        content = page.content()
        assert "Welcome to IELTS Speaking Mastery" in content
        assert "Google Gemini" in content
        assert "核心优势" in content

        # Take a full page screenshot to verify layout
        # We need to ensure the viewport is large enough or full_page=True
        screenshot_path = "intro_packet_v2_full.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    verify_intro_packet()
