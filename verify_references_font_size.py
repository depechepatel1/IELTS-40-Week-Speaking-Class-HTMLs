import asyncio
import os
from playwright.async_api import async_playwright

async def verify_font_size(html_path: str):
    print(f"Verifying font size in {html_path}...")
    file_url = f"file://{os.path.abspath(html_path)}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Get computed font size of the first li in the references section
        font_size_px = await page.evaluate('''() => {
            const el = document.querySelector('.references li');
            return window.getComputedStyle(el).fontSize;
        }''')

        await browser.close()

        # 6pt is exactly 8px (6 * 96 / 72 = 8)
        expected_px = "8px"

        if font_size_px == expected_px:
            print(f"Success! Computed font size is exactly {expected_px} (6pt).")
        else:
            print(f"Error: Computed font size is {font_size_px}, expected {expected_px} (6pt).")
            exit(1)

if __name__ == "__main__":
    html_file = "intro_packet.html"
    if not os.path.exists(html_file):
        print(f"Error: Could not find {html_file}")
        exit(1)

    asyncio.run(verify_font_size(html_file))
