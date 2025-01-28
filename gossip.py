import feedparser
import chromadb
from uuid import uuid4
import html2text
import asyncio
from flask import Flask, request, jsonify, render_template
import itertools

def format_item(item:any, source:str):
    h = html2text.HTML2Text()
    h.ignore_links = True
    metadata = {
        "source":           source,
        "title":            item.get("title", ""),
        "author":           item.get("author", ""),
        "published":        item.get("published", ""),
        "summary":          item.get("summary", ""),
        "content":          item.get("content", [{"value": ""}])[0]["value"],
        "link":             item.get("link", ""),
        "media_thumbnail":  item.get("media_thumbnail", [{"url": ""}])[0]["url"],
        "credit":           item.get("credit", ""),
        "tags":             ",".join([tag['term'] for tag in item.get("tags", [])]),
    }
    document = "\n".join([
        metadata["title"],
        metadata["summary"],
        h.handle(metadata["content"])
    ])
    return (metadata, document, str(uuid4()))

def format_items(items:list, source:str):
    keys = ["metadatas", "documents", "ids"]
    values = zip(*[format_item(item, source) for item in items])
    values = map(list, values)
    return dict(zip(keys, values))

def feed_url_generator(domain_name:str):
    page_number = 0
    while True:
        page_number += 1
        yield f"https://{domain_name}/feed/?paged={page_number}"

def generate_fetch_task(sources: list[str]):
    gen_url = {s:feed_url_generator(s) for s in sources}

    async def fetch_url(domain, url):
        feed = await asyncio.to_thread(feedparser.parse, url)
        if feed.status < 400:
            print(f"{feed.status} {url}")
            return format_items(feed.entries, domain)
        elif domain in gen_url:
            del gen_url[domain]

    while gen_url:
        for domain, url in dict(gen_url).items():
            yield fetch_url(domain, next(url))

async def get_data(sources: list[str], collection):
    async def feed(queue:asyncio.Queue):
        for fetch_task in generate_fetch_task(sources):
            result = await fetch_task
            await queue.put(result)
        await queue.put(None)

    async def store(queue:asyncio.Queue):
        while True:
            feed = await queue.get()
            if feed:
                print("stored")
                await asyncio.to_thread(collection.add, **feed)
            else:
                queue.task_done()
                return
    queue = asyncio.Queue()
    await asyncio.gather(store(queue), feed(queue))
       
def create_app():
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html')  # Serves the HTML file

    @app.route('/search', methods=['GET'])
    def search():
        query = request.args.get('q', '').lower()  # Get the query parameter
        if query:
            results = collection.query(
                query_texts=[query],
                n_results=2)
            return jsonify(results["metadatas"][0])
        return jsonify([])
    
    return app

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./database")
    collection = client.get_or_create_collection(name="gossip")
    sources = ["vsd.fr", "www.public.fr"]
    # need to take into account the etag before starting the scrapping
    # asyncio.run(get_data(sources, collection))
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)
