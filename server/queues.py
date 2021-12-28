from flask_restful import Resource
from flask import render_template, make_response
import constants


class QueueResource(Resource):

    def get(self):
        return make_response(render_template('queue.html', env=constants.env),
                             200, {'Content-Type': 'text/html'})
