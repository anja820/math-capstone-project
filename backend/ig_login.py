import asyncio
from playwright.async_api import async_playwright
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "pw_ig_session")
SESSION_DIR = "pw_ig_session"

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  # must be visible so you can log in
        )
        page = await context.new_page()
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")

        print("\n✅ Log in in the opened window.")
        print("✅ When you see IG home/feed, come back here and press Enter.\n")
        input("Press Enter to save session and close...")

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
