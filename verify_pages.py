from playwright.sync_api import sync_playwright
import os

def check_pages():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{os.path.abspath('intro_packet.html')}", wait_until="networkidle")

        # Get number of pages
        pages = page.locator('.page').all()
        print(f"Found {len(pages)} pages.")

        for i, p_loc in enumerate(pages):
            p_loc.screenshot(path=f"intro_packet_page_{i+1}.png")

        browser.close()

if __name__ == "__main__":
    check_pages()