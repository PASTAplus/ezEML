import pickle
import requests
import string


def get_keyword_xml(letter):
    r = requests.get(f'https://vocab.lternet.edu/vocab/vocab/services.php?task=letter&arg={letter}')
    return r.text


def parse_keywords(txt):
    i = 0
    keywords = []
    while i >= 0:
        i = txt.find('<string><![CDATA[', i)
        if i >= 0:
            i = i + len('<string><![CDATA[')
            j = txt.find(']', i)
            keywords.append(txt[i:j])
    return keywords


def get_all_keywords():
    keywords = []
    for letter in list(string.ascii_lowercase):
        keywords.extend(parse_keywords(get_keyword_xml(letter)))
    return keywords


keywords = get_all_keywords()

with open('webapp/static/lter_keywords.pkl', 'wb') as keyfile:
    pickle.dump(keywords, keyfile)
