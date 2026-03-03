from playwright.sync_api import sync_playwright
import os

def check_pages():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{os.path.abspath('intro_packet.html')}", wait_until="networkidle")

        # Take a screenshot of the entire document to see the flow
        page.screenshot(path="intro_packet_full_flow.png", full_page=True)

        browser.close()

if __name__ == "__main__":
    check_pages()