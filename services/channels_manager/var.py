import sys, os

DEBUG = "-d" in sys.argv

# Directories
SERVICE_NAME = "channels_manager"
DATA_DIR = os.path.join('/var', 'opt', "ghislieri_services", SERVICE_NAME)
if DEBUG:
    DATA_DIR = os.path.join(os.getcwd(), 'data', SERVICE_NAME)

# Files
FACEBOOK_COORDS_FILE = os.path.join(DATA_DIR, 'facebook_coords.fbck')
FACEBOOK_POSTS_FILE = os.path.join(DATA_DIR, 'facebook_posts.fbpst')
CHANNEL_ID_FILE = os.path.join(DATA_DIR, 'channel_id.cmid')

# Facebook Scraping
FACEBOOK_UPDATE_INTERVAL = 15  # minutes
MAX_PAGES_SCRAPED = 3
FACEBOOK_POST_MSG = """<b>❯    {author:<100}</b>

{text}

<a href=\"https://www.facebook.com/groups/577461299856064/permalink/{post_id}\">⮕  vedi su Facebook</a>"""
