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
        if 'CORS_allow_origin' in config:
            self.CORS_allow_origin = config['CORS_allow_origin']
        else:
            self.CORS_allow_origin = None;
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
        sql = "SELECT id, id_hash, name, curvature, paved, length FROM curvature_segments WHERE id_hash = %s"
        cur = self.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, (id,))
        segment = cur.fetchone()
        if segment is None:
            raise NotFound('unknown id')

        sql = "SELECT id, name, curvature, length, h.tag_value AS highway, s.tag_value AS surface, sm.tag_value AS smoothness, m.tag_value AS maxspeed, min_lon, max_lon, min_lat, max_lat FROM segment_ways JOIN tags h ON fk_highway = h.tag_id JOIN tags s ON fk_surface = s.tag_id LEFT JOIN tags sm ON fk_smoothness = sm.tag_id LEFT JOIN tags m ON fk_maxspeed = m.tag_id WHERE fk_segment = %s ORDER BY position ASC"
        cur = self.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, (segment['id'],))
        segment['ways'] = cur.fetchall()

        response = Response(json.dumps(segment))
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        if self.CORS_allow_origin:
            response.headers["Access-Control-Allow-Origin"] = self.CORS_allow_origin
            response.headers["Access-Control-Allow-Headers"] = "X-Requested-With"  # noqa
        return response

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
