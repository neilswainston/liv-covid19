'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=invalid-name
import os
from threading import Thread
import uuid
import zipfile


class JobThread(Thread):
    '''Wraps a job into a thread, and fires events.'''

    def __init__(self, query, max_iter):
        Thread.__init__(self)

        self._job_id = str(uuid.uuid4())
        self._query = query
        self._result = None
        self._cancelled = False

        self.__max_iter = max_iter
        self.__listeners = set()

    def get_job_id(self):
        '''Gets thread job id.'''
        return self._job_id

    def cancel(self):
        '''Cancels the current job.'''
        self._cancelled = True

    def add_listener(self, listener):
        '''Adds an event listener.'''
        self.__listeners.add(listener)

    def remove_listener(self, listener):
        '''Removes an event listener.'''
        self.__listeners.remove(listener)

    def _fire_job_event(self, status, iteration, message=''):
        '''Fires an event.'''
        event = {'update': {'status': status,
                            'message': message,
                            'progress': float(iteration) /
                            self.__max_iter * 100,
                            'iteration': iteration,
                            'max_iter': self.__max_iter}
                 }

        if status == 'finished':
            event['result'] = self._result

        self._fire_event(event)

    def _fire_event(self, event):
        '''Event listener, passes events on to registered listeners.'''
        event.update({'job_id': self._job_id})

        for listener in self.__listeners:
            listener.event_fired(event)


def save_export(parent_dir, out_dir, job_id):
    '''Save export file, returning the url.'''
    out_filename = os.path.join(out_dir, job_id + '.zip')

    with zipfile.ZipFile(out_filename, 'w') as zf:
        for path, _, filenames in os.walk(parent_dir):
            for filename in filenames:
                zf.write(os.path.join(path, filename),
                         os.path.join(path.replace(parent_dir, ''), filename))

    return out_filename
