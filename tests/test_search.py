import httpx

from app.services.search import NullSearchService, WikipediaSearchService

UA = "test-agent/1.0 (https://example.org)"


async def test_null_search_returns_nothing():
    assert await NullSearchService().search("anything") == []


async def test_wikipedia_search_parses_results_and_strips_html():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers["user-agent"]
        seen["query"] = request.url.params["srsearch"]
        return httpx.Response(200, json={"query": {"search": [
            {"title": "Guido van Rossum", "snippet": '<span class="searchmatch">Guido</span> &amp; Python'},
        ]}})

    service = WikipediaSearchService(user_agent=UA, transport=httpx.MockTransport(handler))
    sources = await service.search("Python was created by Guido van Rossum")
    assert seen == {"ua": UA, "query": "Python was created by Guido van Rossum"}
    assert sources[0].title == "Guido van Rossum"
    assert sources[0].url == "https://en.wikipedia.org/wiki/Guido_van_Rossum"
    assert sources[0].snippet == "Guido & Python"


async def test_wikipedia_search_failure_degrades_to_empty():
    service = WikipediaSearchService(user_agent=UA,
                                     transport=httpx.MockTransport(lambda r: httpx.Response(403, text="no")))
    assert await service.search("x") == []
