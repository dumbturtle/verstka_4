import os
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning


def get_response_from_link(link: str) -> requests.models.Response:
    tululu_response = requests.get(link, verify=False, allow_redirects=False)
    tululu_response.raise_for_status()
    if tululu_response.status_code == 302:
        raise requests.exceptions.HTTPError
    return tululu_response


def parse_category_page(html: str) -> str:
    tululu_html_soup = BeautifulSoup(html, "lxml")
    book_html_link = (
        tululu_html_soup.find("body")
        .find("div", id="content")
        .find("table")
        .find("a")["href"]
    )
    return book_html_link


def join_website_with_book_html_link(website_link: str, book_html_link: str) -> str:
    split_link = urlsplit(website_link)
    book_link = urljoin(
        f"{ split_link.scheme }://{ split_link.netloc }", book_html_link
    )
    return book_link


def main():
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    tululu_category_link = "https://tululu.org/l55/"
    link_response = get_response_from_link(tululu_category_link)
    book_html_link = parse_category_page(link_response.text)
    book_link = join_website_with_book_html_link(tululu_category_link, book_html_link)
    print(book_link)


if __name__ == "__main__":
    main()
