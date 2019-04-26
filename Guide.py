import requests
from flask import Flask, request
import logging
import json
import datetime


def get_days_in_feb():
    year = datetime.datetime.today().year
    if year % 4 == 0 and year % 100 != 0 or year % 400 == 0:
        return 29
    else:
        return 28


RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/search/'
TOWN_RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/nearest_settlement/'
GEOCODE_SERVER = 'https://geocode-maps.yandex.ru/1.x/'
SEARCH_SERVER = 'https://search-maps.yandex.ru/v1/'
RASP_API_KEY = 'a8069307-d318-473d-b178-2d1efd99580f'
SEARCH_API_KEY = 'dda3ddba-c9ea-4ead-9010-f43fbc15c6e3'

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

sessionStorage = {}
MONTHS = {1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая',
          6: 'июня', 7: 'июля', 8: 'августа', 9: 'сентября',
          10: 'октября', 11: 'ноября', 12: 'декабря'}
DAYS = {'января': 31, 'февраля': get_days_in_feb(), 'марта': 31,
        'апреля': 30, 'мая': 31, 'июня': 30, 'июля': 31, 'августа': 31,
        'сентября': 30, 'октября': 31, 'ноября': 30, 'декабря': 31}


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
        return response.json()['title'], response.json()['code']
    else:
        raise ErrorTillDoingRequest()


