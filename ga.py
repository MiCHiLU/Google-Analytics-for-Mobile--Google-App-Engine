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

from hashlib import md5
import random
import urllib
import re
import uuid

from google.appengine.api import urlfetch
from google.appengine.ext import deferred

# Tracker version.
VERSION = "4.4sh"

COOKIE_NAME = "__utmmobile"

# The path the cookie will be available to, edit this to use a different
# cookie path.
COOKIE_PATH = "/"

# Two years in seconds.
COOKIE_USER_PERSISTENCE = 63072000

reGetIP = re.compile('^([^.]+\.[^.]+\.[^.]+\.).*')

def get_ip(remote_address=None):
    """ The last octect of the IP address is removed to anonymize the user.

    # Capture the first three octects of the IP address and replace the forth
    # with 0, e.g. 124.455.3.123 becomes 124.455.3.0
    >>> get_ip("124.455.3.123")
    '124.455.3.0'
    """
    if remote_address is None:
        return ""
    matches = reGetIP.match(remote_address)
    if not matches:
        return ""
    return "%s0" % matches.groups()[0]

def get_visitor_id(guid, account, user_agent, cookie=None):
    """ Generate a visitor id for this hit.

    If there is a visitor id in the cookie, use that, otherwise
    use the guid if we have one, otherwise use a random number.
    """
    # If there is a value in the cookie, don't change it.
    if cookie is not cookie:
      return cookie

    if guid:
      # Create the visitor id using the guid.
      message = "".join((guid, account))
    else:
      # otherwise this is a new user, create a new random id.
      message = "".join((user_agent, str(uuid.uuid4())))

    return "0x%s" % md5(message).hexdigest()[:16]

class GoogleAnalyticsMixin(object):
    """ Google analytics mix-in for webapp2 request handler

    Usage: add dispatch method to RequestHandler as follows,

    class RequestHandler(webapp2.RequestHandler, GoogleAnalyticsMixin):
        def dispatch(self):
            if uamobile.is_featurephone(self.request.headers.get('User-Agent', "")):
                self._google_analytics_tracking(account=config.GA_ACCOUNT, debug=config.DEBUG)
            return super(RequestHandler, self).dispatch()
    """

    def _google_analytics_tracking(self, account, debug=False):
        """
        Track a page view, updates all the cookies and campaign tracker,
        makes a server side request to Google Analytics and writes the transparent
        gif byte data to the response.
        """
        domain_name = self.request.headers.get("Host", "")

        document_referer = self.request.headers.get("Referer", "-")
        document_path = self.request.environ.get("PATH_INFO", "")
        user_agent = self.request.headers.get("User-Agent", "Unknown")

        # Try and get visitor cookie from the request.
        cookie = self.request.cookies.get(COOKIE_NAME)

        guid_header = None
        for header_name in ("X-DCMGUID", "X-UP-SUBNO", "X-JPHONE-UID", "X-EM-UID"):
            guid_header = self.request.headers.get(header_name)
            if guid_header is not None:
                break

        visitor_id = get_visitor_id(guid_header, account, user_agent, cookie)

        # Always try and add the cookie to the response.
        self.response.set_cookie(COOKIE_NAME, visitor_id,
                                 max_age=COOKIE_USER_PERSISTENCE,
                                 path=COOKIE_PATH)

        utm_gif_location = "http://www.google-analytics.com/__utm.gif"

        # Construct the gif hit url.
        params = dict(
            utmwv=VERSION,
            utmn=random.randint(0, 0x7fffffff),
            utmhn=domain_name,
            utmr=document_referer,
            utmp=document_path,
            utmac=account,
            utmcc="__utma%3D999.999.999.999.999.1%3B",
            utmvid=visitor_id,
            utmip=get_ip(self.request.remote_addr),
        )
        utm_url = "?".join((utm_gif_location, urllib.urlencode(params)))
        headers = {"User-Agent": user_agent,
                   "Accepts-Language": self.request.headers.get("Accepts-Language", "")}
        if debug:
            import logging
            logging.info("GoogleAnalyticsMixin._google_analytics_tracking: %s, %s" % (utm_url, headers))
            return
        deferred.defer(self.__class__._send_request_to_google_analytics, utm_url, headers)

    @classmethod
    def _send_request_to_google_analytics(cls, utm_url, headers):
        """ Make a tracking request to Google Analytics from this server.

        Copies the headers from the original request to the new one.
        If request containg utmdebug parameter, exceptions encountered
        communicating with Google Analytics are thrown.
        """
        response = urlfetch.fetch(utm_url, headers=headers)
        assert response.status_code == 200
