import tvservice
import unittest
from webob import Request
import json
from StringIO import StringIO
from pyquery import pyquery
import re

def strip_whitespace(s):
    return re.sub(r">\s+<", "><", s)


class MockURLOpener(object):
    def __init__(self, content):
        self.content = content
        
    def __call__(self, *args, **kwargs):
        return StringIO(self.content)

def dummy_app(environ, start_response):
    start_response("200 OK", [])
    return ["OK"]

class TestBasicAuth(unittest.TestCase):
    def test_valid(self):
        passwords = {"user": "pass"}

        req = Request.blank("/")
        req.authorization = "Basic " + "user:pass".encode("base64")
        
        app = tvservice.BasicAuth(dummy_app, passwords, "test")
        resp = req.get_response(app)
        self.assertEqual(resp.status, "200 OK")
        self.assertEqual(resp.body, "OK")        

    def test_invalid(self):
        passwords = {"user": "pass"}

        req = Request.blank("/")
        req.authorization = "Basic " + "user:notpass".encode("base64")
        
        app = tvservice.BasicAuth(dummy_app, passwords, "test")
        resp = req.get_response(app)
        self.assertEqual(resp.status, "401 Unauthorized")
        self.assertEqual(resp.www_authenticate, ("Basic",{"realm": "test"}))

    def test_noauth(self):
        passwords = {"user": "pass"}

        req = Request.blank("/")
        
        app = tvservice.BasicAuth(dummy_app, passwords, "test")
        resp = req.get_response(app)
        self.assertEqual(resp.status, "401 Unauthorized")
        self.assertEqual(resp.www_authenticate, ("Basic",{"realm": "test"}))

        
class TestDetectShow(unittest.TestCase):

    def test_normalize_title(self):
        show_list = ["Something", "How I Met Your Father"]
        title     = "How.I.met.your.father S01E02"
        expected  = ("How I Met Your Father", "S01E02")
        result    = tvservice.detect_show(show_list, title)
        
        self.assertEqual(result, expected)

    def test_normalize_name(self):
        show_list = ["Something", "How.I.Met.Your.Father"]
        title     = "How I met your father S01E02"
        expected  = ("How.I.Met.Your.Father", "S01E02")
        result    = tvservice.detect_show(show_list, title)
        
        self.assertEqual(result, expected)

    def test_date_episode(self):
        show_list = ["Something", "How.I.Met.Your.Father"]
        title     = "How I met your father 2011 12 05"
        expected  = ("How.I.Met.Your.Father", "2011 12 05")
        result    = tvservice.detect_show(show_list, title)
        
        self.assertEqual(result, expected)

    def test_scunthorpe(self):
        show_list = ["Something", "Shit"]
        title     = "How to cook Shitake Mushrooms"
        expected  = None
        result    = tvservice.detect_show(show_list, title)

        self.assertEqual(result, expected)
        
    def test_title_nomatch(self):
        show_list = ["Something", "Shit"]
        title     = "Shitake Mushrooms"
        expected  = None
        result    = tvservice.detect_show(show_list, title)

        self.assertEqual(result, expected)

    def test_title_noepisode(self):
        show_list = ["Something", "Shit Talkers"]
        title     = "Shit Talkers"
        expected  = None
        result    = tvservice.detect_show(show_list, title)

        self.assertEqual(result, expected)


class TestEpisodesDB(unittest.TestCase):
    def setUp(self):
        # Create an inital episodes structure
        with tvservice.episodes_db() as episodes:
            # Mark two episodes as seen
            episodes = tvservice.episode_seen(episodes,
                                              "How I Met Your Father", "S01E04",
                                              "How I Met your Father S01E04 720P")
            episodes = tvservice.episode_seen(episodes,
                                              "Fact Provers", "S01E03",
                                              "Fact Provers S01E03 720P")

    def test_is_not_dupe(self):
        with tvservice.episodes_db() as db:
            episodes = db

        # Episode titles have to be exact to not be a dupe
        self.assertFalse(tvservice.episode_is_dupe(episodes,
                                                   "How I Met Your Father", "S01E04",
                                                   "How I Met your Father S01E04 720P"))

        self.assertFalse(tvservice.episode_is_dupe(episodes,
                                                   "Fact Provers", "S01E03",
                                                   "Fact Provers S01E03 720P"))

        # Any unknown episode is obviously not a dupe
        self.assertFalse(tvservice.episode_is_dupe(episodes,
                                                   "Inspector Spacetime", "S01E03",
                                                   "Inspector Spacetime S01E03 720P"))

        
    def test_is_dupe(self):
        with tvservice.episodes_db() as db:
            episodes = db

        # Episode titles have to be exact to not be a dupe
        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "How I Met Your Father", "S01E04",
                                                  "How I Met your father S01E04 720P"))

        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "Fact Provers", "S01E03",
                                                  "Fact provers S01E03 720P"))

        # Episode quality has to be exact
        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "How I Met Your Father", "S01E04",
                                                  "How I Met your Father S01E04 1080P"))

        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "Fact Provers", "S01E03",
                                                  "Fact Provers S01E03 1080P"))

        # Episode slug has to be exact
        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "How I Met Your Father", "S01E05",
                                                  "How I Met your Father S01E05 720P"))
        self.assertTrue(tvservice.episode_is_dupe(episodes,
                                                  "Fact Provers", "S01E04",
                                                  "Fact Provers S01E04 720P"))
        

