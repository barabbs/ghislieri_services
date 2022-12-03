from . import var
import arrow
import feedparser as fp


class RSSFeed(object):
    def __init__(self):
        pass

    def get_events(self):
        for page in range(1, var.RSSFEED_MAX_PAGES + 1):
            feed = fp.parse(var.RSSFEED_LINK.format(page=page))
            for e in feed.entries:
                raw_id = e['link'].split("/")[-2:]
                id = raw_id[1] or raw_id[0]
                ev_kwargs = var.RSSFEED_DEFAULTS_EVENT_KWARGS.copy()
                ev_kwargs.update({'name': e['title'],
                                  'description': e['summary'],
                                  'url': e['link'],
                                  'begin': e['startdate'],
                                  'end': e['enddate'],
                                  # 'uid': e['id'],
                                  'id': id,
                                  'created': arrow.get(e['published'], var.RSSFEED_PUBLISHEDTIME_FORMAT),
                                  'organizer': {'common_name': e['author']},
                                  'categories': var.RSSFEED_CATEGORIES_BY_AUTHOR.get(e['author'], var.RSSFEED_DEFAULTS_EVENT_KWARGS['categories'])
                                  })
                yield ev_kwargs
