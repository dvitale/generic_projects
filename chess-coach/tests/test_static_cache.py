import pytest

from backend import main
from test_problems import client  # noqa: F401

pytestmark = pytest.mark.skipif(not (main.DIST / 'index.html').exists(), reason='interfaccia non compilata (npm run build)')


def test_the_page_is_revalidated_and_hashed_assets_are_cached_for_good(client):
    page = client.get('/')
    assert page.status_code == 200 and page.headers['cache-control'] == 'no-cache'
    asset = next((main.DIST / 'assets').glob('*.js')).name
    built = client.get(f'/assets/{asset}')
    assert built.status_code == 200 and built.headers['cache-control'] == 'public, max-age=31536000, immutable'
    assert 'cache-control' not in client.get('/assets/missing.js').headers
    assert 'cache-control' not in client.get('/api/health').headers
