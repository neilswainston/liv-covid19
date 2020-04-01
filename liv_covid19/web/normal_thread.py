'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
import os.path
import tempfile

from liv_covid19 import normal
from liv_covid19.web.job import JobThread, save_export


class NormaliseThread(JobThread):
    '''Runs an Normalise job.'''

    def __init__(self, query, out_dir):
        self.__filename, suffix = os.path.splitext(query['file_name'])

        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        self.__in_filename = tmpfile.name

        with open(self.__in_filename, 'w') as fle:
            fle.write(query['file_content'])

        self.__out_dir = out_dir
        JobThread.__init__(self, query, 1)

    def run(self):
        '''Run.'''
        parent_dir = tempfile.mkdtemp()
        iteration = 0

        self._fire_job_event('running', iteration, 'Running...')

        normal.run(in_filename=self.__in_filename,
                   out_dir=parent_dir)

        iteration += 1

        if self._cancelled:
            self._fire_job_event('cancelled', iteration,
                                 message='Job cancelled')
        else:
            save_export(parent_dir, self.__out_dir, self._job_id)
            self._result = self._job_id
            self._fire_job_event('finished', iteration,
                                 message='Job completed')