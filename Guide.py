import requests
from flask import Flask, request
import logging
import json
import datetime


# Функция определения кол-ва дней в феврале этого года
def get_days_in_feb():
    year = datetime.datetime.today().year
    if year % 4 == 0 and year % 100 != 0 or year % 400 == 0:
        return 29
    else:
        return 28


# Константы серверов
RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/search/'
MAP_SERVER = 'https://yandex.ru/maps/'
TOWN_RASP_SERVER = 'https://api.rasp.yandex.net/v3.0/nearest_settlement/'
GEOCODE_SERVER = 'https://geocode-maps.yandex.ru/1.x/'
SEARCH_SERVER = 'https://search-maps.yandex.ru/v1/'
# Константы API-ключей
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
TRANSP_BUTTONS = [{'title': 'На общественном транспорте', 'hide': True},
                  {'title': 'На личном авто', 'hide': True},
                  {'title': 'На такси', 'hide': True},
                  {'title': 'Пешком', 'hide': True}]


# Базовый класс ошибки запроса
class ResponseError(ConnectionError):
    pass


# Класс ошибки во время выполнения запроса
class ErrorTillDoingRequest(ResponseError):
    pass


# Класс ошибки некорректного ответа на запрос
class DoingResponseNotAble(ResponseError):
    pass


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


