"""
pymtoauth is a python library for working with Mindtalk API.
More information about Mindtalk API can be found in:
http://developer.mindtalk.com

Originally written for MTFeed project.
Library depedency:
decorator (http://pypi.python.org/pypi/decorator/)
pycurl (http://pypi.python.org/pypi/pycurl/)

## Example Usage: Anonym API
from pymtoauth import MTOAuth

config = dict(
    client_id="your-client-id",
    client_secret="your-client-secret",
    api_key="your-api-key",
    scopes="all",
    redirect_uri="your-callback-url"
)

mtoauth = MTOAuth(**config)
print mtoauth.user_info(name="rizkyabdilah")

## Example Usage 2: Authenthic API
def login():
    redir_url = mtoauth.authorized_url()
    redirect(url)
    
def callback():
    code = req.get("code")
    err, at = mtoauth.exchange_code_with_access_token(code)
    if err is not None:
        raise MTApiError("Cannot exchange code")
    access_token, refresh_token = at
    mtoauth.set_token(access_token, refresh_token)
    
    ## call some
    my_info = mtoauth.my_info()
"""

__author__ = "Rizky Abdilah"
__version__ = "0.2.0"

import sys
import os
import pycurl
from decorator import decorator
import urllib
import json
import cgi

class HttpResponse(object):
    header = {}
    body = ""

class HttpReq(object):
    
    response = None
    USERAGENT = "Mozilla/5.0 (compatible; HttpReq/0.1; +http://limbotolabs.com/~rizky/httpreq.html)"
    
    def __init__(self, url, method="GET", params={}, header={}):
        self.url = url
        self.method = method.upper()
        self.params = params
        self.header = header
        self.response = HttpResponse()
        self.already_prepared = False
        
    def _header_callback(self, buf):
        ## some header response like status code really doesn't have key value
        try:
            hkey, hval = buf.split(":", 1)
            self.response.header[hkey.lower()] = hval.strip()
        except ValueError:
            pass
    
    def _body_callback(self, buf):
        self.response.body += buf
        
    def _build_get_parameter(self):
        mark = "&" if "?" in self.url else "?"
        return mark + urllib.urlencode(self.params)
    
    def _build_post_parameter(self):
        postfields = []
        for k, v in self.params.iteritems():
            if isinstance(v, file):
                field = (k, (pycurl.FORM_FILE, v.name))
            else:
                field = (k, (pycurl.FORM_CONTENTS, str(v)))
            postfields.append(field)
        return postfields
    
    def build_parameter(self):
        if self.method == "GET" and len(self.params):
            self._build_get_parameter()
            self.url += self._build_get_parameter()
        elif self.method == "POST":
            pf = self._build_post_parameter()
            self.curl.setopt(pycurl.HTTPPOST, pf)
        
    def _build_header(self):
        def _header(k, v):
            return "%s: %s" % (k, v)
        headers = [_header(k, v) for k, v in self.header.iteritems()]
        return headers
    
    def build_header(self):
        self.curl.setopt(pycurl.HTTPHEADER, self._build_header())
    
    def prepare(self):
        self.curl = pycurl.Curl()
        
        self.build_header()
        self.build_parameter()
            
        self.curl.setopt(pycurl.URL, self.url)
        self.curl.setopt(pycurl.FOLLOWLOCATION, 1)
        self.curl.setopt(pycurl.MAXREDIRS, 5)
        self.curl.setopt(pycurl.HEADERFUNCTION, self._header_callback)
        self.curl.setopt(pycurl.WRITEFUNCTION, self._body_callback)
        self.curl.setopt(pycurl.USERAGENT, self.USERAGENT)
        
        self.already_prepared = True
        
    def execute(self):
        if not self.already_prepared:
            self.prepare()
        self.curl.perform()
        
        _effective_url = self.curl.getinfo(pycurl.EFFECTIVE_URL)
        _status_code = self.curl.getinfo(pycurl.HTTP_CODE)
        setattr(self.response, "request_url", _effective_url)
        setattr(self.response, "status_code", int(_status_code))
        
        self.curl.close()
        
        return self.response
    
