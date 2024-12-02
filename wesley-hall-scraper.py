
import os
import json
import asyncio
from scrapy import Spider
from scrapy.http import Request
import time
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy import signals
from pydispatch import dispatcher
from bs4 import BeautifulSoup
import re
            
            

class MenuScraper:


    def scrape_menu():


        output_dir = 'utilities'
        os.makedirs(output_dir, exist_ok=True)

        req = requests.get("https://www.wesleyhall.com/styles/func/cat/PTP")

        soup = BeautifulSoup(req.content, "html.parser")


        categories = soup.find('ul', class_="pure-menu-children")

        data = []

        if categories:
            li_children = categories.find_all('li', recursive=False)
            for li in li_children:
                # print(li)
                categor = li.find('a', recursive=False)
                category_name = categor.text.strip()
                collections = li.find("ul", recursive=False)
                if collections:
                    current_colllect = collections.find_all("li")
                    for item in current_colllect:

                        data.append(
                                {
                                    "category_name": category_name,
                                    "collection_name": item.find("a").text.strip(),
                                    "collection_link": "https://www.wesleyhall.com" + item.find("a").get("href")
                                },
                        )
                else:

                    data.append(
                                {
                                    "category_name": category_name,
                                    "collection_name": category_name,
                                    "collection_link": "https://www.wesleyhall.com" + categor.get("href")
                                },
                        )
                    

        else:
            print("No 'ul' with the class 'pure-menu-children' found.")


        output_file = 'utilities/category-collection.json'
        with open(output_file, "w") as file:
            json.dump(data, file, indent=4)

        print(f"Data successfully saved to {output_file}")








            

class CollectionSpider(scrapy.Spider):
    name = 'collection_spider'
    
    custom_settings = {
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.BaseDupeFilter',
        'CONCURRENT_REQUESTS': 1,
        'FEEDS': {
            'utilities/products-links.json': {
                'format': 'json',
                'overwrite': True,
                'encoding': 'utf8',
            },
        },
    }

    def start_requests(self):
        output_dir = 'utilities'
        os.makedirs(output_dir, exist_ok=True)

        file_path = 'utilities/products-links.json'
        with open(file_path, 'w') as file:
            pass
        
        with open('utilities/category-collection.json') as file:
            self.collections = json.load(file)
        
        if self.collections:
            yield from self.process_collection(self.collections[0], 0)

    def process_collection(self, collection, collection_index):
        category_name = collection['category_name']
        collection_name = collection['collection_name']
        collection_link = collection['collection_link']
        
        yield scrapy.Request(
            url=collection_link,
            callback=self.parse_collection,
            meta={
                'category_name': category_name,
                'collection_name': collection_name,
                'collection_link': collection_link,
                'collection_index': collection_index 
            },
            dont_filter=True
        )

    def parse_collection(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        products = soup.find_all("div", class_ = "pure-u-1 pure-u-sm-8-24 pure-u-lg-1-5 style_thumbs")
        product_links = ["https://www.wesleyhall.com" + item.find('a').get('href') for item in products if item.find('a')]

        for link in product_links:
            yield {
                'category_name': response.meta['category_name'],
                'collection_name': response.meta['collection_name'],
                'product_link': link
            }
            
        next_page_link = soup.find('a', class_='pagination__link', rel='next')
        if next_page_link:
            next_page_url = "https://margecarson.com" + next_page_link.get('href')
            self.log(f"Following next page: {next_page_url}")
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse_collection,
                meta=response.meta,
                dont_filter=True
            )
        else:
            current_index = response.meta['collection_index']
            next_index = current_index + 1
            if next_index < len(self.collections):
                next_collection = self.collections[next_index]
                yield from self.process_collection(next_collection, next_index)
            else:
                self.log("All collections have been processed.")





class ProductSpider(scrapy.Spider):
    name = "product_spider"
    
    custom_settings = {
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.BaseDupeFilter',
        'CONCURRENT_REQUESTS': 1
    }
    
    
    
    def start_requests(self):
        """Initial request handler."""
        os.makedirs('output', exist_ok=True)
        self.scraped_data = []
        scraped_links = set()
        if os.path.exists('output/products-data.json'):
            with open('output/products-data.json', 'r', encoding='utf-8') as f:
                try:
                    self.scraped_data = json.load(f)
                    scraped_links = {item['Product Link'] for item in self.scraped_data}
                except json.JSONDecodeError:
                    pass  
        with open('utilities/products-links.json', 'r', encoding='utf-8') as file:
            products = json.load(file)
        for product in products:
            product_link = product['product_link']
            if product_link not in scraped_links: 
                yield scrapy.Request(
                    url=product_link,
                    callback=self.parse,
                    meta={
                        'category_name': product['category_name'],
                        'collection_name': product['collection_name'],
                        'product_link': product['product_link']
                    }
                )
    
    def parse(self, response):
        """Parse the product page and extract details."""
        category_name = response.meta['category_name']
        collection_name = response.meta['collection_name']
        product_link = response.meta['product_link']
        
        soup = BeautifulSoup(response.text, 'html.parser')
        product_name = soup.find('div', class_ = "prod-details")
        if product_name:
            product_name = product_name.text.strip()


        table = soup.find('table', class_="style_details")
        dimensions = []

        # if table:
        #     rows = table.find_all('tr')
        #     for row in rows:
        #         key = row.find('td').text.strip()  
        #         value = row.find_all('td')[1].text.strip() 
        #         dimensions.append({key.strip(':'): value})


        if table:
            rows = table.find_all('tr')
            for row in rows:
                tds = row.find_all('td') 
                if len(tds) >= 2:  
                    key = tds[0].text.strip()
                    value = tds[1].text.strip()
                    dimensions.append({key.strip(':'): value})
        
        product_images = []
        imgs = soup.find("div", class_ = 'sub-prod-detail')
        if imgs:
            imgs = imgs.find_all("img")
            for item in imgs:
                product_images.append("https://www.wesleyhall.com" + item.get("src"))
        
        
        sku = ""
        if product_name:
            sku = product_name.split()[0].strip()
            product_name = product_name.replace(sku, "").strip()
   

        new_product_data =  {
            'Category': category_name,
            'Collection': collection_name,
            'Product Link': product_link,
            'Product Title': product_name,
            'SKU': sku,
            "View our Brand Portfolio": "https://www.wesleyhall.com/assets/docs/WH-Brandportfolio-SP.pdf",
            'Dimensions': dimensions,
            'Product Images': product_images
        }
        
        self.scraped_data.append(new_product_data)
        
        with open('output/products-data.json', 'w', encoding='utf-8') as f:
            json.dump(self.scraped_data, f, ensure_ascii=False, indent=4)



    
    
    
#   -----------------------------------------------------------Run------------------------------------------------------------------------

def run_spiders():

    

    output_dir = 'utilities'
    os.makedirs(output_dir, exist_ok=True)
    products_links_scraper = MenuScraper()
    products_links_scraper.scrape_menu()
    process = CrawlerProcess()
    process.crawl(CollectionSpider)
    process.crawl(ProductSpider)
    process.start()


run_spiders()