@app.route('/guide', methods=['POST'])
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
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет! Я Навык-Путеводитель!' \
                                  ' Для начала работы, скажите, ' \
                                  'где Вы находитесь?'
        sessionStorage[user_id] = {
            'town1': None,
            'town2': None,
            'c1': None,
            'c2': None,
            'status': None,
            'cities': [],
            'start': 5
        }
        return
    if sessionStorage[user_id]['town1'] is None:
        try:
            town, pos = get_city(req)
        except TypeError:
            res['response']['text'] = 'Мне кажется, это не город'
            return
        except ValueError:
            res['response']['text'] = 'Мне кажется, это не город'
            return
        if not town or not pos:
            res['response']['text'] = 'Мне кажется, это не город'
        elif pos and town:
            check = search_town(pos[1], pos[0])
            if check:
                sessionStorage[user_id]['c1'] = check
            res['response']['text'] = \
                'Назовите какое-либо место, а я подскажу, ' \
                'как до него добраться!'
            sessionStorage[user_id]['town1'] = \
                req['request']['original_utterance']
        return
    if sessionStorage[user_id]['status'] == 1:
        if req['request']['original_utterance'].lower() == 'да':
            city = sessionStorage[user_id]['cities']
            lat, long = city['geometry']['coordinates']
            create_answer(user_id, res, lat, long)
        elif req['request']['original_utterance'].lower() == 'нет':
            res['response']['text'] = 'К сожалению, больше' \
                                      ' ничего найти не удалось(\n' \
                                      'Попробуйте найти что-то другое'
            sessionStorage[user_id]['status'] = None
        else:
            res['response']['text'] = 'Некорректный запрос'
        return
    if sessionStorage[user_id]['status'] == 2:
        temp = req['request']['original_utterance']
        if temp.isdigit():
            if 1 <= int(temp) <= 5:
                move = sessionStorage[user_id]['start']
                city = sessionStorage[user_id]['cities'][int(temp) + move - 6]
                if city:
                    lat, long = city['geometry']['coordinates']
                    create_answer(user_id, res, lat, long)
                else:
                    res['response']['text'] = 'К сожалению, больше' \
                                              ' ничего найти не удалось(\n' \
                                              'Попробуйте найти что-то другое'
                    sessionStorage[user_id]['status'] = None
        elif temp.lower() == 'далее':
            start = sessionStorage[user_id]['start'] + 5
            features = sessionStorage[user_id]['cities'][start - 5: start]
            if len(features) > 0:
                var_text = 'Нашел следующие варианты:\n\n'
                for feature in features:
                    var_text += \
                        '{} по ' \
                        'адресу' \
                        ' {}\n\n'.format(feature['properties']['name'],
                                        feature['properties']['description'])
                var_text += '\nВыберите один из них'
                counter = 1
                temp2 = [{'title': 'Далее', 'hide': True}]
                while counter <= 5 and counter <= len(features):
                    temp2.append({'title': str(counter),
                                 'hide': True})
                    counter += 1
                res['response']['buttons'] = temp2
                res['response']['text'] = var_text
                sessionStorage[user_id]['start'] = start
            else:
                res['response']['text'] = 'К сожалению, ничего не' \
                                          ' найти не удалось.' \
                                          ' Попробуйте найти что-то другое'
                sessionStorage[user_id]['status'] = None

        else:
            res['response']['text'] = 'Некорректный запрос'
        return
    elif sessionStorage[user_id]['status'] == 3:
        text = req['request']['original_utterance'].lower()
        if text == 'на личном авто' or text == 'на такси':
            res['response']['text'] = \
                'Удачной поездки!\nЕсли хотите обратиться снова,' \
                ' введите, из какого города вы отправляетесь?'
            end_session(res, user_id)
        elif text == 'на общественном транспорте':
            sessionStorage[user_id]['status'] = 4
            res['response']['text'] = 'Когда вы хотите поехать?'
        else:
            res['response']['text'] = 'Некорректный запрос'
        return
    elif sessionStorage[user_id]['status'] == 4:
        path_date = get_date(req['request']['original_utterance'])
        if path_date is not None:
            res['response']['text'] = 'Теперь вы можете посмотреть ' \
                                      'расписание по ссылке!'
            res['response']['buttons'] =\
                [
                    {
                        "title": "Расписание",
                        "url": f"https://rasp.yandex.ru/search/?"
                               f"fromId={sessionStorage[user_id]['c1'][1]}"
                               f"&toId={sessionStorage[user_id]['c2']}"
                               f"&when={path_date}",
                        "hide": True
                    }
                ]
            sessionStorage[user_id]['status'] = 5
        else:
            res['response']['text'] = 'Что-то не похоже на дату)'
        return
    elif sessionStorage[user_id]['status'] == 5:
        res['response']['text'] = 'Если хотите обратиться снова,' \
                ' введите, из какого города вы отправляетесь'
        end_session(res, user_id)
        return
    place = req['request']['original_utterance']
    features = search_place(place)
    if features is None or len(features) == 0:
        res['response']['text'] = 'Такого места не найдено. ' \
                                  'Попробуйте найти другое'
    if len(features) == 1:
        res['response']['text'] = \
            'Вы имели ввиду: ' \
            '{} по ' \
            'адресу {}?'.format(features[0]['properties']['name'],
                                features[0]['properties']['description'])
        res['response']['buttons'] = [
            {'title': 'Да', 'hide': True},
            {'title': 'Нет', 'hide': True},
        ]
        sessionStorage[user_id]['status'] = 1
        sessionStorage[user_id]['cities'] = features[0]
    elif len(features) > 0:
        temp2 = [{'title': 'Далее', 'hide': True}]
        counter = 1
        while counter <= 5 and counter <= len(features):
            temp2.append({'title': str(counter), 'hide': True})
            counter += 1
        var_text = 'Нашел следующие варианты:\n\n'
        for feature in features[:5]:
            var_text += '{} по ' \
                        'адресу' \
                        ' {}\n\n'.format(feature['properties']['name'],
                                         feature['properties']['description'])
        var_text += '\nВыберите один из них'
        res['response']['buttons'] = temp2
        res['response']['text'] = var_text
        sessionStorage[user_id]['status'] = 2
        sessionStorage[user_id]['cities'] = features
    elif len(features) < 0:
        res['response']['text'] = 'К сожалению, ничего не найти не удалось.' \
                                  ' Попробуйте найти что-то другое'
        sessionStorage[user_id]['status'] = None