class MTApiException(Exception): pass
    
def intersect(list1, list2):
    return list(set(list1) & set(list2))
    
def check_required_params(path, required_params, **opts):
    def _wrapper(func, mtapi, *args, **kwargs):
        required_param_undefined = False
        all_params_key = kwargs.keys()
        for param in required_params:
            if isinstance(param, tuple):
                if not len(intersect(all_params_key, param)):
                    required_param_undefined = True
                    param = ", ".join(param[0: len(param) - 1]) + " or " + param[len(param) - 1]
                    break
            elif param not in all_params_key:
                required_param_undefined = True
                break
            
        if required_param_undefined:
            msg = "Error during request %s\nRequiring parameter: %s" % (
                path, param
            )
            if opts.get("wiki_path"):
                msg += "\nSee wiki %s" % MTOauth.wiki_url(opts.get("wiki_path"))
            raise MTApiException(msg)
                
        return func(mtapi, *args, **kwargs)
        
    return decorator(_wrapper)

def anonym_method(path, method="GET", required_params=[], **kwargs):
    
    @check_required_params(path, required_params, **kwargs)
    def _call(mtoauth, *args, **kwargs):
        params = kwargs.copy()
        params.update(mtoauth.default_params())
        params["api_key"] = mtoauth.api_key
        
        url = mtoauth.api_url(path)
        httpreq = HttpReq(url, method, params)
        httpreq.execute()
        
        ## store last request state
        mtoauth.last_request = httpreq
        
        rv = json.loads(httpreq.response.body)
        return rv.get("result") or httpreq.response.body
        
    return _call

def authentic_method(path, method="GET", required_params=[], **kwargs):
    
    @check_required_params(path, required_params, **kwargs)
    def _call(mtoauth, *args, **kwargs):
        params = kwargs.copy()
        params.update(mtoauth.default_params())
        
        _access_token = kwargs.get("access_token") or mtoauth.access_token
        if _access_token is not None:
            params["access_token"] = _access_token
        else:
            raise MTApiException("Authentic method need an access_token")
        
        
        url = mtoauth.api_url(path)
        httpreq = HttpReq(url, method, params)
        httpreq.execute()
        
        ## store last request state
        mtoauth.last_request = httpreq
        
        ## todo, check invalid request or not, refresh token if possible
        rv = json.loads(httpreq.response.body)
        return rv.get("result") or httpreq.response.body
        
    return _call

def verified_method(path, method="GET", required_params=[], **kwargs):
    
    @check_required_params(path, required_params, **kwargs)
    def _call(mtoauth, *args, **kwargs):
        params = kwargs.copy()
        params.update(mtoauth.default_params())
        
        _access_token = kwargs.get("access_token") or mtoauth.access_token
        if _access_token:
            params["access_token"] = _access_token
            
        params["client_id"] = mtoauth.client_id
        params["client_secret"] = mtoauth.client_secret
        
        url = mtoauth.api_url(path)
        httpreq = HttpReq(url, method, params)
        httpreq.execute()
        
        ## store last request state
        mtoauth.last_request = httpreq
        
        ## todo, check invalid request or not, refresh token if possible
        rv = json.loads(httpreq.response.body)
        return rv.get("result") or httpreq.response.body
        
    return _call

