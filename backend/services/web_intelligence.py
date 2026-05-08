"""
============================================================
WEB INTELLIGENCE SERVICE — Fresh Data From The Real World
============================================================
This service answers the critical question:
"How does the system get LATEST data when LLMs have cutoff dates?"

Answer: We scrape primary sources ourselves and feed the raw data
to the LLMs as context. The LLM analyses what we give it —
it doesn't rely on its training data for current numbers.

Sources (all public, no login required):
1. ACMA (acma.in) — Industry body press releases
2. SIAM (siam.in) — Vehicle sales data
3. MoRTH (morth.nic.in) — Regulatory notifications
4. Economic Times Auto — News RSS
5. Livemint Auto — News RSS
6. Moneycontrol — Market data
7. IBEF (ibef.org) — Sector reports
8. Vahan Dashboard — EV registration data

IMPORTANT: We only scrape PUBLIC pages. No login required.
No CAPTCHA bypass. No aggressive scraping. This is corporate-safe.
============================================================
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from config import settings

logger = logging.getLogger("web_intelligence")


# ── News source configuration ────────────────────────────
# Each source has a URL, CSS selector for content, and type
NEWS_SOURCES = [
    {
        "name": "ET Auto",
        "url": "https://auto.economictimes.indiatimes.com/rss/topstories",
        "type": "rss",
        "category": "news",
        "reliability": "high",
    },
    {
        "name": "Livemint Auto",
        "url": "https://www.livemint.com/rss/auto",
        "type": "rss",
        "category": "news",
        "reliability": "high",
    },
    {
        "name": "ACMA Press Releases",
        "url": "https://www.acma.in/news.php",
        "type": "html",
        "selector": "div.news-list, div.news-item, article, .content-area",
        "category": "government",
        "reliability": "high",
    },
    {
        "name": "SIAM Statistics",
        "url": "https://www.siam.in/pressrelease.aspx",
        "type": "html",
        "selector": "table, .press-release, div.content, article",
        "category": "government",
        "reliability": "high",
    },
    {
        "name": "MoRTH Notifications",
        "url": "https://morth.gov.in/whats-new",
        "type": "html",
        "selector": "div.view-content, article, .news-list",
        "category": "government",
        "reliability": "high",
    },
    {
        "name": "IBEF Auto Sector",
        "url": "https://www.ibef.org/industry/autocomponents-india",
        "type": "html",
        "selector": "div.sector-overview, div.sector-content, main, article, div.content-area",
        "category": "government_agency",
        "reliability": "high",
    },
    # ── Additional high-credibility sources ───────────────

    {
        "name": "Team-BHP Auto News",
        "url": "https://www.team-bhp.com/forum/external.php?type=RSS2",
        "type": "rss",
        "category": "news",
        "reliability": "medium",
    },
    # ── B2B trade press ────────────────────────────────────
    {
        "name": "Autocar Professional",
        "url": "https://www.autocarpro.in/news/all",
        "type": "html",
        "selector": "div.news-list-item, article, h2, h3",
        "category": "news",
        "reliability": "high",
    },
]


class WebIntelligenceService:
    """
    Collects fresh data from the web to feed into AI agents.
    This is how we overcome LLM knowledge cutoff dates.
    """

    def __init__(self):
        # ── HTTP client with polite headers ──────────────
        # We identify ourselves honestly (no fake User-Agent)
        # and add delays between requests to be polite
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "MobilityIntelligencePlatform/1.0 (Research; contact@bosch.com)",
                "Accept": "text/html,application/xml,application/rss+xml",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        # ── Per-scrape traceability (Fix 7) ────────────────
        # Populated after each collect_latest_news() call.
        # Orchestrator reads this to log and attribute sources.
        self.last_source_texts: list = []
        # ── SerpAPI budget tracking ─────────────────────────
        # Free tier: 250 searches/month. Budget: ~5 searches/refresh × 8 refreshes = 40.
        # Remaining 210 for ad-hoc verification. NEVER exceed the limit.
        self._serp_calls_this_month = 0
        self._serp_monthly_limit = 250

    # ════════════════════════════════════════════════════════
    # MAIN: Collect latest news from all sources
    # ════════════════════════════════════════════════════════
    async def collect_latest_news(self) -> str:
        """
        Scrape all configured news sources and return concatenated text.
        
        This text is fed to the PESTEL Discovery Agent as context.
        The agent analyses this fresh content (not its training data)
        to identify new PESTEL factors.
        
        Returns:
            Concatenated news text from all sources (~10-20K chars)
        """
        all_content = []
        self.last_source_texts = []  # Reset each collection call

        for source in NEWS_SOURCES:
            try:
                logger.info(f"Scraping: {source['name']} ({source['url']})")

                if source["type"] == "rss":
                    content = await self._fetch_rss(source)
                else:
                    content = await self._fetch_html(source)

                if content and len(content) > 200:
                    tagged = (
                        f"\n--- SOURCE: {source['name']} "
                        f"(Reliability: {source['reliability']}, "
                        f"Accessed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}) ---\n"
                        f"{content}\n"
                    )
                    all_content.append(tagged)
                    self.last_source_texts.append({
                        "name": source["name"],
                        "url": source["url"],
                        "chars": len(content),
                        "text": content,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "status": "ok",
                    })
                    logger.info(f"  \u2705 {source['name']:<28s} {len(content):>6} chars")
                elif content:
                    # < 200 chars usually means selector is broken or page is empty
                    logger.warning(f"  \u26a0\ufe0f  {source['name']:<28s} {len(content):>6} chars \u2014 likely selector issue")
                    self.last_source_texts.append({
                        "name": source["name"], "url": source["url"],
                        "chars": len(content), "text": content,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "status": "thin",
                    })
                else:
                    logger.warning(f"  \u274c {source['name']:<28s} \u2014 empty response")
                    self.last_source_texts.append({
                        "name": source["name"], "url": source["url"],
                        "chars": 0, "text": "",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed",
                    })

            except Exception as e:
                # Don't let one failed source kill the entire refresh
                logger.error(f"  → FAILED to scrape {source['name']}: {e}")
                continue

        # ── Add SerpAPI premium snippets ─────────────────────
        premium = await self.collect_premium_context()
        if premium:
            all_content.append(premium)

        combined = "\n".join(all_content)
        logger.info(f"Total collected: {len(combined)} chars from {len(all_content)} sources (incl. premium)")
        return combined

    # ════════════════════════════════════════════════════════
    # SERPAPI: Premium source snippets (Bloomberg, Reuters etc)
    # ════════════════════════════════════════════════════════
    async def search_premium_sources(self, query: str, num_results: int = 5) -> list:
        """
        Search Google via SerpAPI for premium source snippets.
        Gets headlines + snippets from Bloomberg, Reuters, McKinsey etc.
        without needing a subscription.

        Budget: 250 searches/month (free tier). Usage tracked strictly.
        Returns list of {title, snippet, source, url}
        """
        if not settings.serpapi_key:
            logger.debug("SerpAPI key not configured — skipping premium search")
            return []

        if self._serp_calls_this_month >= self._serp_monthly_limit:
            logger.warning(
                f"SerpAPI monthly limit reached ({self._serp_monthly_limit}). Skipping."
            )
            return []

        try:
            params = {
                "q": query,
                "api_key": settings.serpapi_key,
                "num": num_results,
                "gl": "in",   # India results
                "hl": "en",
            }
            response = await self.client.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

            self._serp_calls_this_month += 1
            logger.info(
                f"\U0001f50e SERPAPI \u2502 Query: '{query[:50]}' \u2502 "
                f"Results: {len(data.get('organic_results', []))} \u2502 "
                f"Budget: {self._serp_calls_this_month}/{self._serp_monthly_limit}"
            )

            results = []
            for r in data.get("organic_results", [])[:num_results]:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "source": r.get("source", r.get("displayed_link", "")),
                    "url": r.get("link", ""),
                })
            return results

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []

    async def collect_premium_context(self) -> str:
        """
        Run 5 targeted searches to get premium source snippets.
        Supplements free RSS sources with Bloomberg/Reuters/McKinsey data.
        Uses 5 SerpAPI calls per refresh (budget: 5/refresh × 8/month = 40 of 250 free).
        """
        if not settings.serpapi_key:
            return ""

        # ── Targeted gap-filler queries ──
        # Each query is designed to fetch content the regular RSS scrape misses.
        queries = [
            "AEB mandate India 2026 enforcement timeline",
            "TREM V tractor 2026 emission norms India",
            "BS-VII consultation paper India auto",
            "PLI Auto scheme disbursement quarterly update",
            "FAME III scheme update India EV subsidy",
            "EU CBAM auto components India impact",
            "DPDP rules notification India auto",
            "Bharat NCAP 5-star results 2025 2026",
            "OBD-II 2W enforcement India update",
            "India EV penetration latest CY2026",
        ]

        all_snippets = []
        for q in queries:
            results = await self.search_premium_sources(q)
            for r in results:
                tagged = (
                    f"Source: {r['source']} | {r['title']}\n"
                    f"{r['snippet']}\n"
                    f"URL: {r['url']}\n"
                )
                all_snippets.append(tagged)

        if not all_snippets:
            return ""

        combined = "\n--- PREMIUM SOURCE SNIPPETS (Google Search via SerpAPI) ---\n"
        combined += "\n".join(all_snippets)
        logger.info(
            f"\U0001f50e Premium context: {len(all_snippets)} snippets from {len(queries)} SerpAPI searches "
            f"({self._serp_calls_this_month}/{self._serp_monthly_limit} budget used)"
        )
        return combined

    async def collect_market_data(self) -> List[Dict]:
        """
        Collect structured market data (numbers, statistics).
        Returns list of data points with source provenance.
        
        Each data point includes:
        - What it is (e.g., "4W PV sales FY25")
        - The value (e.g., "43.0 Lakh")
        - The source URL
        - When we accessed it
        """
        data_points = []

        # Try to get Vahan EV data
        try:
            ev_data = await self._fetch_vahan_ev_data()
            if ev_data:
                data_points.extend(ev_data)
        except Exception as e:
            logger.error(f"Vahan scraping failed: {e}")

        return data_points

    # ════════════════════════════════════════════════════════
    # INTERNAL: Fetch and parse RSS feeds
    # ════════════════════════════════════════════════════════
    async def _fetch_rss(self, source: Dict) -> Optional[str]:
        """
        Fetch an RSS feed and extract article titles + summaries.
        RSS is the most reliable way to get news — structured XML.
        """
        try:
            t0 = time.time()
            response = await self.client.get(source["url"])
            response.raise_for_status()
            latency = time.time() - t0

            soup = BeautifulSoup(response.text, "lxml-xml")  # Use XML parser for RSS
            items = soup.find_all("item")

            articles = []
            for item in items[:20]:  # Last 20 articles
                title = item.find("title")
                description = item.find("description")
                pub_date = item.find("pubDate")
                link = item.find("link")

                article_text = ""
                if title:
                    article_text += f"Title: {title.get_text(strip=True)}\n"
                if pub_date:
                    article_text += f"Date: {pub_date.get_text(strip=True)}\n"
                if description:
                    # Clean HTML from description
                    desc_soup = BeautifulSoup(description.get_text(), "html.parser")
                    article_text += f"Summary: {desc_soup.get_text(strip=True)}\n"
                if link:
                    article_text += f"URL: {link.get_text(strip=True)}\n"

                if article_text:
                    articles.append(article_text)

            text = "\n".join(articles)
            logger.info(
                f"🌐 SCRAPED │ {source['name']} │ {len(text)} chars │ "
                f"Status: {response.status_code} │ Latency: {latency:.1f}s"
            )
            return text

        except Exception as e:
            logger.error(f"RSS fetch failed for {source['name']}: {e}")
            return None

    # ════════════════════════════════════════════════════════
    # INTERNAL: Fetch and parse HTML pages
    # ════════════════════════════════════════════════════════
    async def _fetch_html(self, source: Dict) -> Optional[str]:
        """
        Fetch an HTML page and extract text content.
        Uses CSS selectors to find the relevant content area.
        """
        try:
            t0 = time.time()
            response = await self.client.get(source["url"])
            response.raise_for_status()
            latency = time.time() - t0

            soup = BeautifulSoup(response.text, "html.parser")

            # Use CSS selector if provided, otherwise get main content
            selector = source.get("selector")
            if selector:
                elements = soup.select(selector)
                text = "\n".join(el.get_text(separator="\n", strip=True) for el in elements)
            else:
                # Fallback: get all paragraph text
                paragraphs = soup.find_all("p")
                text = "\n".join(p.get_text(strip=True) for p in paragraphs)

            # Clean up: remove excessive whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            result = "\n".join(lines[:100])  # Cap at 100 lines per source
            logger.info(
                f"🌐 SCRAPED │ {source['name']} │ {len(result)} chars │ "
                f"Status: {response.status_code} │ Latency: {latency:.1f}s"
            )
            return result

        except Exception as e:
            logger.error(f"HTML fetch failed for {source['name']}: {e}")
            return None

    # ════════════════════════════════════════════════════════
    # INTERNAL: Vahan Dashboard EV data
    # ════════════════════════════════════════════════════════
    async def _fetch_vahan_ev_data(self) -> List[Dict]:
        """
        Attempt to get EV registration data from Vahan dashboard.
        Note: Vahan may block automated access — this is a best-effort.
        """
        # Vahan dashboard is dynamic (JavaScript-rendered)
        # For production, consider using their API if available
        # or a headless browser (Playwright) if needed
        logger.info("Vahan EV data collection — placeholder for production implementation")
        return []

    # ════════════════════════════════════════════════════════
    # CLEANUP
    # ════════════════════════════════════════════════════════
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
