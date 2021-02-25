import json
import os
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from requests.packages.urllib3.exceptions import InsecureRequestWarning


def get_response_from_link(link: str) -> requests.models.Response:
    tululu_response = requests.get(link, verify=False, allow_redirects=False)
    tululu_response.raise_for_status()
    if tululu_response.status_code == 302:
        raise requests.exceptions.HTTPError
    return tululu_response


def parse_category_page(html: str) -> list:
    html_soup = BeautifulSoup(html, "lxml")
    book_partial_link_selector = "body div#content .d_book tr:nth-of-type(2) a"
    book_roster_partial_link = [
        book_partial_link["href"]
        for book_partial_link in html_soup.select(book_partial_link_selector)
    ]
    return book_roster_partial_link


def join_website_with_book_html_link(website_link: str, book_html_link: str) -> str:
    split_link = urlsplit(website_link)
    book_link = urljoin(
        f"{ split_link.scheme }://{ split_link.netloc }", book_html_link
    )
    return book_link


def write_file_text(data: str, filepath: str):
    with open(filepath, "w") as file:
        file.write(data)


def write_file_cover(data: bytes, filepath: str):
    with open(filepath, "wb") as file:
        file.write(data)


def write_file_json(data: list, filepath: str):
    with open(filepath, "a") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def extract_from_link_extension(link: str) -> str:
    split_link = urlsplit(link)
    split_link_unquote = unquote(split_link.path)
    file_extension = os.path.splitext(split_link_unquote)[1]
    return file_extension


def parse_book_page(html: str) -> dict:
    book_description = dict()
    html_soup = BeautifulSoup(html, "lxml")
    book_text_partial_link_selector = (
        "body div#content .d_book a[title$='скачать книгу txt']"
    )
    book_text_partial_link = html_soup.select_one(book_text_partial_link_selector)
    if book_text_partial_link:
        book_title_and_author_selector = "body div#content h1"
        book_title_and_author = html_soup.select_one(book_title_and_author_selector)
        book_title, book_author = book_title_and_author.text.split("::")

        book_cover_partial_link_selector = "body .bookimage img"
        book_cover_partial_link = html_soup.select_one(book_cover_partial_link_selector)

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
            "img_src": book_cover_partial_link["src"],
            "book_path": book_text_partial_link["href"],
            "genres": book_genres,
            "comments": book_comments,
        }
    return book_description


def download_book_text(url: str, filename: str, folder: str) -> str:
    sanitized_filename = sanitize_filename(filename)
    book_data = get_response_from_link(url)
    full_filepath = f"{ os.path.join(folder, sanitized_filename) }.txt"
    write_file_text(book_data.text, full_filepath)
    return full_filepath


def download_cover(url: str, filename: str, folder: str) -> str:
    sanitized_filename = sanitize_filename(filename)
    cover_data = get_response_from_link(url)
    full_filepath = os.path.join(folder, sanitized_filename)
    write_file_cover(cover_data.content, full_filepath)
    return full_filepath


def get_book_roster_partial_link(
    category_link: str, start_category_page: int, end_category_page: int
) -> list:
    book_roster_partial_link = list()
    for page in range(start_category_page, end_category_page):
        category_page_link = urljoin(category_link, str(page))
        category_page_link_response = get_response_from_link(category_page_link)
        book_roster_partial_link = book_roster_partial_link + parse_category_page(
            category_page_link_response.content
        )
    return book_roster_partial_link


def main():
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    tululu_category_link = "https://tululu.org/l55/"
    tululu_start_category_page = 1
    tululu_end_category_page = 10
    book_number_limit = 100
    book_folder = "books"
    cover_folder = "images"
    json_folder = "json"
    json_filename = "book_desc.json"
    book_description_json_draft = list()
    Path(book_folder).mkdir(parents=True, exist_ok=True)
    Path(cover_folder).mkdir(parents=True, exist_ok=True)
    Path(json_folder).mkdir(parents=True, exist_ok=True)
    file_book_description_json_filepath = os.path.join(json_folder, json_filename)
    try:
        book_roster_partial_link = get_book_roster_partial_link(
            tululu_category_link, tululu_start_category_page, tululu_end_category_page
        )
        for book_partial_link in book_roster_partial_link:
            if len(book_description_json_draft) > book_number_limit:
                print(len(book_description_json_draft))
                break
            book_link = join_website_with_book_html_link(
                tululu_category_link, book_partial_link
            )
            book_link_response = get_response_from_link(book_link)
            book_description = parse_book_page(book_link_response.content)
            if "book_path" in book_description:
                book_cover_link = join_website_with_book_html_link(
                    tululu_category_link, book_description["img_src"]
                )
                book_cover_extension = extract_from_link_extension(book_cover_link)
                book_cover_filename = (
                    f"{ book_description['title'] }{ book_cover_extension }"
                )
                book_description["img_src"] = download_cover(
                    book_cover_link, book_cover_filename, cover_folder
                )
                book_text_link = join_website_with_book_html_link(
                    tululu_category_link, book_description["book_path"]
                )
                book_text_filename = book_description["title"]
                book_description["book_path"] = download_book_text(
                    book_text_link, book_text_filename, book_folder
                )
                book_description_json_draft.append(book_description)
        write_file_json(
            book_description_json_draft, file_book_description_json_filepath
        )
    except requests.exceptions.ConnectionError:
        print("Что-то пошло не так:( Проверьте подключение к интернету!")
    except requests.exceptions.HTTPError:
        print("Проблемы с доступом к сайту tululu.org")


if __name__ == "__main__":
    main()
