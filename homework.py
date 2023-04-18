import logging

import os
import sys
import time

import requests
import telegram

from dotenv import load_dotenv

from exceptions import HTTPRequestError, ParseStatusError


load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s, %(levelname)s, %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])


PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения необходимых для работы"""
    list_env = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    return all(list_env)


def send_message(bot, message):
    """Отправляет сообщение в Telegram"""
    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        logging.error(e)


def get_api_answer(timestamp):
    """Создает и отправляет запрос к энпоинту"""
    try:
        payload = {'from_date': timestamp}
        logging.info(f'Отправлен запрос на {ENDPOINT} с параметрами {payload}')
        homework_statuses = requests.get(url=ENDPOINT, headers=HEADERS, params=payload)
        if homework_statuses.status_code != 200:
            raise HTTPRequestError(homework_statuses)

        return homework_statuses.json()

    except requests.RequestException as e:
        logging.exception(e)


def check_response(response):
    """Проверяет ответ от эндпоинта."""
    if not response:
        message = 'Пустой словарь'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response, dict):
        message = 'Некорректный тип данных'
        logging.error(message)
        raise TypeError(message)

    if not isinstance(response.get('homeworks'), list):
        message = 'Формат ответа не соответствует'
        logging.error(message)
        raise TypeError(message)

    if 'homeworks' not in response:
        message = 'Отсутствует ожидаемый ключ'
        logging.error(message)
        raise KeyError(message)

    return response['homeworks']


def parse_status(homework):
    """Получение статуса домашней работы"""
    if not homework.get('homework_name'):
        logging.warning('Отсутствует имя домашней работы')
        raise KeyError('Отсутствует имя домашней работы')

    homework_name = homework.get('homework_name')

    status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсуствует статуст домашней работы'
        logging.error(message)
        raise ParseStatusError(message)

    verdict = HOMEWORK_VERDICTS.get(status)
    if status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашщней работы'
        logging.error(message)
        raise KeyError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная перменная окружения. Программа остановлена')
        exit()

    last_send = {
        'error': None,
    }

    logging.debug('Бот запущен')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            all_homeworks = check_response(response)

            if len(all_homeworks) == 0:
                logging.debug('Ответ API пуст: нет домашних работ.')
                break

            for homework in all_homeworks:
                message = parse_status(homework)
                if last_send.get(homework['homework_name']) != message:
                    send_message(bot, message)
                    last_send[homework['homework_name']] = message
            timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_send['error'] != message:
                send_message(bot, message)
                last_send['error'] = message

        else:
            last_send['error'] = None

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
