import os
from playwright.sync_api import sync_playwright

def verify_week_1_html():
    file_path = os.path.abspath("lessons/Week_1_Lesson_Plan.html")
    url = f"file://{file_path}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Take full screenshot
        page.screenshot(path="verification/week_1_full.png", full_page=True)
        print("Screenshot saved to verification/week_1_full.png")

        browser.close()

if __name__ == "__main__":
    verify_week_1_html()
