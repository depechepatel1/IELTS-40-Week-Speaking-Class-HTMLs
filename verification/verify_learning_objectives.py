from playwright.sync_api import sync_playwright
import os

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Absolute path to the file
        cwd = os.getcwd()
        filepath = f"file://{cwd}/lessons/Week_1_Lesson_Plan.html"

        print(f"Navigating to {filepath}")
        page.goto(filepath)

        # Take a screenshot of Page 3 (Lesson 1 Teacher Plan)
        # We need to find the card containing "Learning Objectives" on Page 3
        # Page 3 is the 3rd .page element (index 2) if layout holds:
        # P1: Cover, P2: Notes, P3: Teacher L1

        pages = page.locator(".page")
        if pages.count() >= 3:
            page3 = pages.nth(2)
            p3_output = "verification/week1_learning_objectives_l1.png"
            page3.screenshot(path=p3_output)
            print(f"Page 3 screenshot saved to {p3_output}")

        # Take a screenshot of Page 4 (Teacher Lesson Plan L2)
        # Assuming P4 is index 3
        if pages.count() >= 4:
            page4 = pages.nth(5) # Actually L2 Teacher Plan is usually Page 4 or 5?
            # Let's search by text content to be sure.
            l2_headers = page.locator(".header-bar .week-tag").filter(has_text="Lesson 2")
            if l2_headers.count() > 0:
                # Get the page container of this header
                l2_page = l2_headers.first.locator("xpath=../../..") # Ancestor page div
                p4_output = "verification/week1_learning_objectives_l2.png"
                l2_page.screenshot(path=p4_output)
                print(f"L2 Teacher Plan screenshot saved to {p4_output}")

        browser.close()

if __name__ == "__main__":
    run()
