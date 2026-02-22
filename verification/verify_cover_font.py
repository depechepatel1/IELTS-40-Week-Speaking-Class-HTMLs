import os
from playwright.sync_api import sync_playwright

def verify_cover_font():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Get absolute path to the file
        file_path = os.path.abspath("lessons/Week_1_Lesson_Plan.html")
        url = f"file://{file_path}"

        print(f"Navigating to {url}")
        page.goto(url)

        # Select the theme title
        title_locator = page.locator(".cover-title-large")

        # Check computed style
        font_size = title_locator.evaluate("element => window.getComputedStyle(element).fontSize")
        print(f"Computed font-size: {font_size}")

        # Take a screenshot of the cover page (Page 1)
        # The cover page is the first .page element
        cover_page = page.locator(".cover-page")
        cover_page.screenshot(path="verification/cover_page_font.png")
        print("Screenshot saved to verification/cover_page_font.png")

        browser.close()

if __name__ == "__main__":
    verify_cover_font()
