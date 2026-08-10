import os
from pathlib import Path
import jmcomic

from main import create_download_option_string

current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")
os.makedirs(FILE_PATH, exist_ok=True)


def test_get_comic_info():
    testClient = jmcomic.JmOption.default().new_jm_client()
    page = testClient.search_site(search_query="1225432")
    album: jmcomic.JmAlbumDetail = page.single_album
    assert "ヒルチャールに败北" in album.title or "ヒルチャールに敗北" in album.title
    assert "全彩" in album.tags
    assert album.views is not None
    assert album.likes is not None


def test_rank_comic():
    client = jmcomic.JmOption.default().new_jm_client()
    page1: jmcomic.JmCategoryPage = client.month_ranking(1)
    page2: jmcomic.JmCategoryPage = client.week_ranking(1)
    page3: jmcomic.JmCategoryPage = client.day_ranking(1)
    assert page1.page_size > 0
    assert page2.page_size > 0
    assert page3.page_size > 0


def test_comic_download():
    optionStr = create_download_option_string(FILE_PATH)
    option = jmcomic.create_option_by_str(optionStr)
    jmcomic.JmModuleConfig.CLASS_DOWNLOADER = jmcomic.JmDownloader
    album_list = jmcomic.download_album(1225432, option)
    if not album_list:
        raise Exception("Album download failed or returned no results.")
    file_title = album_list[0].title
    zip_file_name = f"{file_title}.zip"
    zip_file_path = FILE_PATH / zip_file_name
    assert zip_file_path.exists() == True
    zip_file_path.unlink()
    assert zip_file_path.exists() == False
