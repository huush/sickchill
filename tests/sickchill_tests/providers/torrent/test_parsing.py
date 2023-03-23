"""
Test Provider Result Parsing
"""

import re
import sys
import unittest
from functools import wraps

import pytest
import validators

import sickchill.oldbeard.providers
from sickchill import movies, settings

pytest.skip(allow_module_level=True)

settings.CPU_PRESET = "NORMAL"


disabled_provider_tests = {
    # ???
    "Cpasbien": ["rss", "episode", "season"],
    "SkyTorrents": ["rss", "episode", "season", "cache", "result"],
    "ilCorsaroNero": ["rss"],
    # api_maintenance still
    "TorrentProject": ["rss", "episode", "season", "cache", "result"],
    # Have to trick it into thinking is an anime search, and add string overrides
    "TokyoToshokan": ["rss", "episode", "season"],
    "LimeTorrents": ["rss", "episode", "season"],
    "KickAssTorrents": ["rss", "episode", "season", "cache", "result"],
    "Torrentz": ["rss", "episode", "season", "cache", "result"],
    "ThePirateBay": ["rss", "episode", "season", "cache", "result"],
    "EZTV": ["rss", "episode", "season", "cache", "result"],
    "Rarbg": ["season", "episode", "rss", "movie"],
    # Demonoid is onion only now
    "Demonoid": ["rss", "episode", "season", "cache", "result"],
    # HorribleSubs needs rewritten
    "HorribleSubs": ["rss", "episode", "season", "cache", "result"],
    "Nyaa": ["rss"],
}

test_string_overrides = {
    "Cpasbien": {"Episode": ["The 100 S07E08"], "Season": ["The 100 S06"]},
    "Torrent9": {"Episode": ["Power Book IV Force S01E01"], "Season": ["The Lost Symbol S01"]},
    "Nyaa": {"Episode": ["Fairy Tail S2"], "Season": ["Fairy Tail S2"]},
    "TokyoToshokan": {"Episode": ["Fairy Tail S2"], "Season": ["Fairy Tail S2"]},
    "HorribleSubs": {"Episode": ["Fairy Tail S2"], "Season": ["Fairy Tail S2"]},
    "Demonoid": {"Episode": ["Star Trek Picard S01E04"], "Season": ["Locke and Key 2020 S01"]},
    "ilCorsaroNero": {"Episode": ["The 100 S06E02"]},
    "Rarbg": {"Season": ["Person of Interest S02"], "Episode": ["WandaVision S01E09"]},
}

magnet_regex = re.compile(r"magnet:\?xt=urn:btih:\w{32,40}(:?&dn=[\w. %+-]+)*(:?&tr=(:?tcp|https?|udp)[\w%. +-]+)*")


