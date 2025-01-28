import feedparser
import chromadb
from uuid import uuid4
import html2text
from pprint import pprint
import asyncio
from flask import Flask, request, jsonify, render_template
from typing import List

async def fetch_feed(url):
    Feed = feedparser.parse(url)
    print(f"url {url} status {Feed.status}")
    if Feed.status < 400:
        return Feed.entries
    return None
 
def format_items(items, source):
    h = html2text.HTML2Text()
    h.ignore_links = True
    metadatas = []
    documents = []
    for item in items:
        metadatas.append({
            "source": source,
            "author": item.author,
            "link": item.link,
            "credit": item.get("credit", ""),
            "media_thumbnail": item.get("media_thumbnail", [{"url": ""}])[0]["url"],
            "published": item.published,
            "summary": item.summary,
            "tags": ",".join([tag['term'] for tag in item.get("tags", [])]),
            "title": item.title,
            "content": item.content[0].value,
        })
        documents.append("\n".join([
                item.title,
                item.summary,
                h.handle(item.content[0].value),
        ]))
    uuids = [str(uuid4()) for _ in range(len(documents))]
    return (metadatas, documents, uuids)

def generate_url(domain_name:str):
    page_number = 0
    while True:
        page_number += 1
        yield f"https://{domain_name}/feed/?paged={page_number}"

async def get_data(sources:List[str], collection):
    url_generators = {domain:generate_url(domain) for domain in sources}
    while url_generators:
        tasks = []
        for domain, generator in url_generators.items():
            async def task(url):
                entries = await fetch_feed(url)
                if entries:
                    meta, docs, ids = format_items(entries, domain)
                    collection.add(ids=ids, documents=docs, metadatas=meta)
                else:
                    url_generators.remove(generator)
            url = next(generator)
            tasks.append(task(url))
        await asyncio.gather(*tasks)

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
            pprint(results)
            return jsonify(results["metadatas"][0])
        return jsonify([])
    
    return app


if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./database")
    collection = client.get_or_create_collection(name="gossip")
    sources = ["vsd.fr", "www.public.fr"]
    asyncio.run(get_data(sources, collection))

    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)