def create_answer(user_id, res, lat, long):
    try:
        town, code = search_town(long, lat)
        if town:
            res['response']['text'] = 'Как предпочитаете ' \
                                      'добраться до этого места?'
            sessionStorage[user_id]['town2'] = town
            sessionStorage[user_id]['c2'] = code
            res['response']['buttons'] = \
                [{'title': 'На общественном транспорте', 'hide': True},
                 {'title': 'На личном авто', 'hide': True},
                 {'title': 'На такси', 'hide': True}]
        else:
            res['response']['text'] = 'Как предпочитаете' \
                                      ' добраться до этого места?'
            sessionStorage[user_id]['town2'] = None
            sessionStorage[user_id]['c2'] = None
            res['response']['button'] = \
                [{'title': 'На личном авто', 'hide': True},
                 {'title': 'На такси', 'hide': True}]
        sessionStorage[user_id]['status'] = 3
    except DoingResponseNotAble:
        res['response']['text'] = 'Извините, но на сервере ' \
                                  'Яндекса произошла ошибка.' \
                                  ' Не беспокойтесь, попробуйте' \
                                  ' позже еще раз'
        sessionStorage[user_id]['status'] = None
    except ErrorTillDoingRequest:
        res['response']['text'] = 'Как предпочитаете добраться' \
                                  ' до этого места?'
        sessionStorage[user_id]['town2'] = None
        sessionStorage[user_id]['c2'] = None
        sessionStorage[user_id]['status'] = 3
        res['response']['button'] = \
            [{'title': 'На личном авто', 'hide': True},
             {'title': 'На такси', 'hide': True}]


def get_city(req):
    for token in req['request']['nlu']['tokens']:
        temp, coord = check_exist(token.lower())
        if temp is not None:
            return temp, coord


def search_place(name):
    params = {'apikey': SEARCH_API_KEY,
              'text': name,
              'lang': 'ru_RU',
              'results': 50}
    try:
        resp = requests.get(SEARCH_SERVER, params=params)
    except Exception:
        raise DoingResponseNotAble()
    if resp:
        json_file = resp.json()
    else:
        raise ErrorTillDoingRequest()
    try:
        return json_file['features']
    except KeyError:
        return None


def check_exist(arg):
    name = arg.lower()
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
        lat, long = map(float, var['GeoObject']['Point']['pos'].split())
        obj = var['GeoObject']['metaDataProperty']['GeocoderMetaData']
        adr = obj['Address']['Components']
        for comp in adr:
            if (comp['kind'] == 'locality' or comp['kind'] == 'province')\
                    and (comp['name'].lower() == name or
                         comp['name'].lower() == 'село {}'.format(name) or
                         comp['name'].lower() == 'город {}'.format(name) or
                         comp['name'].lower() == 'сно {}'.format(name)):
                return obj['text'], (lat, long)
    return None


def get_date(arg):
    string = arg.lower()
    if string == 'сегодня' or string == 'завтра' or string == 'послезавтра':
        day = datetime.datetime.today().day
        day += {'сегодня': 0, 'завтра': 1, 'послезавтра': 2}[string]
        month = datetime.datetime.today().month
        return '{}+{}'.format(day, MONTHS[month])
    else:
        try:
            day, month = string.split()
            if day.isdigit() and month in DAYS.keys():
                if 1 <= int(day) <= DAYS[month]:
                    return '{}+{}'.format(day, month)
            else:
                return None
        except ValueError:
            try:
                day, month = string.split('.')
            except ValueError:
                return None
            if day.isdigit() and month.isdigit():
                if 1 <= int(month) <= 12 and \
                        1 <= int(day) <= DAYS[MONTHS[month]]:
                    return '{}+{}'.format(day, MONTHS[month])
            else:
                return None


def end_session(res, user_id):
    res['response']['end_session'] = True
    sessionStorage[user_id]['status'] = None
    sessionStorage[user_id]['town1'] = None
    sessionStorage[user_id]['town2'] = None
    sessionStorage[user_id]['c1'] = None
    sessionStorage[user_id]['c2'] = None
    sessionStorage[user_id]['status'] = None
    sessionStorage[user_id]['cities'] = None
    sessionStorage[user_id]['start'] = 5


if __name__ == '__main__':
    app.run()
