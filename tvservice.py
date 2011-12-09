import nanoweb
import routes
from routes.middleware import RoutesMiddleware
from webob import Response
from webob.dec import wsgify
from webob.exc import *
from contextlib import contextmanager
from pyquery import PyQuery
from static import Cling
import json
import os
import re

PASSWORD_FILE = os.environ['PASSWORD_FILE']
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
        data = initial_value

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
    episode_pat       = re.compile("(S\d\dE\d\d|\d{4} \d{2} \d{2})", re.I)
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
    content_type = nanoweb.agent_accepts(request, ["text/plain",
                                                   "application/json"])
    # Set up the encoders
    encoders = {"text/plain": lambda d: d['title']}
    encoders.update(nanoweb.encoders)

    # Set up the decoders
    decoders = {"text/plain": lambda s: {"title": s}}
    decoders.update(nanoweb.decoders)

    url = request.environ['routes.url']
    slug = request.urlvars['slug']

    if request.method == "PUT":
        data = nanoweb.decode_body(request, decoders=decoders)
        
        with shows_db() as shows:
            shows[slug] = data['title']
        
        body = nanoweb.encode_body(content_type, data,
                                   encoders=encoders)
        return Response(body, content_type=content_type)

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
        
        data = {"title": name, "slug": slug}
        body = nanoweb.encode_body(content_type, data,
                                   encoders=encoders)
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

##
## WSGI Middleware
##
class BasicAuth(object):
    def __init__(self, app, password_map, realm):
        self.app = app
        self.password_map = password_map
        self.realm = realm

    @wsgify
    def __call__(self, request):
        badauth_response = HTTPUnauthorized("Use basic authorization",
                                            www_authenticate='Basic realm="%s"' % (self.realm, ))
        if request.authorization is None \
                or request.authorization[0].lower() != "basic":
            raise badauth_response

        authtype, param = request.authorization
        username, password = param.decode("base64").split(":")

        if username in self.password_map\
                and self.password_map[username] == password:
            return request.get_response(self.app)
        else:
            raise badauth_response
        

##
## Shows sub app config
##
def shows_subapp():
    """This is a factory for building the shows app that is mapped to 
/shows/

This subapp is needed because it requires authentication"""
    password_map = json.load(open(PASSWORD_FILE))['passwords']
    apps = {
        "shows": shows,
        "show": show,
    }
    mapper = routes.Mapper()
    mapper.connect("/:slug", application="show")
    mapper.connect("/", application="shows")


    subapp = nanoweb.FrontController(apps)
    subapp = RoutesMiddleware(subapp, mapper)
    subapp = BasicAuth(subapp, password_map, "shows")
    return subapp

##
## TVService apps
## 

apps = {
    "shows": shows_subapp(),
    "feed": feed,
}


mapper = routes.Mapper()
mapper.connect("/shows/{path_info:.*}", application="shows")
mapper.connect("/feed/", application="feed")

STATIC_ROOT = os.environ.get('STATIC_ROOT')
if STATIC_ROOT:
    static = Cling(STATIC_ROOT)
    apps['static'] = static
    mapper.connect("/{path_info:.*}", application="static")

application = nanoweb.FrontController(apps)
application = RoutesMiddleware(application, mapper)
