from playwright.sync_api import sync_playwright
import os

def convert_html_to_pdf(html_path, pdf_path):
    print(f"Converting {html_path} to {pdf_path}...")

    # Ensure absolute path
    abs_html_path = os.path.abspath(html_path)
    file_url = f"file://{abs_html_path}"

    with sync_playwright() as p:
        # Launch browser headless
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the HTML file
        # wait_until="networkidle" ensures images (like the cover) are fully loaded
        page.goto(file_url, wait_until="networkidle")

        # Generate the PDF
        # We rely on the CSS @page rules (A4) and remove Playwright's default margins
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True
        )

        browser.close()

    print("Conversion complete!")

if __name__ == "__main__":
    html_file = "intro_packet.html"
    pdf_file = "intro_packet.pdf"

    if os.path.exists(html_file):
        convert_html_to_pdf(html_file, pdf_file)
    else:
        print(f"Error: {html_file} not found.")
