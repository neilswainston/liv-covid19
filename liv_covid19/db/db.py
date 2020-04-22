'''
(c) University of Liverpool 2020

Licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>..

@author: neilswainston
'''
# pylint: disable=no-member
import os.path
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1srAwJ6nzsLVJ4djexBCpkoR_DA46vWvopBp8mcSytiM'


def get_data(spreadsheet_id, rnge='Sheet1'):
    '''Get data.'''
    sheets = _get_spreadsheets()

    result = sheets.values().get(spreadsheetId=spreadsheet_id,
                                 range=rnge).execute()

    return result.get('values', [])


def _get_spreadsheets():
    '''Get spreadsheets.'''
    credentials = _get_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    return service.spreadsheets()


def _get_credentials():
    '''Get credentials.'''
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time:
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in:
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save the credentials for the next run:
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)

    return credentials


def main():
    '''Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    '''
    values = get_data(SAMPLE_SPREADSHEET_ID)

    for row in values:
        print(row)


if __name__ == '__main__':
    main()
