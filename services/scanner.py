import logging
import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page, Request

logger = logging.getLogger(__name__)

class ScannerService:
    def __init__(self):
        pass

    async def scan_url(self, url: str) -> list[str]:
        """
        Visits the URL using a headless browser and returns a list of unique domains 
        that were requested during the page load.
        """
        if not url.startswith('http'):
            url = f'https://{url}'

        domains = set()

        def handle_request(request: Request):
            try:
                parsed = urlparse(request.url)
                if parsed.netloc:
                   domains.add(parsed.netloc)
            except Exception:
                pass

        logger.info(f"Starting scan for {url}")
        
        async with async_playwright() as p:
            # Launch browser
            # args=['--no-sandbox'] is often needed in Docker environments
            browser = await p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            try:
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Subscribe to network requests
                page.on("request", handle_request)
                
                try:
                    # Navigate and wait for network to be largely idle
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    
                    # Scroll down to trigger lazy loading (optional but good for modern sites)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2) # Wait for lazy loads
                    
                except Exception as e:
                    logger.warning(f"Error during page load/navigation: {e}")
                    # We still proceed with whatever domains we caught
                
            finally:
                await browser.close()
                
        logger.info(f"Scan finished. Found {len(domains)} domains.")
        return sorted(list(domains))
