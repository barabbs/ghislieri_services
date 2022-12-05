import sys, os
from ics.component import Container
from ics.grammar.parse import ContentLine
import datetime as dt

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "calendar_manager"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)
CALENDARS_DIR = os.path.join(DATA_DIR, "calendars")

# Files
CALENDAR_NAME = "calendar_"
CALENDAR_EXT = ".ical"
TEMP_EXT = ".temp"

# Calendar
CALENDAR_DEFAULTS = {'creator': "Ghislieri Services Calendar"}
CALENDAR_SHIFT = dt.timedelta(weeks=32)
AUTOCORRECT_DEFAULT_DURATION = dt.timedelta(hours=2)
UID_SEPARATOR = "/"

# Timezone for calcurse integration (NOT WORKING)
CALENDAR_TIMEZONE = Container("VTIMEZONE",
                              ContentLine(name="TZID", value="Europe/Rome"),
                              Container("DAYLIGHT",
                                        ContentLine(name="TZOFFSETFROM", value="+0100"),
                                        ContentLine(name="TZOFFSETTO", value="+0200"),
                                        ContentLine(name="TZNAME", value="CEST"),
                                        ContentLine(name="DTSTART", value="19700329T020000"),
                                        ContentLine(name="RRULE", value="FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU")),
                              Container("STANDARD",
                                        ContentLine(name="TZOFFSETFROM", value="+0200"),
                                        ContentLine(name="TZOFFSETTO", value="+0100"),
                                        ContentLine(name="TZNAME", value="CET"),
                                        ContentLine(name="DTSTART", value="19701025T030000"),
                                        ContentLine(name="RRULE", value="FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU"))
                              )

# Graphics
SYMBOL_BY_CATEGORY = {"conference": "🗣",
                      "concert": "🎼"}
DEFAULT_SYMBOL = "❓"
NO_EVENT_FOR_DAY = "Nessun evento programmato"
EVENT_LINK_TEXT = "Maggiori Informazioni"




# RSSFeed
RSSFEED_UPDATE_TIME = "03:00"
RSSFEED_LINK = "https://www.ghislieri.it/feed/?post_type=ajde_events&paged={page}"
RSSFEED_MAX_PAGES = 100
RSSFEED_MAX_ERRORS = 5
RSSFEED_DEFAULTS_EVENT_KWARGS = {'status': "TENTATIVE",
                                 'classification': "event",
                                 'categories': ("conference",)}
RSSFEED_CATEGORIES_BY_AUTHOR = {'antonio.gurrado': ("conference",),
                                'jacopo': ("concert",)}
RSSFEED_PUBLISHEDTIME_FORMAT = "ddd, DD MMM YYYY HH:mm:ss"
