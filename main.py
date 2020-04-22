'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
# pylint: disable=unused-argument
# pylint: disable=wrong-import-order
# import json
import json
import os
import sys
import tempfile
import traceback
import uuid

from flask import Flask, jsonify, request, Response, send_file

from liv_covid19.web import manager


# Configuration:
SECRET_KEY = str(uuid.uuid4())

# Create application:
_STATIC_FOLDER = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              'static')

_EXPORT_FOLDER = tempfile.gettempdir()

app = Flask(__name__, static_folder=_STATIC_FOLDER)
app.config.from_object(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

DEBUG = False
TESTING = False

_MANAGER = manager.Manager(_EXPORT_FOLDER)


@app.route('/')
def home():
    '''Renders homepage.'''
    return app.send_static_file('index.html')


@app.route('/<path:path>')
def get_path(path):
    '''Renders homepage.'''
    return app.send_static_file('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    '''Responds to submission.'''
    return json.dumps({'job_id': _MANAGER.submit(request.data)})


@app.route('/progress/<job_id>')
def progress(job_id):
    '''Returns progress of job.'''
    return Response(_MANAGER.get_progress(job_id),
                    mimetype='text/event-stream')


@app.route('/cancel/<job_id>')
def cancel(job_id):
    '''Cancels job.'''
    return _MANAGER.cancel(job_id)


@app.route('/result/<job_id>')
def get_result(job_id):
    '''Get result.'''
    return send_file(os.path.join(_EXPORT_FOLDER, job_id + '.zip'),
                     attachment_filename=job_id + '.zip',
                     mimetype='application/octet-stream',
                     as_attachment=True)


@app.errorhandler(Exception)
def handle_error(_):
    '''Handles errors.'''
    # app.logger.error('Exception: %s', (error))
    traceback.print_exc()
    response = jsonify({'message': traceback.format_exc()})
    response.status_code = 500
    return response


def main(argv):
    '''main method.'''
    if argv:
        app.run(host='0.0.0.0', threaded=True, port=int(argv[0]))
    else:
        app.run(host='0.0.0.0', threaded=True)


if __name__ == '__main__':
    main(sys.argv[1:])
