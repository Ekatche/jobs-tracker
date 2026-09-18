import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def generate_cv_pdf(html_content: str) -> bytes:
    """
    Render a self-contained HTML CV into high-fidelity European A4 vector PDF
    using Playwright headless Chromium.
    """
    logger.info("Starting headless Chromium for CV PDF generation")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            viewport={"width": 1200, "height": 1600},
            device_scale_factor=2,
        )
        page = await context.new_page()

        try:
            # Load HTML content
            await page.set_content(html_content, wait_until="networkidle", timeout=15000)
        except Exception:
            # Fallback to load event if networkidle times out (e.g. fonts hanging)
            await page.set_content(html_content, wait_until="load", timeout=15000)

        # Generate vector A4 PDF respecting page CSS
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )

        await page.close()
        await context.close()
        await browser.close()
        logger.info(f"Successfully generated vector CV PDF ({len(pdf_bytes)} bytes)")
        return pdf_bytes