class MTOAuth(object):
    api_domain = "http://api.mindtalk.com"
    api_prefix = "/v1"
    auth_endpoint = "http://auth.mindtalk.com"
    return_format = "json"
    
    # shorthen url, just redirect
    wiki_endpoint = "http://mndt.lk/dev/"
    last_request = None
    
    access_token = None
    refresh_token = None

    def __init__(self, client_id, client_secret, redirect_uri, api_key,
            scopes=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.api_key = api_key
        if isinstance(scopes, (list, tuple)):
            scopes = ",".join(scopes)
        self.scopes = scopes or "basic"
        
    def default_params(self):
        default_params = dict(
            rf=self.return_format,
            ## not used yet
            ## itl="itl"
        )
        return default_params
    
    @classmethod
    def wiki_url(cls, path):
        return "%s%s" % (cls.wiki_endpoint, path)
    
    def authorized_url(self):
        _qs = dict(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scopes=self.scopes
        )
        
        authorized_url = "%(base_auth_url)s/authorize?%(qs)s" % dict(
            base_auth_url=self.auth_endpoint,
            qs=urllib.urlencode(_qs)
        )
        
        return authorized_url
    
    def api_url(self, endpoint=""):
        return "%(api_domain)s%(prefix)s%(endpoint)s" % dict(
            api_domain=self.api_domain,
            prefix=self.api_prefix,
            endpoint=endpoint
        )
        
    def access_token_url(self):
        url = "%(base_auth_url)s/access_token" % dict(
            base_auth_url=self.auth_endpoint
        )
        return url
    
    def exchange_code_with_access_token(self, code):
        params = dict(
            code=code,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        
        httpreq = HttpReq(self.access_token_url(), "GET", params)
        httpreq.execute()
        
        if httpreq.response.status_code == 200:
            raw_data = cgi.parse_qs(httpreq.response.body)
            token = raw_data["access_token"][0], raw_data["refresh_token"][0]
            return True, token
        
        return False, httpreq
    
    def set_token(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token

    ## anonym user
    user_info = anonym_method(path="/user/info",
        required_params=[("id", "name")], wiki_path="UserInfo")
    user_supporters = anonym_method(path="/user/supporters",
        required_params=[("id", "name")], wiki_path="UserSupporters")
    user_supporting = anonym_method(path="/user/supporting",
        required_params=[("id", "name")], wiki_path="UserSupporting")
    user_search = anonym_method(path="/user/search", required_params=["keyword"],
        wiki_path="UserSearch")
    user_channels = anonym_method(path="/user/channels", required_params=["user_id"],
        wiki_path="UserChannels")
    user_newest = anonym_method(path="/user/newest", wiki_path="UserNewest")
    user_is_support = anonym_method(path="/user/is_support",
        required_params=["s_user_id", "t_user_id"], wiki_path="UserIsSupport")
    user_trophies = anonym_method(path="/user/trophies", required_params=["user_id"],
        wiki_path="UserTrophies")
    user_stream = anonym_method(path="/user/stream",
        required_params=[("id", "name")], wiki_path="UserStream")
    
    ## anonym channel
    channel_info = anonym_method(path="/channel/info", wiki_path="ChannelInfo",
        required_params=[("id", "name")])
    channel_search = anonym_method(path="/channel/search",
        required_params=["keyword"], wiki_path="ChannelSearch")
    channel_stream = anonym_method(path="/channel/stream",
        required_params=[("id", "name")], wiki_path="ChannelStream")
    channel_newest = anonym_method(path="/channel/newest", wiki_path="ChannelNewest")
    channel_members = anonym_method(path="/channel/members", wiki_path="ChannelMembers",
        required_params=[("id", "name")])
    channel_is_member = anonym_method(path="/channel/is_member", wiki_path="ChannelIsMember",
        required_params=[("user_id", "user_name"), ("channel_id", "channel_name")])
    channel_suggestion = anonym_method(path="/channel/suggestion", method="GET",
        required_params=["user_id"], wiki_path="ChannelSuggestion")

    ## anonym post
    post_get_one = anonym_method(path="/post/get_one", wiki_path="GetOne",
        required_params=["post_id"])
    post_likes = anonym_method(path="/post/likes", wiki_path="Likes",
        required_params=["post_id"])
    post_responses = anonym_method(path="/post/response", wiki_path="Responses",
        required_params=["post_id"])
    post_is_post_liked = anonym_method(path="/post/is_post_liked",
        wiki_path="IsPostLiked", required_params=["post_id", "user_id"])
    post_is_response_liked = anonym_method(path="/post/is_response_liked",
        wiki_path="IsPostResponse", required_params=["resp_id", "user_id"])
    post_popular_articles = anonym_method(path="/post/popular_articles",
        wiki_path="PopularArticles")
    post_popular_photos = anonym_method(path="/post/popular_photos",
        wiki_path="PopularPhotos")
    post_popular_videos = anonym_method(path="/post/popular_videos",
        wiki_path="PopularVideos")

    ## authentic user
    iam_supporting = authentic_method(path="/iam/supporting",
        wiki_path="IamSupporting")
    my_supporter = authentic_method(path="/my/supporter",
        wiki_path="MySupporter")
    my_stream = authentic_method(path="/my/stream",
        wiki_path="MyStream")
    my_email = authentic_method(path="/my/email",
        wiki_path="MyEmail")
    my_birth_date = authentic_method(path="/my/birth_date",
        wiki_path="MyBirthDate")
    my_info = authentic_method(path="/my/info",
        wiki_path="MyInfo")
    my_channels = authentic_method(path="/my/channels",
        wiki_path="MyChannels")
    my_notifications = authentic_method(path="/my/notifications",
        wiki_path="MyNotifications")
    my_blocked_users = authentic_method(path="/my/blocked_users",
        wiki_path="MyBlockedUsers")
    my_blocked_channels = authentic_method(path="/my/blocked_channels",
        wiki_path="MyBlockedChannels")
    my_dialogue = authentic_method(path="/my/dialogue",
        wiki_path="MyDialogue")
    my_notif = authentic_method(path="/my/notif",
        wiki_path="MyNotif")
    
    user_update_profile = authentic_method(path="/user/update_profile", method="POST",
        wiki_path="UserUpdateProfile")
    user_support = authentic_method(path="/user/support", method="POST",
        wiki_path="UserSupport", required_params=["uidname"])
    user_unsupport = authentic_method(path="/user/unsupport", method="POST",
        wiki_path="UserUnsupport", required_params=["uidname"])
    user_block = authentic_method(path="/user/block", method="POST",
        wiki_path="UserBlock", required_params=["uidname"])
    user_unblock = authentic_method(path="/user/unblock", method="POST",
        wiki_path="UserUnblock", required_params=["uidname"])
    user_report = authentic_method(path="/user/report", method="POST",
        wiki_path="UserReport", required_params=["uidname", "message"])
    
    ## notification
    notification_mark_one = authentic_method(path="/notification/mark_one",
        method="POST", required_params=["id", "state"], wiki_path="NotificationMarkOne")
    notification_mark_all = authentic_method(path="/notification/mark_all",
        method="POST", wiki_path="NotificationMarkAll")
    notification_mark_all_dialogue = authentic_method(path="/notification/mark_all_dialogue",
        method="POST", wiki_path="NotificationMarkAllDialogue")
    notification_mark_all_whisper = authentic_method(path="/notification/mark_all_whisper",
        method="POST", wiki_path="NotificationMarkAllWhisper")
    notification_mark_all_notification = authentic_method(path="/notification/mark_all_notification",
        method="POST", wiki_path="NotificationMarkAllNotification")
    
    notification_reset_dialogue_count = authentic_method(path="/notification/reset_dialogue_count",
        method="POST", wiki_path="NotificationResetDialogueCount")
    notification_reset_whisper_notif_count = authentic_method(path="/notification/reset_whisper_notif_count",
        method="POST", wiki_path="NotificationResetWhisperNotifCount")
    notification_reset_notification_count = authentic_method(path="/notification/reset_notification_count",
        method="POST", wiki_path="NotificationResetNotificationCount")

    ## authentic channel
    channel_create = authentic_method(path="/channel/create", method="POST",
        required_params=["name", "desc"], wiki_path="ChannelCreate")
    channel_remove = authentic_method(path="/channel/remove", method="POST",
        required_params=["id"], wiki_path="ChannelRemove")
    channel_join = authentic_method(path="/channel/join", method="POST",
        required_params=["uidname"], wiki_path="ChannelJoin")
    channel_leave = authentic_method(path="/channel/leave", method="POST",
        required_params=["uidname"], wiki_path="ChannelLeave")
    channel_invite_users = authentic_method(path="/channel/invite_users", method="POST",
        required_params=["uidname", ("user_ids", "user_names")], wiki_path="ChannelInviteUsers")
    channel_scoop = authentic_method(path="/channel/scoop", method="GET",
        wiki_path="ChannelScoop")
    channel_mark_read_new_post = authentic_method(path="/channel/mark_read_new_post", method="POST",
        required_params=["ch_id"], wiki_path="ChannelMarkReadNewPost")
    channel_block = authentic_method(path="/channel/block", method="POST",
        required_params=["uidname"], wiki_path="ChannelBlock")
    channel_unblock = authentic_method(path="/channel/unblock", method="POST",
        required_params=["uidname"], wiki_path="ChannelUnblock")

    ## authentic post
    post_write_mind = authentic_method(path="/post/write_mind", method="POST",
        required_params=["message", "origin_id"], wiki_path="WriteMind")
    post_create_deal = authentic_method(path="/post/create_deal", method="POST",
        required_params=["name", "desc", "currency", "price", "origin_id",
            "locale", "location", "condition"], wiki_path="CreateDeal")
    post_create_article = authentic_method(path="/post/create_article", method="POST",
        required_params=["title", "message", "origin_id"], wiki_path="CreateArticle")
    post_create_ask = authentic_method(path="/post/create_ask", method="POST",
        required_params=["subject", "message", "origin_id"], wiki_path="CreateAsk")
    post_write_response = authentic_method(path="/post/write_response", method="POST",
        required_params=["post_id", "origin_id", "message"], wiki_path="PostWriteResponse")
    post_like_response = authentic_method(path="/post/like_response", method="POST",
        required_params=["id"], wiki_path="LikeResponse")
    post_unlike_response = authentic_method(path="/post/unlike_response", method="POST",
        required_params=["id"], wiki_path="UnlikeResponse")
    post_write_answer = authentic_method(path="/post/write_answer", method="POST",
        required_params=["ask_id", "origin_id", "message"], wiki_path="PostWriteAnswer")
    post_like_answer = authentic_method(path="/post/like_answer", method="POST",
        required_params=["answer_id"], wiki_path="LikeAnswer")
    post_unlike_answer = authentic_method(path="/post/unlike_answer", method="POST",
        required_params=["answer_id"], wiki_path="UnlikeAnswer")
    post_like_post = authentic_method(path="/post/like_post", method="POST",
        required_params=["post_id"], wiki_path="LikePost")
    post_unlike_post = authentic_method(path="/post/unlike_post", method="POST",
        required_params=["post_id"], wiki_path="UnlikePost")
    post_hide_post = authentic_method(path="/post/hide_post", method="POST",
        required_params=["post_id"], wiki_path="HidePost")
    post_remove_post = authentic_method(path="/post/remove_post", method="POST",
        required_params=["post_id"], wiki_path="RemovePost")
    post_shout = authentic_method(path="/post/shout", method="POST",
        required_params=["post_id"], wiki_path="Shout")

    ## whisper
    whisper_get_one = authentic_method(path="/whisper/get_one", required_params=["id"],
        wiki_path="WhisperGetOne")
    whisper_get_all = authentic_method(path="/whisper/get_all", wiki_path="WhisperGetAll")
    whisper_send = authentic_method(path="/whisper/send", method="POST",
        required_params=["message"], wiki_path="WhisperSend")
    whisper_write_response = authentic_method(path="", method="POST",
        required_params=["id", "message"], wiki_path="WhisperWriteResponse")
    whisper_get_responses = authentic_method(path="/whisper/get_responses", method="POST",
        required_params=["id"], wiki_path="WhisperGetResponses")
