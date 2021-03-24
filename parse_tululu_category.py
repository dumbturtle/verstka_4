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
        default=1,
        help="Первая страница",
    )
    parser.add_argument(
        "--last_page",
        type=int,
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
        "--json_filepath",
        type=str,
        default="json/book_desc.json",
        help="Указать имя и путь до файла описания",
    )
    return parser


def fetch_response(link: str) -> requests.models.Response:
    link_response = requests.get(link, verify=False, allow_redirects=False)
    link_response.raise_for_status()
    if link_response.status_code == 302:
        raise requests.exceptions.HTTPError
    return link_response


def parse_category_page(html: bytes, website_link: str) -> list:
    html_soup = BeautifulSoup(html, "lxml")
    book_link_selector = "body div#content .d_book tr:nth-of-type(2) a"
    book_links = [
        get_full_link(website_link, book_link["href"])
        for book_link in html_soup.select(book_link_selector)
    ]
    return book_links


def get_full_link(website_link: str, short_link: str) -> str:
    separated_link = urlsplit(website_link)
    book_link = urljoin(
        f"{ separated_link.scheme }://{ separated_link.netloc }", short_link
    )
    return book_link


def extract_file_extension(link: str) -> str:
    separated_link = urlsplit(link)
    unquoted_separated_link = unquote(separated_link.path)
    file_extension = os.path.splitext(unquoted_separated_link)[1]
    return file_extension


def fetch_book_text_link(html: str) -> str:
    html_soup = BeautifulSoup(html, "lxml")
    book_text_link_selector = "body div#content .d_book a[title$='скачать книгу txt']"
    book_text_link = html_soup.select_one(book_text_link_selector)
    return book_text_link


def parse_book_page(html: str) -> dict:
    book_description = {}
    html_soup = BeautifulSoup(html, "lxml")
    book_title_and_author_selector = "body div#content h1"
    book_title_and_author = html_soup.select_one(book_title_and_author_selector)
    book_title, book_author = book_title_and_author.text.split("::")

    book_cover_link_selector = "body .bookimage img"
    book_cover_link = html_soup.select_one(book_cover_link_selector)

    book_comment_selector = "body div#content .texts .black"
    book_comments = [
        book_comment.text for book_comment in html_soup.select(book_comment_selector)
    ]

    book_genre_selector = "body div#content span.d_book a"
    book_genres = [
        book_genre.text for book_genre in html_soup.select(book_genre_selector)
    ]

    book_description = {
        "title": book_title.strip(),
        "author": book_author.strip(),
        "img_src_link": book_cover_link["src"],
        "genres": book_genres,
        "comments": book_comments,
    }
    return book_description


def download_book_text(
    category_link: str, text_link: str, folder: str, filename: str
) -> str:
    book_text_link = get_full_link(category_link, text_link)
    sanitized_filename = sanitize_filename(filename)
    response = fetch_response(book_text_link)
    filepath = f"{ os.path.join(folder, sanitized_filename) }.txt"
    with open(filepath, "w") as file:
        file.write(response.text)
    return filepath


def download_cover(category_link: str, book_description: dict, folder: str) -> str:
    book_cover_link = get_full_link(category_link, book_description["img_src_link"])
    book_cover_extension = extract_file_extension(book_cover_link)
    book_cover_filename = f"{ book_description['title'] }{ book_cover_extension }"
    response = fetch_response(book_cover_link)
    sanitized_filename = sanitize_filename(book_cover_filename)
    filepath = os.path.join(folder, sanitized_filename)
    with open(filepath, "wb") as file:
        file.write(response.content)
    return filepath


def get_book_links(
    category_link: str, start_category_page: int, end_category_page: int
) -> list:
    book_links = []
    for page in range(start_category_page, end_category_page):
        category_page_link = urljoin(category_link, str(page))
        category_page_link_response = fetch_response(category_page_link)
        book_links = book_links + parse_category_page(
            category_page_link_response.content, category_link
        )
    return book_links


def fetch_category_last_page(category_link: str) -> int:
    response = fetch_response(category_link)
    html_soup = BeautifulSoup(response.content, "lxml")
    category_last_page_selector = "body div#content p.center a:last-child"
    category_last_page = html_soup.select_one(category_last_page_selector)
    return int(category_last_page.text)


def main():
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    input_parser = create_input_parser()
    args = input_parser.parse_args()
    tululu_category_link = "https://tululu.org/l55/"
    book_folder = sanitize_filepath(os.path.join(args.dest_folder, "books"))
    cover_folder = sanitize_filepath(os.path.join(args.dest_folder, "images"))
    book_description_filepath = sanitize_filepath(args.json_filepath)
    book_description_json = []
    Path(book_folder).mkdir(parents=True, exist_ok=True)
    Path(cover_folder).mkdir(parents=True, exist_ok=True)
    filepath, filename = os.path.split(book_description_filepath)
    Path(filepath).mkdir(parents=True, exist_ok=True)
    if not args.last_page:
        args.last_page = fetch_category_last_page(tululu_category_link)
    book_links = get_book_links(tululu_category_link, args.start_page, args.last_page)
    for book_link in book_links:
        try:
            response = fetch_response(book_link)
            text_link = fetch_book_text_link(response.content)
            if not text_link:
                continue
            book_description = parse_book_page(response.content)
            if not args.skip_imgs:
                book_description["img_src"] = download_cover(
                    tululu_category_link, book_description, cover_folder
                )
            if not args.skip_txt:
                book_description["book_path"] = download_book_text(
                    tululu_category_link,
                    text_link["href"],
                    book_folder,
                    book_description["title"],
                )
            book_description.pop("img_src_link", None)
            book_description_json.append(book_description)
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ):
            continue
    with open(book_description_filepath, "a") as file:
        json.dump(book_description_json, file, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
