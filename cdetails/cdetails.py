import psycopg2
import psycopg2.extras
import atexit
import json

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound

class Cdetails(object):

    def __init__(self, config):
        self.db = psycopg2.connect(config['database'])
        atexit.register(self.close_connections)

        self.url_map = Map([
            Rule('/<id>.json', endpoint='segment'),
        ])

    def close_connections(self):
        self.db.close()

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def on_segment(self, request, id):
        sql = "SELECT id, name, curvature, paved, length, highway, surface FROM curvature_segments WHERE id = %s"
        cur = self.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, (id,))
        segment = cur.fetchone()
        if segment is None:
            raise NotFound('unknown id')

        sql = "SELECT id, name, curvature, length, highway, surface, min_lon, max_lon, min_lat, max_lat FROM segment_ways WHERE fk_segment = %s ORDER BY position ASC"
        cur = self.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, (id,))
        segment['ways'] = cur.fetchall()

        return Response(json.dumps(segment))

def create_app(config):
    app = Cdetails(config)
    # if with_static:
    #     app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
    #         '/static':  os.path.join(os.path.dirname(__file__), 'static')
    #     })
    return app

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 4580, app, use_debugger=True, use_reloader=True)
