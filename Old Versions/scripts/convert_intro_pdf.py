import asyncio
import os
from playwright.async_api import async_playwright

async def generate_pdf(html_path: str, output_pdf: str):
    print(f"Loading {html_path}...")
    
    # Resolve absolute file path for local loading
    file_url = f"file://{os.path.abspath(html_path)}"
    
    async with async_playwright() as p:
        # Launch Chromium headless for exact rendering
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Go to HTML file and wait for network idle to ensure fonts/images load
        await page.goto(file_url, wait_until="networkidle")
        
        print("Generating PDF...")
        # Generate the PDF with precise A4 dimensions and no margins
        # 'print_background=True' is crucial for retaining the cover image and pastel boxes
        await page.pdf(
            path=output_pdf,
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True  # Respects the @page CSS rule from the HTML
        )
        
        await browser.close()
    
    print(f"Success! PDF saved to {output_pdf}")

if __name__ == "__main__":
    html_file = "intro_packet.html"
    pdf_file = "intro_packet.pdf"
    
    if not os.path.exists(html_file):
        print(f"Error: Could not find {html_file}")
    else:
        asyncio.run(generate_pdf(html_file, pdf_file))
