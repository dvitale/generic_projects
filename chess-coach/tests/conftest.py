import os

# The project .env may enable the login; API tests run unauthenticated unless they opt in (see test_auth.py).
os.environ['CHESS_COACH_DISABLE_AUTH'] = '1'
