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
EPISODE_DB_FILE = os.path.join(DB_ROOT, "episodes.json")

##
# Models
##
@contextmanager
def db(db_file, 
       initial_value,
       load=lambda x:x,
       dump=lambda x:x):

    if os.path.exists(db_file):
        data = load(json.load(open(db_file)))
    else:
        data = initial_value()

    yield data

    json.dump(dump(data), open(db_file, "w"))

def shows_db():
    return db(DB_FILE, {})

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


def init_episodes():
    """The episode data structure is a map of sets.

The key of the map is the show's canonical name
Each element in the set is (episode_slug, rss_title)"""
    return {}


def dump_episodes(data):
    """The show's seen episode set is serialized as a JSON list"""
    newdata = {}
    for key, value in data.items():
        newdata[key] = list(value)
    return newdata


def load_episodes(data):
    """The show's seen episode JSON list is deserialized as a python set"""
    newdata = {}
    for key, value in data.items():
        # Convert the elements to a hashable value
        newvalue = (tuple(e) for e in value)
        newdata[key] = set(newvalue)
    return newdata


def episodes_db():
    return db(EPISODE_DB_FILE,
              init_episodes,
              dump=dump_episodes,
              load=load_episodes)


def episode_seen(episodes, name, episode_slug, rss_title):
    show_data      = episodes.get(name, set([]))

    show_data.add((episode_slug, rss_title))

    episodes[name] = show_data
    return episodes


def episode_is_dupe(episodes, name, episode_slug, rss_title):
    show_data = episodes.get(name, set([]))
    was_seen  = (episode_slug, rss_title) in show_data

    # Any unknown episodes are obviously not a dupe
    # Any rss titles that have already been seen are not dupes
    if name not in episodes or was_seen:
        return False
    else:
        # Anything else is a dupe
        return True
    
##
# WSGI Apps
##
@wsgify
def shows(request):
    nanoweb.allowed(request, ["GET"])
    content_type = nanoweb.agent_accepts(request, ["application/json"])

    with shows_db() as shows:
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
        with shows_db() as shows:
            shows[slug] = name
        return Response(name, content_type="text/plain")

    elif request.method == "DELETE":
        try:
            with shows_db() as shows:
                del shows[slug]
            return HTTPNoContent()
        except KeyError:
            return HTTPNotFound()

    elif request.method == "GET":
        try:
            with shows_db() as shows:
                name = shows[slug]
        except KeyError:
            return HTTPNotFound()
        
        return Response(name, content_type="text/plain")


@wsgify
def feed(request):
    with shows_db() as shows:
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
