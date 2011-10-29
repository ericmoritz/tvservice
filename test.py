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


class TestShowResource(unittest.TestCase):
    def setUp(self):
        self.tearDown()

    def tearDown(self):
        with tvservice.db() as shows:
            keys = shows.keys()
            for key in keys:
                del shows[key]
        

    def testPUT(self):
        req = Request.blank("/shows/test", method="PUT", body="Test",
                            content_type="text/plain")
        
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.body, "Test")
        self.assertEqual(res.content_type, "text/plain")

        with tvservice.db() as shows:
            self.assertEqual(shows["test"], "Test")

    def testDELETE(self):
        with tvservice.db() as shows:
            shows['test'] = "Test"

        req = Request.blank("/shows/test", method="DELETE")
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "204 No Content")

    
        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "404 Not Found")
        

    def testGET(self):
        req = Request.blank("/shows/test", method="GET")

        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "404 Not Found")

        with tvservice.db() as shows:
            shows['test'] = "Test"

        res = req.get_response(tvservice.application)
        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.body, "Test")
        self.assertEqual(res.content_type, "text/plain")

class TestShowsResource(unittest.TestCase):
    def setUp(self):
        with tvservice.db() as shows:
            shows['test'] = "Test!"
            shows['himym'] = "How I Met Your Mother"

    def testGET(self):
        expected = {"test": "Test!",
                    "himym": "How I Met Your Mother"}

        req = Request.blank("/shows/")
        res = req.get_response(tvservice.application)

        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.content_type, "application/json")
        self.assertEqual(json.loads(res.body), expected)
        

class TestFeed(unittest.TestCase):
    def setUp(self):
        with tvservice.db() as shows:
            shows['test'] = "Test"
            shows['period'] = "Show with a . in it"
            shows['shit'] = 'Shit'

        self.fixture = """<rss version="2.0">
   <item><title>Test S01E01</title></item>
   <item><title>Show with a . in it S01E01</title></item>
   <item><title>Show with a x in it S01E01</title></item>
   <item><title>Shitake Mushrooms S01E01</title></item>
   <item><title>Shit Talkers S01E01</title></item>
   <item><title>Shit Talkers s01e01</title></item>
   <item><title>Test</title></item>
</rss>"""

        self._urlopen = pyquery.urlopen
        pyquery.urlopen = MockURLOpener(self.fixture)

    def tearDown(self):
        with tvservice.db() as shows:
            keys = shows.keys()
            for key in keys:
                del shows[key]

        pyquery.urlopen = self._urlopen
        
    def testFeed(self):
        expected = """<rss version="2.0">
   <item><title>Test S01E01</title></item>
   <item><title>Show with a . in it S01E01</title></item>
   <item><title>Shit Talkers S01E01</title></item>
   <item><title>Shit Talkers s01e01</title></item>
</rss>"""

        req = Request.blank("/feed/")
        res = req.get_response(tvservice.application)
        
        self.assertEqual(res.status, "200 OK")
        self.assertEqual(res.content_type, "application/rss+xml")

        self.assertEqual(strip_whitespace(res.body),
                         strip_whitespace(expected))
        
