from response import HTTPResponse
import boto.dynamodb
from boto.dynamodb.condition import *
from auth import generate_key, salt_string, check_salted
import json
import sys, traceback
from datetime import datetime
from time import mktime

def timestamp():
    return int(mktime(datetime.utcnow().timetuple()))

def cookie(session_id=''):
    return 'session_id=%s; Path=/; Expires=Tue, 31-Dec-2019 23:59:59 GMT' % (session_id, )        

class Resource(object):
    connection = None
    tables = {}
    
    def __init__(self, request):
        self.request = request
        self.response = None
        self.session = None
        
        if not self.connection:
            self.connection =  boto.dynamodb.connect_to_region('eu-west-1')
        
        if not self.tables:
            for table_name in ['user', 'email', 'username', 'session']:
                self.tables[table_name] = self.connection.get_table(table_name)
        
        if self.request.session_id:
            self.session = self.tables['session'].get_item(hash_key=self.request.session_id)
        
        try:
            getattr(self, {
                    'GET': 'do_get',
                    'POST': 'do_post',
                    'PUT': 'do_put',
                    'DELETE': 'do_delete',
                    }[self.request.method.upper()])()
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print traceback.format_exception(exc_type, exc_value, exc_traceback)
            
            self.response = HTTPResponse(status=405)

class UserResource(Resource):
    resource_name = 'user'
    
    def do_get(self):        
        self.response = HTTPResponse(status=200, headers={'foo': 'bar', 'baz': 'quux'}, body='GET user')
    
    def do_post(self):
        self.response = HTTPResponse(status=200, headers={'foo': 'bar', 'baz': 'quux'}, body='POST user')
    
class SessionResource(Resource):
    resource_name = 'session'
    
    def do_get(self):
        print self.session
        self.response = HTTPResponse(status=200, headers={'foo': 'bar', 'baz': 'quux'}, body='GET session')
    
    def do_post(self): # log in user
        if self.session: # user already logged in
            self.response = HTTPResponse(status=400)
            return
        
        try:
            credentials = json.loads(self.request.body)
            if not credentials['login'] or not credentials['password']: # malformed credential payload
                self.response = HTTPResponse(status=400)
                return
        except: # malformed credential payload
            self.response = HTTPResponse(status=400)
            return
        
        if '@' in credentials['login']: # log in with email address
            lookup = self.tables['email'].get_item(hash_key=credentials['login'])
        else: # log in with username
            lookup = self.tables['username'].get_item(hash_key=credentials['login'])
        user = self.tables['user'].get_item(hash_key=lookup['user'])
        
        if not user: # no such user
            self.response = HTTPResponse(status=400)
            return
        
        if not check_salted(credentials['password'], user['password']): # incorrect password
            self.response = HTTPResponse(status=401)
            return
        
        session_id = generate_key()
        attrs = { 'timestamp': timestamp(), 'user': user['id'], 'email': user['email'], 'username': user['username'] }
        session = self.tables['session'].new_item(hash_key=session_id, attrs=attrs)
        session.put()
        
        self.response = HTTPResponse(status=200, headers={'Set-Cookie': cookie(session_id) })
        
    def do_delete(self):
        print self.session

        if not self.session:
            self.response = HTTPResponse(status=400)
            return
                
        self.session.delete()
        
        self.response = HTTPResponse(status=200, headers={'Set-Cookie': cookie() })
