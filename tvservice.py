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

##
# Models
##
@contextmanager
def db():
    if os.path.exists(DB_FILE):
        data = json.load(open(DB_FILE))
    else:
        data = {}

    yield data

    json.dump(data, open(DB_FILE, "w"))


def detect_show(show_list, title):
    """Takes a title and returns a (show, episode) tuple or None if not found.

Args:

show_list
  A list of show titles to match on

title
  title CDATA from a RSS field

Types:

show
  A string matching the show name in the database

episode
  A string in the format S\d\dE\d\d"""
    def normalize(string):
        return re.sub(r"\W+", " ", string).lower()

    pats              =\
        [(name, re.compile(r"\b%s\b" % re.escape(normalize(name)), re.I))
         for name in show_list]
    episode_pat       = re.compile("S\d\dE\d\d", re.I)
    normailized_title = normalize(title)

    for name, pat in pats:
        if pat.search(normailized_title):
            # extract the episode slug
            match = episode_pat.search(title)
            if match:
                return (name, match.group(0).upper())

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
        show_list = shows.values()
    
    d = PyQuery(url=FEED_URL, parser="xml")

    for item in d("item"):
        ditem = PyQuery(item)
        title = ditem.find("title").text()
        match = detect_show(show_list, title)
        if match:
            name, episode = match 
            # TODO: Record episode in the feed so that future versions of this episod will be ignored
        else:
            ditem.remove()

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
