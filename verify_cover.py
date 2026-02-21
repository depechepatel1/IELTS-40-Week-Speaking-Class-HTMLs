from playwright.sync_api import sync_playwright
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Load the local HTML file
        file_path = os.path.abspath("Week_2_Lesson_Plan.html")
        page.goto(f"file://{file_path}")

        # Take a screenshot of the first page (Cover Page)
        # The cover page is the first page. A4 size is roughly 800x1100 px at default DPI, but let's just capture the viewport.
        # We can set viewport to A4 ratio.
        page.set_viewport_size({"width": 794, "height": 1123}) # 96 DPI A4

        # Wait a bit for the image to load
        page.wait_for_timeout(1000)

        # Screenshot
        screenshot_path = "verification_cover.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    run()
