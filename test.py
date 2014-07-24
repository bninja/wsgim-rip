import threading
import urllib2
import wsgiref.simple_server
import wsgiref.validate

import pytest

import wsgim_rip


def echo(environ, start_response):
    response_headers = [
        ('X-Wsgim-Rip', environ['REMOTE_ADDR']),
        ('Content-Type', 'text/plain'),
    ]
    start_response('200 OK', response_headers)
    return []


@pytest.fixture(scope='module')
def server(request):
    app = wsgiref.validate.validator(wsgim_rip.RIPMiddleware(
        echo,
        internal='10.0.0.0/8',
        proxies={
            '50.18.213.180': '192.168.0.0/16',
        },
    ))

    server = wsgiref.simple_server.make_server('127.0.0.1', 0, app)

    def _shutdown():
        server.shutdown()

    thd = threading.Thread(target=server.serve_forever)
    thd.daemon = True
    thd.start()

    request.addfinalizer(_shutdown)

    return 'http://{0}:{1}'.format(*server.server_address)


def test_no_fwd(server):
    req = urllib2.Request(server)
    resp = urllib2.urlopen(req)
    assert resp.getcode() == 200
    assert 'X-Wsgim-Rip' in resp.info()
    assert resp.info()['X-Wsgim-Rip'] == '127.0.0.1'


def test_one_fwd(server):
    req = urllib2.Request(server, headers={
        'X-Forwarded-For': '123.123.123.234,10.12.4.4,10.12.34.4',
    })
    resp = urllib2.urlopen(req)
    assert resp.getcode() == 200
    assert 'X-Wsgim-Rip' in resp.info()
    assert resp.info()['X-Wsgim-Rip'] == '123.123.123.234'


def test_multiple_fwds(server):
    req = urllib2.Request(server, headers={
        'X-Forwarded-For': '123.123.123.234,192.168.0.0,50.18.213.180,10.12.4.4',
    })
    resp = urllib2.urlopen(req)
    assert resp.getcode() == 200
    assert 'X-Wsgim-Rip' in resp.info()
    assert resp.info()['X-Wsgim-Rip'] == '123.123.123.234'


def test_garbage(server):
    req = urllib2.Request(server, headers={
        'X-Forwarded-For': 'balls',
    })
    resp = urllib2.urlopen(req)
    assert resp.getcode() == 200
    assert 'X-Wsgim-Rip' in resp.info()
    assert resp.info()['X-Wsgim-Rip'] == '127.0.0.1'
