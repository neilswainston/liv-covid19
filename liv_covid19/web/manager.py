'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
import json
import os.path
from threading import Thread
import time

from liv_covid19.web.artic import normal_thread, opentrons_thread


class Manager():
    '''Wbapp manager.'''

    def __init__(self, out_dir):
        self.__out_dir = out_dir
        self.__status = {}
        self.__threads = {}
        self.__writers = {}

        if not os.path.exists(self.__out_dir):
            os.makedirs(self.__out_dir)

    def submit(self, data):
        '''Responds to submission.'''
        query = json.loads(data)

        # Do job in new thread, return result when completed:
        thread = self.__get_thread(query)
        job_id = thread.get_job_id()
        thread.add_listener(self)
        self.__threads[job_id] = thread

        # Start new Threads:
        thread_pool = ThreadPool(thread)
        thread_pool.start()

        return job_id

    def get_progress(self, job_id):
        '''Returns progress of job.'''
        def _check_progress(job_id):
            '''Checks job progress.'''
            while (job_id not in self.__status or
                    self.__status[job_id]['update']['status'] == 'running'):
                time.sleep(1)

                if job_id in self.__status:
                    yield 'data:' + self.__get_response(job_id) + '\n\n'

            yield 'data:' + self.__get_response(job_id) + '\n\n'

        return _check_progress(job_id)

    def cancel(self, job_id):
        '''Cancels job.'''
        self.__threads[job_id].cancel()
        return job_id

    def event_fired(self, event):
        '''Responds to event being fired.'''
        self.__status[event['job_id']] = event

    def __get_response(self, job_id):
        '''Returns current progress for job id.'''
        return json.dumps(self.__status[job_id])

    def __get_thread(self, query):
        '''Get thread.'''
        app = query.get('app', 'undefined')

        if app == 'Opentrons':
            return opentrons_thread.OpentronsThread(query, self.__out_dir)

        if app == 'Normalise':
            return normal_thread.NormaliseThread(query, self.__out_dir)

        raise ValueError('Unknown app: ' + app)


class ThreadPool(Thread):
    '''Basic class to run job Threads sequentially.'''

    def __init__(self, thread):
        self.__thread = thread
        Thread.__init__(self)

    def run(self):
        self.__thread.start()
        self.__thread.join()
