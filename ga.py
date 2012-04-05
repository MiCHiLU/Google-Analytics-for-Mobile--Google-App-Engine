"""
Google App Engine implementation of ga.php.

Original Google Analytics Reference:
http://code.google.com/mobile/analytics/docs/web/

Cookies Reference:
On http://www.google.com/support/conversionuniversity/bin/static.py?hl=en&page=iq_learning_center.cs&rd=1,
    watch the Cookies and Google Analytics presentation

Adapted from:
http://github.com/b1tr0t/Google-Analytics-for-Mobile--python-/blob/master/ga.py
"""

from Cookie import SimpleCookie, CookieError
from hashlib import md5
from random import randint
from urllib import quote
import logging
import os
import re
import struct
import time
import uuid

from google.appengine.api import urlfetch

VERSION = "4.4sh"
COOKIE_NAME = "__utmmobile"
COOKIE_PATH = "/"
COOKIE_USER_PERSISTENCE = 63072000

GIF_DATA = reduce(lambda x,y: x + struct.pack('B', y),
                  [0x47,0x49,0x46,0x38,0x39,0x61,
                   0x01,0x00,0x01,0x00,0x80,0x00,
                   0x00,0x00,0x00,0x00,0xff,0xff,
                   0xff,0x21,0xf9,0x04,0x01,0x00,
                   0x00,0x00,0x00,0x2c,0x00,0x00,
                   0x00,0x00,0x01,0x00,0x01,0x00,
                   0x00,0x02,0x01,0x44,0x00,0x3b], '')

# WHITE GIF:
# 47 49 46 38 39 61
# 01 00 01 00 80 ff
# 00 ff ff ff 00 00
# 00 2c 00 00 00 00
# 01 00 01 00 00 02
# 02 44 01 00 3b

# TRANSPARENT GIF:
# 47 49 46 38 39 61
# 01 00 01 00 80 00
# 00 00 00 00 ff ff
# ff 21 f9 04 01 00
# 00 00 00 2c 00 00
# 00 00 01 00 01 00
# 00 02 01 44 00 3b

def get_ip(remote_address):
    # dbgMsg("remote_address: " + str(remote_address))
    if not remote_address:
        return ""
    matches = re.match('^([^.]+\.[^.]+\.[^.]+\.).*', remote_address)
    if matches:
        return matches.groups()[0] + "0"
    else:
        return ""

def get_visitor_id():
    """
    // Generate a visitor id for this hit.
    """
    usrKey = str(uuid.uuid4())
    md5String = md5(usrKey).hexdigest()
    return "0x" + md5String[:16]

def get_random_number():
    """
    // Get a random number string.
    """
    return str(randint(0, 0x7fffffff))

def send_request_to_google_analytics(utm_url):
    """
    // Make a tracking request to Google Analytics from this server.
    // Copies the headers from the original request to the new one.
    // If request containg utmdebug parameter, exceptions encountered
    // communicating with Google Analytics are thrown.
    """
    headers = {'User-Agent': os.environ.get('HTTP_USER_AGENT', 'Unknown'),
               'Accepts-Language:': os.environ.get("HTTP_ACCEPT_LANGUAGE",'')}
    httpresp = urlfetch.fetch(
                   url      = utm_url,
                   method   = urlfetch.GET,
                   headers =  headers
                   )
    doLogging = False
    if doLogging:
        if httpresp.status_code == 200:
            logging.info("IntfGA success: %s(%s)\n%s" % (utm_url, headers, httpresp.headers) )
        else:
            logging.warning("IntfGA fail: %s %d" % (utm_url, httpresp.status_code) )

def track_page_view(path, env, account, domain):
    """
    // Track a page view, updates all the cookies and campaign tracker,
    // makes a server side request to Google Analytics and writes the transparent
    // gif byte data to the response.
    """
    time_tup = time.localtime(time.time() + COOKIE_USER_PERSISTENCE)

    # Get the referrer from the utmr parameter, this is the referrer to the
    # page that contains the tracking pixel, not the referrer for tracking
    # pixel.
    document_referer = "-"
    document_path = path

    visitor_id = get_visitor_id()

    # // Always try and add the cookie to the response.
    cookie = SimpleCookie()
    cookie[COOKIE_NAME] = visitor_id
    morsel = cookie[COOKIE_NAME]
    morsel['expires'] = time.strftime('%a, %d-%b-%Y %H:%M:%S %Z', time_tup)
    morsel['path'] = COOKIE_PATH

    utm_gif_location = "http://www.google-analytics.com/__utm.gif"

    utm_url = utm_gif_location + "?" + \
            "utmwv=" + VERSION + \
            "&utmn=" + get_random_number() + \
            "&utmhn=" + quote(domain) + \
            "&utmsr=" + '-' + \
            "&utme=" + '-' + \
            "&utmr=" + quote(document_referer) + \
            "&utmp=" + quote(document_path) + \
            "&utmac=" + account + \
            "&utmcc=__utma%3D999.999.999.999.999.1%3B" + \
            "&utmvid=" + visitor_id + \
            "&utmip=" + get_ip(env.request.remote_addr)
    # dbgMsg("utm_url: " + utm_url)
    send_request_to_google_analytics(utm_url)
