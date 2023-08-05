#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Stefan Jansen'

import re
from pathlib import Path
from random import random
from time import sleep
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from furl import furl
from selenium import webdriver
from urllib.parse import urlparse

transcript_path = Path('transcripts')
transcript_html_path = Path('transcripts/html')


def get_filename_by_url(url):
    # Parse the URL
    parsed_url = urlparse(url)

    # Split the path by '/' and get the last part
    last_part = parsed_url.path.split('/')[-1]
    return last_part

def store_result(meta, participants, content):
    """Save parse content to csv"""
    path = transcript_path / 'parsed' / meta['symbol']
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(content, columns=['speaker', 'q&a', 'content']).to_csv(path / 'content.csv', index=False)
    pd.DataFrame(participants, columns=['type', 'name']).to_csv(path / 'participants.csv', index=False)
    pd.Series(meta).to_csv(path / 'earnings.csv')

def save_html(content, filename):
    with open(filename, 'w') as f:
        f.write(content)

def parse_html(html):
    """Main html parser function"""
    date_pattern = re.compile(r'(\d{2})-(\d{2})-(\d{2})')
    quarter_pattern = re.compile(r'(\bQ\d\b)')
    soup = BeautifulSoup(html, 'lxml')

    meta, participants, content = {}, [], []
#    h1 = soup.find('h1', itemprop='headline')
    h1 = soup.find('h1', {'data-test-id': 'post-title'})
    # Print the text inside the h1 tag
    if h1 is None:
        print('Headline not found, abandon parsing')
        return
    h1 = h1.text
    meta['company'] = h1[:h1.find('(')].strip()
    meta['symbol'] = h1[h1.find('(') + 1:h1.find(')')]

    subtitle = soup.find('span', {'data-test-id': 'post-date'})
#    print(subtitle)
    match = date_pattern.search(subtitle.text)
    if match:
        m, d, y = match.groups()
        meta['month'] = int(m)
        meta['day'] = int(d)
        meta['year'] = int(y)

    match = quarter_pattern.search(h1)
    if match:
        meta['quarter'] = match.group(0)

    qa = 0
    speaker_types = ['Executives', 'Analysts']
    for header in [p.parent for p in soup.find_all('strong')]:
        text = header.text.strip()
        if text.lower().startswith('copyright'):
            continue
        elif text.lower().startswith('question-and'):
            qa = 1
            continue
        elif any([type in text for type in speaker_types]):
            for participant in header.find_next_siblings('p'):
                if participant.find('strong'):
                    break
                else:
                    participants.append([text, participant.text])
        else:
            p = []
            for participant in header.find_next_siblings('p'):
                if participant.find('strong'):
                    break
                else:
                    p.append(participant.text)
            content.append([header.text, qa, '\n'.join(p)])
    return meta, participants, content


SA_URL = 'https://seekingalpha.com/'
TRANSCRIPT = re.compile('Earnings Call Transcript')

next_page = True
page = 1
driver = webdriver.Firefox()
while next_page:
    print(f'Page: {page}')
    url = f'{SA_URL}/earnings/earnings-call-transcripts?page={page}'
    driver.get(urljoin(SA_URL, url))
    sleep(8 + (random() - .5) * 2)
    response = driver.page_source
    page += 1
    soup = BeautifulSoup(response, 'lxml')
    links = soup.find_all(name='a', string=TRANSCRIPT)
    if len(links) == 0:
        next_page = False
    else:
        for link in links:
            transcript_url = link.attrs.get('href')
            transcript_url = urljoin(SA_URL, transcript_url)
            filename = get_filename_by_url(transcript_url) + '.html'
            file_path = transcript_html_path/filename
            file_exists = file_path.is_file()
            
            if not file_exists:
                article_url = furl(transcript_url).add({'part': 'single'})
                driver.get(article_url.url)
                html = driver.page_source
                save_html(html, file_path)
                sleep(8 + (random() - .5) * 2)
            else:
                with open(file_path, 'r') as f:
                    html = f.read()
            result = parse_html(html)
            if result is not None:
                meta, participants, content = result
                meta['link'] = link
                store_result(meta, participants, content)
            else:
                print('Failed to scrape ',transcript_url)

driver.close()
#pd.Series(articles).to_csv('articles.csv')
