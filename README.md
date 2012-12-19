pymtoauth
=========

pymtoauth is a python wrapper for working with Mindtalk API.
More information about Mindtalk API can be found in:

http://developer.mindtalk.com

Originally written for MTFeed Project (http://mtfeed.limbotolabs.com).

Library depedency
-----------------

 * decorator (http://pypi.python.org/pypi/decorator/)
 * pycurl (http://pypi.python.org/pypi/pycurl/)

Example usage
-------------

Usage with anonymous access (without access_token).

```python
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
```

Usage with authentic access (with access_token).

```python
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
```

Author
------

pymtoauth is developed and maintained by Rizky Abdilah (rizky@abdi.la). It can be found here: http://github.com/rizkyabdilah/pymtoauth

This library is originally written for MTFeed project and can be accessed here: http://mtfeed.limbotolabs.com

Link
----

 * http://developer.mindtalk.com/
 * http://developer.mindtalk.com/api/wiki/APIResources




