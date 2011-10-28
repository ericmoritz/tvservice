import nanoweb
import routes
from routes.middleware import RoutesMiddleware
from webob import Response
from webob.dec import wsgify
from webob.exc import *
from contextlib import contextmanager
import json
import os


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


apps = {
    "shows": shows,
    "show": show
}

mapper = routes.Mapper()
mapper.connect("/shows/", application="shows")
mapper.connect("/shows/:slug", application="show")

application = nanoweb.FrontController(apps)
application = RoutesMiddleware(application, mapper)