class TestShowResource(unittest.TestCase):
    def setUp(self):
        self.authorization = "Basic " + "test-user:test-password".encode("base64")
        self.tearDown()

    def tearDown(self):
        with tvservice.shows_db() as shows:
            keys = shows.keys()
            for key in keys:
                del shows[key]
        

    def testPUT(self):
        req = Request.blank("/shows/test", method="PUT", body="Test",
                            authorization=self.authorization,
                            content_type="text/plain")
        
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.body, "Test")
        self.assertEqual(res.content_type, "text/plain")

        with tvservice.shows_db() as shows:
            self.assertEqual(shows["test"], "Test")

    def testPUTJSON(self):
        req = Request.blank("/shows/test", method="PUT",
                            authorization=self.authorization,
                            content_type="application/json")

        req.body = json.dumps({"title": "Test"})

        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.body, "Test")
        self.assertEqual(res.content_type, "text/plain")

        with tvservice.shows_db() as shows:
            self.assertEqual(shows["test"], "Test")

    def testDELETE(self):
        with tvservice.shows_db() as shows:
            shows['test'] = "Test"

        req = Request.blank("/shows/test", method="DELETE",
                            authorization=self.authorization)
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "204 No Content")

        req = Request.blank("/shows/test", method="DELETE",
                            authorization=self.authorization)
        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "404 Not Found")
        

    def testGET(self):
        req = Request.blank("/shows/test", method="GET",
                            authorization=self.authorization)

        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "404 Not Found")

        with tvservice.shows_db() as shows:
            shows['test'] = "Test"


        req = Request.blank("/shows/test", method="GET",
                            authorization=self.authorization)

        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.body, "Test")
        self.assertEqual(res.content_type, "text/plain")


class TestShowsResource(unittest.TestCase):
    def setUp(self):
        self.authorization = "Basic " + "test-user:test-password".encode("base64")
        with tvservice.shows_db() as shows:
            shows['test'] = "Test!"
            shows['himym'] = "How I Met Your Mother"

    def testGET(self):
        expected = {"test": "Test!",
                    "himym": "How I Met Your Mother"}

        req = Request.blank("/shows/",
                            authorization=self.authorization)
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.content_type, "application/json")
        self.assertEqual(json.loads(res.body), expected)
        

class TestFeed(unittest.TestCase):
    def setUp(self):
        with tvservice.shows_db() as shows:
            shows['test'] = "Test"
            shows['shit'] = 'Shit'

        self.fixture = """<rss version="2.0">
   <item><title>Test S01E01</title></item>
   <item><title>Show with a x in it S01E01</title></item>
   <item><title>Shitake Mushrooms S01E01</title></item>
   <item><title>Shit Talkers S01E01</title></item>
   <item><title>Shit Talkers s01e01</title></item>
   <item><title>Shit.Talkers.S01E01</title></item>
   <item><title>Test</title></item>
</rss>"""

        self._urlopen = pyquery.urlopen
        pyquery.urlopen = MockURLOpener(self.fixture)

    def tearDown(self):
        with tvservice.shows_db() as shows:
            keys = shows.keys()
            for key in keys:
                del shows[key]

        pyquery.urlopen = self._urlopen
        
    def testFeed(self):
        expected = """<rss version="2.0">
   <item><title>Test S01E01</title></item>
   <item><title>Shit Talkers S01E01</title></item>
   <item><title>Shit Talkers s01e01</title></item>
   <item><title>Shit.Talkers.S01E01</title></item>
</rss>"""

        req = Request.blank("/feed/")

        res = req.get_response(tvservice.application)
        
        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.content_type, "application/rss+xml")

        self.assertEqual(strip_whitespace(res.body),
                         strip_whitespace(expected))
        