class BaseParser(type):
    class TestCase(unittest.TestCase):
        provider = None

        def __init__(self, test):
            """Initialize the test suite"""
            super().__init__(test)

            self.provider.session.verify = True
            settings.SSL_VERIFY = True

            self.provider.username = self.username
            self.provider.password = self.password
            settings.movie_list = movies.MovieList()

        @property
        def username(self):
            # TODO: Make this read usernames from somewhere
            return ""

        @property
        def password(self):
            # TODO: Make this read passwords from somewhere
            return ""

        def search_strings(self, mode):
            _search_strings = {"RSS": [""], "Episode": ["The 100 S07E08"], "Season": ["Game of Thrones S08"], "Movie": ["Black Panther 2018"]}
            _search_strings.update(self.provider.cache.search_params)
            _search_strings.update(test_string_overrides.get(self.provider.name, {}))
            return {mode: _search_strings[mode]}

        def magic_skip(func):  # pylint:disable=no-self-argument
            @wraps(func)
            def magic(self, *args, **kwargs):
                if func.__name__.split("_")[1] in disabled_provider_tests.get(self.provider.name, []):
                    self.skipTest("Test is programmatically disabled for provider {}".format(self.provider.name))
                func(self, *args, **kwargs)

            return magic

        def shortDescription(self):
            if self._testMethodDoc:
                return self._testMethodDoc.replace("the provider", self.provider.name)
            return None

        @magic_skip
        def test_rss_search(self):
            """Check that the provider parses rss search results"""
            if self.provider.can_daily:
                results = self.provider.search(self.search_strings("RSS"))
                assert results, results

        @magic_skip
        def test_episode_search(self):
            """Check that the provider parses episode search results"""
            if self.provider.can_backlog:
                results = self.provider.search(self.search_strings("Episode"))
                assert results, results

        @magic_skip
        def test_season_search(self):
            """Check that the provider parses season search results"""
            if self.provider.can_backlog:
                results = self.provider.search(self.search_strings("Season"))
                assert results, results

        # @pytest.mark.skip("Need to add a movie to the database before movie search works")
        @magic_skip
        def test_movie_search(self):
            """Check that the provider parses episode search results"""
            if self.provider.supports_movies:
                results = self.provider.search(self.search_strings("Movie"))
                assert results, results

        @magic_skip
        def test_cache_update(self):
            """Check that the provider's cache parses rss search results"""
            if self.provider.can_daily:
                self.provider.cache.update_cache()

        @magic_skip
        def test_result_values(self):
            """Check that the provider returns results in proper format"""
            if self.provider.can_backlog:
                for result in self.provider.search(self.search_strings("Episode")):
                    self.assertIsInstance(result, dict)
                    assert sorted(result) == ["hash", "leechers", "link", "seeders", "size", "title"]

                    self.assertIsInstance(result["title"], str)
                    self.assertIsInstance(result["link"], str)
                    self.assertIsInstance(result["hash"], str)
                    self.assertIsInstance(result["seeders"], int)
                    self.assertIsInstance(result["leechers"], int)
                    self.assertIsInstance(result["size"], int)

                    assert len(result["title"])
                    assert len(result["link"])
                    assert len(result["hash"]) in (0, 32, 40)
                    assert result["seeders"] >= 0
                    assert result["leechers"] >= 0

                    assert result["size"] >= -1

                    if result["link"].startswith("magnet"):
                        assert magnet_regex.match(result["link"])
                    else:
                        assert validators.url(result["link"]) == True, result["link"]

                    self.assertIsInstance(self.provider._get_size(result), int)
                    assert all(self.provider._get_title_and_url(result))
                    assert self.provider._get_size(result)

        @pytest.mark.skip("Not yet implemented")
        def test_season_search_strings_format(self):
            """Check format of the provider's season search strings"""
            pass

        @pytest.mark.skip("Not yet implemented")
        def test_episode_search_strings_format(self):
            """Check format of the provider's season search strings"""
            pass


def generate_test_cases():
    """
    Auto Generate TestCases from providers and add them to globals()
    """
    for p in sickchill.oldbeard.providers.__all__:
        provider = sickchill.oldbeard.providers.getProviderModule(p).Provider()
        if provider.can_backlog and provider.provider_type == "torrent" and provider.public:
            generated_class = type(str(provider.name), (BaseParser.TestCase,), {"provider": provider})
            globals()[generated_class.__name__] = generated_class
            del generated_class


generate_test_cases()

if __name__ == "__main__":
    import inspect

    print("=====> Testing %s", __file__)

    def override_log(msg, *args, **kwargs):
        """Override the SickChill logger so we can see the debug output from providers"""
        _ = args, kwargs
        print(msg)

    sickchill.logger.info = override_log
    sickchill.logger.debug = override_log
    sickchill.logger.error = override_log
    sickchill.logger.warning = override_log

    suite = unittest.TestSuite()
    members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for _, provider_test_class in members:
        if provider_test_class not in (BaseParser, BaseParser.TestCase):
            suite.addTest(unittest.TestLoader().loadTestsFromTestCase(provider_test_class))

    unittest.TextTestRunner(verbosity=3).run(suite)
