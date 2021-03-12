import argparse
import json
import os
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename, sanitize_filepath
from requests.packages.urllib3.exceptions import InsecureRequestWarning


def create_input_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start_page",
        type=int,
        required=True,
        help="Первая страница",
    )
    parser.add_argument(
        "--end_page",
        type=int,
        default=702,
        help="Последняя страница",
    )
    parser.add_argument(
        "--dest_folder",
        type=str,
        default=".",
        help="Папка хранения обложки, текста, json",
    )
    parser.add_argument(
        "--skip_imgs",
        action="store_true",
        help="Отключить скачивание обложки",
    )
    parser.add_argument(
        "--skip_txt",
        action="store_true",
        help="Отключить скачивание текста",
    )
    parser.add_argument(
        "--json_path",
        type=str,
        default="json",
        help="Указать путь до файла описания",
    )
    return parser


def fetch_response(link: str) -> requests.models.Response:
    link_response = requests.get(link, verify=False, allow_redirects=False)
    link_response.raise_for_status()
    if link_response.status_code == 302:
        raise requests.exceptions.HTTPError
    return link_response


def parse_category_page(html: str) -> list:
    html_soup = BeautifulSoup(html, "lxml")
    book_link_selector = "body div#content .d_book tr:nth-of-type(2) a"
    book_short_links = [
        book_link["href"] for book_link in html_soup.select(book_link_selector)
    ]
    return book_short_links


def get_full_link(website_link: str, short_link: str) -> str:
    split_link = urlsplit(website_link)
    book_link = urljoin(f"{ split_link.scheme }://{ split_link.netloc }", short_link)
    return book_link


def write_file_json(data: list, filepath: str):
    with open(filepath, "a") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def extract_file_extension(link: str) -> str:
    split_link = urlsplit(link)
    split_link_unquote = unquote(split_link.path)
    file_extension = os.path.splitext(split_link_unquote)[1]
    return file_extension


def parse_book_page(website_link: str, book_short_link: str) -> dict:
    book_description = {}
    book_link = get_full_link(website_link, book_short_link)
    book_link_response = fetch_response(book_link)
    html_soup = BeautifulSoup(book_link_response.content, "lxml")
    book_text_link_selector = "body div#content .d_book a[title$='скачать книгу txt']"
    book_text_link = html_soup.select_one(book_text_link_selector)
    if book_text_link:
        book_title_and_author_selector = "body div#content h1"
        book_title_and_author = html_soup.select_one(book_title_and_author_selector)
        book_title, book_author = book_title_and_author.text.split("::")

        book_cover_link_selector = "body .bookimage img"
        book_cover_link = html_soup.select_one(book_cover_link_selector)

        book_comment_selector = "body div#content .texts .black"
        book_comments = [
            book_comment.text
            for book_comment in html_soup.select(book_comment_selector)
        ]

        book_genre_selector = "body div#content span.d_book a"
        book_genres = [
            book_genre.text for book_genre in html_soup.select(book_genre_selector)
        ]

        book_description = {
            "title": book_title.strip(),
            "author": book_author.strip(),
            "img_src_link": book_cover_link["src"],
            "book_path_link": book_text_link["href"],
            "genres": book_genres,
            "comments": book_comments,
        }
    return book_description


def download_book_text(category_link: str, book_description: dict, folder: str) -> str:
    book_text_link = get_full_link(category_link, book_description["book_path_link"])
    book_text_filename = book_description["title"]
    sanitized_filename = sanitize_filename(book_text_filename)
    page_response = fetch_response(book_text_link)
    filepath = f"{ os.path.join(folder, sanitized_filename) }.txt"
    with open(filepath, "w") as file:
        file.write(page_response.text)
    return filepath


def download_cover(category_link: str, book_description: dict, folder: str) -> str:
    book_cover_link = get_full_link(category_link, book_description["img_src_link"])
    book_cover_extension = extract_file_extension(book_cover_link)
    book_cover_filename = f"{ book_description['title'] }{ book_cover_extension }"
    page_response = fetch_response(book_cover_link)
    sanitized_filename = sanitize_filename(book_cover_filename)
    filepath = os.path.join(folder, sanitized_filename)
    with open(filepath, "wb") as file:
        file.write(page_response.content)
    return filepath


def get_book_short_links(
    category_link: str, start_category_page: int, end_category_page: int
) -> list:
    book_short_links = []
    for page in range(start_category_page, end_category_page):
        category_page_link = urljoin(category_link, str(page))
        category_page_link_response = fetch_response(category_page_link)
        book_short_links = book_short_links + parse_category_page(
            category_page_link_response.content
        )
    return book_short_links


def main():
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    input_parser = create_input_parser()
    args = input_parser.parse_args()
    tululu_category_link = "https://tululu.org/l55/"
    book_folder = sanitize_filepath(f"{ args.dest_folder }/books")
    cover_folder = sanitize_filepath(f"{ args.dest_folder }/images")
    json_folder = sanitize_filepath(f"{ args.dest_folder }/{ args.json_path }")
    json_filename = "book_desc.json"
    book_description_json = []
    Path(book_folder).mkdir(parents=True, exist_ok=True)
    Path(cover_folder).mkdir(parents=True, exist_ok=True)
    Path(json_folder).mkdir(parents=True, exist_ok=True)
    book_description_filepath = os.path.join(json_folder, json_filename)
    try:
        book_short_links = get_book_short_links(
            tululu_category_link, args.start_page, args.end_page
        )
        for book_short_link in book_short_links:
            book_description = parse_book_page(tululu_category_link, book_short_link)
            if "book_path_link" in book_description:
                if not args.skip_imgs:
                    book_description["img_src"] = download_cover(
                        tululu_category_link, book_description, cover_folder
                    )
                if not args.skip_txt:
                    book_description["book_path"] = download_book_text(
                        tululu_category_link, book_description, book_folder
                    )
                book_description.pop("img_src_link", None)
                book_description.pop("book_path_link", None)
                book_description_json.append(book_description)
        write_file_json(book_description_json, book_description_filepath)
    except requests.exceptions.ConnectionError:
        print("Что-то пошло не так:( Проверьте подключение к интернету!")
    except requests.exceptions.HTTPError:
        print("Проблемы с доступом к сайту tululu.org")


if __name__ == "__main__":
    main()
