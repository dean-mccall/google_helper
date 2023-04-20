import json
import logging
import pickle
from pathlib import Path

import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery
import pandas as pd
import requests
from google_auth_oauthlib.flow import InstalledAppFlow


logger = logging.getLogger(__name__)


class Token(object):
    """keep oauth token information"""
    def __init__(self, secret_file, scopes):
        #  assign token attributes
        self.scopes = scopes
        self.cached_secret_file = secret_file
        self.credentials = None

        #  set the name for the stored token
        pickle_file = Path(secret_file + '.pickle')

        #  check for existing stored token
        if pickle_file.exists():
            logger.debug('found existing token')
            with open(pickle_file, 'rb') as token :
                self.credentials = pickle.load(token)

        #  check validity of stored token
        if not self.credentials or not self.credentials.valid:
            #  token needs to be refreshed
            if self.credentials and self.credentials.expired and self.credentials.refresh_token :
                logger.debug('refreshing token')
                self.credentials.refresh(google.auth.transport.requests.Request())
            #  follow flow to get a new token
            else:
                logger.debug('getting new token')
                flow = InstalledAppFlow.from_client_secrets_file(secret_file, scopes)
                self.credentials = flow.run_local_server()
                with open(pickle_file, 'wb') as token :
                    pickle.dump(self.credentials, token)


class NotFoundException(Exception):
    """search for value failed"""
    pass


class TooManyException(Exception):
    """search returned more rows than expected"""
    pass



class GoogleService(object):
    """handle connection to google api services"""
    #  this can be used for other google api services.  google photos is the first one

    def __init__(self, cached_secret_file, scopes, api_version, api_name):
        """initial token and google api service"""
        self.cached_secret_file = cached_secret_file
        self.scopes = scopes
        self.api_version = api_version
        self.api_name = api_name
        logger.debug('cached_secret_file = %s', self.cached_secret_file)
        logger.debug('scopes = %s', scopes)
        logger.debug('api_version = %s', api_version)
        logger.debug('api_name = %s', api_name)

        #  authentication token
        self.token = Token(cached_secret_file, scopes)

        #  service for calling API
        self.service = googleapiclient.discovery.build(api_name, api_version, credentials = self.token.credentials, static_discovery = False)




class GooglePhotoService(GoogleService):
    """google photo service connect"""
    #  paging size default
    PAGE_SIZE = 50

    def __init__(self, cached_secret_file):
        """pass google photos service information to super class"""
        GoogleService.__init__(
            self,
            cached_secret_file = cached_secret_file,
            scopes = ['https://www.googleapis.com/auth/photoslibrary.readonly', 'https://www.googleapis.com/auth/photoslibrary.sharing'],
            api_version = 'v1',
            api_name = 'photoslibrary')


    def albums(self):
        """retrieve a list of all albums"""

        #  result
        result = []
        page_token = None
        while True:
            #  call the api via service
            response = self.service.albums().list(pageSize = self.PAGE_SIZE, pageToken = page_token).execute()

            #  append the albums to the result
            for album in response['albums']:
                result.append(album)

            #  when there is no nextPageToken, you are done
            if not 'nextPageToken' in response:
                break

            #  set starting point for the next page
            page_token = response['nextPageToken']

        logger.debug('return %s albums', len(result))
        return result


    def album_by_title(self, title):
        """find an album by album title"""

        #  get a list of all the albums
        albums_df = pd.DataFrame(self.albums())

        #  use a dataframe to find the album by title
        found_album_df = albums_df[albums_df['title'] == title]

        #  test if the album is not found
        if len(found_album_df.index) == 0:
            raise NotFoundException()

        #  if there are more than one album with the same name, raise an exception
        if len(found_album_df.index) > 1:
            raise TooManyException()

        logger.debug('found an album to return')
        return found_album_df.to_dict('records')[0]


    def media_items_by_album(self, album_id):
        """search for the media items (pictures or videos) in the album"""
        #  result set
        result = []

        #  search request body
        request_body = dict()
        request_body['albumId'] = album_id
        request_body['pageSize'] = self.PAGE_SIZE

        #  pageToken is empty on first call
        page_token = None
        while True:
            request_body['pageToken'] = page_token

            #  search for media items
            response = self.service.mediaItems().search(body = request_body).execute()

            #  add the results to the result list
            for media_item in response['mediaItems']:
                result.append(media_item)

            #  if there is no nextPageToken, you are at the end
            if not 'nextPageToken' in response:
                break

            #  not finished, prepare for the next page
            page_token = response['nextPageToken']

        logger.debug('found %s media items', len(result))
        return result


    def album_export_by_title(self, title, output_directory_name:str):
        """export the contents of an album to folder"""
        output_directory = Path(output_directory_name)
        output_directory.mkdir(parents = True, exist_ok = True)

        album = self.album_by_title(title)
        media_items = self.media_items_by_album(album.get('id'))

        #  save the items to the folder
        for media_item in media_items:
            output_file_name = media_item['id'] + '_' + media_item['filename']
            output_file = output_directory / output_file_name

            #  retrieve the contents of the file
            response = requests.get(media_item['baseUrl'])

            with open(output_file, 'wb') as media_item_file:
                media_item_file.write(response.content)

        #  serialize the media items json as an inventory
        with open(output_directory / 'media_items.json', 'w') as inventory_file:
            inventory_file.write(json.dumps(media_items))

        logger.debug('wrote %s files plus inventory', len(media_items))
