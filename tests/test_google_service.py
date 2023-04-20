from google_helper import google_helper
import pytest
import tempfile
from pathlib import Path
import glob
import logging


logger = logging.getLogger(__name__)
TEST_ALBUM_NAME = 'One-Test'
CREDENTIALS_FOLDER_NAME = 'credentials'



def test_album_by_title():
    """test methods to find albums"""
    google_photos_service = google_helper.GooglePhotoService(cached_secret_file = CREDENTIALS_FOLDER_NAME + '/client_secret.json')

    #  search for an album that exists
    album = google_photos_service.album_by_title(TEST_ALBUM_NAME)
    assert album['id'] is not None, 'expected to get an id'

    #  serach for an album that does not exist
    with pytest.raises(google_helper.NotFoundException):
        album = google_photos_service.album_by_title(TEST_ALBUM_NAME + 'not found')



def test_album_export_by_title():
    """confirm export function is working"""
    google_photos_service = google_helper.GooglePhotoService(cached_secret_file = CREDENTIALS_FOLDER_NAME + '/client_secret.json')

    #  have the expected album contents to confirm the number of files created
    media_items = google_photos_service.media_items_by_album(google_photos_service.album_by_title(TEST_ALBUM_NAME)['id'])
    with tempfile.TemporaryDirectory() as temporary_directory:
        google_photos_service.album_export_by_title(TEST_ALBUM_NAME, str(temporary_directory))

        file_count = len(glob.glob(temporary_directory + '/*'))
        assert file_count == len(media_items) + 1, 'incorrect number of files in directory'






