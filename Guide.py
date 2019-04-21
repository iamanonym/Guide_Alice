import requests
from flask import Flask, request
import logging
import json


RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/schedule/'
TOWN_RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/nearest_settlement/'
GEOCODE_SERVER = 'https://geocode-maps.yandex.ru/1.x/'
RASP_API_KEY = 'a8069307-d318-473d-b178-2d1efd99580f'

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


class ResponseError(ConnectionError):
    pass


class ErrorTillDoingRequest(ResponseError):
    pass


class DoingResponseNotAble(ResponseError):
    pass


def search_town(lat, long):
    if type(lat) != float or type(lat) != float:
        raise ValueError()
    town_params = {'apikey': RASP_API_KEY,
                   'lat': str(lat),
                   'lng': str(long),
                   'distance': 50,
                   'lang': 'ru_RU'}
    try:
        response = requests.get(TOWN_RASP_SERVER, params=town_params)
    except Exception:
        raise DoingResponseNotAble()
    if response:
        return response.json()['code']
    else:
        raise ErrorTillDoingRequest()


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)

    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }

    handle_dialog(request.json, response)
    logging.info('Response: %r', request.json)
    return json.dumps(response)


def handle_dialog(req, res):
    if req['session']['new']:
        res['response']['text'] = 'Привет! Я Навык-Путеводитель!' \
                                  'Для начала работы, скажите, где Вы живете?'
        return


def get_city(req):
    cities = []
    for token in req['request']['nlu']['tokens']:
        temp = check_exist(token)
        if temp is not None:
            cities.append(temp)
    return cities


def check_exist(name_without_reg):
    name = name_without_reg.lower()
    params = {'geocode': name,
              'kind': 'locality',
              'format': 'json'}
    try:
        resp = requests.get(GEOCODE_SERVER, params=params)
    except Exception:
        raise DoingResponseNotAble()
    if resp:
        json_file = resp.json()
    else:
        raise ErrorTillDoingRequest()
    vars = json_file['response']['GeoObjectCollection']['featureMember']
    for var in vars:
        obj = var['GeoObject']['metaDataProperty']['GeocoderMetaData']
        adr = obj['Address']['Components']
        for comp in adr:
            if (comp['kind'] == 'locality' or comp['kind'] == 'province')\
                    and (comp['name'].lower() == name or
                         comp['name'].lower() == 'село {}'.format(name) or
                         comp['name'].lower() == 'город {}'.format(name) or
                         comp['name'].lower() == 'сно {}'.format(name)):
                return obj['text']
    return None


if __name__ == '__main__':
    print(check_exist('Шакша'))
