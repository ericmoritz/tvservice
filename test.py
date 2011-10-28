import tvservice
import unittest
from webob import Request
import json

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
        
