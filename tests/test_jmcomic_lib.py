import os
from pathlib import Path
import jmcomic

current_dir = os.getcwd()
FILE_PATH = Path(f"{current_dir}/temp")
os.makedirs(FILE_PATH, exist_ok=True)


def test_get_comic_info():
    testClient = jmcomic.JmOption.default().new_jm_client()
    page = testClient.search_site(search_query="1225432")
    album: jmcomic.JmAlbumDetail = page.single_album
    assert album.title == "［酸菜鱼ゅ°］ヒルチャールに败北した胡桃 表情、台词差分"
    assert album.tags == ["全彩", "贫乳", "调教", "中文"]
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
    optionStr = f"""
           client:
             cache: null
             domain: []
             impl: api
             postman:
               meta_data:
                 headers: null
                 impersonate: chrome
                 proxies: {{}}
               type: curl_cffi
             retry_times: 5
           dir_rule:
             base_dir: {FILE_PATH}
             rule: Bd_Pname
           download:
             cache: true
             image:
               decode: true
               suffix: null
             threading:
               image: 30
               photo: 8
           log: true
           plugins:
             valid: log
             after_album:
               - plugin: zip
                 kwargs:
                   level: photo 
                   filename_rule: Ptitle 
                   zip_dir: {FILE_PATH}
                   delete_original_file: true
           version: '2.1'
           """
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