# Функция ведения диалога
def handle_dialog(req, res):
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет! Я Навык-Путеводитель!' \
                                  ' Для начала работы, назовите город, ' \
                                  'где Вы находитесь'
        sessionStorage[user_id] = {
            'town1': None,
            'town2': None,
            'c1': None,
            'c2': None,
            'status': None,
            'cities': [],
            'start': 5,
            'transp_able': True
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
        except DoingResponseNotAble:
            res['response']['text'] = 'Мне кажется, это не город'
            return
        except ErrorTillDoingRequest:
            res['response']['text'] = 'Мне кажется, это не город'
            return
        if not town or not pos:
            res['response']['text'] = 'Мне кажется, это не город'
        elif pos and town:
            try:
                check = search_town(pos[1], pos[0])
            except ErrorTillDoingRequest:
                res['response']['text'] = 'Мне кажется, это не город'
                return
            except DoingResponseNotAble:
                res['response']['text'] = 'Мне кажется, это не город'
                return
            if check:
                sessionStorage[user_id]['c1'] = check
            res['response']['text'] = \
                'Назовите какое-либо место, а я подскажу, ' \
                'как до него добраться!'
            sessionStorage[user_id]['town1'] = \
                req['request']['original_utterance']
        return
    if sessionStorage[user_id]['status'] == 1:
        ask_right(req, res, user_id)
    elif sessionStorage[user_id]['status'] == 2:
        ask_from_list(req, res, user_id)
    elif sessionStorage[user_id]['status'] == 3:
        check_transp(req, res, user_id)
    elif sessionStorage[user_id]['status'] == 4:
        show_rasp(req, res, user_id)
    elif sessionStorage[user_id]['status'] == 5:
        res['response']['text'] = 'Если хотите обратиться снова,' \
                ' введите, из какого города вы отправляетесь'
        end_session(res, user_id)
    else:
        show_vars(req, res, user_id)


# Функция поиска ближайшего города Яндекс.Расписаний
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


# Диалоговая функция; проверяет, являются ли слова "да" и "нет" ответами
def ask_right(req, res, user_id):
    if req['request']['original_utterance'].lower() == 'да':
        city = sessionStorage[user_id]['cities']
        lat, long = city['geometry']['coordinates']
        ask_transp(user_id, res, lat, long)
    elif req['request']['original_utterance'].lower() == 'нет':
        res['response']['text'] = 'К сожалению, больше' \
                                  ' ничего найти не удалось(\n' \
                                  'Попробуйте найти что-то другое'
        sessionStorage[user_id]['status'] = None
    else:
        res['response']['text'] = 'Некорректный запрос'


# Диалоговая функция; взимодействует со списком городов
def ask_from_list(req, res, user_id):
    temp = req['request']['original_utterance']
    if temp.isdigit():
        if 1 <= int(temp) <= 5:
            move = sessionStorage[user_id]['start']
            city = sessionStorage[user_id]['cities'][int(temp) + move - 6]
            if city:
                lat, long = city['geometry']['coordinates']
                sessionStorage[user_id]['place'] =\
                    city['properties']['description']
                ask_transp(user_id, res, lat, long)
            else:
                res['response']['text'] = 'К сожалению, больше' \
                                          ' ничего найти не удалось(\n' \
                                          'Попробуйте найти что-то другое'
                sessionStorage[user_id]['status'] = None
    elif temp.lower() == 'далее':
        mover(res, user_id)
    else:
        res['response']['text'] = 'Некорректный запрос'


# Диалоговая функция; реализует сдвиг вперед списка городов
def mover(res, user_id):
    start = sessionStorage[user_id]['start'] + 5
    features = sessionStorage[user_id]['cities'][start - 5: start]
    if len(features) > 0:
        var_text = 'Нашел следующие варианты:\n\n'
        for feature in features:
            var_text += '{} по адресу' \
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


# Диалоговая функция; проверяет, какой вид транспорта выбран
def check_transp(req, res, user_id):
    text = req['request']['original_utterance'].lower()
    if text == 'на личном авто':
        res['response']['text'] = \
            'Удачной поездки!\nПо ссылке внизу (кнопка)' \
            ' доступен маршрут на авто'
        res['response']['buttons'] = \
            [{'title': 'Маршрут',
              'url':
                  get_map_url(get_pos(sessionStorage[user_id]['town1']),
                              get_pos(sessionStorage[user_id]['place']),
                              'auto'),
              'hide': True}]
        sessionStorage[user_id]['status'] = 5
    elif text == 'на такси':
        res['response']['text'] = \
            'Удачной поездки! Яндекс.Такси домчит вас куда угодно)' \
            '\nЕсли хотите обратиться снова,' \
            ' введите, из какого города вы отправляетесь?'
        res['response']['buttons'] = [{'title': 'Сайт такси',
                                       'url': 'https://taxi.yandex.ru/#index',
                                       'hide': True}]
        sessionStorage[user_id]['status'] = 5
    elif text == 'пешком':
        res['response']['text'] = \
            'Удачной прогулки!\nПо ссылке внизу (кнопка)' \
            ' доступен маршрут на авто'
        res['response']['buttons'] = \
            [{'title': 'Маршрут',
              'url':
                  get_map_url(get_pos(sessionStorage[user_id]['town1']),
                              get_pos(sessionStorage[user_id]['place']),
                              'pd'),
              'hide': True}]
        sessionStorage[user_id]['status'] = 5
    elif text == 'на общественном транспорте' and \
            sessionStorage[user_id]['transp_able']:
        sessionStorage[user_id]['status'] = 4
        res['response']['text'] = 'Когда вы хотите поехать?'
    else:
        res['response']['text'] = 'Некорректный запрос'
        if sessionStorage[user_id]['transp_able']:
            res['response']['buttons'] = TRANSP_BUTTONS
        else:
            res['response']['buttons'] = TRANSP_BUTTONS[1:]


# Диалоговая функция; создает кнопку со ссылкой на расписание
def show_rasp(req, res, user_id):
    path_date = get_date(req['request']['original_utterance'])
    if path_date is not None:
        res['response']['text'] = 'Теперь вы можете посмотреть ' \
                                  'расписание по ссылке!'
        res['response']['buttons'] = \
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


# Диалоговая функция; спрашивает предпочтения в транспорте
def ask_transp(user_id, res, lat, long):
    try:
        town, code = search_town(long, lat)
        if town:
            res['response']['text'] = 'Как предпочитаете ' \
                                      'добраться до этого места?'
            sessionStorage[user_id]['town2'] = town
            sessionStorage[user_id]['c2'] = code
            sessionStorage[user_id]['transp_able'] = True
            res['response']['buttons'] = TRANSP_BUTTONS
        else:
            res['response']['text'] = 'Как предпочитаете' \
                                      ' добраться до этого места?'
            sessionStorage[user_id]['town2'] = None
            sessionStorage[user_id]['c2'] = None
            sessionStorage[user_id]['transp_able'] = False
            res['response']['buttons'] = TRANSP_BUTTONS[1:]
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
        sessionStorage[user_id]['transp_able'] = False
        res['response']['buttons'] = TRANSP_BUTTONS[1:]


# Диалоговая функция показа вариантов поиска
def show_vars(req, res, user_id):
    place = req['request']['original_utterance']
    sessionStorage[user_id]['place'] = place
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


# Поиск нпзвания города в строке
def get_city(req):
    for token in req['request']['nlu']['tokens']:
        if token != 'город' and token != 'село':
            temp, coord = check_exist(token.lower())
            if temp is not None:
                return temp, coord


# Поиск места
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


# Проверка существования города
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


# Поиск даты в строке
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


# Функция окончания сессии
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


# Функция; возвращает url маршрута
def get_map_url(pos1, pos2, mode):
    if pos1 is not None and pos2 is not None:
        return f'{MAP_SERVER}?mode=routes&rtt={mode}&' \
            f'rtext={pos1[1]},{pos1[0]}~{pos2[1]},{pos2[0]}'
    elif pos1 is not None:
        return f'{MAP_SERVER}?mode=routes&rtt={mode}&' \
            f'rtext={pos1[1]},{pos1[0]}'
    elif pos2 is not None:
        return f'{MAP_SERVER}?mode=routes&rtt={mode}&' \
            f'rtext={pos2[1]},{pos2[0]}'
    else:
        return MAP_SERVER


# Функция; возвращает координаты места
def get_pos(arg):
    name = arg.lower()
    try:
        features = search_place(name)
        return features[0]['geometry']['coordinates']
    except KeyError:
        return None
    except IndexError:
        return None
    except DoingResponseNotAble:
        return None
    except ErrorTillDoingRequest:
        return None


if __name__ == '__main__':
    app.run()
