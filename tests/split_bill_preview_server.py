"""In-memory synthetic Split Bill API for FE verification. Never accesses app DB."""
import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4
from pydantic import ValidationError
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.split_bill_schema import GroupCreate, GroupUpdate
from app.services.split_bill_service import calculate
from app.services.split_bill_pdf import export_pdf

groups = {}
authorization = ''


def project(group):
    return group | {'Calculation': calculate(GroupCreate.model_validate({key: value for key, value in group.items() if key not in ('Id','Version')})), 'UserId': 'forbidden', 'AccessToken': 'forbidden'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, value=None):
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        if value is not None:
            self.wfile.write(json.dumps(value).encode())

    def handle_request(self):
        global authorization
        authorization = self.headers.get('Authorization','') if self.path != '/__authorization' else authorization
        if self.path == '/__authorization':
            self.send(200, {'Authorization': authorization}); return
        if self.path == '/auth/me':
            self.send(200, {'Id':'synthetic', 'Name':'Split Bill Preview', 'Email':'preview@example.test','PictureUrl':None}); return
        try:
            if self.path == '/split-bills' and self.command == 'GET':
                self.send(200,[project(group) for group in groups.values()]); return
            if self.command == 'GET' and self.path.endswith('/export'):
                group_id = self.path.split('/')[-2]
                if group_id not in groups:
                    self.send(404,{'detail':'missing'}); return
                self.send_response(200)
                self.send_header('Content-Type','application/pdf')
                self.end_headers()
                self.wfile.write(export_pdf(project(groups[group_id]))); return
            group_id = self.path.split('/')[-1]
            if self.command in ('GET','PATCH','DELETE') and group_id not in groups:
                self.send(404,{'detail':'missing'}); return
            if self.command == 'GET':
                self.send(200,project(groups[group_id])); return
            if self.command == 'DELETE':
                del groups[group_id]; self.send(204); return
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            payload=(GroupCreate if self.command == 'POST' else GroupUpdate).model_validate(body)
            calculate(payload)
            if self.command == 'PATCH' and payload.version != groups[group_id]['Version']:
                self.send(409,{'detail':'conflict'}); return
            group_id = str(uuid4()) if self.command == 'POST' else group_id
            group = payload.model_dump(mode='json',by_alias=True,exclude={'version'}) | {'Id':group_id,'Version':1 if self.command == 'POST' else groups[group_id]['Version']+1}
            groups[group_id]=group
            self.send(201 if self.command == 'POST' else 200,project(group))
        except ValidationError as error:
            self.send(422,{'detail':[{'loc':['body',*issue['loc']], 'msg':issue['msg'],'type':issue['type'], 'input':'forbidden'} for issue in error.errors()]})
        except HTTPException as error:
            self.send(error.status_code,{'detail':error.detail})
        except (ValueError, KeyError):
            self.send(400,{'detail':'invalid'})

    do_GET = do_POST = do_PATCH = do_DELETE = handle_request


if __name__ == '__main__':
    HTTPServer(('127.0.0.1',int(sys.argv[1])),Handler).serve_forever()
