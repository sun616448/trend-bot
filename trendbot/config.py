"""Source lists. Edit freely: every entry here is US-focused and free to access."""

USER_AGENT = "python:trend-bot:v0.1 (weekly trend digest; +https://github.com/)"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# How many items to keep per source before ranking. Keeps the LLM prompt bounded.
PER_SOURCE_CAP = 40
PER_SUBREDDIT = 12
PER_FEED = 10

# Reddit: where consumers actually talk. Grouped so the digest can weight them.
SUBREDDITS: dict[str, list[str]] = {
    "general": ["all", "popular", "OutOfTheLoop", "InternetIsBeautiful", "popculturechat", "Fauxmoi"],
    "beauty_fashion": [
        "SkincareAddiction", "MakeupAddiction", "BeautyGuruChatter", "Sephora", "Ulta",
        "streetwear", "femalefashionadvice", "malefashionadvice", "Sneakers", "handbags",
    ],
    "food_bev": ["fastfood", "snackexchange", "TraderJoes", "Costco", "starbucks", "energydrinks", "Coffee", "Sodastream"],
    "consumer": ["BuyItForLife", "Frugal", "shutupandtakemymoney", "gadgets", "Target", "amazon", "hydrohomies"],
    "tech_apps": ["technology", "apple", "ChatGPT", "artificial", "androidapps", "iphone", "productivity"],
    "marketing": ["marketing", "advertising", "CommercialsIHate", "socialmedia", "Entrepreneur"],
}

# Bluesky full-text searches. Kept broad; ranking does the rest.
BLUESKY_QUERIES = [
    "sold out everywhere", "went viral", "obsessed with this", "new drop", "brand collab", "pop-up shop",
    "everyone is talking about", "just launched", "new campaign", "brand activation", "ad campaign",
    "NYFW", "skincare routine", "new app", "AI app", "restock", "limited edition", "trader joe's",
    "sephora", "costco", "new flavor", "starbucks", "sneaker drop", "chatgpt", "tiktok trend",
]

# RSS: trade press, culture press, and product press. All verified reachable.
RSS_FEEDS: dict[str, str] = {
    # marketing & advertising
    "Adweek": "https://www.adweek.com/feed/",
    "Marketing Brew": "https://www.marketingbrew.com/feed.xml",
    "Marketing Dive": "https://www.marketingdive.com/feeds/news/",
    "Digiday": "https://digiday.com/feed/",
    "Campaign": "https://www.campaignlive.com/rss/news",
    "Muse by Clio": "https://musebyclio.com/feed",
    "Creative Bloq": "https://www.creativebloq.com/feed",
    # retail & consumer
    "Retail Dive": "https://www.retaildive.com/feeds/news/",
    "Modern Retail": "https://www.modernretail.co/feed/",
    "CNBC Retail": "https://www.cnbc.com/id/10000116/device/rss/rss.html",
    "Fast Company": "https://www.fastcompany.com/latest/rss",
    "Morning Brew": "https://www.morningbrew.com/feed",
    # fashion & beauty
    "Glossy": "https://www.glossy.co/feed/",
    "WWD": "https://wwd.com/feed/",
    "Fashionista": "https://fashionista.com/.rss/full/",
    "Hypebeast": "https://hypebeast.com/feed",
    "Highsnobiety": "https://www.highsnobiety.com/feed/",
    "Allure": "https://www.allure.com/feed/rss",
    "Cosmetics Business": "https://www.cosmeticsbusiness.com/rss",
    "Dazed": "https://www.dazeddigital.com/rss",
    "NYLON": "https://www.nylon.com/rss",
    "NYT Style": "https://rss.nytimes.com/services/xml/rss/nyt/FashionandStyle.xml",
    # food & beverage
    "Food Dive": "https://www.fooddive.com/feeds/news/",
    "Eater": "https://www.eater.com/rss/index.xml",
    "Delish": "https://www.delish.com/rss/all.xml/",
    "Bon Appetit": "https://www.bonappetit.com/feed/rss",
    "Nation's Restaurant News": "https://www.nrn.com/rss.xml",
    "The Food Institute": "https://foodinstitute.com/feed/",
    "Snaxshot": "https://www.snaxshot.com/feed",
    "Sprudge": "https://sprudge.com/feed",
    # tech & apps
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Wired": "https://www.wired.com/feed/rss",
    "9to5Mac": "https://9to5mac.com/feed/",
    "NYT Tech": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "The Information": "https://www.theinformation.com/feed",
    # internet culture
    "Know Your Meme": "https://knowyourmeme.com/newsfeed.rss",
    "BuzzFeed": "https://www.buzzfeed.com/index.xml",
}

# TikTok Creative Center: industry filters to pull a separate top list for (logged-in only).
# Options as of Sept 2026: Education, Vehicle & Transportation, Baby, Kids & Maternity, Beauty & Personal Care,
# Tech & Electronics, Travel, Household Products, Pets, Home Improvement, Apparel & Accessories,
# News & Entertainment, Games, Food & Beverage, Sports & Outdoor, Health.
TIKTOK_INDUSTRIES = ["Beauty & Personal Care", "Apparel & Accessories", "Food & Beverage", "Tech & Electronics", "Household Products", "Health"]
TIKTOK_ROWS_PER_INDUSTRY = 30

# Keyword hints so the ranker can boost signals that smell like the four sections.
SECTION_KEYWORDS = {
    "products": ["launch", "launches", "drop", "sold out", "restock", "new flavor", "limited edition", "collab", "collection", "skincare", "makeup", "snack", "drink", "sneaker"],
    "digital": ["app", "ai", "chatgpt", "feature", "update", "beta", "startup", "platform", "tiktok", "instagram", "threads", "openai", "apple", "google"],
    "campaigns": ["campaign", "ad", "ads", "commercial", "activation", "pop-up", "popup", "billboard", "sponsor", "partnership", "nyfw", "fashion week", "super bowl", "stunt", "brand"],
    "culture": ["meme", "trend", "viral", "aesthetic", "core", "sound", "challenge", "discourse", "everyone is", "obsessed", "slang"],
}
