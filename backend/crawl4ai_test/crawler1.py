import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy


# Configure the strategy
strategy = BFSDeepCrawlStrategy(
    max_depth=2,  # Explorer jusqu'à 2 niveaux de profondeur
    include_external=False,  # Ne pas sortir du domaine
    max_pages=3,  # Limiter à 10 pages au total
)

load_more_js = [
    # Scroller en bas de page
    "window.scrollTo(0, document.body.scrollHeight);",
    # Cliquer sur un bouton 'Afficher plus d'offres' si présent
    "document.querySelector('button, a').textContent.includes('Afficher_plus') && document.querySelector('button, a').click();",
    # Cliquer sur le bouton de pagination pour aller à la page 2
    "Array.from(document.querySelectorAll('a, button')).find(el => el.textContent.trim() === '2')?.click();",
]

run_config = CrawlerRunConfig(
    js_code=load_more_js,
    word_count_threshold=10,  # Minimum words per content block
    exclude_external_links=False,  # Remove external links
    remove_overlay_elements=True,  # Remove popups/modals
    process_iframes=True,  # Process iframe content
)


async def main():
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun(
            "https://www.hellowork.com/fr-fr/emploi/metier_data-scientist-departement_rhone-69.html",
            config=run_config,
        )

        # Process the result
        print("Crawling succeeded!")
        print(f"Crawled {len(results)} pages in total")
        print("\n\n")

        for i, result in enumerate(results):
            print(f"\n--- Page {i+1}/{len(results)} ---")
            print(f"URL: {result.url}")
            print(f"Depth: {result.metadata.get('depth', 0)}")
            print(f"Content preview: {result.html}")  # Show preview of content


if __name__ == "__main__":
    asyncio.run(main())
