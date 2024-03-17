import json
import requests
from bs4 import BeautifulSoup
import bs4.element
import tinycss2
from . import var


# Fetching
def _get_facebook_coords():
    with open(var.FACEBOOK_COORDS_FILE, 'r') as coord_file:
        return json.load(coord_file)


COORDS = _get_facebook_coords()
COOKIES = COORDS['cookies']
BASIC_URL = "https://mbasic.facebook.com"
BASE_URL = "https://www.facebook.com"
GROUP_URL = f"/groups/{COORDS['group_id']}"
POST_URL = "/permalink/{post_id}"


def _fetch_soup(options="", post_id=None):
    url = BASIC_URL + GROUP_URL
    url += ("?" + options) if post_id is None else POST_URL.format(post_id=post_id)
    page = requests.get(url, headers={"cookie": COOKIES})
    with open(f"temp/{post_id}.html", 'wb') as file:
        file.write(page.content)
    return BeautifulSoup(page.content, "html.parser")


# Scraping

STYLE_RECON = {('font-weight', 600): "bold",
               ('font-style', "italic"): "italic",
               ('text-decoration', "underline"): "underline"}

STYLE_MARKUP = {"bold": ('<b>', '</b>'),
                "italic": ('<i>', '</i>'),
                "underline": ('<u>', '</u>'),
                "code": ('<code>', '</code>'),
                "blockquote": ('<blockquote>', '</blockquote>'),
                "link": ('<a href="{href}">', '</a>'),
                None: ('', '')}


def _get_style(soup):
    style_tag = soup.head.find('style', type='text/css')
    css = tinycss2.parse_stylesheet(style_tag.text, skip_comments=True, skip_whitespace=True)
    style_dict = dict()
    for rule in filter(lambda r: r.type == 'qualified-rule' and len(r.prelude) == 2, css):
        cont = rule.content
        for i, token in enumerate(cont[:-2]):
            if token.type != 'ident':
                continue
            style = STYLE_RECON.get((token.value, cont[i + 2].value))
            if style is not None:
                style_dict[rule.prelude[1].value] = style
    return style_dict


def _sanify(tag, style, ):
    if type(tag) == bs4.element.NavigableString:
        return str(tag)
    elif tag.name == "br":
        return "\n"
    elif tag.name == "span" and "class" in tag.attrs.keys():
        marks = STYLE_MARKUP[style.get(tag.attrs['class'][0])]
    elif tag.name == "blockquote":
        marks = STYLE_MARKUP["blockquote"]
    elif tag.name == "a" and not "https://lm.facebook.com/l.php" in tag["href"]:
        marks = STYLE_MARKUP["link"]
        href = BASE_URL + (tag["href"].split("&")[0] if "/profile.php?" in tag["href"] else tag["href"].split("?")[0])
        marks = (marks[0].format(href=href), marks[1])
    else:
        marks = STYLE_MARKUP[None]
    return marks[0] + "".join(_sanify(c, style) for c in tag.contents) + marks[1]


def _get_image(url):
    page = requests.get(f"{BASIC_URL}/{url}", headers={"cookie": COOKIES})
    soup = BeautifulSoup(page.content, "html.parser")
    root = soup.find(attrs={"id": "root"})
    src = root.div.div.div.div.div.div.img["src"]
    img_data = requests.get(src).content
    return img_data


def _get_post(post_id):
    soup = _fetch_soup(post_id=post_id)
    root = soup.find(attrs={"id": "m_story_permalink_view"})
    post = {"post_id": post_id,
            "author": soup.find("h3").find("a").text.upper(),
            "time": root.div.div.contents[1].div.abbr.text}
    style = _get_style(soup)
    parts, newline = root.find_all("p"), "\n\n"
    if len(parts) == 0:
        parts, newline = root.div.div.div.contents[1].div.div.contents, "\n"
    post["text"] = newline.join(_sanify(p, style) for p in parts)
    post["text"] = "\n".join(s.lstrip() for s in post["text"].split("\n"))
    try:
        img_url = root.div.div.div.contents[2].div.a["href"]
    except (IndexError, AttributeError, TypeError):
        pass
    else:
        if "/photo.php?" in img_url:
            post["img"] = _get_image(img_url)
    return post


def get_facebook_group_posts(pages=var.MAX_PAGES_SCRAPED):
    next_page = ""
    for i in range(pages):
        soup = _fetch_soup(options=next_page)
        posts = (int(p["href"].split("/")[6]) for p in soup.find_all("a", string="Full Story"))
        for p in posts:
            yield _get_post(p)
        next_page = soup.find("a", string="See more posts")["href"].split("&")[0].split("?")[1]
