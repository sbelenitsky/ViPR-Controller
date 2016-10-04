__author__ = 'belens'

"""
VseHttp library is responsible for HTTP communication, mostly to and from
ViPR RESTful APIs.

This library will store cookie jar, ViPR connection cookie, and implement
GET/PUT/DELETE/POST calls - the outlook here is on connection to multiple
ViPR instances by instantiating HTTP to multiple ViPRs and negotiating
logon to each separately.

Default protocol is HTTPS, always
"""

# TODO: cookie timeout is 2 hours, need to manage timestamp of a cookie
# TODO: idea - need_to_refresh_login function ?

from vseCmn import module_var
# from requests import codes, Session, Request, Response, __version__
import requests
import json

# suppress annoying insecure HTTPS warnings
# shows an error in Editor, but actually works in practice.
# from requests.packages.urllib3.connectionpool import InsecureRequestWarning
# requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class VseHttp:
    IDX_CMN = "Module_Ref_Common"
    IDX_IP = "Connection_IP"
    IDX_PORT = "Connection_Port"
    IDX_VIPR_USER = "ViPR_C_User"
    IDX_VIPR_PASSWORD = "ViPR_C_Password"
    IDX_SESSION = "HTTP_Session"
    IDX_VIPR_AUTH_COOKIE = "ViPR_C_Auth_Cookie"
    IDX_HTTP_PROTOCOL = "HTTP Protocol"

    VIPR_AUTH_HEADER = "X-SDS-AUTH-TOKEN"
    PROTOCOL_HTTPS = "https"

    def __init__(self, cmn, ip, port, vipr_user=None, vipr_password=None):
        module_var(self, self.IDX_CMN, cmn)
        module_var(self, self.IDX_HTTP_PROTOCOL, self.PROTOCOL_HTTPS)
        module_var(self, self.IDX_IP, ip)
        module_var(self, self.IDX_PORT, port)
        module_var(self, self.IDX_SESSION, requests.Session())

        if vipr_user is not None:
            module_var(self, self.IDX_VIPR_USER, vipr_user)

        if vipr_password is not None:
            module_var(self, self.IDX_VIPR_PASSWORD, vipr_password)

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "VseHttp module initialization is complete for [{0}:{"
                     "1}]".format(ip, port))


    def request(self, method, resource, body=None,
                content_type='application/json',
                filename=None,
                custom_headers=None,
                vipr_request=True):
        """
        Assumptions:
            - returns JSON body always
            - attaches ViPR Auth token as header if it has a value

        :param method: HTTP method - GET, POST, PUT, DELETE
        :param resource: web address (omit ip/port, they are implied)
        :param body: body encoded with JSON by default, but can be overridden
        :param content_type: specification for how body is encoded
        :param filename: if file is to be uploaded to downloaded into
        :param custom_headers: a dictionary of additional headers if required
        :param vipr_request: defaults to True, set to False if not

        :return: HTTP response object
        """
        cmn = module_var(self, self.IDX_CMN)

        if vipr_request and not self.vipr_logged_in():
            raise RuntimeError("Not logged into ViPR")

        session = module_var(self, self.IDX_SESSION)

        #
        # setup basic headers
        # ViPR authorization header is cached in session
        # add custom headers if any come in
        #
        session.headers.update({
            'Content-Type': content_type,
            'ACCEPT': 'application/json, application/octet-stream'
        })

        if custom_headers is not None:
            session.headers.update(custom_headers)

        full_url = "{0}://{1}:{2}{3}".format(
            module_var(self, self.IDX_HTTP_PROTOCOL),
            module_var(self, self.IDX_IP),
            module_var(self, self.IDX_PORT),
            resource
        )

        if method not in ['GET', 'PUT', 'POST', 'DELETE']:
            raise RuntimeError(
                "Unknown/Unsupported HTTP method: {0}".format(method))

        #
        # Details @ http://docs.python-requests.org/en/latest/api/
        #
        # Session.request(method, url, params=None, data=None, headers=None,
        #                 cookies=None, files=None, auth=None, timeout=None,
        #                 allow_redirects=True, proxies=None, hooks=None,
        #                 stream=None, verify=None, cert=None, json=None)
        #
        # Details @ http://docs.python-requests.org/en/v0.14.2/api/
        #
        # Session.request(method, url, params=None, data=None, headers=None,
        #                 cookies=None, files=None, auth=None, timeout=None,
        #                 allow_redirects=True, proxies=None, hooks=None,
        #                 return_response=True, config=None, prefetch=None,
        #                 verify=None, cert=None)
        #
        # only versions prior to v1.x.x have prefetch, others have "streaming"
        # furthermore, prefetch needs to be set to False, while streaming to
        #  True... weird...
        #

        #
        # Print what we are trying to do
        #
        msg = ""
        msg += "Executing ViPR API Call:\n"
        msg += "\tHTTP Method: {0}\n".format(method)
        msg += "\tURL        : {0}\n".format(full_url)
        msg += "\tHeaders    : {0}\n".format(session.headers)
        msg += "\tFile       : {0}\n".format(
            filename if filename is not None else "")
        msg += "\tBody       : {0}\n".format(
            body if body is not None else "")
        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     msg,
                     None,
                     print_only_in_full_debug_mode=True)


        #
        # GET into a file...
        #
        if method == 'GET' and filename is not None:
            #
            # depending on library versions different settings are required
            #
            if requests.__version__.startswith('0'):
                response = session.request(
                    method, full_url, verify=False, prefetch=False)

            else:
                response = session.request(
                    method, full_url, verify=False, stream=True)

            with open(filename, 'wb') as fp:
                while True:
                    chunk = response.raw.read(1024 * 1024)
                    if not chunk:
                        break
                    fp.write(chunk)
        #
        # GET plain vanilla
        #
        elif method == 'GET':
            response = session.request(method, full_url, verify=False)

        #
        # POST a file
        #
        elif method == 'POST' and filename is not None:
            response = session.request(
                method, full_url, data=open(filename, "rb"), verify=False)

        #
        # POST vanilla, PUT, DELETE
        #
        else:
            response = session.request(
                method, full_url, data=body, verify=False)

        if response.status_code == requests.codes['ok'] or \
           response.status_code == requests.codes['accepted']:
            return response.status_code, response.text

        else:
            cmn.printMsg(
                cmn.MSG_LVL_ERROR,
                "Request failed, message:\n {0}".format(response.text))
            response.raise_for_status()


    def vipr_login(self):
        """
        Logs into ViPR instance (assuming vipr parameters have been provided)

        throws exceptions when credentials are not supplied or problem
        connecting

        :return: nothing. if no exception thrown then login succeeded
        """
        cmn = module_var(self, self.IDX_CMN)
        protocol = module_var(self, self.IDX_HTTP_PROTOCOL)
        ip = module_var(self, self.IDX_IP)
        port = module_var(self, self.IDX_PORT)
        user = module_var(self, self.IDX_VIPR_USER)
        pwd = module_var(self, self.IDX_VIPR_PASSWORD)

        if user is None or pwd is None:
            raise RuntimeError("Username or password for ViPR are undefined")

        if self.vipr_logged_in():
            cmn.printMsg(cmn.MSG_LVL_DEBUG,
                         "User {0} @ {1}:{2} is already logged in, need to "
                         "logout first...".format(user, ip, port))
            self.vipr_logout()

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Logging into ViPR - {0} @ {1}:{2}...".format(
                         user, ip, port
                     ))

        session = module_var(self, self.IDX_SESSION)
        response = session.get(
            "{0}://{1}:{2}/login".format(protocol, ip, port),
            auth=(user, pwd),
            verify=False)

        if response.status_code != requests.codes['ok']:
            cmn.printMsg(cmn.MSG_LVL_ERROR,
                         "Login failed, message:\n {0}".format(response.text))
            response.raise_for_status()

        # save authorization header
        module_var(self,
                   self.IDX_VIPR_AUTH_COOKIE,
                   response.headers[self.VIPR_AUTH_HEADER])

        # set authorization header for the session
        session.headers.update({
            self.VIPR_AUTH_HEADER: response.headers[self.VIPR_AUTH_HEADER]
        })


    def vipr_logout(self):
        """
        logout of vipr. throws errors/exceptions if no creds, never logged in,
        etc

        :return:
        """
        cmn = module_var(self, self.IDX_CMN)
        protocol = module_var(self, self.IDX_HTTP_PROTOCOL)
        ip = module_var(self, self.IDX_IP)
        port = module_var(self, self.IDX_PORT)
        user = module_var(self, self.IDX_VIPR_USER)
        pwd = module_var(self, self.IDX_VIPR_PASSWORD)

        if user is None or pwd is None:
            raise RuntimeError("Username or password for ViPR are undefined")

        if not self.vipr_logged_in():
            raise RuntimeError("Not logged into ViPR")

        cmn.printMsg(cmn.MSG_LVL_DEBUG,
                     "Logging out of ViPR - {0} @ {1}:{2}...".format(
                         user, ip, port
                     ))

        session = module_var(self, self.IDX_SESSION)
        response = session.get(
            "{0}://{1}:{2}/logout".format(protocol, ip, port),
            verify=False)

        if response.status_code != requests.codes['ok']:
            cmn.printMsg(cmn.MSG_LVL_ERROR,
                         "Logout failed, message:\n {0}".format(
                             response.text))
            response.raise_for_status()

        module_var(self, self.IDX_VIPR_AUTH_COOKIE, delete=True)


    def vipr_logged_in(self):
        """
        Returns True or False if logged into ViPR. Decision is based on
        presence of ViPR Auth Token, even though it may be expired by now
        though unlikely.

        :return:  True/False
        """
        if module_var(self, self.IDX_VIPR_AUTH_COOKIE) is not None:
            return True
        return False


def json_decode(rsp):
    return json.loads(rsp, object_hook=_decode_dict)


def json_encode(name, value):
    return json.dumps({name: value})


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv