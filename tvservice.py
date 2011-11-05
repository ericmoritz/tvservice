import nanoweb
import routes
from routes.middleware import RoutesMiddleware
from webob import Response
from webob.dec import wsgify
from webob.exc import *
from contextlib import contextmanager
from pyquery import PyQuery
import json
import os
import re

FEED_URL = os.environ['FEED_URL']
DB_ROOT = os.environ['WRITABLE_ROOT']
DB_FILE = os.path.join(DB_ROOT, "shows.json")


@contextmanager
def db():
    if os.path.exists(DB_FILE):
        data = json.load(open(DB_FILE))
    else:
        data = {}

    yield data

    json.dump(data, open(DB_FILE, "w"))

##
# WSGI Apps
##
@wsgify
def shows(request):
    nanoweb.allowed(request, ["GET"])
    content_type = nanoweb.agent_accepts(request, ["application/json"])

    with db() as shows:
        response = Response(nanoweb.encode_body(content_type, shows),
                            content_type=content_type)
        return response


@wsgify
def show(request):
    nanoweb.allowed(request, ["GET", "PUT", "DELETE"])
    url = request.environ['routes.url']
    slug = request.urlvars['slug']

    if request.method == "PUT":
        if request.content_type != "text/plain":
            raise HTTPUnsupportedMediaType("use text/plain")
        
        name = request.body
        with db() as shows:
            shows[slug] = name
        return Response(name, content_type="text/plain")

    elif request.method == "DELETE":
        try:
            with db() as shows:
                del shows[slug]
            return HTTPNoContent()
        except KeyError:
            return HTTPNotFound()

    elif request.method == "GET":
        try:
            with db() as shows:
                name = shows[slug]
        except KeyError:
            return HTTPNotFound()
        
        return Response(name, content_type="text/plain")


@wsgify
def feed(request):
    with db() as shows:
        names = shows.values()
    
    def normalize(string):
        return re.sub(r"\W+", " ", string)
    
    def not_wanted(title):
        # Treat any non-word char as whitespace
        normalized_title = normalize(title)
        result = any(pat.search(title) for pat in pats)
        return not result

    def not_episode(title):
        """remove any items that do not have S\d\dE\d\d in the title"""
        return not re.search(r"S\d\dE\d\d", title, re.I)
        
    def remove_show(i):
        title = PyQuery(this).find("title").text()
        return not_episode(title) or not_wanted(title)


    pats = [re.compile(r"\b%s\b" % re.escape(normalize(name)), re.I)
            for name in names]
    
    d = PyQuery(url=FEED_URL, parser="xml")

    d("item").filter(remove_show).remove()

    response = Response()
    response.content_type = "application/rss+xml"
    response.ubody = unicode(d)
    response.cache_control = "no-cache"
    return response    


apps = {
    "shows": shows,
    "show": show,
    "feed": feed,
}

mapper = routes.Mapper()
mapper.connect("/feed/", application="feed")
mapper.connect("/shows/", application="shows")
mapper.connect("/shows/:slug", application="show")

application = nanoweb.FrontController(apps)
application = RoutesMiddleware(application, mapper)
