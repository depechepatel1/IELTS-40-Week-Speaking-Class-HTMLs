import os
import sys
from playwright.sync_api import sync_playwright

def batch_convert(input_dir="."):
    """
    Finds all Week_*.html files and converts them to PDF.
    """
    html_files = [f for f in os.listdir(input_dir) if f.startswith("Week_") and f.endswith(".html")]
    html_files.sort() # Process in order
    
    if not html_files:
        print("No HTML files found.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        
        for html_file in html_files:
            pdf_file = html_file.replace(".html", ".pdf")
            html_path = os.path.join(input_dir, html_file)
            pdf_path = os.path.join(input_dir, pdf_file)
            
            print(f"Converting {html_file} -> {pdf_file}...")
            
            try:
                page = context.new_page()
                page.goto(f"file://{os.path.abspath(html_path)}", wait_until="networkidle")
                
                page.pdf(
                    path=pdf_path,
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
                )
                page.close()
                print("Done.")
            except Exception as e:
                print(f"Failed to convert {html_file}: {e}")

        browser.close()

if __name__ == "__main__":
    batch_convert()
